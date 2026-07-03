import AVFoundation

/// Reads text aloud with the system speech synthesizer — no dependency, no
/// permission. It speaks the brain's answer, and equally speaks the honest unknown,
/// so the cite-or-unknown promise carries into voice. It never decides anything; it
/// only voices whatever the brain already returned.
///
/// Voice: picks the best-quality English voice installed (premium > enhanced >
/// default), preferring en-US. Download a "Premium" voice in System Settings →
/// Accessibility → Spoken Content → Manage Voices and it's used automatically. If
/// none is downloaded it falls back to the standard en-US voice — never a novelty
/// voice (Zarvox, Bells, …).
@MainActor
final class Speaker {
    private let synth = AVSpeechSynthesizer()
    private lazy var voice: AVSpeechSynthesisVoice? = Self.bestEnglishVoice()

    /// Speak `text`, interrupting anything currently being spoken (barge-in).
    func speak(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        stop()
        let utterance = AVSpeechUtterance(string: trimmed)
        if let voice { utterance.voice = voice }
        synth.speak(utterance)
    }

    /// Stop mid-sentence, cleanly.
    func stop() {
        if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
    }

    /// Best premium/enhanced English voice (prefer en-US); else the standard en-US
    /// default so we never land on a novelty voice.
    private static func bestEnglishVoice() -> AVSpeechSynthesisVoice? {
        let good = AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.hasPrefix("en") && $0.quality != .default }
        if let best = good.max(by: { rank($0) < rank($1) }) {
            return best
        }
        return AVSpeechSynthesisVoice(language: "en-US")
    }

    private static func rank(_ v: AVSpeechSynthesisVoice) -> Int {
        v.quality.rawValue * 10 + (v.language == "en-US" ? 1 : 0)
    }
}
