import AppKit
import SwiftUI

/// A translucent, non-activating panel that floats above other apps. Its title
/// bar is present (`.titled`) but transparent and hidden, so it reads as
/// chromeless rather than truly borderless. `.nonactivatingPanel` keeps the
/// user's current app focused when the panel appears; `.canJoinAllSpaces` lets
/// it follow across Spaces and over full-screen apps. Generic over its SwiftUI
/// content so the overlay view stays decoupled.
final class FloatingPanel<Content: View>: NSPanel {
    init(@ViewBuilder content: () -> Content) {
        // Seed size; the hosting controller drives the real size from here on.
        super.init(contentRect: NSRect(x: 0, y: 0, width: 560, height: 120),
                   styleMask: [.titled, .fullSizeContentView, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        // The .titled styleMask defaults this to true; since the panel is cached
        // and reused, a future close() path would over-release it and crash on
        // re-show. Keep the instance alive across close/show cycles.
        isReleasedWhenClosed = false
        isFloatingPanel = true
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        titleVisibility = .hidden
        titlebarAppearsTransparent = true
        isMovableByWindowBackground = true
        backgroundColor = .clear
        isOpaque = false
        hasShadow = true
        // Size the panel from the SwiftUI content's ideal size, and keep resizing
        // as it changes — so a long answer is shown in full instead of clipped.
        let hosting = NSHostingController(rootView: content())
        hosting.sizingOptions = .preferredContentSize
        contentViewController = hosting
    }

    // A panel can take key focus (so the text field is typable) but never
    // becomes the main window — it must not displace the user's real app.
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
