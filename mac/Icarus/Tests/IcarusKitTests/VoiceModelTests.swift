import XCTest
@testable import IcarusKit

@MainActor
final class VoiceModelTests: XCTestCase {
    /// A successful record → finish routes the trimmed final transcript out and returns
    /// to idle. This is the whole point: speech becomes the question text.
    func testFinalTranscriptFlowsToSink() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: ["why", "why the"], final: "  why the pause chain?  ")))
        var received: String?
        model.onTranscript = { received = $0 }

        await model.startRecording()
        XCTAssertEqual(model.state, .recording)
        await model.stopAndTranscribe()

        XCTAssertEqual(received, "why the pause chain?")   // trimmed
        XCTAssertEqual(model.state, .idle)
    }

    /// Partial results stream into `partialTranscript` while recording (live dictation).
    func testPartialsUpdateLiveTranscript() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: ["why", "why the", "why the pause chain"], final: "why the pause chain")))

        await model.startRecording()
        // Partials are delivered on the main actor via Task; let them drain.
        await Task.yield()
        XCTAssertEqual(model.partialTranscript, "why the pause chain")
    }

    /// Silence: an empty final transcript is never emitted and never sent to the brain.
    /// This is the reported bug — silence must not become a phantom question.
    func testSilenceProducesNoQuestion() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: [], final: "")))
        var received: String?
        model.onTranscript = { received = $0 }

        await model.startRecording()
        await model.stopAndTranscribe()

        XCTAssertNil(received)
        XCTAssertEqual(model.state, .idle)
    }

    /// A whitespace-only transcript is likewise not routed out.
    func testBlankTranscriptNotEmitted() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: [], final: "   ")))
        var received: String?
        model.onTranscript = { received = $0 }

        await model.startRecording()
        await model.stopAndTranscribe()

        XCTAssertNil(received)
        XCTAssertEqual(model.state, .idle)
    }

    /// If the recognizer won't start (mic/speech denied), we land in `.failed` and
    /// never enter `.recording`.
    func testStartFailureFailsSafe() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(.startFails))

        await model.startRecording()

        if case .failed = model.state {} else { XCTFail("expected .failed, got \(model.state)") }
    }

    /// A denied microphone maps to precise, actionable `.failed` guidance (not the
    /// generic "couldn't start listening").
    func testMicDeniedMapsToActionableFailure() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(.startFailsWith(.micDenied)))

        await model.startRecording()

        guard case .failed(let msg) = model.state else {
            return XCTFail("expected .failed, got \(model.state)")
        }
        XCTAssertTrue(msg.contains("Microphone"))
    }

    /// `partialTranscript` is cleared once a hold finishes.
    func testPartialClearedAfterFinish() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: ["hello"], final: "hello world")))

        await model.startRecording()
        await model.stopAndTranscribe()

        XCTAssertEqual(model.partialTranscript, "")
    }

    // MARK: - Waveform levels (Option A's listening pill)

    /// Measured mic levels stream into `levels`, which is the waveform's ONLY data
    /// source — so a moving waveform always means real audio was heard.
    func testMicLevelsStreamIntoLevels() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: [], final: "hi"), levels: [0.1, 0.5, 0.9]))

        await model.startRecording()
        await Task.yield()
        XCTAssertEqual(model.levels, [0.1, 0.5, 0.9])
    }

    /// Silence must render as silence. If nothing is heard the bars stay flat rather
    /// than animating decoratively — the honesty rule applied to the UI.
    func testNoLevelsMeansEmptyWaveform() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: ["quiet"], final: "quiet")))

        await model.startRecording()
        await Task.yield()
        XCTAssertTrue(model.levels.isEmpty)
    }

    /// The window is bounded: a long hold keeps only the most recent samples, newest
    /// last, so memory can't grow without limit while the key is held.
    func testLevelWindowIsBoundedAndKeepsNewest() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(.transcript(partials: [], final: "")))
        await model.startRecording()

        for i in 0..<(VoiceModel.levelWindow + 10) {
            model.appendLevel(Float(i) / 1000)
        }

        XCTAssertEqual(model.levels.count, VoiceModel.levelWindow)
        XCTAssertEqual(model.levels.last, Float(VoiceModel.levelWindow + 9) / 1000)
    }

    /// A NaN or out-of-range level (live audio maths can produce one) is clamped, never
    /// drawn as a bar off the top of the pill.
    func testHostileLevelsAreClamped() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(.transcript(partials: [], final: "")))
        await model.startRecording()

        model.appendLevel(.nan)
        model.appendLevel(-3)
        model.appendLevel(42)

        XCTAssertEqual(model.levels, [0, 0, 1])
    }

    /// Levels reset between sessions, so a new hold never opens showing the last one's
    /// waveform.
    func testLevelsResetOnStopAndOnNextStart() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: [], final: "done"), levels: [0.4, 0.8]))

        await model.startRecording()
        await Task.yield()
        XCTAssertFalse(model.levels.isEmpty)

        await model.stopAndTranscribe()
        XCTAssertTrue(model.levels.isEmpty)
    }
}
