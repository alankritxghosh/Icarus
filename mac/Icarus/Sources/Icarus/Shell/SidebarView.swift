import SwiftUI
import IcarusKit

/// The shell's left rail: brand mark, the four nav rows, and a footer showing the
/// REAL connected repo (from /status) — never a fabricated tenant name.
struct SidebarView: View {
    @Binding var selected: ShellSurface
    @Bindable var auth: AuthModel
    let connect: ConnectModel

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Top inset clears the real macOS traffic-light buttons, which now
            // float over the sidebar (the window's own title bar is hidden).
            HStack(alignment: .bottom, spacing: 9) {
                MarkView(height: 26)
                Text("Icarus").font(Theme.display(20, .medium)).foregroundStyle(Theme.ink)
            }
            .padding(.leading, 4).padding(.top, 30).padding(.bottom, 24)

            VStack(spacing: 3) {
                ForEach(ShellSurface.allCases) { s in
                    NavRow(surface: s, selected: $selected)
                }
            }

            Spacer(minLength: 24)

            VStack(alignment: .leading, spacing: 3) {
                // "Company Brain" is a claim about WHOSE code this is: a shared
                // private index is a company's memory, a public repo's is not.
                // Read from the brain's /status, never inferred from the name.
                MonoLabel(connect.isPrivate ? "COMPANY BRAIN" : "REPO BRAIN")
                // Show a repo ONLY once THIS user has actually connected one —
                // the brain's /status always serves the public default, so keying
                // off it made simonw/llm look like hardcoded UI chrome. The connect
                // state is the app's own truth (and drops to "Not connected" if the
                // server ever loses the session).
                if case .ready(let repo) = connect.state {
                    Text(repo)
                        .font(Theme.mono(13)).foregroundStyle(Theme.ink)
                        .padding(.top, 3)
                    // Was hardcoded "PUBLIC REPOSITORY ALPHA" — false since
                    // private repos were re-enabled 2026-07-16, and shown while
                    // a private repo was connected. State the real one.
                    Text(connect.isPrivate ? "PRIVATE REPOSITORY · ALPHA" : "PUBLIC REPOSITORY · ALPHA")
                        .font(Theme.mono(10))
                        .foregroundStyle(Theme.muted)
                        .padding(.top, 2)
                } else {
                    Text("Not connected")
                        .font(Theme.mono(13)).foregroundStyle(Theme.muted)
                        .padding(.top, 3)
                }
                if auth.isSignedIn, connect.isReady {
                    Button("Disconnect repo") { connect.disconnect() }
                        .buttonStyle(.plain)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.muted)
                        .padding(.top, 8)
                        .help("Deletes your indexed data on the server and returns to setup")
                }
                if auth.isSignedIn {
                    Button("Sign out") { auth.signOut() }
                        .buttonStyle(.plain)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.muted)
                        .padding(.top, auth.isSignedIn && connect.isReady ? 4 : 8)
                        .help("Sign out to use another GitHub account")
                }
            }
            .padding(.leading, 4)
        }
        .padding(16)
        .frame(width: 210)
        .frame(maxHeight: .infinity, alignment: .top)
        // A shade off `surface` rather than a token of its own: the rail should
        // separate from the content area without becoming a second card.
        .background(Color(hex: 0x121216))
    }
}
