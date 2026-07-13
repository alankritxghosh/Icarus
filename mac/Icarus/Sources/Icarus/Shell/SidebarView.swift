import SwiftUI
import IcarusKit

/// The shell's left rail: brand mark, the five nav rows, and a footer showing the
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
                Text("Icarus").font(.system(size: 19, weight: .semibold)).foregroundStyle(Theme.ink)
            }
            .padding(.leading, 4).padding(.top, 30).padding(.bottom, 24)

            VStack(spacing: 3) {
                ForEach(ShellSurface.allCases) { s in
                    NavRow(surface: s, selected: $selected)
                }
            }

            Spacer(minLength: 24)

            VStack(alignment: .leading, spacing: 3) {
                MonoLabel("COMPANY BRAIN")
                // Show a repo ONLY once THIS user has actually connected one —
                // the brain's /status always serves the public default, so keying
                // off it made simonw/llm look like hardcoded UI chrome. The connect
                // state is the app's own truth (and drops to "Not connected" if the
                // server ever loses the session).
                if case .ready(let repo, _) = connect.state {
                    Text(repo)
                        .font(Theme.mono(13)).foregroundStyle(Theme.ink)
                        .padding(.top, 3)
                    Text("PUBLIC REPOSITORY ALPHA")
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
        .background(Color(hex: 0xF2F0E9))
    }
}
