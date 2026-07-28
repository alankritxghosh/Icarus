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

    /// Deliberately a short opacity/shape animation, NOT a spring on the layout.
    ///
    /// The panel sizes itself from its content (`FloatingPanel`'s
    /// `sizingOptions = .preferredContentSize`), so animating anything that changes
    /// HEIGHT makes AppKit resize the window on every frame of the animation — and each
    /// resize re-runs the bottom-pin and recomputes the vibrancy blur behind it. That is
    /// what made the morph lag. Now the window resizes ONCE and the content fades in over
    /// it, which reads as the same gesture and costs a fraction as much.
    private var morph: Animation { .easeOut(duration: 0.18) }

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
        // Constant, not isExpanded-dependent: animating padding animates HEIGHT, which
        // resizes the window every frame (see `morph`).
        .padding(.vertical, 16)
        // 430pt, not 560: "cannot occupy much of the screen" is a stated constraint, and
        // the narrower measure also keeps the answer near a readable line length.
        .frame(width: 430, alignment: .leading)
        // Glass, not a flat card: real behind-window vibrancy, then a translucent wash of
        // the card colour over it. The wash is not decoration — raw vibrancy alone lets
        // whatever is behind the panel show through hard enough to hurt legibility, and an
        // answer you can't read is a failure regardless of how good the blur looks.
        .background {
            ZStack {
                VisualEffectBackground()
                Theme.card.opacity(0.62)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
            .stroke(Theme.border.opacity(0.8), lineWidth: 1))
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

            // Opacity only, no `.move`. A move transition animates the section's height,
            // which drags the window through a resize on every frame; a fade lets the
            // panel take its new size once and the content appear over it. The upward
            // growth still reads, because the panel is pinned to its bottom edge.
            resultSection()
                .transition(.opacity)
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

    /// Direction 03 "Receipt": the spoken headline, then the PROOF ITSELF quoted from the
    /// source — not a pointer to it. A pointer still makes you leave the overlay to check
    /// anything, which is the wrong default for a product whose claim is that it never
    /// asks to be taken on faith.
    @ViewBuilder
    private func answer(_ r: AskResponse) -> some View {
        VStack(alignment: .leading, spacing: 11) {
            Text(r.answer)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Theme.ink)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)

            ForEach(r.citations) { citation in
                evidence(citation)
            }
        }
    }

    /// One piece of quoted evidence: the excerpt behind a green rule, with its ref
    /// beneath as the link. When the brain is older than the excerpt field, this
    /// degrades to the ref alone rather than showing an empty quote block.
    @ViewBuilder
    private func evidence(_ citation: Citation) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            if let excerpt = citation.excerpt, !excerpt.isEmpty {
                HStack(alignment: .top, spacing: 8) {
                    Rectangle().fill(Theme.cited).frame(width: 2)
                    Text(excerpt)
                        .font(Theme.mono(10.5))
                        .foregroundStyle(Theme.ink.opacity(0.78))
                        .textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            CitationChip(citation: citation)
        }
    }

    @ViewBuilder
    private func honestUnknown(_ r: AskResponse) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            // While the index is still building, an abstention is "I haven't
            // finished reading", NOT "no one wrote this down" — so it must not
            // wear the honest-unknown hero, which is a claim about the repo.
            if let note = r.incompleteIndexNote {
                MonoLabel("STILL INDEXING", Theme.unknown)
                Text("I haven't finished reading this repo.")
                    .font(.system(size: 21, weight: .bold))
                    .foregroundStyle(Theme.ink)
                Text(note)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.muted)
            } else {
                MonoLabel("HONEST UNKNOWN", Theme.unknown)
                Text("No one wrote this down.")
                    .font(.system(size: 21, weight: .bold))
                    .foregroundStyle(Theme.ink)
            }
            // The evidence trail, in two parts. A single flat list made a
            // refusal that HAD looked up the named ref first read as one that
            // ignored the question entirely — the mechanism was right and the
            // display made it look broken (reported live 2026-07-28).
            if let named = r.anchoredLine {
                Text(named)
                    .font(Theme.mono(11)).foregroundStyle(Theme.ink.opacity(0.75))
            }
            if !r.searched.isEmpty {
                Text(r.searchedLine)
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
