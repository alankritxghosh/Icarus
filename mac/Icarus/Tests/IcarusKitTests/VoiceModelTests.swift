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

    /// `partialTranscript` is cleared once a hold finishes.
    func testPartialClearedAfterFinish() async {
        let model = VoiceModel(recognizer: StubSpeechRecognizer(
            .transcript(partials: ["hello"], final: "hello world")))

        await model.startRecording()
        await model.stopAndTranscribe()

        XCTAssertEqual(model.partialTranscript, "")
    }
}
