import Foundation
import Observation
import IcarusKit

/// Loads the repo's SHARED ask ledger — what the whole team asked, not this
/// session's history.
///
/// The distinction is the entire point. `AskHistory` is in-memory and per-run,
/// so the Unknowns surface used to reset every launch and only ever showed your
/// own questions. The ledger is per-REPO and append-only on the server, so a gap
/// three colleagues hit last week is still there, counted three times.
///
/// Failure is surfaced, never silently rendered as "no gaps": an empty list and
/// a failed fetch look identical on screen and mean opposite things — the first
/// says the codebase is well documented, the second says we don't know.
@MainActor
@Observable
final class LedgerModel {
    enum State: Equatable {
        case idle
        case loading
        case loaded(repo: String, gaps: [MemoryGap])
        case failed(String)
    }

    private(set) var state: State = .idle
    enum RecordState: Equatable {
        case idle
        case submitting
        case succeeded(URL)
        case failed(String, URL?)
    }
    private(set) var recordState: RecordState = .idle

    private let client: BrainClient
    private var task: Task<Void, Never>?
    private var recordTask: Task<Void, Never>?

    var isRecording: Bool {
        if case .submitting = recordState { return true }
        return false
    }

    init(client: BrainClient = BrainClient()) {
        self.client = client
    }

    func load() {
        task?.cancel()
        state = .loading
        task = Task {
            do {
                let response = try await client.memoryGaps(includeResolved: true)
                state = .loaded(repo: response.repo, gaps: response.gaps)
            } catch is CancellationError {
                return  // superseded by a newer load; leave state to the canceller
            } catch let error as BrainError {
                state = .failed(error.userMessage)
            } catch {
                state = .failed("Can't reach Icarus's brain — check your internet connection.")
            }
        }
    }

    func record(
        gap: MemoryGap,
        rationale: String,
        tradeoffs: String,
        references: [String]
    ) {
        guard !isRecording else { return }
        guard gap.status == .open, gap.actionable else {
            recordState = .failed(
                "Only an open, undocumented-rationale gap can be recorded.", nil
            )
            return
        }
        recordState = .submitting
        recordTask = Task {
            do {
                let result = try await client.recordEngineeringMemory(
                    gapID: gap.id,
                    rationale: rationale,
                    tradeoffs: tradeoffs,
                    references: references
                )
                recordState = .succeeded(result.pullRequestURL)
                load()
            } catch is CancellationError {
                return
            } catch let error as MemoryRecordFailure {
                recordState = .failed(error.message, error.recoveryURL)
            } catch let error as BrainError {
                recordState = .failed(error.userMessage, nil)
            } catch {
                recordState = .failed(
                    "Icarus couldn't create the GitHub proposal. Nothing was claimed as recorded.",
                    nil
                )
            }
        }
    }

    func resetRecordState() {
        guard !isRecording else { return }
        recordState = .idle
    }
}
