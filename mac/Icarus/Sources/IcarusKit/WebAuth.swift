import Foundation

/// Abstracts the system web-auth sheet (ASWebAuthenticationSession) so the login
/// orchestration is testable. The real implementation lives in the app target;
/// tests use a stub. Main-actor: the sheet must be presented on the main thread.
@MainActor
public protocol WebAuthenticating {
    /// Present a web auth sheet at `url` and capture the redirect to
    /// `callbackScheme` (e.g. "icarus"). Returns the full callback URL.
    func authenticate(url: URL, callbackScheme: String) async throws -> URL
}

public enum WebAuthError: Error, Equatable {
    case cancelled
    case failed(String)
    case badCallback
}

/// Extract the one-time session id from the `icarus://auth?session=…` callback.
/// Pure and testable; returns nil for a malformed or session-less URL.
public func parseCallbackSession(_ url: URL) -> String? {
    guard let comps = URLComponents(url: url, resolvingAgainstBaseURL: false),
          let value = comps.queryItems?.first(where: { $0.name == "session" })?.value,
          !value.isEmpty
    else { return nil }
    return value
}
