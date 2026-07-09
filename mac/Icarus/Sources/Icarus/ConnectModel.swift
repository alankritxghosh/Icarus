import Foundation
import Observation
import IcarusKit

/// Drives connecting the brain to a repo (public or private): POST /connect,
/// then poll /status until the repo is ready. Owned by the app delegate and
/// shared with the overlay so asking is gated on a connected repo.
///
/// The brain does all the routing — a private repo is verified with the
/// caller's own token and answered only by the paid private-safe writer; this
/// model just renders the truth `/status` reports (`private: true/false`).
/// It also remembers the last successful connection (`SavedConnection`) so the
/// repo persists across launches, and flips to `.lost` when the server drops
/// the session (restart / LRU eviction) — never silently showing the public
/// default as if it were still the user's repo.
@MainActor
@Observable
final class ConnectModel {
    enum State: Equatable {
        case idle
        case connecting(String)
        case ready(repo: String, isPrivate: Bool)
        case failed(String)
        /// The server no longer holds this connection (restart or eviction);
        /// /status reports "ready" on a different repo. Reconnect to continue.
        case lost(repo: String, isPrivate: Bool)
    }

    var repoInput: String = ""
    private(set) var state: State = .idle

    private let client: BrainClient
    private let saved: SavedConnection
    private var task: Task<Void, Never>?

    /// owner/name — same shape the brain's /connect accepts.
    private static let repoPattern = #"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"#

    init(client: BrainClient = BrainClient(), saved: SavedConnection = SavedConnection()) {
        self.client = client
        self.saved = saved
    }

    var isReady: Bool {
        if case .ready = state { return true }
        return false
    }

    /// Whether the CURRENTLY connected repo is private (paid writer). False
    /// until connected.
    var isPrivate: Bool {
        if case .ready(_, let isPrivate) = state { return isPrivate }
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

    /// Reconnect the repo remembered from a previous launch (or a lost session).
    /// The server reuses its on-disk cache when it still has one, so this is
    /// cheap; a private repo is re-verified and re-ingested with the caller's
    /// token. No-op when nothing was saved.
    func resumeSaved() {
        guard let connection = saved.load() else { return }
        repoInput = connection.repo
        connect()
    }

    /// POST /disconnect — the brain deletes the caller's own indexed data and
    /// resets them to the public default. Only forgets the saved connection
    /// once the server confirms — a failed delete must not look like a delete.
    func disconnect() {
        task?.cancel()
        task = Task {
            do {
                try await client.disconnect()
                saved.clear()
                state = .idle
                repoInput = ""
            } catch {
                state = .failed("Couldn't disconnect — the server didn't confirm deleting your data. Check your connection and try again.")
            }
        }
    }

    /// Fed the shell's /status poll. If the server reports "ready" on a repo
    /// other than the one we connected, the session was dropped server-side —
    /// surface it explicitly instead of pretending nothing happened.
    func noteStatus(_ status: RepoStatus) {
        guard case .ready = state, saved.isLost(given: status),
              let connection = saved.load() else { return }
        state = .lost(repo: connection.repo, isPrivate: connection.isPrivate)
    }

    private func run(repo: String) async {
        do {
            try await client.connect(repo: repo)
            // The brain ingests in the background and keeps the previous repo active
            // until the new one is ready, so wait for state==ready AND repo match.
            // Matches the server's own embed timeout (evals/retriever.py's
            // SemanticRetriever, demo/library.py's _EMBED_TIMEOUT_SECONDS = 900)
            // -- a CPU-throttled host can take much longer than a small demo repo
            // implies, and giving up client-side before the server does just
            // shows "Timed out" on a connect that's still genuinely working.
            let deadline = Date().addingTimeInterval(900)
            while Date() < deadline {
                try await Task.sleep(for: .seconds(2))
                if Task.isCancelled { return }
                let status = try await client.status()
                if status.isError {
                    state = .failed(status.error ?? "Indexing failed.")
                    return
                }
                if status.isReady, status.repo.lowercased() == repo.lowercased() {
                    saved.save(repo: status.repo, isPrivate: status.isPrivate)
                    state = .ready(repo: status.repo, isPrivate: status.isPrivate)
                    return
                }
                // otherwise still indexing — keep polling
            }
            state = .failed("Timed out indexing \(repo).")
        } catch is CancellationError {
            // superseded by a newer connect; leave state as set by the canceller
        } catch {
            state = .failed("Can't reach Icarus's brain — check your internet connection.")
        }
    }
}
