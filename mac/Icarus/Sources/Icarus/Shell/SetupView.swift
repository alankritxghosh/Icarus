import SwiftUI
import IcarusKit

/// The in-shell setup gate, shown on Home until a repo is connected: sign in with
/// GitHub, then connect a public repo. Replaces the old separate onboarding window
/// (folded into the shell). Drives the same shared `AuthModel` / `ConnectModel`.
struct SetupView: View {
    @Bindable var auth: AuthModel
    @Bindable var connect: ConnectModel

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle("Welcome to Icarus",
                         "Sign in with GitHub, connect a public repo, and start asking why.")
            ShellCard { content }.frame(maxWidth: 620)
        }
    }

    @ViewBuilder private var content: some View {
        switch auth.state {
        case .signedOut:
            signIn(message: nil)
        case .error(let message):
            signIn(message: message)
        case .requesting:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Waiting for GitHub…").font(.system(size: 14)).foregroundStyle(Theme.muted)
            }
        case .signedIn:
            connectRepo()
        }
    }

    @ViewBuilder private func signIn(message: String?) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            MonoLabel("STEP 1 — CONNECT GITHUB")
            Text("Sign in with GitHub to load a public repository. Your code is never trained on.")
                .font(.system(size: 14)).foregroundStyle(Theme.muted)
            if let message {
                Text(message).font(.system(size: 13)).foregroundStyle(Theme.unknown)
            }
            if !auth.isConfigured {
                Text("Developer setup: set ICARUS_GH_CLIENT_ID to your OAuth App Client ID, then relaunch.")
                    .font(Theme.mono(11)).foregroundStyle(Theme.muted)
            }
            Button("Sign in with GitHub") { auth.connect() }
                .buttonStyle(PrimaryButton())
                .keyboardShortcut(.defaultAction)
        }
    }

    @ViewBuilder private func connectRepo() -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Label("Signed in to GitHub", systemImage: "checkmark.seal.fill")
                .font(.system(size: 14, weight: .medium)).foregroundStyle(Theme.cited)

            MonoLabel("STEP 2 — CONNECT A PUBLIC REPOSITORY")
            HStack(spacing: 8) {
                TextField("owner/repo  (e.g. simonw/llm)", text: $connect.repoInput)
                    .textFieldStyle(.plain)
                    .font(Theme.mono(13))
                    .foregroundStyle(Theme.ink)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Theme.card)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border, lineWidth: 1))
                    .onSubmit { connect.connect() }
                Button("Connect") { connect.connect() }.buttonStyle(PrimaryButton())
            }

            switch connect.state {
            case .idle:
                Text("Public repositories only. The first index of a new repo can take a minute.")
                    .font(.system(size: 13)).foregroundStyle(Theme.muted)
            case .connecting(let repo):
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Indexing \(repo)…").font(.system(size: 14)).foregroundStyle(Theme.muted)
                }
            case .ready(let repo):
                Text("✓ Loaded \(repo).").font(.system(size: 14, weight: .medium)).foregroundStyle(Theme.cited)
            case .failed(let message):
                Text(message).font(.system(size: 14)).foregroundStyle(Theme.unknown)
            }

            Button("Sign out") { auth.signOut() }.buttonStyle(.plain).foregroundStyle(Theme.muted)
        }
    }
}
