import SwiftUI
import IcarusKit

/// The app's Settings window (⌘, / the "Icarus > Settings…" menu item / the
/// new in-shell "Settings" button — SidebarView.swift, 2026-09-02). Wired via
/// SwiftUI's `Settings` scene (IcarusApp.swift), so it's a real separate
/// window, not a sheet.
///
/// **Raycast-pattern tabs (2026-09-02, Alankrit)**, absorbing what used to be
/// a single-section Form: a top tab bar, Account first, each tab a grouped
/// label-left/control-right form. `auth`/`connect`/`status` are the SAME
/// instances the main shell uses (threaded through from AppDelegate via
/// IcarusApp.swift) — never a second set of models that could disagree with
/// the window behind it about whether the user is signed in.
///
/// **The styling pass (2026-09-02)** matches the mockup's look — bundled
/// fonts (`Theme.sans`/`Theme.mono`/`Theme.display`, `FontLoader.swift`) and
/// glass cards (`SettingsCard` below) — but NOT its content: see the note
/// below on the transparency ledger.
///
/// **What this deliberately does NOT show:** a per-repository "everything
/// Icarus remembers about you" ledger (github id, last-seen commit per repo,
/// etc.). That data exists server-side (`demo/visits.py`) but there is no
/// client-facing endpoint for it today — inventing one here would mean
/// fabricating numbers, which is the one thing this product exists not to do.
/// It needs a real `GET /me`-style endpoint first; flagged as follow-up, not
/// silently dropped.
struct SettingsView: View {
    private enum Tab: String, CaseIterable, Identifiable {
        case account, general, privacy, repository, agentMode, about
        var id: String { rawValue }
        var title: String {
            switch self {
            case .account: "Account"
            case .general: "General"
            case .privacy: "Privacy"
            case .repository: "Repository"
            case .agentMode: "Agent Mode"
            case .about: "About"
            }
        }
    }

    let auth: AuthModel
    let connect: ConnectModel
    let statusModel: StatusModel

    @State private var tab: Tab = .account
    // OFF until the user turns it on. Must stay in step with
    // `SharePreferences.shareContent`'s own default -- `@AppStorage` shows this
    // value before any choice is written, so a `true` here would render an
    // enabled toggle over a store that is actually off.
    @AppStorage(icarusShareContentDefaultsKey) private var shareContent = false
    @State private var connectorStatus: ClaudeConnector.Status?
    @State private var connectorBusy = false

    private var appearanceBinding: Binding<AppAppearance> {
        Binding(get: { ThemeState.shared.appearance }, set: { ThemeState.shared.appearance = $0 })
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            tabBar
            Divider().background(Theme.border)
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    switch tab {
                    case .account: accountTab
                    case .general: generalTab
                    case .privacy: privacyTab
                    case .repository: repositoryTab
                    case .agentMode: agentModeTab
                    case .about: aboutTab
                    }
                }
                .padding(20)
            }
        }
        .frame(width: 460, height: 380)
        .background(Theme.surface)
        .task { await refreshConnector() }
    }

    // MARK: - Tab bar

    private var tabBar: some View {
        HStack(spacing: 3) {
            ForEach(Tab.allCases) { t in
                Button { tab = t } label: {
                    Text(t.title)
                        .font(Theme.sans(12, tab == t ? .semibold : .regular))
                        .foregroundStyle(tab == t ? Theme.ink : Theme.muted)
                        .padding(.horizontal, 10).padding(.vertical, 7)
                        .background {
                            if tab == t {
                                // The lit-glass active pill (mockup's `.tab.active`):
                                // a top-brighter gradient fill + a matching stroke,
                                // not a flat tint.
                                RoundedRectangle(cornerRadius: 7)
                                    .fill(LinearGradient(
                                        colors: [Theme.accent.opacity(0.32), Theme.accent.opacity(0.14)],
                                        startPoint: .top, endPoint: .bottom))
                                    .overlay(RoundedRectangle(cornerRadius: 7)
                                        .strokeBorder(Theme.accent.opacity(0.35), lineWidth: 1))
                            }
                        }
                }
                .buttonStyle(.plain)
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.card)
    }

    // MARK: - Account

    @ViewBuilder private var accountTab: some View {
        SettingsCard {
            VStack(alignment: .leading, spacing: 5) {
                MonoLabel(auth.isSignedIn ? "SIGNED IN" : "NOT SIGNED IN",
                          auth.isSignedIn ? Theme.cited : Theme.muted)
                Text(auth.isSignedIn ? "Signed in with GitHub." : "Sign in from the Icarus window to connect a repository.")
                    .font(Theme.sans(12)).foregroundStyle(Theme.ink)
                if auth.isSignedIn {
                    Button("Sign out") { auth.signOut() }
                        .buttonStyle(.plain)
                        .font(Theme.sans(12, .semibold))
                        .foregroundStyle(Theme.muted)
                        .padding(.top, 4)
                }
            }
        }
        MonoLabel("CONNECTED")
        SettingsCard {
            if case .ready(let repo) = connect.state {
                VStack(alignment: .leading, spacing: 4) {
                    Text(repo).font(Theme.mono(13)).foregroundStyle(Theme.ink)
                    Text(connect.isPrivate ? "private repo" : "public repo")
                        .font(Theme.sans(11)).foregroundStyle(Theme.muted)
                }
            } else {
                Text("No repository connected.").font(Theme.sans(12)).foregroundStyle(Theme.muted)
            }
        }
    }

    // MARK: - General

    @ViewBuilder private var generalTab: some View {
        MonoLabel("APPEARANCE")
        SettingsCard {
            VStack(alignment: .leading, spacing: 10) {
                Text("Theme").font(Theme.sans(13, .semibold)).foregroundStyle(Theme.ink)
                Text("Icarus shipped dark-only. The whole app repaints from one set of tokens.")
                    .font(Theme.sans(11)).foregroundStyle(Theme.muted)
                Picker("", selection: appearanceBinding) {
                    Text("Dark").tag(AppAppearance.dark)
                    Text("Light").tag(AppAppearance.light)
                }
                .pickerStyle(.segmented)
                .labelsHidden()
                .frame(width: 160)
            }
        }
    }

    // MARK: - Privacy

    @ViewBuilder private var privacyTab: some View {
        MonoLabel("PRIVACY")
        SettingsCard {
            VStack(alignment: .leading, spacing: 8) {
                Toggle("Help improve Icarus", isOn: $shareContent)
                    .toggleStyle(.switch)
                    .font(Theme.sans(13))
                Text(
                    "Off by default. Turn this on and Icarus shares three "
                    + "things with our product analytics: the question you "
                    + "asked, the full answer it gave back, and the references "
                    + "and excerpts of the code that answer cited. Never "
                    + "shared: your repository's full source, or anything an "
                    + "answer did not cite. Questions asked by a coding agent "
                    + "through MCP never share this content, whatever this is "
                    + "set to. Whether it is on or off, Icarus records that a "
                    + "question happened, from which surface, and a one-way "
                    + "hash of the repository — never its name."
                )
                .font(Theme.sans(11))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: - Repository

    @ViewBuilder private var repositoryTab: some View {
        MonoLabel("REPOSITORY")
        SettingsCard {
            if connect.isReady, case .ready(let repo) = connect.state {
                VStack(alignment: .leading, spacing: 10) {
                    HStack {
                        Text(repo).font(Theme.mono(13)).foregroundStyle(Theme.ink)
                        Spacer()
                        Text(connect.isPrivate ? "private" : "public")
                            .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                    }
                    if let pr = statusModel.counts?.pr {
                        Text("\(pr) PRs indexed").font(Theme.sans(12)).foregroundStyle(Theme.muted)
                    }
                    if let freshness = statusModel.status?.indexFreshness {
                        Text(freshness.summary).font(Theme.sans(11)).foregroundStyle(Theme.muted)
                    }
                    Button("Disconnect repo") { connect.disconnect() }
                        .buttonStyle(.plain)
                        .font(Theme.sans(12, .semibold))
                        .foregroundStyle(Theme.unknown)
                        .padding(.top, 2)
                        .help("Deletes your indexed data on the server and returns to setup")
                }
            } else {
                Text("No repository connected. Connect one from the Icarus window.")
                    .font(Theme.sans(12)).foregroundStyle(Theme.muted)
            }
        }
    }

    // MARK: - Agent Mode

    @ViewBuilder private var agentModeTab: some View {
        MonoLabel("CLAUDE CODE")
        SettingsCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .center, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(connectorTitle)
                            .font(Theme.sans(13, .semibold))
                        Text(connectorDetail)
                            .font(Theme.sans(11))
                            .foregroundStyle(Theme.muted)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer()
                    if connectorBusy {
                        ProgressView().controlSize(.small)
                    } else if let actionTitle = connectorActionTitle {
                        Button(actionTitle) { Task { await connectorAction() } }
                    }
                }
                Text(
                    "Icarus registers its installed app as a user-scoped, read-only MCP server. "
                    + "It never puts your GitHub credential in Claude's configuration."
                )
                .font(Theme.sans(11))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    // MARK: - About

    @ViewBuilder private var aboutTab: some View {
        HStack(spacing: 10) {
            MarkView(height: 26)
            Text("Icarus").font(Theme.display(20, .medium)).foregroundStyle(Theme.ink)
        }
        SettingsCard {
            HStack {
                Text("Version").font(Theme.sans(12)).foregroundStyle(Theme.ink)
                Spacer()
                Text(appVersion).font(Theme.mono(11)).foregroundStyle(Theme.muted)
            }
        }
    }

    private var appVersion: String {
        let short = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String
        switch (short, build) {
        case let (.some(s), .some(b)): return "\(s) (\(b))"
        case let (.some(s), .none): return s
        default: return "—"
        }
    }

    private var connectorTitle: String {
        switch connectorStatus {
        case nil: "Checking Claude Code…"
        case .unavailable: "Claude Code not found"
        case .notConfigured: "Icarus is not connected"
        case .connected: "Icarus is connected"
        case .legacyUserRegistration: "Legacy connector found"
        case .conflict: "A different ‘icarus’ server exists"
        case .failed: "Connector check failed"
        }
    }

    private var connectorDetail: String {
        switch connectorStatus {
        case nil: "Reading Claude Code's MCP configuration."
        case .unavailable:
            "Install Claude Code first, then return here to connect Icarus."
        case .notConfigured:
            "Connect once to make Icarus available in every Claude Code project."
        case .connected:
            "Healthy and available in every Claude Code project."
        case .legacyUserRegistration:
            "Claude is still using this repository's Python adapter. Repair it to use the installed app."
        case .conflict(let detail), .failed(let detail): detail
        }
    }

    private var connectorActionTitle: String? {
        switch connectorStatus {
        case .notConfigured: "Connect"
        case .legacyUserRegistration: "Repair"
        case .connected, .conflict, .failed: "Check Again"
        case nil, .unavailable: nil
        }
    }

    @MainActor
    private func refreshConnector() async {
        connectorBusy = true
        defer { connectorBusy = false }
        guard let connector = ClaudeConnector.live() else {
            connectorStatus = .unavailable
            return
        }
        connectorStatus = await connector.status()
    }

    @MainActor
    private func connectorAction() async {
        guard connectorStatus == .notConfigured
                || connectorStatus == .legacyUserRegistration else {
            await refreshConnector()
            return
        }
        connectorBusy = true
        defer { connectorBusy = false }
        guard let connector = ClaudeConnector.live() else {
            connectorStatus = .unavailable
            return
        }
        do {
            connectorStatus = try await connector.installOrRepair()
        } catch {
            connectorStatus = .failed(error.localizedDescription)
        }
    }
}

/// A glass card for the Settings window ONLY (2026-09-02, the styling pass):
/// a top-brighter gradient fill, a matching lit-edge stroke, and a soft
/// layered shadow, versus the shared `ShellCard`'s flat fill + hairline used
/// everywhere else in the shell. Deliberately a SEPARATE type rather than a
/// new mode on `ShellCard` — extending glass to the rest of the app (Home,
/// Investigate, the Agent Mode inbox) is a bigger, separate call than
/// restyling this one window, and `DESIGN_VISION.md`'s brutalist-flat-card
/// rule still governs everywhere this type isn't used.
struct SettingsCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background {
                RoundedRectangle(cornerRadius: 12)
                    .fill(LinearGradient(
                        colors: [Theme.card.opacity(1), Theme.card.opacity(0.92)],
                        startPoint: .top, endPoint: .bottom))
            }
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .strokeBorder(LinearGradient(
                        colors: [Color.white.opacity(0.16), Theme.border, Theme.border.opacity(0.6)],
                        startPoint: .top, endPoint: .bottom), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 12))
            .shadow(color: .black.opacity(0.22), radius: 10, y: 4)
    }
}
