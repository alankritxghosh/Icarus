import Foundation

/// The press/release decision behind hold-to-talk, as a pure state machine so it can be
/// tested without a keyboard, a microphone, or AppKit.
///
/// It exists because the rule is asymmetric, and getting that asymmetry wrong leaves the
/// microphone open:
///
/// - **Starting** is deliberately narrow — only the RIGHT Option key (keyCode 61) begins
///   a session, so ordinary left-Option accented typing never opens the mic.
/// - **Stopping** must be as wide as possible. Any event showing Option is no longer held
///   ends the session, whatever key it came from. An earlier version required the release
///   to arrive as a right-Option event too; if that exact event never came — flags cleared
///   by another key, focus moving mid-hold, monitoring access revoked — the app stayed in
///   "listening" with the mic live and no key down. Observed 2026-07-22.
///
/// The product rule this encodes: recording is opt-in and explicit, so ANY evidence the
/// user let go is enough to stop, while only one specific key is enough to start.
public struct PushToTalkState: Equatable, Sendable {
    /// Right Option. Left Option is 58 and deliberately never starts a session.
    public static let rightOptionKeyCode: UInt16 = 61

    public enum Transition: Equatable, Sendable {
        case none
        case start
        case stop
    }

    public private(set) var isDown = false

    public init() {}

    /// Feed one modifier-flags event. Returns the transition the caller should act on.
    public mutating func apply(keyCode: UInt16, optionHeld: Bool) -> Transition {
        if !isDown, keyCode == Self.rightOptionKeyCode, optionHeld {
            isDown = true
            return .start
        }
        if isDown, !optionHeld {
            isDown = false
            return .stop
        }
        return .none
    }

    /// Force the session closed (app resigning, monitors torn down). Idempotent, and
    /// reports whether anything was actually open, so a caller never fires a spurious stop.
    public mutating func forceStop() -> Transition {
        guard isDown else { return .none }
        isDown = false
        return .stop
    }
}
