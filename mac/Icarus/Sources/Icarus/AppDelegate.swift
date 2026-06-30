import AppKit
import KeyboardShortcuts

extension KeyboardShortcuts.Name {
    /// Global hotkey that toggles the overlay. Default ⌘⇧I; user-rebindable later.
    static let toggleIcarus = Self("toggleIcarus", default: .init(.i, modifiers: [.command, .shift]))
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var statusItem: NSStatusItem!
    private let overlay = OverlayController()

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)   // menu-bar agent: no Dock icon
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.title = "☉"           // placeholder glyph; real icon comes in a later brick
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Ask…", action: #selector(ask), keyEquivalent: ""))
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Quit Icarus",
                                action: #selector(NSApplication.terminate(_:)),
                                keyEquivalent: "q"))
        statusItem.menu = menu

        // Registered global hotkey — works from any app without Accessibility
        // permission. The callback is main-actor-isolated, matching OverlayController.
        KeyboardShortcuts.onKeyUp(for: .toggleIcarus) { [weak self] in
            self?.overlay.toggle()
        }
    }

    @objc private func ask() { overlay.toggle() }
}
