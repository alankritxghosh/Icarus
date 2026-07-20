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
        // Pin the panel to the light appearance. The vibrancy material follows the
        // system theme, but Theme's palette is hardcoded light (dark ink on a light
        // card) — so on a Mac in Dark Mode the glass would render dark and the answer
        // text would be dark-on-dark. Until the palette itself is theme-aware, the
        // honest fix is to keep the surface light rather than ship unreadable text.
        appearance = NSAppearance(named: .aqua)
        // Size the panel from the SwiftUI content's ideal size, and keep resizing
        // as it changes — so a long answer is shown in full instead of clipped.
        let hosting = NSHostingController(rootView: content())
        hosting.sizingOptions = .preferredContentSize
        contentViewController = hosting

        // Option A anchors the pill to the bottom of the screen and lets it grow UPWARD
        // into the answer card. Positioning once isn't enough: `.preferredContentSize`
        // resizes the panel every time the content changes state, and AppKit's resize
        // does not keep the bottom edge where we put it. So re-pin on every resize --
        // that, not the initial placement, is what makes the morph grow upward instead
        // of drifting or running off-screen.
        NotificationCenter.default.addObserver(
            forName: NSWindow.didResizeNotification, object: self, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.pinToBottomCenter() }
        }
        // A drag is the user overriding us; once they move it, stop re-pinning so the
        // panel stays where they put it (the pre-existing behaviour this must not break).
        NotificationCenter.default.addObserver(
            forName: NSWindow.didMoveNotification, object: self, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self, !self.isRepositioning else { return }
                self.userHasMoved = true
            }
        }
    }

    /// True once the user has dragged the panel — auto-pinning yields to them from then on.
    private(set) var userHasMoved = false
    /// Guards the drag detector against our OWN programmatic moves.
    private var isRepositioning = false

    /// Place the panel bottom-centre on the active screen, clear of the Dock and menu
    /// bar (`visibleFrame` already excludes both). No-op once the user has dragged it.
    func pinToBottomCenter(margin: CGFloat = 28) {
        guard !userHasMoved, let screen = NSScreen.main ?? NSScreen.screens.first else { return }
        let visible = screen.visibleFrame
        let origin = NSPoint(x: visible.midX - frame.width / 2,
                             y: visible.minY + margin)
        guard origin != frame.origin else { return }
        isRepositioning = true
        setFrameOrigin(origin)
        isRepositioning = false
    }

    // A panel can take key focus (so the text field is typable) but never
    // becomes the main window — it must not displace the user's real app.
    override var canBecomeKey: Bool { true }
    override var canBecomeMain: Bool { false }
}
