import AppKit
import KeyboardShortcuts
import IcarusKit

extension KeyboardShortcuts.Name {
    /// Global hotkey that toggles the ask overlay. Default ⌘⇧I; user-rebindable later.
    static let toggleIcarus = Self("toggleIcarus", default: .init(.i, modifiers: [.command, .shift]))
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    /// One Keychain-backed token store, shared everywhere so the token has a single
    /// source of truth. Persists across launches — sign in once per device — and the
    /// BrainClient reads it to authorize /ask and /connect. Sign out deletes it.
    private let tokenStore: TokenStore = KeychainTokenStore()
    /// A thread-safe reader for the current token, for the Authorization header.
    private lazy var tokenReader: @Sendable () -> String? = { [tokenStore] in
        (try? tokenStore.load()) ?? nil
    }
    /// Auth (web GitHub login) + repo connection, shared by the shell and overlay.
    private lazy var auth = AuthModel(store: tokenStore, client: BrainClient(base: AppConfig.brainBaseURL), webAuth: AppleWebAuth())
    private lazy var connect = ConnectModel(client: BrainClient(base: AppConfig.brainBaseURL, token: tokenReader))
    /// Voice-in: real-time on-device streaming via Apple's Speech framework.
    private lazy var voice = VoiceModel(recognizer: AppleSpeechRecognizer())
    /// The real in-session ask record, shared by the overlay (which records into it)
    /// and the shell window (which displays it).
    private let history = AskHistory()
    private lazy var status = StatusModel(client: BrainClient(base: AppConfig.brainBaseURL, token: tokenReader))
    /// The repo's SHARED ask ledger — what the whole TEAM asked, which is a
    /// different (and far more useful) thing than `history`'s per-session list.
    private lazy var ledger = LedgerModel(client: BrainClient(base: AppConfig.brainBaseURL, token: tokenReader))
    /// "What changed since you were last here" -- fetched once per connected
    /// repo, never polled (see BriefingModel).
    private lazy var briefing = BriefingModel(client: BrainClient(base: AppConfig.brainBaseURL, token: tokenReader))
    private lazy var overlay = OverlayController(auth: auth, connect: connect, voice: voice, tokenReader: tokenReader, history: history)
    /// The primary window: the full app shell. Sign-in + connect are folded into
    /// Home's setup gate, so there's no separate onboarding window.
    private lazy var shell = MainWindowController {
        ShellView(auth: self.auth, connect: self.connect,
                  history: self.history, status: self.status, ledger: self.ledger,
                  briefing: self.briefing,
                  onTryQuestion: { [weak self] in self?.overlay.toggle() })
    }
    /// Hold Right Option (⌥) to talk. Held here so the monitors live for the app's life.
    private var pushToTalk: PushToTalkMonitor?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // A real app: Dock icon + the shell window, plus a menu-bar item and the
        // ⌘⇧I ask overlay. (Setup is folded into the shell's Home gate; Q&A stays
        // an overlay.)
        NSApp.setActivationPolicy(.regular)
        NSApp.applicationIconImage = IconArt.appIcon()   // Signal Spine in the Dock

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = IconArt.menuBarGlyph()   // monochrome menu-bar mark
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Icarus", action: #selector(openWindow), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Ask… (⌘⇧I)", action: #selector(ask), keyEquivalent: ""))
        // Only shown when the build was stamped with an update feed and key --
        // an item that silently does nothing is worse than no item.
        if Updater.shared.isConfigured {
            menu.addItem(.separator())
            menu.addItem(NSMenuItem(title: "Check for Updates…",
                                    action: #selector(checkForUpdates), keyEquivalent: ""))
        }
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Quit Icarus",
                                action: #selector(NSApplication.terminate(_:)),
                                keyEquivalent: "q"))
        statusItem.menu = menu

        // Registered global hotkey — works from any app without Accessibility
        // permission. Main-actor-isolated, matching OverlayController.
        KeyboardShortcuts.onKeyUp(for: .toggleIcarus) { [weak self] in
            self?.overlay.toggle()
        }

        // Push-to-talk: hold Right Option (⌥). Needs Input Monitoring to fire from
        // other apps — prompt once; the local monitor still works when Icarus is up.
        if !PushToTalkMonitor.hasInputMonitoringAccess {
            PushToTalkMonitor.requestInputMonitoringAccess()
        }
        let ptt = PushToTalkMonitor(
            onDown: { [weak self] in self?.overlay.beginVoice() },
            onUp: { [weak self] in self?.overlay.endVoice() }
        )
        ptt.start()
        pushToTalk = ptt

        // The first screen: the app shell (its Home surface gates on sign-in + connect).
        shell.show()

        // Reconnect the cached last repo when sign-in survives a relaunch.
        if auth.isSignedIn { connect.resumeSaved() }
    }

    /// Re-open the window when the user clicks the Dock icon with no window visible.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { shell.show() }
        return true
    }

    @objc private func checkForUpdates() { Updater.shared.checkForUpdates() }

    @objc private func openWindow() { shell.show() }
    @objc private func ask() { overlay.toggle() }
}
