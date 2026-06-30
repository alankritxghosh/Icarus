import AppKit
import SwiftUI

/// Owns the floating overlay panel and its show/hide logic, so `AppDelegate`
/// stays a thin wiring layer. Main-actor isolated because it touches AppKit.
@MainActor
final class OverlayController {
    private var panel: FloatingPanel<OverlayView>?
    /// Ask state lives here (not in the view) so it survives hide/re-show. Auth is
    /// shared with the onboarding window, so it's injected by the app delegate.
    private let auth: AuthModel
    private let connect: ConnectModel
    private let model = AskModel()

    init(auth: AuthModel, connect: ConnectModel) {
        self.auth = auth
        self.connect = connect
    }

    /// Show the overlay if hidden, hide it if visible.
    func toggle() {
        if let panel, panel.isVisible {
            panel.orderOut(nil)
            return
        }
        show()
    }

    private func show() {
        let panel: FloatingPanel<OverlayView>
        if let existing = self.panel {
            panel = existing
        } else {
            panel = FloatingPanel { OverlayView(auth: self.auth, connect: self.connect, model: self.model) }
            self.panel = panel
            // Center only on first creation; reusing the cached panel preserves
            // wherever the user last dragged it instead of yanking it back.
            panel.center()
        }
        // Show + take key focus (the text field is typable) WITHOUT activating
        // the app — a non-activating panel must not steal focus from the user's
        // current app, so we deliberately avoid NSApp.activate here.
        panel.makeKeyAndOrderFront(nil)
    }
}
