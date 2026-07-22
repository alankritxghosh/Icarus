import XCTest
@testable import IcarusKit

/// Hold-to-talk decides when the microphone is open, so these are privacy tests as much
/// as behaviour tests: the machine must be hard to start and easy to stop.
final class PushToTalkStateTests: XCTestCase {
    private let rightOption = PushToTalkState.rightOptionKeyCode
    private let leftOption: UInt16 = 58
    private let shift: UInt16 = 56

    func testRightOptionStartsAndReleaseStops() {
        var s = PushToTalkState()
        XCTAssertEqual(s.apply(keyCode: rightOption, optionHeld: true), .start)
        XCTAssertTrue(s.isDown)
        XCTAssertEqual(s.apply(keyCode: rightOption, optionHeld: false), .stop)
        XCTAssertFalse(s.isDown)
    }

    /// THE BUG (observed 2026-07-22): the release arrived as some other event, so the old
    /// code — which ignored anything that wasn't right-Option — never saw it and left the
    /// mic open. Any event showing Option is no longer held must stop the session.
    func testReleaseIsDetectedEvenFromAnotherKeysEvent() {
        var s = PushToTalkState()
        XCTAssertEqual(s.apply(keyCode: rightOption, optionHeld: true), .start)
        XCTAssertEqual(s.apply(keyCode: shift, optionHeld: false), .stop,
                       "any event without Option held must end the session")
        XCTAssertFalse(s.isDown)
    }

    /// Starting stays narrow: left Option is for typing accents, not for opening a mic.
    func testLeftOptionNeverStartsASession() {
        var s = PushToTalkState()
        XCTAssertEqual(s.apply(keyCode: leftOption, optionHeld: true), .none)
        XCTAssertFalse(s.isDown)
    }

    func testRepeatedDownEventsDoNotRestart() {
        var s = PushToTalkState()
        XCTAssertEqual(s.apply(keyCode: rightOption, optionHeld: true), .start)
        XCTAssertEqual(s.apply(keyCode: rightOption, optionHeld: true), .none)
        XCTAssertEqual(s.apply(keyCode: shift, optionHeld: true), .none,
                       "still holding Option — not a release")
    }

    func testReleaseWhenNothingIsOpenIsNotATransition() {
        var s = PushToTalkState()
        XCTAssertEqual(s.apply(keyCode: rightOption, optionHeld: false), .none)
        XCTAssertEqual(s.apply(keyCode: shift, optionHeld: false), .none)
    }

    /// Tearing down the monitors means no release can ever arrive, so the session must be
    /// closed explicitly — and only when one was actually open.
    func testForceStopClosesAnOpenSessionAndIsIdempotent() {
        var s = PushToTalkState()
        _ = s.apply(keyCode: rightOption, optionHeld: true)
        XCTAssertEqual(s.forceStop(), .stop)
        XCTAssertEqual(s.forceStop(), .none, "must not fire a spurious second stop")
        XCTAssertFalse(s.isDown)
    }

    func testForceStopOnAnIdleMachineDoesNothing() {
        var s = PushToTalkState()
        XCTAssertEqual(s.forceStop(), .none)
    }
}
