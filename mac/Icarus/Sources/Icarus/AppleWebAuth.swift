import AppKit
import AuthenticationServices
import IcarusKit

/// The real web-auth sheet: `ASWebAuthenticationSession` presents GitHub's login
/// in a secure sheet and captures the redirect to the `icarus://` scheme — no
/// custom URL-scheme registration or Keychain needed. Main-actor: the sheet must
/// be started on the main thread and anchored to a window.
@MainActor
final class AppleWebAuth: NSObject, WebAuthenticating, ASWebAuthenticationPresentationContextProviding {
    func authenticate(url: URL, callbackScheme: String) async throws -> URL {
        try await withCheckedThrowingContinuation { cont in
            let session = ASWebAuthenticationSession(url: url, callbackURLScheme: callbackScheme) { callbackURL, error in
                if let error {
                    if let asError = error as? ASWebAuthenticationSessionError, asError.code == .canceledLogin {
                        cont.resume(throwing: WebAuthError.cancelled)
                    } else {
                        cont.resume(throwing: WebAuthError.failed(error.localizedDescription))
                    }
                    return
                }
                guard let callbackURL else { cont.resume(throwing: WebAuthError.badCallback); return }
                cont.resume(returning: callbackURL)
            }
            session.presentationContextProvider = self
            // Reuse the existing GitHub browser session so re-login is one click.
            session.prefersEphemeralWebBrowserSession = false
            if !session.start() {
                cont.resume(throwing: WebAuthError.failed("Couldn't open the sign-in sheet."))
            }
        }
    }

    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        NSApp.keyWindow ?? NSApp.windows.first ?? ASPresentationAnchor()
    }
}
