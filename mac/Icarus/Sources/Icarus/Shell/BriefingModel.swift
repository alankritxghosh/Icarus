import Foundation
import Observation
import IcarusKit

/// Fetches `GET /briefing` — what changed since this user was last here.
///
/// Fetched ONCE per connected repo, not polled: the answer only changes when
/// the index does, and polling it would spend GitHub API calls to re-learn the
/// same thing.
///
/// Acknowledgement is deliberately separate and deliberately explicit. The
/// server's GET is pure, so a briefing survives a client that crashes
/// mid-render; `acknowledge()` is called only once the user has actually SEEN
/// it. Calling it on fetch would reproduce, on the client, exactly the bug the
/// server was designed to avoid.
@MainActor
@Observable
final class BriefingModel {
    private(set) var briefing: Briefing?
    /// True when the fetch itself failed. Kept separate from a briefing that
    /// says "unknown": a transport failure is not the brain telling you
    /// something, and conflating them would let a network blip masquerade as
    /// a considered answer.
    private(set) var unreachable = false

    private let client: BrainClient
    private var loadedRepo: String?

    init(client: BrainClient = BrainClient()) {
        self.client = client
    }

    func load(repo: String?) async {
        guard let repo, repo != loadedRepo else { return }
        loadedRepo = repo
        do {
            briefing = try await client.briefing()
            unreachable = false
        } catch {
            briefing = nil
            unreachable = true
        }
    }

    /// Mark the briefing seen, moving the anchor to the current commit. Safe to
    /// call more than once; a failure is ignored, because failing to record a
    /// visit must never surface as an error to someone who just read a summary.
    func acknowledge() async {
        guard briefing != nil else { return }
        try? await client.acknowledgeBriefing()
    }

    /// Reset when the connected repo changes, so a briefing about one repo can
    /// never be shown against another.
    func forget() {
        briefing = nil
        loadedRepo = nil
        unreachable = false
    }
}
