import AppKit
import SwiftUI
import IcarusKit

/// Owns the floating overlay panel and its show/hide logic, so `AppDelegate`
/// stays a thin wiring layer. Main-actor isolated because it touches AppKit.
@MainActor
final class OverlayController {
    private var panel: FloatingPanel<OverlayView>?
    /// Ask state lives here (not in the view) so it survives hide/re-show. Auth is
    /// shared with the onboarding window, so it's injected by the app delegate.
    private let auth: AuthModel
    private let connect: ConnectModel
    private let model: AskModel
    /// Voice state (push-to-talk). Injected so the app delegate can pre-warm the
    /// transcriber. Its transcript feeds the same ask path a typed question uses.
    private let voice: VoiceModel
    private let latency: VoiceLatencyTracker
    /// Speaks the brain's reply aloud (voice-out). The promise carries into voice:
    /// it reads the honest unknown just as it reads a cited answer.
    private let speaker = Speaker()

    init(auth: AuthModel, connect: ConnectModel, voice: VoiceModel,
         latency: VoiceLatencyTracker,
         tokenReader: @escaping @Sendable () -> String? = { nil },
         history: AskHistory? = nil) {
        self.auth = auth
        self.connect = connect
        self.voice = voice
        self.latency = latency
        self.model = AskModel(client: BrainClient(base: AppConfig.brainBaseURL, token: tokenReader))
        self.model.history = history   // asks flow into the shared shell history
        // Speech becomes the exact same question a user would type, then submits.
        self.voice.onTranscript = { [weak self] text in
            guard let self else { return }
            self.latency.transcriptReady()
            self.model.question = text
            Task { await self.model.submit() }
        }
        // Speak whatever the brain returned — verbatim answer, or the honest unknown.
        self.model.onResult = { [weak self] state in
            guard let self else { return }
            if case .response = state {
                self.latency.answerReady()
                self.speak(for: state)
            } else {
                self.latency.cancel()
            }
        }
        self.speaker.onFirstWordStarted = { [weak self] in
            self?.latency.firstWordStarted()
        }
    }

    private func speak(for state: AskModel.State) {
        guard case .response(let r) = state else { return }
        if r.verdict == .answer {
            // Speak the HEADLINE, not the whole answer: the overlay carries the full
            // text and the quoted proof, so reciting all of it talks over the reading.
            // A strict subset of the grounded answer -- never a re-generated summary.
            speaker.speak(SpokenSummary.summarize(r.answer))
        } else {
            speaker.speak("I couldn’t find where anyone wrote this down.")
        }
    }

    /// Show the overlay if hidden, hide it if visible. Either way, barge-in: stop any
    /// answer currently being spoken.
    func toggle() {
        speaker.stop()
        if let panel, panel.isVisible {
            panel.orderOut(nil)
            return
        }
        present()
    }

    /// Push-to-talk down: bring the overlay up (so "Listening…" is visible) and start
    /// recording — but only once setup is done, else just show the setup hint. Barge-in
    /// stops any speech first, so you can interrupt an answer by starting to talk.
    func beginVoice() {
        speaker.stop()
        present()
        guard auth.isSignedIn, connect.isReady else { return }
        latency.begin()
        Task { await voice.startRecording() }
    }

    /// Push-to-talk up: stop + transcribe (transcript flows via `onTranscript`).
    func endVoice() {
        latency.released()
        Task { await voice.stopAndTranscribe() }
    }

    /// Show + take key focus without activating the app (a non-activating panel must
    /// not steal focus). Shows if hidden; no-op re-show keeps the dragged position.
    private func present() {
        let panel: FloatingPanel<OverlayView>
        if let existing = self.panel {
            panel = existing
        } else {
            panel = FloatingPanel {
                OverlayView(auth: self.auth, connect: self.connect, model: self.model, voice: self.voice)
            }
            self.panel = panel
            panel.pinToBottomCenter()
        }
        panel.makeKeyAndOrderFront(nil)
    }
}
