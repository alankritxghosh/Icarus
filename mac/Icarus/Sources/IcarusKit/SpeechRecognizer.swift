import Foundation

/// Streaming, on-device speech-to-text. The real implementation (in the app target)
/// wraps Apple's `SFSpeechRecognizer`; tests use `StubSpeechRecognizer`. Behind a
/// protocol so `VoiceModel` is testable without the Speech framework or a microphone —
/// the same seam pattern as `TokenStore`.
///
/// It streams: partial transcripts arrive live via `onPartial` while the user speaks,
/// and `finish()` returns the final transcript once the hold ends. A silent hold
/// yields an empty final transcript (nothing to ask) — no fabricated text.
public protocol SpeechRecognizer: Sendable {
    /// Begin a streaming session. `onPartial` fires with the running transcript as
    /// speech is recognized. Throws if the mic/recognizer is unavailable or denied.
    func start(onPartial: @escaping @Sendable (String) -> Void) async throws
    /// End the session and return the final transcript (empty if nothing was heard).
    func finish() async -> String
}

/// In-memory double for tests ONLY. Optionally emits scripted partials on start, then
/// returns `final` from finish; `startFails` makes start throw.
public final class StubSpeechRecognizer: SpeechRecognizer, @unchecked Sendable {
    public enum Behavior: Sendable {
        case transcript(partials: [String], final: String)
        case startFails
    }

    private let behavior: Behavior

    public init(_ behavior: Behavior) { self.behavior = behavior }

    public func start(onPartial: @escaping @Sendable (String) -> Void) async throws {
        switch behavior {
        case .startFails:
            throw NSError(domain: "StubSpeechRecognizer", code: 1)
        case .transcript(let partials, _):
            for p in partials { onPartial(p) }
        }
    }

    public func finish() async -> String {
        if case .transcript(_, let final) = behavior { return final }
        return ""
    }
}
