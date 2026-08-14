import SwiftUI

/// The app's native Settings window (⌘, and the "Icarus > Settings…" menu
/// item, wired automatically by SwiftUI's `Settings` scene in IcarusApp.swift
/// -- no custom window/sheet needed).
///
/// Lets a Mac-app user install, diagnose, or safely repair Icarus's universal
/// Claude Code registration without editing Claude configuration by hand.
struct SettingsView: View {
    @State private var connectorStatus: ClaudeConnector.Status?
    @State private var connectorBusy = false

    var body: some View {
        Form {
            Section("Claude Code") {
                HStack(alignment: .center, spacing: 12) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(connectorTitle)
                            .font(.system(size: 13, weight: .semibold))
                        Text(connectorDetail)
                            .font(.system(size: 11))
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
                .font(.system(size: 11))
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
            }

        }
        .padding(20)
        .frame(width: 430)
        .task { await refreshConnector() }
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
