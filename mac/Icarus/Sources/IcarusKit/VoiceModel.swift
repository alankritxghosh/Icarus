import Foundation
import Observation

/// Orchestrates push-to-talk with a *streaming* recognizer: while the key is held the
/// transcript builds up live (`partialTranscript`); on release the final transcript is
/// routed out. It never decides anything about the answer — it only turns speech into
/// the same question text a user would type, then hands it off via `onTranscript`.
///
/// Silence is handled for free: a silent hold yields an empty final transcript, which
/// is not emitted — so nothing is ever fabricated or sent to the brain. Main-actor
/// isolated because it drives UI state (like `AskModel`).
@MainActor
@Observable
public final class VoiceModel {
    public enum State: Equatable, Sendable {
        case idle
        case recording
        case transcribing   // brief: after release, awaiting the final transcript
        case failed(String)
    }

    public private(set) var state: State = .idle
    /// The running transcript shown live while recording (like macOS dictation).
    public private(set) var partialTranscript: String = ""

    /// Called with the final, non-empty transcript when a hold ends. The app wires
    /// this to the ask path (set the question, submit to the brain).
    public var onTranscript: ((String) -> Void)?

    private let recognizer: SpeechRecognizer

    public init(recognizer: SpeechRecognizer) {
        self.recognizer = recognizer
    }

    public var isRecording: Bool { state == .recording }

    /// Push-to-talk down: start streaming recognition. No-op unless idle or recovering
    /// from a prior failure.
    public func startRecording() async {
        switch state {
        case .idle, .failed:
            break
        case .recording, .transcribing:
            return
        }
        partialTranscript = ""
        do {
            try await recognizer.start(onPartial: { [weak self] text in
                // Capture self weakly in the Task too (not the outer closure's
                // captured var) -- Swift 5.10 strict-concurrency flags the nested
                // reference otherwise; harmless and clearer under 6.0 as well.
                Task { @MainActor [weak self] in self?.partialTranscript = text }
            })
            state = .recording
        } catch let reason as SpeechStartError {
            // Typed reasons get precise, actionable guidance. (A missing on-device model
            // never reaches here — it falls back to the cloud recognizer, zero-setup.)
            switch reason {
            case .micDenied:
                state = .failed("Microphone access is off. Turn it on in System Settings "
                    + "→ Privacy & Security → Microphone, then hold ⌥ to speak.")
            case .notAuthorized:
                state = .failed("Speech recognition access is off. Turn it on in System "
                    + "Settings → Privacy & Security → Speech Recognition.")
            case .unavailable:
                state = .failed("Speech recognition isn’t available on this Mac right now.")
            }
        } catch {
            state = .failed("Couldn’t start listening.")
        }
    }

    /// Push-to-talk up: finalize the transcript and route it out. Empty/blank (a silent
    /// hold) returns quietly to idle — never transcribed into a phantom question.
    public func stopAndTranscribe() async {
        guard state == .recording else { return }
        state = .transcribing
        let text = await recognizer.finish()
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        state = .idle
        partialTranscript = ""
        if !trimmed.isEmpty { onTranscript?(trimmed) }
    }
}
