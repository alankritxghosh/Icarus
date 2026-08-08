import Foundation
import Observation
import IcarusKit

/// Runs an investigation and holds its result for the Investigate surface.
///
/// Deliberately holds NO conversational state. The server owns what "it" refers
/// to (demo/investigations.py), keyed on the caller's identity and connected
/// repo, so a follow-up cannot be aimed at a subject the server never agreed to
/// — and every client resolves references the same way instead of each one
/// inventing its own rule. What is kept here is only the transcript this window
/// is currently showing.
///
/// A failed request is never rendered as an abstention. "I could not reach the
/// brain" and "no one wrote this down" look identical on screen if a transport
/// error is folded into an unknown, and they mean opposite things — the same
/// distinction `TourModel` and `LedgerModel` already keep.
///
/// The same rule applies one level down: a server REFUSAL (401/403/429/5xx) is
/// not a transport failure. The server answered, and what it said is
/// actionable, so it is reported as itself rather than as a connection problem.
@MainActor
@Observable
final class InvestigationModel {
    struct Turn: Identifiable {
        let id = UUID()
        let question: String
        let response: InvestigationResponse
    }

    enum State: Equatable {
        case idle
        case investigating
        case failed(String)

        static func == (a: State, b: State) -> Bool {
            switch (a, b) {
            case (.idle, .idle), (.investigating, .investigating): return true
            case let (.failed(x), .failed(y)): return x == y
            default: return false
            }
        }
    }

    private(set) var state: State = .idle
    private(set) var turns: [Turn] = []

    private let client: BrainClient
    private var task: Task<Void, Never>?

    init(client: BrainClient) {
        self.client = client
    }

    var isBusy: Bool { state == .investigating }

    /// The most recent turn — what the surface shows in full.
    var latest: Turn? { turns.last }

    func investigate(_ question: String) {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isBusy else { return }
        // `fresh` on the FIRST question of a transcript only. A follow-up must
        // reach the server as a follow-up, or the subject it depends on is
        // discarded by the very request that needs it.
        let fresh = turns.isEmpty
        state = .investigating
        task?.cancel()
        task = Task { [client] in
            do {
                let response = try await client.investigate(trimmed, fresh: fresh)
                guard !Task.isCancelled else { return }
                turns.append(Turn(question: trimmed, response: response))
                state = .idle
            } catch let error as BrainError {
                // The server ANSWERED and refused. Reporting that as a
                // connection problem tells the user to check their network when
                // the real fix is to sign in, wait, or pick a repo they can
                // read -- a confident claim about a state the client does not
                // know to hold. BrainError.userMessage already carries the
                // accurate recovery text for each case.
                guard !Task.isCancelled else { return }
                state = .failed(error.userMessage)
            } catch {
                guard !Task.isCancelled else { return }
                state = .failed("Couldn't reach the brain. This is a connection "
                                + "problem, not an answer about the repository.")
            }
        }
    }

    /// Abandon the conversation and start a new enquiry. The next question is
    /// sent with `fresh: true`, so the server drops the subject rather than the
    /// app quietly keeping one it no longer shows.
    func startOver() {
        task?.cancel()
        turns.removeAll()
        state = .idle
    }
}
