import Foundation
import Sparkle

/// In-app updates.
///
/// WHY: shipping any change to the app currently means emailing every tester,
/// asking them to re-download a DMG, clear Gatekeeper again, and re-authorise
/// their Keychain. That cost is paid by the user, every time, and it is the
/// thing standing between this and being comfortable asking a team to try it.
///
/// Sparkle signs its update feed with its OWN EdDSA key, so this works without
/// an Apple Developer ID. It does NOT make the app notarized: a first install
/// still takes the one-time Gatekeeper step. What it removes is every step
/// AFTER the first one.
///
/// Deliberately inert unless the build was stamped with a feed and a public
/// key (`package_dmg.sh` does that). A local `swift run` or an unstamped build
/// has no feed to check, and must not pester a developer with update dialogs
/// or -- worse -- fail open and install something unverified.
@MainActor
final class Updater {
    static let shared = Updater()

    private let controller: SPUStandardUpdaterController?

    private init() {
        let info = Bundle.main.infoDictionary ?? [:]
        let feed = (info["SUFeedURL"] as? String)?.trimmingCharacters(in: .whitespaces) ?? ""
        let key = (info["SUPublicEDKey"] as? String)?.trimmingCharacters(in: .whitespaces) ?? ""
        // BOTH are required. A feed without a key would let Sparkle download
        // an update it cannot verify, which is a worse failure than having no
        // updater at all -- so this refuses rather than degrades.
        guard !feed.isEmpty, !key.isEmpty, URL(string: feed) != nil else {
            controller = nil
            return
        }
        controller = SPUStandardUpdaterController(startingUpdater: true,
                                                 updaterDelegate: nil,
                                                 userDriverDelegate: nil)
    }

    /// True when this build can actually check for updates, so the UI can hide
    /// a menu item that would otherwise do nothing.
    var isConfigured: Bool { controller != nil }

    func checkForUpdates() {
        controller?.updater.checkForUpdates()
    }
}
