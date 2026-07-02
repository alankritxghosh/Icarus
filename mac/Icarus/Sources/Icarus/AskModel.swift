import Foundation
import Observation
import IcarusKit

/// Holds the question text and the current ask state. Owned by `OverlayController`
/// (not the SwiftUI view) so state survives the overlay being hidden/re-shown.
/// Main-actor isolated: it drives UI and is mutated from async UI actions.
@MainActor
@Observable
final class AskModel {
    enum State {
        case idle
        case loading
        case response(AskResponse)   // may be .answer OR honest .unknown — the view branches on verdict
        case unreachable             // brain not running / unexpected response
    }

    var question: String = ""
    private(set) var state: State = .idle

    /// Called with the final state after each submit (`.response` or `.unreachable`),
    /// so the app can react — e.g. speak the answer aloud. Never mutates the verdict.
    var onResult: ((State) -> Void)?

    /// The real in-session record. Each successful ask is appended here so the shell's
    /// recent/history/unknowns/proof surfaces show truth, never seeded data.
    var history: AskHistory?

    private let client: BrainClient

    init(client: BrainClient = BrainClient()) {
        self.client = client
    }

    /// Send the current question to the brain and store the result. Empty/blank
    /// questions are ignored.
    func submit() async {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        state = .loading
        do {
            let response = try await client.ask(trimmed)
            state = .response(response)
            history?.record(question: trimmed, response: response)
        } catch {
            state = .unreachable
        }
        onResult?(state)
    }
}
