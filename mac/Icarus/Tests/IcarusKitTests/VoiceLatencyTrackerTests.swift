import XCTest
@testable import IcarusKit

@MainActor
final class VoiceLatencyTrackerTests: XCTestCase {
    func testCompleteVoiceJourneyRecordsEveryStage() {
        var now: TimeInterval = 10
        let tracker = VoiceLatencyTracker(now: { now })

        tracker.begin()
        now = 12
        tracker.released()
        now = 12.4
        tracker.transcriptReady()
        now = 14.0
        tracker.answerReady()
        now = 14.2
        tracker.firstWordStarted()

        let sample = try! XCTUnwrap(tracker.latest)
        XCTAssertEqual(sample.hold, 2, accuracy: 0.0001)
        XCTAssertEqual(sample.transcription, 0.4, accuracy: 0.0001)
        XCTAssertEqual(sample.brain, 1.6, accuracy: 0.0001)
        XCTAssertEqual(sample.speechQueue, 0.2, accuracy: 0.0001)
        XCTAssertEqual(sample.releaseToFirstWord, 2.2, accuracy: 0.0001)
        XCTAssertEqual(sample.total, 4.2, accuracy: 0.0001)
    }

    func testIncompleteOrOutOfOrderJourneyNeverBecomesAMeasurement() {
        var now: TimeInterval = 1
        let tracker = VoiceLatencyTracker(now: { now })

        tracker.begin()
        now = 2
        tracker.answerReady()
        now = 3
        tracker.firstWordStarted()

        XCTAssertTrue(tracker.samples.isEmpty)
    }

    func testSamplesAreBoundedToTheNewestFifty() {
        var now: TimeInterval = 0
        let tracker = VoiceLatencyTracker(now: { now })

        for _ in 0..<55 {
            tracker.begin()
            now += 1
            tracker.released()
            now += 1
            tracker.transcriptReady()
            now += 1
            tracker.answerReady()
            now += 1
            tracker.firstWordStarted()
        }

        XCTAssertEqual(tracker.samples.count, 50)
        XCTAssertEqual(tracker.samples.first?.total, 4)
    }

    func testSessionPercentilesUseReleaseToFirstWord() {
        var now: TimeInterval = 0
        let tracker = VoiceLatencyTracker(now: { now })

        for latency in [1.0, 2.0, 3.0, 4.0, 20.0] {
            tracker.begin()
            tracker.released()
            tracker.transcriptReady()
            tracker.answerReady()
            now += latency
            tracker.firstWordStarted()
        }

        XCTAssertEqual(tracker.releaseToFirstWordP50, 3)
        XCTAssertEqual(tracker.releaseToFirstWordP95, 20)
    }

    func testStartingAgainDiscardsAnIncompleteJourney() {
        var now: TimeInterval = 0
        let tracker = VoiceLatencyTracker(now: { now })

        tracker.begin()
        now = 100
        tracker.begin()
        now = 101
        tracker.released()
        tracker.transcriptReady()
        tracker.answerReady()
        tracker.firstWordStarted()

        XCTAssertEqual(tracker.latest?.total, 1)
    }
}
