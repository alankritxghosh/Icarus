import SwiftUI
import IcarusKit

/// The shell's left rail: brand mark, the four nav rows, and a footer showing the
/// REAL connected repo (from /status) — never a fabricated tenant name.
struct SidebarView: View {
    @Binding var selected: ShellSurface
    @Bindable var auth: AuthModel
    let connect: ConnectModel
    // SwiftUI's own action for opening the `Settings` scene (IcarusApp.swift) --
    // the in-window equivalent of the app-menu item and ⌘, (AppDelegate's
    // `openSettings()`, which sends the same `showSettingsWindow:` selector from
    // outside SwiftUI). Before this, Settings had no entry point IN the shell
    // itself.
    @Environment(\.openSettings) private var openSettings

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
                // Show a repo ONLY once THIS user has actually connected one —
                // the brain's /status always serves the public default, so keying
                // off it made simonw/llm look like hardcoded UI chrome. The connect
                // state is the app's own truth (and drops to "Not connected" if the
                // server ever loses the session).
                //
                // Deliberately just the name: the earlier "COMPANY BRAIN"/"REPO
                // BRAIN" label and the "PRIVATE/PUBLIC REPOSITORY · CONNECTED"
                // line were cut as footer clutter (2026-09-02, Alankrit). That
                // drops the private-vs-public signal from the rail; if it's
                // needed again, prefer a small glyph beside the name over
                // reinstating the text.
                if case .ready(let repo) = connect.state {
                    Text(repo)
                        .font(Theme.mono(13)).foregroundStyle(Theme.ink)
                } else {
                    Text("Not connected")
                        .font(Theme.mono(13)).foregroundStyle(Theme.muted)
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
                Button("Settings") { openSettings() }
                    .buttonStyle(.plain)
                    .font(.system(size: 12))
                    .foregroundStyle(Theme.muted)
                    .padding(.top, auth.isSignedIn ? 4 : 8)
                    .help("Account, appearance, privacy, repository, and Claude Code")
            }
            .padding(.leading, 4)
        }
        .padding(16)
        .frame(width: 210)
        .frame(maxHeight: .infinity, alignment: .top)
        // A shade off `surface`, not `card` — the rail separates from the
        // content area without becoming a second card. `Theme.rail`, not a
        // bare literal: this was previously stuck dark through the light/dark
        // switch because it never read the palette at all.
        .background(Theme.rail)
    }
}
