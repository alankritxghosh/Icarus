import SwiftUI
import IcarusKit

/// The overlay's content. Gated on GitHub auth: connect → (G4: pick a repo) → ask.
/// Renders the brain's verdict verbatim — it never decides grounding itself; the
/// cite-or-unknown gate lives in the Python brain. Styling is plain here; the
/// Honest-Brutalism polish lands in a later brick.
struct OverlayView: View {
    @Bindable var auth: AuthModel
    @Bindable var model: AskModel

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            switch auth.state {
            case .signedOut:
                connect(message: nil)
            case .error(let message):
                connect(message: message)
            case .requesting:
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Contacting GitHub…").foregroundStyle(.secondary)
                }
            case .awaitingApproval(let code, let uri):
                awaitingApproval(code: code, uri: uri)
            case .signedIn:
                signedIn()
            }
        }
        .padding(20)
        .frame(width: 560, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Auth states

    @ViewBuilder
    private func connect(message: String?) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Connect Icarus to GitHub").font(.title3).fontWeight(.semibold)
            Text("Sign in to load a public repository and ask about it.")
                .font(.callout).foregroundStyle(.secondary)
            if let message {
                Text(message).font(.callout).foregroundStyle(.orange)
            }
            if !auth.isConfigured {
                Text("Set ICARUS_GH_CLIENT_ID to your OAuth App Client ID, then relaunch.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Button("Connect GitHub") { auth.connect() }
                .keyboardShortcut(.defaultAction)
        }
    }

    @ViewBuilder
    private func awaitingApproval(code: String, uri: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Enter this code on GitHub").font(.title3).fontWeight(.semibold)
            Text(code)
                .font(.system(.largeTitle, design: .monospaced)).fontWeight(.bold)
                .textSelection(.enabled)
            Text("Your browser opened to GitHub and the code is on your clipboard. Waiting for approval…")
                .font(.callout).foregroundStyle(.secondary)
            HStack {
                if let url = URL(string: uri) {
                    Link("Reopen GitHub", destination: url)
                }
                Button("Cancel") { auth.signOut() }
            }
        }
    }

    @ViewBuilder
    private func signedIn() -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Label("Signed in to GitHub", systemImage: "checkmark.seal.fill")
                    .font(.caption).foregroundStyle(.secondary)
                Spacer()
                Button("Sign out") { auth.signOut() }.font(.caption).buttonStyle(.plain)
            }
            // NOTE: repo selection/connection gating arrives in G4. For now the ask
            // box is shown directly once signed in.
            askBox()
        }
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
