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
            state = .response(try await client.ask(trimmed))
        } catch {
            state = .unreachable
        }
    }
}
