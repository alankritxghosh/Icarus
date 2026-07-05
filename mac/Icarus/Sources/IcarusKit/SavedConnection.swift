import Foundation

/// Remembers the last repo the user successfully connected (repo persistence
/// across launches) and detects the server-side downgrade: if the brain later
/// reports "ready" on a DIFFERENT repo, the server dropped the session (Render
/// restart, or the registry's LRU eviction of a private repo it holds no token
/// to resume). The app must surface that explicitly — never silently show the
/// public default as if it were still the user's repo.
public struct SavedConnection {
    public struct Connection: Equatable, Sendable {
        public let repo: String
        public let isPrivate: Bool
    }

    private let defaults: UserDefaults
    private static let repoKey = "icarus.lastConnectedRepo"
    private static let privateKey = "icarus.lastConnectedPrivate"

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public func save(repo: String, isPrivate: Bool) {
        defaults.set(repo, forKey: Self.repoKey)
        defaults.set(isPrivate, forKey: Self.privateKey)
    }

    public func load() -> Connection? {
        guard let repo = defaults.string(forKey: Self.repoKey), !repo.isEmpty else { return nil }
        return Connection(repo: repo, isPrivate: defaults.bool(forKey: Self.privateKey))
    }

    public func clear() {
        defaults.removeObject(forKey: Self.repoKey)
        defaults.removeObject(forKey: Self.privateKey)
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
