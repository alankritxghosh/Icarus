import Foundation

/// Remembers the last repo the user successfully connected (repo persistence
/// across launches) and detects the server-side downgrade: if the brain later
/// reports "ready" on a DIFFERENT repo, the server dropped the session. The app
/// must surface that explicitly instead of showing the public default as if it
/// were still the user's repo.
public struct SavedConnection {
    public struct Connection: Equatable, Sendable {
        public let repo: String
    }

    private let defaults: UserDefaults
    private static let repoKey = "icarus.lastConnectedRepo"

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public func save(repo: String) {
        defaults.set(repo, forKey: Self.repoKey)
    }

    public func load() -> Connection? {
        guard let repo = defaults.string(forKey: Self.repoKey), !repo.isEmpty else { return nil }
        return Connection(repo: repo)
    }

    public func clear() {
        defaults.removeObject(forKey: Self.repoKey)
    }

    /// True only when a saved connection exists and the brain reports "ready"
    /// on a different repo. Indexing is never "lost" (a connect in flight shows
    /// the old repo until the new one is ready); errors surface via the connect
    /// flow, not this check.
    public func isLost(given status: RepoStatus) -> Bool {
        guard let saved = load(), status.isReady else { return false }
        return status.repo.lowercased() != saved.repo.lowercased()
    }
}
