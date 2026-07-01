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
    /// Auth + repo connection are shared by the onboarding window and the ask overlay.
    private let auth = AuthModel()
    private let connect = ConnectModel()
    /// Voice-in: real-time on-device streaming via Apple's Speech framework.
    private lazy var voice = VoiceModel(recognizer: AppleSpeechRecognizer())
    private lazy var overlay = OverlayController(auth: auth, connect: connect, voice: voice)
    private lazy var onboarding = OnboardingWindowController(auth: auth, connect: connect)
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
    @objc private func ask() { overlay.toggle() }
}
