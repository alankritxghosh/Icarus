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
    /// Auth (web GitHub login) + repo connection, shared by the shell and overlay.
    private lazy var auth = AuthModel(store: tokenStore, client: BrainClient(base: AppConfig.brainBaseURL), webAuth: AppleWebAuth())
    private lazy var connect = ConnectModel(client: AppConfig.client())
    /// Voice-in: real-time on-device streaming via Apple's Speech framework.
    private lazy var voice = VoiceModel(recognizer: AppleSpeechRecognizer())
    /// Durations only, in memory: proves the shipped voice loop against Phase 3's
    /// latency budget without retaining questions, transcripts, or answers.
    private let voiceLatency = VoiceLatencyTracker()
    /// The real in-session ask record, shared by the overlay (which records into it)
    /// and the shell window (which displays it).
    private let history = AskHistory()
    private lazy var status = StatusModel(client: AppConfig.client())
    /// The repo's SHARED ask ledger — what the whole TEAM asked, which is a
    /// different (and far more useful) thing than `history`'s per-session list.
    private lazy var ledger = LedgerModel(client: AppConfig.client())
    /// "What changed since you were last here" -- fetched once per connected
    /// repo, never polled (see BriefingModel).
    private lazy var briefing = BriefingModel(client: AppConfig.client())
    /// Multi-step investigations. Holds no conversational state of its own --
    /// the server owns what "it" refers to (demo/investigations.py).
    private lazy var investigation = InvestigationModel(client: AppConfig.client())
    private lazy var overlay = OverlayController(
        auth: auth,
        connect: connect,
        voice: voice,
        latency: voiceLatency,
        tokenReader: AppConfig.tokenReader,
        history: history
    )
    /// The primary window: the full app shell. Sign-in + connect are folded into
    /// Home's setup gate, so there's no separate onboarding window.
    private lazy var shell = MainWindowController {
        ShellView(auth: self.auth, connect: self.connect,
                  history: self.history, status: self.status, ledger: self.ledger,
                  briefing: self.briefing, investigation: self.investigation,
                  onTryQuestion: { [weak self] in self?.overlay.toggle() })
    }
    /// Hold Right Option (⌥) to talk. Held here so the monitors live for the app's life.
    private var pushToTalk: PushToTalkMonitor?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // A real app: Dock icon + the shell window, plus a menu-bar item and the
        // ⌘⇧I ask overlay. (Setup is folded into the shell's Home gate; Q&A stays
        // an overlay.)
        NSApp.setActivationPolicy(.regular)
        // Theme's palette is dark, and AppKit does NOT take its cue from it: the
        // traffic lights, ProgressView spinners, the TextField caret, Divider,
        // and every scroller stay light until the app's appearance says
        // otherwise. Without this line a fully dark app looks broken rather than
        // dark, which is worse than either.
        NSApp.appearance = NSAppearance(named: .darkAqua)
        NSApp.applicationIconImage = IconArt.appIcon()   // the wings, in the Dock

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = IconArt.menuBarGlyph()   // monochrome menu-bar mark
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Icarus", action: #selector(openWindow), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Ask… (⌘⇧I)", action: #selector(ask), keyEquivalent: ""))
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Settings…", action: #selector(openSettings), keyEquivalent: ","))
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

    func application(_ application: NSApplication, open urls: [URL]) {
        guard let url = urls.first,
              let origin = try? NativeHostManifest.extensionOrigin(fromInstallURL: url),
              let executable = Bundle.main.executableURL
        else { return }

        let extensionID = URL(string: origin)?.host ?? "unknown"
        let confirmation = NSAlert()
        confirmation.messageText = "Connect the Icarus Chrome extension?"
        confirmation.informativeText = (
            "This allows Chrome extension \(extensionID) to ask the installed "
            + "Icarus app for repository status and cited explanations. "
            + "Your GitHub token stays in the Mac Keychain."
        )
        confirmation.alertStyle = .informational
        confirmation.addButton(withTitle: "Connect extension")
        confirmation.addButton(withTitle: "Cancel")
        guard confirmation.runModal() == .alertFirstButtonReturn else { return }

        let result = NSAlert()
        do {
            try NativeHostManifest.install(
                extensionOrigin: origin,
                executableURL: executable
            )
            result.messageText = "Chrome extension connected"
            result.informativeText = "Reload the extension or GitHub tab if it is already open."
            result.alertStyle = .informational
        } catch {
            result.messageText = "Couldn’t connect the Chrome extension"
            result.informativeText = "Icarus could not install its per-user Chrome bridge."
            result.alertStyle = .warning
        }
        result.runModal()
    }

    @objc private func checkForUpdates() { Updater.shared.checkForUpdates() }

    /// Opens SwiftUI's `Settings` scene (IcarusApp.swift). `showSettingsWindow:`
    /// is the selector SwiftUI itself installs on the responder chain for this --
    /// there's no AppKit-facing API to open it directly from a status-bar menu.
    @objc private func openSettings() {
        NSApp.activate(ignoringOtherApps: true)
        NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil)
    }

    @objc private func openWindow() { shell.show() }
    @objc private func ask() { overlay.toggle() }
}
