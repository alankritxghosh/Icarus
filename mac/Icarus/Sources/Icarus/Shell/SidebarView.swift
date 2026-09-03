import SwiftUI
import IcarusKit

/// The shell's left rail: brand mark, the four nav rows, and a footer showing the
/// REAL connected repo (from /status) — never a fabricated tenant name.
///
/// **Collapsible (2026-09-03, Alankrit)**, persisted across launches. Reclaims
/// width for the content area; the footer (repo name, Disconnect, Sign out,
/// Settings) hides while collapsed rather than inventing a compact icon-only
/// treatment for four text actions that don't have one yet — expand to reach
/// them. Each nav row shows a custom-drawn `SurfaceIcon` (`SidebarIcons.swift`)
/// when collapsed — hairline `Path` shapes in this app's own hand, the same
/// spirit as `IconArt.swift`'s logo, not a borrowed SF Symbol (this app has
/// never used one).
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
    // Local to this one view -- nothing else reads or writes it, so a bare
    // @AppStorage is the right size (unlike AppearancePreference/
    // SharePreferences, which needed a dedicated type because Theme.swift and
    // BrainClient read them from OUTSIDE SwiftUI).
    @AppStorage("icarus.sidebarCollapsed") private var collapsed = false

    private let expandedWidth: CGFloat = 210
    private let collapsedWidth: CGFloat = 64
    private var morph: Animation { .easeOut(duration: 0.18) }   // OverlayView's own value

    var body: some View {
        VStack(alignment: collapsed ? .center : .leading, spacing: 0) {
            // Top inset clears the real macOS traffic-light buttons, which now
            // float over the sidebar (the window's own title bar is hidden).
            Group {
                if collapsed {
                    VStack(spacing: 10) {
                        MarkView(height: 26)
                        collapseToggle
                    }
                } else {
                    HStack(alignment: .bottom, spacing: 9) {
                        MarkView(height: 26)
                        Text("Icarus").font(Theme.display(20, .medium)).foregroundStyle(Theme.ink)
                        Spacer(minLength: 8)
                        collapseToggle
                    }
                }
            }
            .padding(.leading, collapsed ? 0 : 4).padding(.top, 30).padding(.bottom, 24)

            VStack(spacing: 3) {
                ForEach(ShellSurface.allCases) { s in
                    NavRow(surface: s, selected: $selected, collapsed: collapsed)
                }
            }

            Spacer(minLength: 24)

            if !collapsed {
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
                .transition(.opacity)
            }
        }
        .padding(16)
        .frame(width: collapsed ? collapsedWidth : expandedWidth)
        .frame(maxHeight: .infinity, alignment: .top)
        // A shade off `surface`, not `card` — the rail separates from the
        // content area without becoming a second card. `Theme.rail`, not a
        // bare literal: this was previously stuck dark through the light/dark
        // switch because it never read the palette at all.
        .background(Theme.rail)
        .animation(morph, value: collapsed)
    }

    private var collapseToggle: some View {
        Button {
            collapsed.toggle()
        } label: {
            Text("◂")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(Theme.muted)
                .rotationEffect(.degrees(collapsed ? 180 : 0))
                .frame(width: 20, height: 20)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .keyboardShortcut("b", modifiers: .command)
        .help(collapsed ? "Expand sidebar (⌘B)" : "Collapse sidebar (⌘B)")
    }
}
