import SwiftUI
import IcarusKit

/// The hotkey overlay's content: the ask box + the brain's reply. Auth/onboarding
/// live in the separate onboarding window, so the overlay only asks. It renders the
/// brain's verdict verbatim — it never decides grounding itself; the cite-or-unknown
/// gate lives in the Python brain. Honest-Brutalism polish lands in a later brick.
struct OverlayView: View {
    @Bindable var auth: AuthModel
    @Bindable var model: AskModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if auth.isSignedIn {
                askBox()
            } else {
                VStack(alignment: .leading, spacing: 6) {
                    Text("Finish setup first").font(.headline)
                    Text("Open the Icarus window, connect GitHub, then press ⌘⇧I here to ask.")
                        .font(.callout).foregroundStyle(.secondary)
                }
            }
        }
        .padding(20)
        .frame(width: 560, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Ask + answer states

    @ViewBuilder
    private func askBox() -> some View {
        VStack(alignment: .leading, spacing: 14) {
            TextField("Ask Icarus about the codebase…", text: $model.question)
                .textFieldStyle(.plain)
                .font(.title3)
                .onSubmit { Task { await model.submit() } }

            switch model.state {
            case .idle:
                EmptyView()
            case .loading:
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Searching the codebase…").foregroundStyle(.secondary)
                }
            case .response(let r) where r.verdict == .answer:
                answer(r)
            case .response(let r):
                honestUnknown(r)
            case .unreachable:
                Text("Can't reach the brain. Is it running on 127.0.0.1:8000?")
                    .foregroundStyle(.secondary)
            }
        }
    }

    @ViewBuilder
    private func answer(_ r: AskResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider()
            Text(r.answer).font(.body).textSelection(.enabled)
            if !r.citations.isEmpty {
                HStack(spacing: 8) {
                    ForEach(r.citations) { chip($0) }
                }
            }
        }
    }

    @ViewBuilder
    private func chip(_ citation: Citation) -> some View {
        let label = Text(citation.ref).font(.system(.caption, design: .monospaced))
        if let urlString = citation.url, let url = URL(string: urlString) {
            Link(destination: url) { label }
        } else {
            label.foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private func honestUnknown(_ r: AskResponse) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider()
            Text("No one wrote this down.").font(.title2).fontWeight(.semibold)
            if !r.searched.isEmpty {
                Text("Looked at: " + r.searched.joined(separator: ", "))
                    .font(.system(.caption, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
        }
    }
}
