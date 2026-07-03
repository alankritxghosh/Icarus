import AppKit
import AuthenticationServices
import IcarusKit

/// The real web-auth sheet: `ASWebAuthenticationSession` presents GitHub's login
/// in a secure sheet and captures the redirect to the `icarus://` scheme.
///
/// Concurrency: the completion handler is invoked on a BACKGROUND XPC thread, so
/// it must be `@Sendable` / non-isolated — it only touches the (thread-safe)
/// continuation. The session is created and `start()`ed on the main actor, and
/// retained until it completes.
final class AppleWebAuth: NSObject, WebAuthenticating, ASWebAuthenticationPresentationContextProviding, @unchecked Sendable {
    private var session: ASWebAuthenticationSession?

    func authenticate(url: URL, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<URL, Error>) in
            // Non-isolated: safe to call from the background completion thread.
            let handler: @Sendable (URL?, Error?) -> Void = { callbackURL, error in
                if let error {
                    if let asError = error as? ASWebAuthenticationSessionError,
                       asError.code == .canceledLogin {
                        cont.resume(throwing: WebAuthError.cancelled)
                    } else {
                        cont.resume(throwing: WebAuthError.failed(error.localizedDescription))
                    }
                    return
                }
                guard let callbackURL else { cont.resume(throwing: WebAuthError.badCallback); return }
                cont.resume(returning: callbackURL)
            }
            Task { @MainActor in
                let s = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme,
                                                   completionHandler: handler)
                s.presentationContextProvider = self
                // Ephemeral: no shared cookies, so each sign-in lets the user pick a
                // GitHub account (matters after Sign out → use another account). The
                // token is persisted by us, so a fresh login only happens rarely.
                s.prefersEphemeralWebBrowserSession = true
                self.session = s                              // retain until it completes
                if !s.start() {
                    cont.resume(throwing: WebAuthError.failed("Couldn't open the sign-in sheet."))
                }
            }
        }
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        NSApp.keyWindow ?? NSApp.windows.first ?? ASPresentationAnchor()
    }
}
