import Foundation
import Observation

/// The guided onboarding tour, client side.
///
/// The brain decides what the tour IS (`demo/onboarding.py`: which steps ship,
/// their wording, their order) and what each step ANSWERS. This file renders
/// that and nothing more — it never reorders, re-judges, softens or hides a
/// step. In particular an abstention is displayed exactly as the brain sent it,
/// because "no one wrote this down" is the product, not a failure to be tidied
/// away.

/// What a step needs in order to be shown.
public enum OnboardingStepKind: String, Decodable, Sendable {
    /// Answered deterministically from `GET /map` — no writer, no retrieval, so
    /// it is solid even while the semantic index is still building.
    case map
    /// How the code is ARRANGED, served deterministically from `GET /map`'s
    /// `indexed_structure` (`demo/structure.py`). Like `.map` it asks no
    /// writer, so it cannot abstain and cannot bluff -- which is the whole
    /// reason the arrangement is derived from imports rather than asked of a
    /// model. Older builds decode this to `.unsupported` and skip it, which is
    /// exactly why the brain could ship it without a DMG.
    case structure
    /// Answered by the brain's ordinary gated pipeline via `POST /onboarding`.
    case question
    /// A kind this build has never heard of. A newer brain must be able to add
    /// steps without breaking an older app, so an unknown kind decodes to this
    /// and is skipped rather than taking the whole tour down.
    case unsupported

    public init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = OnboardingStepKind(rawValue: raw) ?? .unsupported
    }
}

public struct OnboardingStep: Decodable, Identifiable, Sendable {
    public let id: String
    public let kind: OnboardingStepKind
    public let title: String
    /// The question the brain will ask on the user's behalf (question steps).
    /// Shown so the tour is never a black box: you can see what was asked.
    public let question: String?
    /// A plain-language note about a non-question step (map steps).
    public let detail: String?

    public init(id: String, kind: OnboardingStepKind, title: String,
                question: String?, detail: String?) {
        self.id = id
        self.kind = kind
        self.title = title
        self.question = question
        self.detail = detail
    }
}

/// `GET /onboarding` — the ordered tour for the connected repo.
public struct OnboardingPlan: Decodable, Sendable {
    public let repo: String?
    public let commit: String?
    public let semanticIndexingInProgress: Bool
    /// The brain's own words about the still-building index. Rendered verbatim
    /// rather than restated here, so there is one wording, not two that drift.
    public let note: String
    public let steps: [OnboardingStep]

    enum CodingKeys: String, CodingKey {
        case repo, commit, note, steps
        case semanticIndexingInProgress = "semantic_indexing_in_progress"
    }

    public init(repo: String?, commit: String?, semanticIndexingInProgress: Bool,
                note: String, steps: [OnboardingStep]) {
        self.repo = repo
        self.commit = commit
        self.semanticIndexingInProgress = semanticIndexingInProgress
        self.note = note
        self.steps = steps
    }
}

/// `POST /onboarding {step}` — the identical `/ask` payload plus which step it
/// answered, so the app renders a tour step with the renderer it already has.
public struct TourStepAnswer: Decodable, Sendable {
    public let step: String
    public let title: String?
    public let response: AskResponse

    enum CodingKeys: String, CodingKey { case step, title }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        step = try c.decode(String.self, forKey: .step)
        title = try c.decodeIfPresent(String.self, forKey: .title)
        // The answer fields are FLAT alongside `step`/`title`, so the same
        // decoder reads them — one shape, decoded one way, everywhere.
        response = try AskResponse(from: decoder)
    }

    public init(step: String, title: String?, response: AskResponse) {
        self.step = step
        self.title = title
        self.response = response
    }
}

/// Drives the tour: load the plan, walk it a step at a time, remember what each
/// step said.
///
/// Holds no persistent state and no session. The brain's tour is stateless by
/// design, so "interrupt with your own question and come back" costs nothing —
/// this object just keeps the answers already fetched so revisiting a step
/// never bills the writer twice.
@MainActor
@Observable
public final class TourModel {
    public private(set) var plan: OnboardingPlan?
    public private(set) var currentIndex: Int = 0
    public private(set) var isLoading: Bool = false
    /// A transport/HTTP failure, in the user's words. Deliberately SEPARATE
    /// from an abstention: "we couldn't reach the brain" and "nobody wrote this
    /// down" are opposite claims, and only one of them is about their code.
    public private(set) var error: String?
    /// Whether the writer-backed steps can be asked yet.
    ///
    /// False while the semantic index is still building. Measured: `stack`
    /// answers 10/10 across ten repos once the index is built, and abstained
    /// live purely because the embed was still running -- and a first-time
    /// user takes the tour in exactly that window. Holding those steps costs
    /// a short wait; not holding them costs the first impression.
    ///
    /// Driven by the app's `/status` poll rather than by a field in the plan:
    /// the plan is fetched ONCE and indexing finishes later, so a readiness
    /// flag baked into it would be a stale snapshot of a live condition.
    ///
    /// Defaults to true, so a repo that is already indexed -- and any caller
    /// that never sets it -- behaves exactly as before.
    public private(set) var questionsReady: Bool = true

    private var answers: [String: TourStepAnswer] = [:]
    private let loadPlan: @Sendable () async throws -> OnboardingPlan
    private let loadStep: @Sendable (String) async throws -> TourStepAnswer

    public init(loadPlan: @Sendable @escaping () async throws -> OnboardingPlan,
                loadStep: @Sendable @escaping (String) async throws -> TourStepAnswer) {
        self.loadPlan = loadPlan
        self.loadStep = loadStep
    }

    public convenience init(client: BrainClient) {
        self.init(loadPlan: { try await client.onboardingPlan() },
                  loadStep: { try await client.onboardingStep($0) })
    }

    public var steps: [OnboardingStep] { plan?.steps ?? [] }
    public var currentStep: OnboardingStep? {
        steps.indices.contains(currentIndex) ? steps[currentIndex] : nil
    }
    public var isOnLastStep: Bool { currentIndex >= steps.count - 1 }
    public func answer(for stepID: String) -> TourStepAnswer? { answers[stepID] }

    public func start() async {
        guard plan == nil else { return }
        error = nil
        do {
            plan = try await loadPlan()
            currentIndex = 0
            await loadCurrentIfNeeded()
        } catch {
            self.error = Self.message(for: error)
        }
    }

    public func next() async {
        guard currentIndex < steps.count - 1 else { return }
        currentIndex += 1
        await loadCurrentIfNeeded()
    }

    public func back() async {
        guard currentIndex > 0 else { return }
        currentIndex -= 1
        await loadCurrentIfNeeded()
    }

    /// Tell the tour whether the index is ready. Becoming ready fetches the
    /// step the user is already sitting on, so the wait ends by itself rather
    /// than needing them to click something.
    public func setQuestionsReady(_ ready: Bool) async {
        let wasReady = questionsReady
        questionsReady = ready
        if ready && !wasReady { await loadCurrentIfNeeded() }
    }

    public func retry() async {
        error = nil
        await loadCurrentIfNeeded()
    }

    /// Fetch the current step's answer unless it is already known or needs no
    /// writer at all. A map step never reaches the brain's writer.
    private func loadCurrentIfNeeded() async {
        // A not-ready question step is not fetched at all: it must never
        // reach the billed writer only to come back visibly worse.
        guard let step = currentStep, step.kind == .question,
              questionsReady, answers[step.id] == nil else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            answers[step.id] = try await loadStep(step.id)
            error = nil
        } catch {
            self.error = Self.message(for: error)
        }
    }

    private static func message(for error: Error) -> String {
        if let brain = error as? BrainError { return brain.userMessage }
        return "Couldn't reach Icarus's brain. Check it's running, then try again."
    }
}
