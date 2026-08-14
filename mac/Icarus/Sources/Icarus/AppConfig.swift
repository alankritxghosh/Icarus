import Foundation
import IcarusKit

/// App-wide configuration read from the bundle at launch. `brainBaseURL` points
/// at the hosted brain in a shipped build (Info.plist key `ICARUS_BRAIN_URL`,
/// stamped in by `scripts/package_dmg.sh`) and at the local brain otherwise, so
/// `swift run` and a plain `bundle.sh` build keep talking to 127.0.0.1:8000.
enum AppConfig {
    static let brainBaseURL: URL = BrainEndpoint.resolve(from: Bundle.main.infoDictionary)

    /// One Keychain-backed store, so every caller reads the SAME token and a
    /// fresh sign-in takes effect everywhere at once.
    private static let tokenStore: TokenStore = KeychainTokenStore()

    /// A thread-safe reader for the current GitHub token, for the Authorization
    /// header. Read lazily at request time, never cached, so signing out takes
    /// effect on the very next request.
    static let tokenReader: @Sendable () -> String? = { (try? tokenStore.load()) ?? nil }

    /// Backs the Settings "help improve Icarus" toggle (SharePreferences reads
    /// the same UserDefaults key SettingsView's @AppStorage writes).
    static let shareContentReader: @Sendable () -> Bool = { SharePreferences().shareContent }

    /// An authorized client for the connected brain.
    ///
    /// The ONLY supported way to build one. Constructing `BrainClient` by hand
    /// silently drops whichever readers the call site forgets -- the overlay
    /// did exactly that and ignored the share-content toggle for every typed
    /// and spoken question. `tokenReader` is injectable so a caller with its
    /// own reader (the overlay) still gets the share preference wired.
    static func client(
        tokenReader: @escaping @Sendable () -> String? = AppConfig.tokenReader
    ) -> BrainClient {
        BrainClient(base: brainBaseURL, token: tokenReader, shareContent: shareContentReader)
    }
}
