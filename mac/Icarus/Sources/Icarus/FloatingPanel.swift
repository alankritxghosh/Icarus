import AppKit
import SwiftUI

/// A borderless, translucent, non-activating panel that floats above other apps.
/// `.nonactivatingPanel` keeps the user's current app focused when the panel
/// appears; `.canJoinAllSpaces` lets it follow across Spaces and over full-screen
/// apps. Generic over its SwiftUI content so the overlay view stays decoupled.
final class FloatingPanel<Content: View>: NSPanel {
    init(contentRect: NSRect, @ViewBuilder content: () -> Content) {
        super.init(contentRect: contentRect,
                   styleMask: [.titled, .fullSizeContentView, .nonactivatingPanel],
                   backing: .buffered, defer: false)
        isFloatingPanel = true
        level = .floating
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
        titleVisibility = .hidden
        titlebarAppearsTransparent = true
        isMovableByWindowBackground = true
        backgroundColor = .clear
        isOpaque = false
        hasShadow = true
        contentView = NSHostingView(rootView: content())
    }

    // A panel can take key focus (so the text field is typable) but never
    // becomes the main window — it must not displace the user's real app.
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
