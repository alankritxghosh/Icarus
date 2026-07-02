import Foundation
import Observation
import IcarusKit

/// Drives connecting the brain to a public repo: POST /connect, then poll /status
/// until the repo is ready. Owned by the app delegate and shared with the overlay
/// so asking is gated on a connected repo. Public repos only.
@MainActor
@Observable
final class ConnectModel {
    enum State: Equatable {
        case idle
        case connecting(String)
        case ready(repo: String)
        case failed(String)
    }

    var repoInput: String = ""
    private(set) var state: State = .idle

    private let client: BrainClient
    private var task: Task<Void, Never>?

    /// owner/name — same shape the brain's /connect accepts.
    private static let repoPattern = #"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"#

    init(client: BrainClient = BrainClient()) {
        self.client = client
    }

    var isReady: Bool {
        if case .ready = state { return true }
        return false
    }

    func connect() {
        let repo = repoInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard repo.range(of: Self.repoPattern, options: .regularExpression) != nil else {
            state = .failed("Enter a repository as owner/name, e.g. simonw/llm.")
            return
        }
        task?.cancel()
        state = .connecting(repo)
        task = Task { await run(repo: repo) }
    }

    private func run(repo: String) async {
        do {
            try await client.connect(repo: repo)
            // The brain ingests in the background and keeps the previous repo active
            // until the new one is ready, so wait for state==ready AND repo match.
            let deadline = Date().addingTimeInterval(180)  // past the web UI's 150s poll
            while Date() < deadline {
                try await Task.sleep(for: .seconds(2))
                if Task.isCancelled { return }
                let status = try await client.status()
                if status.isError {
                    state = .failed(status.error ?? "Indexing failed.")
                    return
                }
                if status.isReady, status.repo.lowercased() == repo.lowercased() {
                    state = .ready(repo: status.repo)
                    return
                }
                // otherwise still indexing — keep polling
            }
            state = .failed("Timed out indexing \(repo).")
        } catch is CancellationError {
            // superseded by a newer connect; leave state as set by the canceller
        } catch {
            state = .failed("Can't reach the brain. Is it running on 127.0.0.1:8000?")
        }
    }
}
