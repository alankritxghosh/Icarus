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
                         "Sign in with GitHub, connect a repo, and start asking why.")
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
            Text("Sign in with GitHub to load a public repository.")
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

            if case .lost(let repo) = connect.state {
                lostBanner(repo: repo)
            }

            MonoLabel("STEP 2 — CONNECT A REPOSITORY")
            HStack(spacing: 8) {
                TextField("owner/repo  (e.g. simonw/llm)", text: $connect.repoInput)
                    .textFieldStyle(.plain)
                    .font(Theme.mono(13))
                    .foregroundStyle(Theme.ink)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Theme.card)
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).stroke(Theme.border, lineWidth: 1))
                    .onSubmit { if !connect.isConnecting { connect.connect() } }
                    .disabled(connect.isConnecting)
                // Disabled mid-connect: a second click starts a WHOLE NEW server-side
                // index of the same repo (the server's single-flight guard covers the
                // download, not the expensive embed), so impatient clicking pinned the
                // container's one CPU at 100% and made the connect slower, not faster
                // -- live-confirmed 2026-07-14 from Azure's own CPU metrics.
                Button("Connect") { connect.connect() }
                    .buttonStyle(PrimaryButton())
                    .disabled(connect.isConnecting)
            }

            switch connect.state {
            case .idle:
                Text("This alpha supports public repositories only. The first index of a new repo can take a minute.")
                    .font(.system(size: 13)).foregroundStyle(Theme.muted)
            case .connecting(let repo):
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Indexing \(repo)…").font(.system(size: 14)).foregroundStyle(Theme.muted)
                }
            case .ready(let repo):
                Text("✓ Loaded \(repo).")
                    .font(.system(size: 14, weight: .medium)).foregroundStyle(Theme.cited)
            case .failed(let message):
                Text(message).font(.system(size: 14)).foregroundStyle(Theme.unknown)
            case .lost:
                EmptyView()   // the banner above carries this state
            }

            Button("Sign out") { auth.signOut() }.buttonStyle(.plain).foregroundStyle(Theme.muted)
        }
    }

    /// The server dropped the session. Explicit, with a one-click reconnect — never
    /// silently show the public default as if it were still the user's repo.
    @ViewBuilder private func lostBanner(repo: String) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoLabel("CONNECTION LOST", Theme.unknown)
            Text("The server dropped your connection to \(repo) — it restarted or evicted your session. Your questions would answer against the public default until you reconnect.")
                .font(.system(size: 13)).foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            Button("Reconnect \(repo)") { connect.resumeSaved() }
                .buttonStyle(PrimaryButton())
                .padding(.top, 4)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.unknownBg)
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.unknown.opacity(0.5), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 9))
    }
}
