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
        .padding(20)
        .frame(width: 560, alignment: .leading)
        .background(Theme.card)
        .clipShape(RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).stroke(Theme.border, lineWidth: 1))
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
            TextField("Ask Icarus about the codebase…", text: $model.question)
                .textFieldStyle(.plain)
                .font(.system(size: 20, weight: .medium))
                .foregroundStyle(Theme.ink)
                .onSubmit { Task { await model.submit() } }

            voiceStatus()

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
                Text("Can't reach the brain. Is it running on 127.0.0.1:8000?")
                    .font(.system(size: 14)).foregroundStyle(Theme.muted)
            }
        }
    }

    /// Push-to-talk feedback. When idle, a quiet hint that you can hold ⌥ to speak;
    /// otherwise the live recording/transcribing/failed state.
    @ViewBuilder
    private func voiceStatus() -> some View {
        switch voice.state {
        case .idle:
            Text("Hold Right Option (⌥) to speak")
                .font(Theme.mono(11)).foregroundStyle(Theme.muted)
        case .recording:
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    Circle().fill(Theme.unknown).frame(width: 9, height: 9)
                    Text("Listening…").font(Theme.mono(12)).foregroundStyle(Theme.ink)
                }
                // Live transcript as you speak (like macOS dictation).
                if !voice.partialTranscript.isEmpty {
                    Text(voice.partialTranscript)
                        .font(.system(size: 16)).foregroundStyle(Theme.muted)
                }
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
            Rectangle().fill(Theme.border).frame(height: 1)
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
