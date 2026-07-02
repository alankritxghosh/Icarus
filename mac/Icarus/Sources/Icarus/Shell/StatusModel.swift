import Foundation
import Observation
import IcarusKit

/// Polls the brain's `/status` so the shell can show the real connected repo and
/// real index counts (never fabricated numbers). Read-only; no token needed.
@MainActor
@Observable
final class StatusModel {
    private(set) var status: RepoStatus?

    private let client: BrainClient
    private var task: Task<Void, Never>?

    init(client: BrainClient = BrainClient()) {
        self.client = client
    }

    func start() {
        guard task == nil else { return }
        task = Task { [weak self] in
            while !Task.isCancelled {
                if let s = try? await self?.client.status() { self?.status = s }
                try? await Task.sleep(for: .seconds(5))
            }
        }
    }

    func stop() { task?.cancel(); task = nil }

    var repo: String? { status?.repo }
    var counts: IndexCounts? { status?.counts }
}
