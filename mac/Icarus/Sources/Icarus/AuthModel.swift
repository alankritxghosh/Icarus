import AppKit
import Foundation
import Observation
import IcarusKit

/// Drives the GitHub OAuth Device Flow UX and holds the signed-in state. Owned by
/// `OverlayController` so the session survives the overlay hiding/re-showing.
/// The token lives in the Keychain (via `TokenStore`), never here in plaintext on disk.
@MainActor
@Observable
final class AuthModel {
    enum State: Equatable {
        case signedOut
        case requesting
        case awaitingApproval(userCode: String, verificationUri: String)
        case signedIn
        case error(String)
    }

    private(set) var state: State = .signedOut

    private let store: TokenStore
    /// Device flow uses a public Client ID (not a secret). Per-install via env.
    private let clientID = ProcessInfo.processInfo.environment["ICARUS_GH_CLIENT_ID"]
    private var flow: Task<Void, Never>?

    init(store: TokenStore = KeychainTokenStore()) {
        self.store = store
        if let token = (try? store.load()) ?? nil, !token.isEmpty {
            state = .signedIn
        }
    }

    var isConfigured: Bool { !(clientID ?? "").isEmpty }
    var isSignedIn: Bool { state == .signedIn }

    /// Start the device flow: request a code, open the browser, copy the code, poll.
    func connect() {
        guard let clientID, !clientID.isEmpty else {
            state = .error("Set ICARUS_GH_CLIENT_ID (your OAuth App Client ID) and relaunch.")
            return
        }
        flow?.cancel()
        state = .requesting
        flow = Task { await run(clientID: clientID) }
    }

    func signOut() {
        flow?.cancel()
        try? store.delete()
        state = .signedOut
    }

    private func run(clientID: String) async {
        do {
            let dc = try await GitHubDeviceAuth.requestDeviceCode(clientID: clientID)
            // Open GitHub's device page and put the code on the clipboard for easy paste.
            if let url = URL(string: dc.verificationUri) { NSWorkspace.shared.open(url) }
            NSPasteboard.general.clearContents()
            NSPasteboard.general.setString(dc.userCode, forType: .string)
            state = .awaitingApproval(userCode: dc.userCode, verificationUri: dc.verificationUri)

            var interval = max(dc.interval, 1)
            let deadline = Date().addingTimeInterval(TimeInterval(dc.expiresIn))
            while Date() < deadline {
                try await Task.sleep(for: .seconds(interval))
                if Task.isCancelled { return }
                switch try await GitHubDeviceAuth.pollOnce(clientID: clientID, deviceCode: dc.deviceCode) {
                case .pending:
                    continue
                case .slowDown(let newInterval):
                    interval = newInterval
                case .token(let token):
                    try store.save(token)
                    state = .signedIn
                    return
                case .denied:
                    state = .error("Access was denied on GitHub.")
                    return
                case .expired:
                    state = .error("The code expired — connect again.")
                    return
                case .error(let message):
                    state = .error("Sign-in failed: \(message)")
                    return
                }
            }
            state = .error("The code expired — connect again.")
        } catch is CancellationError {
            // sign-out / restart: leave state as set by the canceller
        } catch {
            state = .error("Couldn't reach GitHub. Check your connection.")
        }
    }
}
