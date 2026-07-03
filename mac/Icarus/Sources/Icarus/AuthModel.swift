import Foundation
import Observation
import IcarusKit

/// Drives the Google-style web GitHub login and holds the signed-in state. Click
/// "Sign in with GitHub" → a secure sheet opens GitHub's login → authorize → the
/// brain exchanges the code (it holds the secret) and bounces back via `icarus://`
/// → the app redeems a one-time session id for the token and keeps it IN MEMORY.
/// No Keychain, no device code. Quit = signed out (in-memory `TokenStore`).
@MainActor
@Observable
final class AuthModel {
    enum State: Equatable {
        case signedOut
        case requesting          // the sheet is open / exchanging
        case signedIn
        case error(String)
    }

    private(set) var state: State = .signedOut

    private let store: TokenStore
    private let client: BrainClient
    private let webAuth: WebAuthenticating
    private var flow: Task<Void, Never>?

    init(store: TokenStore, client: BrainClient, webAuth: WebAuthenticating) {
        self.store = store
        self.client = client
        self.webAuth = webAuth
        if let token = (try? store.load()) ?? nil, !token.isEmpty { state = .signedIn }
    }

    /// Config now lives on the brain (client id + secret), so the app is always
    /// "configured"; the brain returns a clear error if its side isn't set up.
    var isConfigured: Bool { true }
    var isSignedIn: Bool { state == .signedIn }

    /// Start the web login: begin → open the sheet → redeem the session → signed in.
    func connect() {
        flow?.cancel()
        state = .requesting
        flow = Task { await run() }
    }

    func signOut() {
        flow?.cancel()
        try? store.delete()
        state = .signedOut
    }

    private func run() async {
        do {
            let authorizeURL = try await client.beginGitHubLogin()
            let callback = try await webAuth.authenticate(url: authorizeURL, callbackScheme: "icarus")
            guard let session = parseCallbackSession(callback) else {
                state = .error("Sign-in didn't complete — try again.")
                return
            }
            let token = try await client.redeemGitHubSession(session)
            try store.save(token)
            state = .signedIn
        } catch is CancellationError {
            // superseded by a newer attempt / sign-out
        } catch let e as WebAuthError {
            switch e {
            case .cancelled: state = .signedOut
            default: state = .error("Sign-in failed — try again.")
            }
        } catch {
            state = .error("Couldn't reach Icarus's brain to sign in — check your internet connection.")
        }
    }
}
