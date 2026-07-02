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
    /// source of truth. The BrainClient reads it to authorize /ask and /connect.
    private let tokenStore: TokenStore = KeychainTokenStore()
    /// A thread-safe reader for the current token, for the Authorization header.
    private lazy var tokenReader: @Sendable () -> String? = { [tokenStore] in
        (try? tokenStore.load()) ?? nil
    }
    /// Auth + repo connection are shared by the onboarding window and the ask overlay.
    private lazy var auth = AuthModel(store: tokenStore)
    private lazy var connect = ConnectModel(client: BrainClient(token: tokenReader))
    /// Voice-in: real-time on-device streaming via Apple's Speech framework.
    private lazy var voice = VoiceModel(recognizer: AppleSpeechRecognizer())
    /// The real in-session ask record, shared by the overlay (which records into it)
    /// and the shell window (which displays it).
    private let history = AskHistory()
    private lazy var status = StatusModel(client: BrainClient(token: tokenReader))
    private lazy var overlay = OverlayController(auth: auth, connect: connect, voice: voice, tokenReader: tokenReader, history: history)
    private lazy var onboarding = OnboardingWindowController(auth: auth, connect: connect)
    /// Additive full-app shell window (Phase B). Opens from the menu bar; the
    /// existing onboarding + overlay stay intact until the shell is promoted.
    private lazy var shell = MainWindowController {
        ShellView(history: self.history, status: self.status,
                  onTryQuestion: { [weak self] in self?.overlay.toggle() })
    }
    /// Hold Right Option (⌥) to talk. Held here so the monitors live for the app's life.
    private var pushToTalk: PushToTalkMonitor?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // A real app: Dock icon + a visible window, plus a menu-bar item and the
        // hotkey overlay. (Onboarding/setup wants a window; Q&A stays an overlay.)
        NSApp.setActivationPolicy(.regular)
        NSApp.applicationIconImage = IconArt.appIcon()   // Signal Spine in the Dock

        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = IconArt.menuBarGlyph()   // monochrome menu-bar mark
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Open Icarus", action: #selector(openWindow), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Open shell (preview)", action: #selector(openShell), keyEquivalent: ""))
        menu.addItem(NSMenuItem(title: "Ask… (⌘⇧I)", action: #selector(ask), keyEquivalent: ""))
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

        // The first screen: the onboarding window.
        onboarding.show()
    }

    /// Re-open the window when the user clicks the Dock icon with no window visible.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        if !flag { onboarding.show() }
        return true
    }

    @objc private func openWindow() { onboarding.show() }
    @objc private func openShell() { shell.show() }
    @objc private func ask() { overlay.toggle() }
}
