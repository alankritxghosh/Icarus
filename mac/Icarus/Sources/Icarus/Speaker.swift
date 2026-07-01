import AVFoundation

/// Reads text aloud with the system speech synthesizer — no dependency, no
/// permission. It speaks the brain's answer, and equally speaks the honest unknown,
/// so the cite-or-unknown promise carries into voice. It never decides anything; it
/// only voices whatever the brain already returned.
@MainActor
final class Speaker {
    private let synth = AVSpeechSynthesizer()

    /// Speak `text`, interrupting anything currently being spoken (barge-in).
    func speak(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        stop()
        synth.speak(AVSpeechUtterance(string: trimmed))
    }

    /// Stop mid-sentence, cleanly.
    func stop() {
        if synth.isSpeaking { synth.stopSpeaking(at: .immediate) }
    }
}
