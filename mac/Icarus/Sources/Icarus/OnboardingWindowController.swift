import AppKit
import SwiftUI

/// Owns the app's onboarding/main window (the visible application window). Lazily
/// builds an NSWindow hosting `OnboardingView`; `show()` brings it to front and is
/// safe to call repeatedly (menu "Open Icarus", Dock re-open).
@MainActor
final class OnboardingWindowController {
    private var window: NSWindow?
    private let auth: AuthModel

    init(auth: AuthModel) {
        self.auth = auth
    }

    func show() {
        if let window {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
            return
        }
        let hosting = NSHostingController(rootView: OnboardingView(auth: auth))
        let window = NSWindow(contentViewController: hosting)
        window.title = "Icarus"
        window.styleMask = [.titled, .closable, .miniaturizable]
        window.isReleasedWhenClosed = false   // keep it so we can re-show the same window
        window.center()
        self.window = window
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
