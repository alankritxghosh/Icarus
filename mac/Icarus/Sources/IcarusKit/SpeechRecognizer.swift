import Foundation

/// Streaming speech-to-text (on-device when the Mac has the local model, else
/// Apple's cloud service). The real implementation (in the app target)
/// wraps Apple's `SFSpeechRecognizer`; tests use `StubSpeechRecognizer`. Behind a
/// protocol so `VoiceModel` is testable without the Speech framework or a microphone —
/// the same seam pattern as `TokenStore`.
///
/// It streams: partial transcripts arrive live via `onPartial` while the user speaks,
/// and `finish()` returns the final transcript once the hold ends. A silent hold
/// yields an empty final transcript (nothing to ask) — no fabricated text.
public protocol SpeechRecognizer: Sendable {
    /// Begin a streaming session. `onPartial` fires with the running transcript as
    /// speech is recognized; `onLevel` fires with the REAL microphone loudness of each
    /// audio buffer, normalized 0...1, which drives the listening waveform.
    ///
    /// `onLevel` exists so the waveform can never be a decorative animation loop: if the
    /// mic is silent the bars are flat, because the value is measured from the same audio
    /// buffers the recognizer consumes. A moving waveform is evidence of real input.
    /// Throws if the mic/recognizer is unavailable or denied.
    func start(onPartial: @escaping @Sendable (String) -> Void,
               onLevel: @escaping @Sendable (Float) -> Void) async throws
    /// End the session and return the final transcript (empty if nothing was heard).
    func finish() async -> String
}

/// Why a streaming session couldn't start — a *typed* reason so the UI can guide the
/// user precisely instead of a generic "couldn't start." Lives in IcarusKit (not the
/// app target) so `VoiceModel` can map each case to its own copy without importing the
/// Speech framework.
///
/// Note: a MISSING on-device speech model is deliberately NOT one of these. macOS has
/// no API to install it from code (Apple DevForums 703770), so rather than dead-end a
/// fresh Mac, `AppleSpeechRecognizer` falls back to Apple's speech service — voice stays
/// zero-setup. These cases are the genuine can't-start conditions worth guiding on.
public enum SpeechStartError: Error, Equatable, Sendable {
    case notAuthorized // speech-recognition permission denied
    case micDenied     // microphone permission denied
    case unavailable   // recognizer not available right now
}

/// In-memory double for tests ONLY. Optionally emits scripted partials on start, then
/// returns `final` from finish; `startFails` makes start throw.
public final class StubSpeechRecognizer: SpeechRecognizer, @unchecked Sendable {
    public enum Behavior: Sendable {
        case transcript(partials: [String], final: String)
        case startFails
        case startFailsWith(SpeechStartError)
    }

    private let behavior: Behavior
    /// Scripted mic levels emitted on start, so the waveform is testable without a mic.
    private let levels: [Float]

    public init(_ behavior: Behavior, levels: [Float] = []) {
        self.behavior = behavior
        self.levels = levels
    }

    public func start(onPartial: @escaping @Sendable (String) -> Void,
                      onLevel: @escaping @Sendable (Float) -> Void) async throws {
        switch behavior {
        case .startFails:
            throw NSError(domain: "StubSpeechRecognizer", code: 1)
        case .startFailsWith(let reason):
            throw reason
        case .transcript(let partials, _):
            for p in partials { onPartial(p) }
            for l in levels { onLevel(l) }
        }
    }

    public func finish() async -> String {
        if case .transcript(_, let final) = behavior { return final }
        return ""
    }
}
