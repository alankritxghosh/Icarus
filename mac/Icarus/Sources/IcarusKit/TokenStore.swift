import Foundation

/// Where the GitHub access token lives. The real implementation is the macOS
/// Keychain (in the app target); tests use the in-memory double. The token is a
/// credential: never log it, never write it to a file, never commit it.
public protocol TokenStore: Sendable {
    func save(_ token: String) throws
    func load() throws -> String?
    func delete() throws
}

/// In-memory double for tests ONLY — not persisted, not secure.
public final class InMemoryTokenStore: TokenStore, @unchecked Sendable {
    private var token: String?
    private let lock = NSLock()

    public init() {}

    public func save(_ token: String) throws {
        lock.lock(); defer { lock.unlock() }
        self.token = token
    }

    public func load() throws -> String? {
        lock.lock(); defer { lock.unlock() }
        return token
    }

    public func delete() throws {
        lock.lock(); defer { lock.unlock() }
        token = nil
    }
}
