import Foundation
import Observation
import IcarusKit

/// Pending Agent Mode recommendations for the connected repository. Human
/// confirmation is the only transition out of pending; a successful accepted
/// choice must carry the GitHub pull request that makes it reviewable.
@MainActor
@Observable
final class DecisionInboxModel {
    struct Outcome: Equatable {
        let message: String
        let pullRequestURL: URL?
    }
    enum State: Equatable {
        case idle
        case loading
        case loaded(repo: String, candidates: [DecisionCandidate])
        case failed(String)
    }

    enum ConfirmationState: Equatable {
        case submitting
        case succeeded(URL?)
        case failed(String, URL?)
    }

    /// The confirmed-decision history (proposals + merged), distinct from the
    /// pending inbox above. A transport failure is kept separate from "none",
    /// same as everywhere else in the app — an empty log is not proof there
    /// are no decisions, only that none have been confirmed yet.
    enum LogState: Equatable {
        case idle
        case loading
        case loaded([AgentDecision])
        case failed(String)
    }

    private(set) var state: State = .idle
    private(set) var confirmation: [String: ConfirmationState] = [:]
    private(set) var latestOutcome: Outcome?
    private(set) var logState: LogState = .idle

    private let client: BrainClient
    private var loadTask: Task<Void, Never>?
    private var logTask: Task<Void, Never>?
    private var confirmationTasks: [String: Task<Void, Never>] = [:]

    init(client: BrainClient = BrainClient()) {
        self.client = client
    }

    func load() {
        loadTask?.cancel()
        state = .loading
        loadTask = Task {
            do {
                let response = try await client.decisionCandidates()
                state = .loaded(repo: response.repo, candidates: response.candidates)
            } catch is CancellationError {
                return
            } catch let error as BrainError {
                state = .failed(error.userMessage)
            } catch {
                state = .failed(
                    "Icarus couldn't load decision confirmations. This is not the same as having none."
                )
            }
        }
    }

    func loadLog() {
        logTask?.cancel()
        logState = .loading
        logTask = Task {
            do {
                let response = try await client.agentDecisions()
                logState = .loaded(response.decisions)
            } catch is CancellationError {
                return
            } catch let error as BrainError {
                logState = .failed(error.userMessage)
            } catch {
                logState = .failed(
                    "Icarus couldn't load the decision history. This is not the same as having none."
                )
            }
        }
    }

    func confirm(_ candidate: DecisionCandidate, selection: DecisionSelection) {
        guard confirmationTasks[candidate.id] == nil else { return }
        guard case .loaded(_, let candidates) = state,
              candidates.contains(where: { $0.id == candidate.id && $0.status == .pending })
        else {
            confirmation[candidate.id] = .failed(
                "Only a currently pending decision can be confirmed.", nil)
            return
        }
        let cleanedSelection: DecisionSelection
        if case .other(let text) = selection {
            let cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !cleaned.isEmpty else {
                confirmation[candidate.id] = .failed(
                    "Write the intent you want Icarus to preserve.", nil)
                return
            }
            cleanedSelection = .other(cleaned)
        } else {
            cleanedSelection = selection
        }

        confirmation[candidate.id] = .submitting
        confirmationTasks[candidate.id] = Task {
            defer { confirmationTasks[candidate.id] = nil }
            do {
                let result = try await client.confirmDecision(
                    candidateID: candidate.id,
                    selection: cleanedSelection
                )
                let accepted: Bool
                switch cleanedSelection {
                case .recommended, .alternative, .other: accepted = true
                case .notSure, .reject: accepted = false
                }
                if accepted, result.proposal == nil {
                    confirmation[candidate.id] = .failed(
                        "Icarus did not return a reviewed GitHub proposal, so the decision was not claimed as recorded.",
                        nil
                    )
                    return
                }
                if case .loaded(let repo, let current) = state {
                    state = .loaded(
                        repo: repo,
                        candidates: current.filter { $0.id != candidate.id }
                    )
                }
                confirmation[candidate.id] = .succeeded(
                    result.proposal?.pullRequestURL)
                let message: String
                switch cleanedSelection {
                case .notSure:
                    message = "Kept as Not sure. It will not be sent to future agents as project intent."
                case .reject:
                    message = "Dismissed. It will not become project intent."
                case .recommended, .alternative, .other:
                    message = "Human-confirmed proposal created. It is not indexed project truth until review, merge, and re-index."
                }
                latestOutcome = Outcome(
                    message: message,
                    pullRequestURL: result.proposal?.pullRequestURL
                )
            } catch is CancellationError {
                return
            } catch let error as MemoryRecordFailure {
                confirmation[candidate.id] = .failed(
                    error.message, error.recoveryURL)
            } catch let error as BrainError {
                confirmation[candidate.id] = .failed(error.userMessage, nil)
            } catch {
                confirmation[candidate.id] = .failed(
                    "Icarus couldn't confirm this decision. It remains pending.", nil)
            }
        }
    }

    func isSubmitting(_ id: String) -> Bool {
        if case .submitting = confirmation[id] { return true }
        return false
    }

    func dismissOutcome() { latestOutcome = nil }
}
