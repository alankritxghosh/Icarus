import XCTest
@testable import IcarusKit

/// The guided tour's client-side contract, written before the views.
///
/// The tour is the first thing Icarus says about a repository, unprompted, so
/// these tests exist to keep the app a THIN renderer of what the brain decided:
/// it must not reorder, soften or re-judge a step, and an abstention has to
/// survive the trip intact.
@MainActor
final class OnboardingTests: XCTestCase {

    // MARK: decoding the brain's shapes

    func testPlanDecodesTheTour() throws {
        let json = """
        {"repo":"simonw/llm","commit":"94769b8","semantic_indexing_in_progress":false,
         "note":"",
         "steps":[{"id":"overview","kind":"map","title":"What Icarus has read","detail":"no writer"},
                  {"id":"purpose","kind":"question","title":"What is this project?",
                   "question":"What does this repository do?"}]}
        """.data(using: .utf8)!
        let plan = try JSONDecoder().decode(OnboardingPlan.self, from: json)
        XCTAssertEqual(plan.repo, "simonw/llm")
        XCTAssertEqual(plan.steps.map(\.id), ["overview", "purpose"])
        XCTAssertEqual(plan.steps[0].kind, .map)
        XCTAssertEqual(plan.steps[1].kind, .question)
        XCTAssertFalse(plan.semanticIndexingInProgress)
    }

    func testPlanCarriesTheIndexingNote() throws {
        let json = """
        {"repo":"a/b","commit":"c","semantic_indexing_in_progress":true,
         "note":"still building","steps":[]}
        """.data(using: .utf8)!
        let plan = try JSONDecoder().decode(OnboardingPlan.self, from: json)
        XCTAssertTrue(plan.semanticIndexingInProgress)
        XCTAssertEqual(plan.note, "still building")
    }

    func testAnUnknownStepKindDecodesRatherThanFailing() throws {
        // A newer brain may add a step kind this build has never heard of. It
        // must not take the whole tour down — the app degrades to skipping it.
        let json = """
        {"repo":"a/b","commit":"c","semantic_indexing_in_progress":false,"note":"",
         "steps":[{"id":"future","kind":"hologram","title":"Something new"}]}
        """.data(using: .utf8)!
        let plan = try JSONDecoder().decode(OnboardingPlan.self, from: json)
        XCTAssertEqual(plan.steps[0].kind, .unsupported)
    }

    func testStepAnswerDecodesTheAskShapePlusItsStep() throws {
        let json = """
        {"verdict":"answer","answer":"A CLI for LLMs.",
         "citations":[{"ref":"doc:README.md","url":"https://x","excerpt":"# llm"}],
         "searched":["doc:README.md"],"step":"purpose","title":"What is this project?"}
        """.data(using: .utf8)!
        let step = try JSONDecoder().decode(TourStepAnswer.self, from: json)
        XCTAssertEqual(step.step, "purpose")
        XCTAssertEqual(step.title, "What is this project?")
        XCTAssertEqual(step.response.verdict, .answer)
        XCTAssertEqual(step.response.citations.first?.ref, "doc:README.md")
    }

    func testAnAbstainingStepSurvivesDecodingIntact() throws {
        let json = """
        {"verdict":"unknown","answer":"","citations":[],"searched":["pr:1","pr:2"],
         "indexing":true,"step":"decisions","title":"Decisions that shaped it"}
        """.data(using: .utf8)!
        let step = try JSONDecoder().decode(TourStepAnswer.self, from: json)
        XCTAssertEqual(step.response.verdict, .unknown)
        XCTAssertTrue(step.response.answer.isEmpty)
        XCTAssertTrue(step.response.citations.isEmpty)
        // The SAME caveat the overlay and proof drawer use — one wording for
        // "I haven't finished reading", never a second one that drifts.
        XCTAssertNotNil(step.response.incompleteIndexNote)
    }

    // MARK: the tour model

    private func model(plan: OnboardingPlan? = nil,
                       answer: @escaping @Sendable (String) async throws -> TourStepAnswer
                        = { _ in .stub() }) -> TourModel {
        TourModel(loadPlan: { plan ?? .stub() }, loadStep: answer)
    }

    func testTheTourStartsEmptyAndLoadsItsPlan() async {
        let m = model()
        XCTAssertNil(m.plan)
        await m.start()
        XCTAssertEqual(m.plan?.steps.map(\.id), ["overview", "purpose", "stack"])
        XCTAssertEqual(m.currentIndex, 0)
    }

    func testAdvancingFetchesOnlyQuestionSteps() async {
        let asked = Locked<[String]>([])
        let m = model(answer: { id in asked.append(id); return .stub(step: id) })
        await m.start()                       // lands on `overview`, a map step
        XCTAssertEqual(asked.value, [], "a map step must not reach the writer")
        await m.next()                        // -> purpose
        XCTAssertEqual(asked.value, ["purpose"])
        XCTAssertEqual(m.currentStep?.id, "purpose")
    }

    func testAStepIsFetchedOnceAndThenRemembered() async {
        let asked = Locked<[String]>([])
        let m = model(answer: { id in asked.append(id); return .stub(step: id) })
        await m.start()
        await m.next(); await m.back(); await m.next()
        XCTAssertEqual(asked.value, ["purpose"], "revisiting must not re-bill the writer")
    }

    func testTheTourCannotRunOffEitherEnd() async {
        let m = model()
        await m.start()
        await m.back()
        XCTAssertEqual(m.currentIndex, 0)
        await m.next(); await m.next(); await m.next(); await m.next()
        XCTAssertEqual(m.currentIndex, 2)
        XCTAssertTrue(m.isOnLastStep)
    }

    func testAnAbstainingStepIsShownAsIsNeverSkipped() async {
        // The honest "no one wrote this down" is the product. A tour that
        // quietly hid a refusal would be the one thing Icarus must never do.
        let m = model(answer: { _ in .stub(verdict: .unknown, answer: "") })
        await m.start()
        await m.next()
        XCTAssertEqual(m.answer(for: "purpose")?.response.verdict, .unknown)
        XCTAssertNil(m.error)
    }

    func testAFailedStepSurfacesAsAnErrorNotAsAnAbstention() async {
        // "The brain is unreachable" and "nobody wrote this down" are opposite
        // claims; rendering a transport failure as an abstention would put a
        // false statement about the user's repo on screen.
        let m = model(answer: { _ in throw BrainError.rateLimited })
        await m.start()
        await m.next()
        XCTAssertNil(m.answer(for: "purpose"))
        XCTAssertEqual(m.error, BrainError.rateLimited.userMessage)
    }

    func testAFailedPlanSurfacesAnError() async {
        let m = TourModel(loadPlan: { throw BrainError.forbidden }, loadStep: { _ in .stub() })
        await m.start()
        XCTAssertNil(m.plan)
        XCTAssertEqual(m.error, BrainError.forbidden.userMessage)
    }

    func testRetryingAFailedStepClearsTheError() async {
        let fail = Locked<Bool>(true)
        let m = model(answer: { id in
            if fail.value { fail.set(false); throw BrainError.server(500) }
            return .stub(step: id)
        })
        await m.start()
        await m.next()
        XCTAssertNotNil(m.error)
        await m.retry()
        XCTAssertNil(m.error)
        XCTAssertNotNil(m.answer(for: "purpose"))
    }
}

// MARK: - helpers

/// Minimal thread-safe box so the async tests can record calls without
/// tripping Swift 6 concurrency checking.
final class Locked<T>: @unchecked Sendable {
    private var storage: T
    private let lock = NSLock()
    init(_ value: T) { storage = value }
    var value: T { lock.lock(); defer { lock.unlock() }; return storage }
    func set(_ value: T) { lock.lock(); storage = value; lock.unlock() }
}

extension Locked where T == [String] {
    func append(_ s: String) { lock_append(s) }
    private func lock_append(_ s: String) { set(value + [s]) }
}

extension OnboardingPlan {
    static func stub() -> OnboardingPlan {
        OnboardingPlan(repo: "simonw/llm", commit: "94769b8",
                       semanticIndexingInProgress: false, note: "",
                       steps: [
                        OnboardingStep(id: "overview", kind: .map, title: "What Icarus has read",
                                       question: nil, detail: "no writer"),
                        OnboardingStep(id: "purpose", kind: .question, title: "What is this project?",
                                       question: "What does this repository do?", detail: nil),
                        OnboardingStep(id: "stack", kind: .question, title: "What it is built with",
                                       question: "What is it built with?", detail: nil),
                       ])
    }
}

extension TourStepAnswer {
    static func stub(step: String = "purpose", verdict: Verdict = .answer,
                     answer: String = "Because of X.") -> TourStepAnswer {
        TourStepAnswer(step: step, title: "T",
                       response: AskResponse(verdict: verdict, answer: answer,
                                             citations: verdict == .answer
                                                ? [Citation(ref: "doc:README.md", url: nil)] : [],
                                             searched: ["doc:README.md"]))
    }
}
