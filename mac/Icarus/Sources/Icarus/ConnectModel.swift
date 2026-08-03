import Foundation
import Observation
import IcarusKit

/// Drives connecting the brain to a public repo: POST /connect, then poll
/// /status until the repo is ready. Owned by the app delegate and shared with
/// the overlay so asking is gated on a connected repo.
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
        case ready(repo: String)
        case failed(String)
        /// The server no longer holds this connection (restart or eviction);
        /// /status reports "ready" on a different repo. Reconnect to continue.
        case lost(repo: String)
    }

    var repoInput: String = ""
    private(set) var state: State = .idle
    /// The brain's current progress line while indexing (e.g. "Reading the
    /// repository…"), shown under the spinner so the wait isn't a silent
    /// spinner. Only meaningful during `.connecting`; nil otherwise.
    private(set) var indexingPhase: String?
    /// How far the embed has got and roughly how long is left, when the brain
    /// knows. Separate from `indexingPhase` because one says WHAT is happening
    /// and the other says HOW FAR -- a user waiting minutes needs both.
    private(set) var indexingProgressLine: String?
    /// Is the connected repo private? Read from the brain's own /status, never
    /// guessed from the repo name — it decides whether this is a Company Brain
    /// (a private index a team shares) or a Repo Brain (a public one). False
    /// until a connect confirms otherwise, so it can never over-claim privacy.
    private(set) var isPrivate = false

    /// A re-read of the connected repo is in flight. Separate from `state`
    /// because the repo stays connected and answerable while it runs.
    private(set) var isRefreshing = false
    /// Why the last refresh was refused, when the brain actually refused it.
    /// nil for a refresh that was accepted — or one whose request timed out,
    /// which is not evidence of failure (see `refreshConnected`).
    private(set) var refreshError: String?

    private let client: BrainClient
    private let saved: SavedConnection
    private var task: Task<Void, Never>?
    private var refreshTask: Task<Void, Never>?

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

    /// True while a connect is in flight. The UI disables the Connect button on this:
    /// a repeat click spawns a duplicate server-side index of the same repo, which
    /// competes for the same CPU and makes the connect slower, not faster.
    var isConnecting: Bool {
        if case .connecting = state { return true }
        return false
    }

    func connect() {
        let repo = repoInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard repo.range(of: Self.repoPattern, options: .regularExpression) != nil else {
            state = .failed("Enter a repository as owner/name, e.g. simonw/llm.")
            return
        }
        task?.cancel()
        indexingPhase = nil
        indexingProgressLine = nil
        state = .connecting(repo)
        task = Task { await run(repo: repo) }
    }

    /// Re-read the CONNECTED repo, for an index the brain reported stale.
    ///
    /// Deliberately does NOT go through `connect()`'s state machine. A refresh
    /// leaves the repo connected and answerable throughout — the brain keeps
    /// serving the existing corpus until the new one is ready — so flipping
    /// `state` to `.connecting` would drop the user out of the dashboard and
    /// back to the setup gate for the several minutes a re-ingest takes, while
    /// claiming they were disconnected from a repo they can still ask about.
    ///
    /// The repo comes from `state`, never `repoInput`: the user may have typed
    /// another name into the box without connecting it, and re-reading
    /// something other than what the banner described would be a silent switch.
    func refreshConnected() {
        guard case .ready(let repo) = state, !isRefreshing else { return }
        isRefreshing = true
        refreshError = nil
        refreshTask = Task {
            defer { isRefreshing = false }
            do {
                try await client.connect(repo: repo, refresh: true)
            } catch let error as BrainError {
                // The brain answered and refused — a rate limit, a sign-out.
                refreshError = error.userMessage
            } catch {
                // TRANSPORT failure, and here it is EXPECTED rather than
                // exceptional: a refresh re-reads the whole repository (283s
                // measured) while Azure cuts an inbound request at 240s, so a
                // successful refresh routinely never gets to answer. Reporting
                // that as a failure would be the same misdiagnosis `run()`
                // documents. The freshness banner is the real signal — it
                // re-checks against the indexed commit and clears itself.
            }
        }
    }

    /// Reconnect the repo remembered from a previous launch (or a lost session).
    /// The server reuses its on-disk cache when it still has one, so this is
    /// cheap. No-op when nothing was saved.
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
                isPrivate = false
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
        state = .lost(repo: connection.repo)
    }

    private func run(repo: String) async {
        do {
            do {
                try await client.connect(repo: repo)
            } catch let error as BrainError {
                // The brain ANSWERED and refused. That's definitive — say what it
                // actually was, and stop. Never dress a refusal up as a network fault.
                state = .failed(error.userMessage)
                return
            } catch is CancellationError {
                return
            } catch {
                // TRANSPORT failure: we never got an answer. This is NOT proof the
                // connect failed. A first-time index can outlive the host's ingress
                // ceiling (Azure cuts a request at 240s) while the server keeps
                // working and finishes — live-confirmed 2026-07-14, when a connect
                // that had genuinely SUCCEEDED server-side (wolf3d, 185 chunks,
                // state "ready") was reported to the user as "can't reach the brain".
                // So fall through to the status poll below: it is the only thing that
                // can tell us what actually happened. If the brain really is
                // unreachable, the poll throws too and the outer catch says so.
            }

            // The brain keeps the previous repo active until the new one is ready, so
            // wait for state==ready AND a repo match. The long deadline matches the
            // server's own embed timeout (demo/library.py) -- a CPU-throttled host can
            // take far longer than a small demo repo implies, and giving up before the
            // server does just shows a failure on a connect that's still working.
            let deadline = Date().addingTimeInterval(900)
            while Date() < deadline {
                try await Task.sleep(for: .seconds(2))
                if Task.isCancelled { return }
                let status = try await client.status()
                if status.isError {
                    indexingPhase = nil
                    state = .failed(status.error ?? "Indexing failed.")
                    return
                }
                if status.isReady, status.repo.lowercased() == repo.lowercased() {
                    indexingPhase = nil
                    isPrivate = status.isPrivate == true
                    saved.save(repo: status.repo)
                    state = .ready(repo: status.repo)
                    return
                }
                // Still indexing — surface the brain's own progress line (e.g.
                // "Reading the repository…") so the wait isn't a silent spinner.
                indexingPhase = status.phase
                indexingProgressLine = status.indexingLine
            }
            state = .failed("Timed out indexing \(repo).")
        } catch is CancellationError {
            // superseded by a newer connect; leave state as set by the canceller
        } catch let error as BrainError {
            state = .failed(error.userMessage)
        } catch {
            // Only now is "can't reach it" actually true: the connect gave us no
            // answer AND the status poll couldn't reach the brain either.
            state = .failed("Can't reach Icarus's brain — check your internet connection.")
        }
    }
}
