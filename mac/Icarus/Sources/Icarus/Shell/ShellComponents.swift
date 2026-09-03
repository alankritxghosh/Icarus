import SwiftUI
import IcarusKit

/// The Icarus mark — spread wings rising from a downward V. Drawn by `IconArt`
/// rather than redrawn here, so the sidebar can never disagree with the Dock
/// icon about what the logo is.
struct MarkView: View {
    var height: CGFloat = 26
    var body: some View {
        Image(nsImage: IconArt.markGlyph(size: height * 2, color: NSColor(Theme.accent)))
            .resizable()
            .frame(width: height, height: height)   // @2x source, so it stays crisp
    }
}

/// One sidebar nav row: filled accent dot + ink label when active, muted otherwise.
///
/// **Collapsed (2026-09-03)**: the label and its box hide; the dot alone
/// marks selection with no highlight box (the box reads as an odd floating
/// square around nothing once there's no label to anchor it to — matching
/// the fix already made to the standalone sidebar mockup this ports). A
/// custom-drawn `SurfaceIcon` (`SidebarIcons.swift`) marks which surface is
/// which, since a plain dot can't tell "Home" from "Investigate" apart.
struct NavRow: View {
    let surface: ShellSurface
    @Binding var selected: ShellSurface
    var collapsed: Bool = false

    var body: some View {
        let active = surface == selected
        Button {
            selected = surface
        } label: {
            if collapsed {
                SurfaceIcon(surface: surface, color: active ? Theme.accent : Theme.inactiveDot)
                    .frame(width: 30, height: 30)
                    .contentShape(Rectangle())
                    .help(surface.title)
            } else {
                HStack(spacing: 11) {
                    Circle().fill(active ? Theme.accent : Theme.inactiveDot).frame(width: 7, height: 7)
                    Text(surface.title)
                        .font(.system(size: 14, weight: active ? .semibold : .regular))
                        .foregroundStyle(active ? Theme.ink : Theme.muted)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 11).padding(.vertical, 9)
                .background(active ? Theme.card : .clear)
                .overlay(RoundedRectangle(cornerRadius: 8).stroke(active ? Theme.border : .clear, lineWidth: 1))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                .contentShape(Rectangle())
            }
        }
        .buttonStyle(.plain)
    }
}

/// A verdict pill: green "cited" or amber "unknown" — the shell's honesty at a glance.
struct VerdictPill: View {
    let cited: Bool
    var body: some View {
        Text(cited ? "cited" : "unknown")
            .font(Theme.mono(11, .bold))
            .foregroundStyle(cited ? Theme.cited : Theme.unknown)
            .padding(.horizontal, 9).padding(.vertical, 3)
            .background(cited ? Theme.citedBg : Theme.unknownBg)
            .overlay(RoundedRectangle(cornerRadius: 7).stroke(cited ? Theme.cited : Theme.unknown, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 7))
    }
}

/// One real history row (shared by Home's recent list and Decision history).
struct HistoryRow: View {
    let entry: AskHistory.Entry
    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Text(entry.at, style: .time)
                .font(Theme.mono(12)).foregroundStyle(Theme.muted)
                .frame(width: 74, alignment: .leading)
            VStack(alignment: .leading, spacing: 5) {
                Text(entry.question).font(.system(size: 14)).foregroundStyle(Theme.ink)
                Text(evidenceLine).font(Theme.mono(12)).foregroundStyle(Theme.muted)
            }
            Spacer(minLength: 12)
            VerdictPill(cited: entry.isCited)
        }
    }

    private var evidenceLine: String {
        guard entry.response.verdict == .answer else {
            // An abstention leads with the ref the question NAMED, when there
            // was one — that is what tells a reader it looked where they asked.
            return entry.response.compactTrail
        }
        // displayLabel, not ref: index evidence reads as "Icarus's own index"
        // here too, or the recent-asks list quietly reintroduces the raw
        // `index:overview` the chip was just fixed to stop showing.
        let refs = entry.response.citations.map(\.displayLabel)
        return "evidence: " + (refs.isEmpty ? "—" : refs.prefix(4).joined(separator: " · "))
    }
}

/// A card surface (white, hairline border) used across the shell.
struct ShellCard<Content: View>: View {
    @ViewBuilder var content: Content
    var body: some View {
        content
            .padding(20)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 12))
    }
}
