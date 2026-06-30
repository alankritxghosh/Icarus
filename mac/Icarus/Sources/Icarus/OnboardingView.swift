import SwiftUI
import IcarusKit

/// The app's first screen, in a real window, styled to "Quiet Native Memory v2":
/// Welcome → Sign in with GitHub → connect a public repo. GitHub is the login —
/// there is no separate Icarus account.
struct OnboardingView: View {
    @Bindable var auth: AuthModel
    @Bindable var connect: ConnectModel

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            header
            Rectangle().fill(Theme.border).frame(height: 1)
            content
            Spacer(minLength: 0)
        }
        .padding(28)
        .frame(width: 520, height: 460, alignment: .topLeading)
        .background(Theme.surface)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Icarus").font(.system(size: 34, weight: .bold)).foregroundStyle(Theme.ink)
            Text("Ask your codebase anything — and get an honest answer, with citations.")
                .font(.system(size: 15)).foregroundStyle(Theme.muted)
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
                Text("Contacting GitHub…").font(.system(size: 15)).foregroundStyle(Theme.muted)
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
            MonoLabel("STEP 1 — CONNECT GITHUB")
            Text("Sign in with GitHub to load a public repository. Your code is never trained on.")
                .font(.system(size: 15)).foregroundStyle(Theme.muted)
            if let message {
                Text(message).font(.system(size: 14)).foregroundStyle(Theme.unknown)
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

    @ViewBuilder
    private func awaitingApproval(code: String, uri: String) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            MonoLabel("STEP 2 — ENTER THIS CODE ON GITHUB")
            Text(code)
                .font(Theme.mono(40, .bold))
                .foregroundStyle(Theme.ink)
                .textSelection(.enabled)
            Text("Your browser opened to GitHub and the code is on your clipboard. Paste it there to authorize — this window updates automatically.")
                .font(.system(size: 14)).foregroundStyle(Theme.muted)
            HStack(spacing: 14) {
                if let url = URL(string: uri) {
                    Link("Reopen GitHub", destination: url).foregroundStyle(Theme.accent)
                }
                Button("Cancel") { auth.signOut() }.buttonStyle(.plain).foregroundStyle(Theme.muted)
            }
        }
    }

    @ViewBuilder
    private func signedIn() -> some View {
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
                Text("✓ Loaded \(repo). Press ⌘⇧I anywhere to ask.")
                    .font(.system(size: 14, weight: .medium)).foregroundStyle(Theme.cited)
            case .failed(let message):
                Text(message).font(.system(size: 14)).foregroundStyle(Theme.unknown)
            }

            Spacer(minLength: 0)
            Button("Sign out") { auth.signOut() }.buttonStyle(.plain).foregroundStyle(Theme.muted)
        }
    }
}
