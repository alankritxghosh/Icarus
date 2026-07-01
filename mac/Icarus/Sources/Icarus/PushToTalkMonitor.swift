import AppKit
import Carbon.HIToolbox   // kVK_RightOption

/// Push-to-talk on a single key: hold **Right Option (⌥)** to talk. A modifier-only
/// key can't be a Carbon hotkey, so this watches `.flagsChanged` instead of using
/// `KeyboardShortcuts` (which still owns ⌘⇧I). Two monitors: a global one for when
/// other apps are frontmost, and a local one for when Icarus itself is frontmost.
///
/// Global keyboard monitoring needs the **Input Monitoring** grant
/// (`CGRequestListenEventAccess`); without it only the local monitor fires. We prompt
/// once and degrade calmly — never crash.
@MainActor
final class PushToTalkMonitor {
    private var globalMonitor: Any?
    private var localMonitor: Any?
    private var isDown = false
    private let onDown: () -> Void
    private let onUp: () -> Void

    init(onDown: @escaping () -> Void, onUp: @escaping () -> Void) {
        self.onDown = onDown
        self.onUp = onUp
    }

    /// Whether global keyboard events can be observed (Input Monitoring granted).
    static var hasInputMonitoringAccess: Bool { CGPreflightListenEventAccess() }

    /// Prompt for Input Monitoring (adds Icarus to the list; the user flips it on).
    @discardableResult
    static func requestInputMonitoringAccess() -> Bool { CGRequestListenEventAccess() }

    func start() {
        globalMonitor = NSEvent.addGlobalMonitorForEvents(matching: .flagsChanged) { [weak self] event in
            self?.handle(event)
        }
        localMonitor = NSEvent.addLocalMonitorForEvents(matching: .flagsChanged) { [weak self] event in
            self?.handle(event)
            return event
        }
    }

    func stop() {
        if let g = globalMonitor { NSEvent.removeMonitor(g) }
        if let l = localMonitor { NSEvent.removeMonitor(l) }
        globalMonitor = nil
        localMonitor = nil
    }

    /// Right Option is keyCode 61; left Option is 58 (ignored, so accented-character
    /// typing on the left key is unaffected). `.option` present ⇒ down, absent ⇒ up.
    private func handle(_ event: NSEvent) {
        guard event.keyCode == UInt16(kVK_RightOption) else { return }
        let held = event.modifierFlags.contains(.option)
        if held, !isDown {
            isDown = true
            onDown()
        } else if !held, isDown {
            isDown = false
            onUp()
        }
    }
}
