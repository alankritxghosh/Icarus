import Foundation

/// Abstracts the system web-auth sheet (ASWebAuthenticationSession) so the login
/// orchestration is testable. The real implementation lives in the app target;
/// tests use a stub. NOT main-actor: ASWebAuthenticationSession's completion
/// handler fires on a background thread, so the conformer must present on main
/// itself and keep the completion callback non-isolated (`@Sendable`).
public protocol WebAuthenticating: Sendable {
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
