import AppKit
import KeyboardShortcuts

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
    private lazy var overlay = OverlayController(auth: auth, connect: connect)
    private lazy var onboarding = OnboardingWindowController(auth: auth, connect: connect)

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
