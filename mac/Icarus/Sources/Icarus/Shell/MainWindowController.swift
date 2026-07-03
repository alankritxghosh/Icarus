import AppKit
import SwiftUI

/// Hosts the shell in a standard resizable window. Additive: it lives alongside
/// the onboarding window + overlay, so the existing working app is untouched. Once
/// the shell is verified it can be promoted to the primary window.
@MainActor
final class MainWindowController {
    private var window: NSWindow?
    private let content: AnyView

    init<Content: View>(@ViewBuilder content: () -> Content) {
        self.content = AnyView(content())
    }

    func show() {
        if window == nil {
            let hosting = NSHostingController(rootView: content)
            let w = NSWindow(contentViewController: hosting)
            w.title = "Icarus"
            w.setContentSize(NSSize(width: 1180, height: 760))
            // Chromeless title bar: content fills the window and the traffic-light
            // buttons float over the sidebar, so there's one set of dots, not two.
            w.styleMask = [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView]
            w.titlebarAppearsTransparent = true
            w.titleVisibility = .hidden
            w.isMovableByWindowBackground = true
            w.isReleasedWhenClosed = false
            w.center()
            window = w
        }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }
}
