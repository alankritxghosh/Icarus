import SwiftUI
import IcarusKit

/// The Home surface: hero (real ⌥ trigger), metrics (real /status counts + real
/// session cited-rate), recent asks (real, with honest empty state), and the proof
/// drawer (the last real answer's receipts). No fabricated numbers or history.
struct HomeView: View {
    let auth: AuthModel
    let connect: ConnectModel
    let history: AskHistory
    let status: StatusModel
    let onTryQuestion: () -> Void

    var body: some View {
        // Signed in AND a repo connected → the dashboard; otherwise the setup gate.
        // (Both checks so Sign out drops straight back to the gate.)
        if auth.isSignedIn && connect.isReady {
            dashboard
        } else {
            SetupView(auth: auth, connect: connect)
        }
    }

    private var dashboard: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            if status.status?.isTruncated == true { truncatedBanner }
            HStack(alignment: .top, spacing: 16) {
                heroCard.frame(maxWidth: .infinity)
                metricsCard.frame(width: 200)
            }
            HStack(alignment: .top, spacing: 16) {
                recentCard.frame(maxWidth: .infinity)
                ProofDrawerView(entry: history.mostRecent, counts: status.counts).frame(width: 264)
            }
        }
    }

    /// Honest coverage notice (Brick 2a/2b): a big repo that hit the size cap is
    /// only PARTIALLY indexed, so a dropped file's "no one wrote this down" is
    /// explained rather than mistaken for full coverage. Amber = the same
    /// honest-unknown palette, deliberately.
    private var truncatedBanner: some View {
        HStack(alignment: .top, spacing: 10) {
            Text("⚠").font(.system(size: 13)).foregroundStyle(Theme.unknown)
            VStack(alignment: .leading, spacing: 2) {
                Text("Large repo — partial index")
                    .font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.ink)
                Text("This repo hit the index size cap, so some files aren't covered yet. A question about an unindexed file may honestly return \u{201C}no one wrote this down.\u{201D}")
                    .font(.system(size: 12)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.unknownBg)
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.unknown.opacity(0.5), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 9))
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Welcome back, Alankrit").font(.system(size: 22, weight: .semibold)).foregroundStyle(Theme.ink)
                Text("Hold the hotkey, ask why, and let the proof sit one glance away.")
                    .font(.system(size: 13)).foregroundStyle(Theme.muted)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 6) {
                pill("hold ⌥ Right Option", filled: true)
                pill("GitHub · \(status.repo ?? "not connected")", filled: false)
                if let s = status.status, s.isReady {
                    pill("public repo", filled: false)
                }
            }
        }
    }

    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Hold ⌥ (Right Option) to ask Icarus")
                .font(.system(size: 24, weight: .semibold)).foregroundStyle(Theme.card)
                .fixedSize(horizontal: false, vertical: true)
            Text("Ask in the middle of work. Icarus answers like a teammate, then shows the PRs, issues, and exact files behind the answer. Press ⌘⇧I to type instead.")
                .font(.system(size: 13)).foregroundStyle(Color(hex: 0xC9C6BE))
                .padding(.top, 12).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                Button(action: onTryQuestion) { Text("Try a question") }.buttonStyle(LightButton())
                Text("never always-listening")
                    .font(Theme.mono(11)).foregroundStyle(Color(hex: 0xC9C6BE))
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color(hex: 0x55534E), lineWidth: 1))
            }
            .padding(.top, 22)
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.ink)
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var metricsCard: some View {
        VStack(alignment: .leading, spacing: 16) {
            metric(status.counts.map { "\($0.pr)" } ?? "—", "PRs indexed")
            metric(citedRateText, "answers cited · this session")
        }
        .padding(20)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.card)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 12))
    }

    private var recentCard: some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 0) {
                MonoLabel("RECENT · THIS SESSION")
                if history.entries.isEmpty {
                    Text("No questions yet this session — hold ⌥ or press ⌘⇧I to ask. Only real asks appear here.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                        .padding(.top, 14)
                } else {
                    ForEach(history.entries.prefix(4)) { entry in
                        Divider().background(Theme.border).padding(.vertical, 14)
                        HistoryRow(entry: entry)
                    }
                }
            }
        }
    }

    private var citedRateText: String {
        guard let r = history.citedRate else { return "—" }
        return "\(Int((r * 100).rounded()))%"
    }

    private func metric(_ value: String, _ label: String) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(value).font(.system(size: 26, weight: .semibold)).foregroundStyle(Theme.ink)
            Text(label).font(.system(size: 12)).foregroundStyle(Theme.muted)
        }
    }

    private func pill(_ text: String, filled: Bool) -> some View {
        Text(text)
            .font(Theme.mono(11))
            .foregroundStyle(filled ? Theme.card : Theme.muted)
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(filled ? Theme.ink : Color.clear)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(filled ? Color.clear : Theme.border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

/// The light "Try a question" button on the black hero card.
struct LightButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(Theme.ink)
            .padding(.horizontal, 16).padding(.vertical, 9)
            .background(Theme.card.opacity(configuration.isPressed ? 0.85 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
    }
}

/// The proof drawer: the last real answer's spoken text + receipts, or the honest
/// unknown, or an empty state before any ask.
struct ProofDrawerView: View {
    let entry: AskHistory.Entry?
    let counts: IndexCounts?

    var body: some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 12) {
                Text("Proof drawer").font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink)
                Text("The answer stays short. The receipts stay typed and inspectable.")
                    .font(.system(size: 12)).foregroundStyle(Theme.muted)

                if let entry {
                    if entry.response.verdict == .answer {
                        boxed(bg: Theme.card, border: Theme.border) {
                            MonoLabel("SPOKEN ANSWER")
                            Text(entry.response.answer).font(.system(size: 13)).foregroundStyle(Theme.ink).padding(.top, 5)
                        }
                        boxed(bg: Theme.citedBg, border: Theme.cited.opacity(0.5)) {
                            MonoLabel("RECEIPTS", Theme.cited)
                            FlowLayout(spacing: 6) {
                                ForEach(entry.response.citations) { CitationChip(citation: $0) }
                            }.padding(.top, 8)
                        }
                    } else {
                        boxed(bg: Theme.unknownBg, border: Theme.unknown.opacity(0.5)) {
                            MonoLabel("HONEST UNKNOWN", Theme.unknown)
                            Text("No one wrote this down.").font(.system(size: 14, weight: .semibold)).foregroundStyle(Theme.ink).padding(.top, 5)
                            Text("searched: " + searchedLine(entry)).font(Theme.mono(11)).foregroundStyle(Theme.unknown).padding(.top, 5)
                        }
                    }
                } else {
                    Text("Ask a question and the receipts behind the answer land here.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                }
            }
        }
    }

    private func searchedLine(_ entry: AskHistory.Entry) -> String {
        let s = entry.response.searched
        return s.isEmpty ? "—" : s.prefix(4).joined(separator: " · ")
    }

    @ViewBuilder private func boxed<C: View>(bg: Color, border: Color, @ViewBuilder _ content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 0) { content() }
            .padding(12)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(bg)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
    }
}
