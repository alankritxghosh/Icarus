import SwiftUI
import IcarusKit

/// The hotkey overlay's content: the ask box + the brain's reply, styled to the
/// Honest-Brutalism "Quiet Native Memory v2" language. Renders the brain's verdict
/// verbatim — it never decides grounding itself; the cite-or-unknown gate lives in
/// the Python brain. Cited answers use green receipt pills; the honest unknown is an
/// amber signature card.
struct OverlayView: View {
    @Bindable var auth: AuthModel
    @Bindable var connect: ConnectModel
    @Bindable var model: AskModel
    @Bindable var voice: VoiceModel

    /// Option A's two shapes. Collapsed = a pill (asking, or listening); expanded = the
    /// flat answer card it grows upward into. Derived from state rather than stored, so
    /// the shape can never disagree with what's actually on screen.
    ///
    /// Listening is deliberately COLLAPSED even though a lot is happening: the waveform
    /// row is the pill's content, which is exactly the mockup's "while listening" state.
    private var isExpanded: Bool {
        if voice.isRecording { return false }
        if !auth.isSignedIn || !connect.isReady { return true }
        if case .idle = model.state { return false }
        return true
    }

    private var cornerRadius: CGFloat { isExpanded ? 20 : 30 }

    /// One spring drives every part of the morph (shape, padding, content) so the pill
    /// expands as a single object instead of several elements animating out of step.
    private var morph: Animation { .spring(response: 0.34, dampingFraction: 0.85) }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if !auth.isSignedIn {
                setupHint("Open the Icarus window and sign in with GitHub, then press ⌘⇧I here to ask.")
            } else if !connect.isReady {
                setupHint("Connect a repository in the Icarus window first, then press ⌘⇧I here to ask.")
            } else {
                askBox()
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, isExpanded ? 20 : 14)
        .frame(width: 560, alignment: .leading)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .stroke(Theme.border, lineWidth: 1))
        .animation(morph, value: isExpanded)
        .animation(morph, value: voice.isRecording)
    }

    @ViewBuilder
    private func setupHint(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoLabel("FINISH SETUP")
            Text(message).font(.system(size: 15)).foregroundStyle(Theme.muted)
        }
    }

    @ViewBuilder
    private func askBox() -> some View {
        VStack(alignment: .leading, spacing: 14) {
            // While listening, the waveform row IS the whole pill — the text field would
            // only compete with it, and the words are already shown live in the row.
            if !voice.isRecording {
                TextField("Ask Icarus about the codebase…", text: $model.question)
                    .textFieldStyle(.plain)
                    .font(.system(size: 20, weight: .medium))
                    .foregroundStyle(Theme.ink)
                    .onSubmit { Task { await model.submit() } }
            }

            voiceStatus()

            // Grows upward out of the pill: the panel is pinned to its bottom edge
            // (FloatingPanel.pinToBottomCenter), so a bottom-edge move transition reads
            // as the answer rising out of the pill rather than dropping onto it.
            resultSection()
                .transition(.move(edge: .bottom).combined(with: .opacity))
        }
    }

    @ViewBuilder
    private func resultSection() -> some View {
        switch model.state {
        case .idle:
            EmptyView()
        case .loading:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Searching the codebase…").font(Theme.mono(12)).foregroundStyle(Theme.muted)
            }
        case .response(let r) where r.verdict == .answer:
            answer(r)
        case .response(let r):
            honestUnknown(r)
        case .unreachable:
            Text("Can't reach Icarus's brain — check your internet connection.")
                .font(.system(size: 14)).foregroundStyle(Theme.muted)
        }
    }

    /// Push-to-talk feedback. When idle, a quiet hint that you can hold ⌥ to speak;
    /// otherwise the live recording/transcribing/failed state.
    @ViewBuilder
    private func voiceStatus() -> some View {
        switch voice.state {
        case .idle:
            // Only while collapsed: in the expanded answer card the hint is noise
            // between the question and the answer, and the mockup doesn't carry it.
            if !isExpanded {
                Text("Hold Right Option (⌥) to speak")
                    .font(Theme.mono(11)).foregroundStyle(Theme.muted)
            }
        case .recording:
            // Option A's listening row: live level, then the words it's hearing.
            HStack(spacing: 10) {
                Circle().fill(Theme.unknown).frame(width: 9, height: 9)
                WaveformView(levels: voice.levels)
                // Truncate the HEAD, not the tail: dictation grows at the end, so the
                // most recent words are the ones worth keeping on screen.
                Text(voice.partialTranscript.isEmpty ? "Listening…" : voice.partialTranscript)
                    .font(.system(size: 15))
                    .foregroundStyle(voice.partialTranscript.isEmpty ? Theme.muted : Theme.ink)
                    .lineLimit(1)
                    .truncationMode(.head)
            }
        case .transcribing:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Finishing…").font(Theme.mono(12)).foregroundStyle(Theme.muted)
            }
        case .failed(let message):
            Text(message).font(Theme.mono(12)).foregroundStyle(Theme.muted)
        }
    }

    @ViewBuilder
    private func answer(_ r: AskResponse) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            MonoLabel("THE ANSWER")
            Text(r.answer)
                .font(.system(size: 17, weight: .medium))
                .foregroundStyle(Theme.ink)
                .textSelection(.enabled)
            if !r.citations.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    MonoLabel("RECEIPTS", Theme.cited)
                    FlowLayout(spacing: 8) {
                        ForEach(r.citations) { CitationChip(citation: $0) }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func honestUnknown(_ r: AskResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            MonoLabel("HONEST UNKNOWN", Theme.unknown)
            Text("No one wrote this down.")
                .font(.system(size: 21, weight: .bold))
                .foregroundStyle(Theme.ink)
            if !r.searched.isEmpty {
                Text("searched: " + r.searched.joined(separator: ", "))
                    .font(Theme.mono(11)).foregroundStyle(Theme.muted)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.unknownBg)
        .clipShape(RoundedRectangle(cornerRadius: 14))
        .overlay(RoundedRectangle(cornerRadius: 14).stroke(Theme.unknown, lineWidth: 1))
    }
}
