import AppKit
import Carbon.HIToolbox   // kVK_RightOption
import IcarusKit

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
    private var state = PushToTalkState()
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
        // Tearing down the monitors means no release event can ever arrive, so close any
        // open session here rather than leaving the microphone live.
        if state.forceStop() == .stop { onUp() }
    }

    /// Every flags event is fed to the state machine — note this is NOT gated on the
    /// key code any more. Gating the whole handler on right-Option meant a release that
    /// arrived as any other event was never seen, leaving the mic open with no key held
    /// (see PushToTalkState for the full account). Starting stays right-Option-only;
    /// PushToTalkState owns that asymmetry.
    private func handle(_ event: NSEvent) {
        switch state.apply(keyCode: event.keyCode,
                           optionHeld: event.modifierFlags.contains(.option)) {
        case .start: onDown()
        case .stop:  onUp()
        case .none:  break
        }
    }
}
