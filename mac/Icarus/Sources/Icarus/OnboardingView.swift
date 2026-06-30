import SwiftUI
import IcarusKit

/// The app's first screen, shown in a real window: Welcome → Sign in with GitHub
/// → (signed in). GitHub is the login — there is no separate Icarus account.
/// Repo selection (G4) will slot in below the signed-in state.
struct OnboardingView: View {
    @Bindable var auth: AuthModel
    @Bindable var connect: ConnectModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            Divider()
            content
            Spacer(minLength: 0)
        }
        .padding(28)
        .frame(width: 520, height: 440, alignment: .topLeading)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Icarus").font(.largeTitle).fontWeight(.bold)
            Text("Ask your codebase anything — and get an honest answer, with citations.")
                .font(.callout).foregroundStyle(.secondary)
        }
    }

    @ViewBuilder
    private var content: some View {
        switch auth.state {
        case .signedOut:
            signIn(message: nil)
        case .error(let message):
            signIn(message: message)
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

    @ViewBuilder
    private func signIn(message: String?) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Step 1 — Connect GitHub").font(.headline)
            Text("Sign in with GitHub to load a public repository. Your code is never trained on.")
                .font(.callout).foregroundStyle(.secondary)
            if let message {
                Text(message).font(.callout).foregroundStyle(.orange)
            }
            if !auth.isConfigured {
                Text("Developer setup: set ICARUS_GH_CLIENT_ID to your OAuth App Client ID, then relaunch.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Button {
                auth.connect()
            } label: {
                Label("Sign in with GitHub", systemImage: "arrow.right.circle.fill")
            }
            .controlSize(.large)
            .keyboardShortcut(.defaultAction)
        }
    }

    @ViewBuilder
    private func awaitingApproval(code: String, uri: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Step 2 — Enter this code on GitHub").font(.headline)
            Text(code)
                .font(.system(size: 40, weight: .bold, design: .monospaced))
                .textSelection(.enabled)
            Text("Your browser opened to GitHub and the code is on your clipboard. Paste it there to authorize — this window updates automatically.")
                .font(.callout).foregroundStyle(.secondary)
            HStack(spacing: 12) {
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
            Label("Signed in to GitHub", systemImage: "checkmark.seal.fill")
                .font(.callout).foregroundStyle(.green)

            Text("Step 2 — Connect a public repository").font(.headline)
            HStack(spacing: 8) {
                TextField("owner/repo  (e.g. simonw/llm)", text: $connect.repoInput)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit { connect.connect() }
                Button("Connect") { connect.connect() }
            }

            switch connect.state {
            case .idle:
                Text("Public repositories only. The first index of a new repo can take a minute.")
                    .font(.caption).foregroundStyle(.secondary)
            case .connecting(let repo):
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Indexing \(repo)…").foregroundStyle(.secondary)
                }
            case .ready(let repo):
                Text("✓ Loaded \(repo). Press ⌘⇧I anywhere to ask Icarus about it.")
                    .font(.callout).foregroundStyle(.green)
            case .failed(let message):
                Text(message).font(.callout).foregroundStyle(.orange)
            }

            Spacer(minLength: 0)
            Button("Sign out") { auth.signOut() }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
        }
    }
}
