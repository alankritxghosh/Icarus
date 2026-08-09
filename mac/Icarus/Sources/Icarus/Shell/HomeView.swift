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
    let briefing: BriefingModel
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
            briefingRow
            freshnessRow
            HStack(alignment: .top, spacing: 16) {
                heroCard.frame(maxWidth: .infinity)
                metricsCard.frame(width: 200)
            }
            HStack(alignment: .top, spacing: 16) {
                recentCard.frame(maxWidth: .infinity)
                ProofDrawerView(entry: history.mostRecent, counts: status.counts).frame(width: 264)
            }
        }
        // Keyed on the repo, so switching repos refetches and a briefing about
        // one repo can never be shown against another.
        .task(id: status.repo) {
            await briefing.load(repo: status.repo)
            // Acknowledged only once it has actually been rendered -- the
            // server's GET is pure precisely so this can be a separate,
            // deliberate step rather than a side effect of fetching.
            await briefing.acknowledge()
        }
    }

    /// What changed since this user was last here (`demo/visits.py`).
    ///
    /// `BriefingChange` is an enum for the same reason `IndexFreshness` is:
    /// `commitsSince` is optional on the wire, and `?? 0` here would turn
    /// "Icarus couldn't work out what changed" into "nothing changed" -- a
    /// reassuring falsehood. Every case is named, including unknown.
    ///
    /// A transport failure shows NOTHING rather than a briefing-shaped
    /// message: not being able to reach the brain is not the brain telling
    /// you your repo is unchanged.
    @ViewBuilder private var briefingRow: some View {
        if let b = briefing.briefing {
            switch b.change {
            case .firstVisit:
                staleRow(BriefingChange.firstVisit.summary,
                         detail: "Icarus will tell you what changed the next time you come back.",
                         colour: Theme.muted)
            case .nothingChanged:
                EmptyView()   // silence is the right amount of noise for "no news"
            case .changed(let n):
                staleRow(BriefingChange.changed(n).summary,
                         detail: "Since your last visit to this repository.",
                         colour: Theme.accent)
            case .unknown:
                staleRow(BriefingChange.unknown.summary,
                         detail: "You have been here before, but the comparison did not complete.",
                         colour: Theme.unknown)
            }
        }
    }

    /// Whether the index still matches the repository (`demo/freshness.py`).
    ///
    /// Driven by `RepoStatus.indexFreshness`, which is an ENUM rather than the
    /// optional Bool it decodes from -- so there is no `?? false` here that
    /// could quietly render "Icarus couldn't check" as "up to date". Each case
    /// is named, including the one that says nothing was learned.
    ///
    /// `.matches` shows nothing at all: a banner confirming that everything is
    /// normal is noise, and the absence of a warning already carries it.
    @ViewBuilder private var freshnessRow: some View {
        switch status.status?.indexFreshness ?? .unknown {
        case .matches:
            EmptyView()
        case .behind(let n):
            // The only branch that offers the button, and it asks the enum
            // rather than assuming: `offersRefresh` is where the policy lives
            // (never for `pinned`, whose refresh the server forbids; never for
            // `unknown`, which does not know it is stale).
            staleRow(IndexFreshness.behind(n).summary,
                     detail: connect.refreshError
                        ?? "Icarus is answering from the older index until you re-read it.",
                     colour: Theme.accent,
                     refresh: IndexFreshness.behind(n).offersRefresh)
        case .unknown:
            // Amber, the honest-unknown palette -- deliberately neither the
            // green of "fine" nor the red of "broken". It is a third state.
            staleRow(IndexFreshness.unknown.summary,
                     detail: "It may or may not be current.", colour: Theme.unknown)
        case .pinned(let n):
            staleRow(IndexFreshness.pinned(n).summary,
                     detail: "This is the built-in demo corpus and is not refreshable.",
                     colour: Theme.muted)
        }
    }

    private func staleRow(_ title: String, detail: String, colour: Color,
                          refresh: Bool = false) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("◷").font(.system(size: 13)).foregroundStyle(colour)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 13, weight: .semibold)).foregroundStyle(Theme.ink)
                Text(detail).font(.system(size: 12)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if refresh {
                Spacer(minLength: 12)
                Button(connect.isRefreshing ? "Re-reading…" : "Re-read repository") {
                    connect.refreshConnected()
                }
                .disabled(connect.isRefreshing)
                .font(.system(size: 12, weight: .semibold))
                .buttonStyle(.borderedProminent)
                .tint(colour)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(colour.opacity(0.5), lineWidth: 1))
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
                Text("Welcome back, Alankrit").font(Theme.display(24, .medium)).foregroundStyle(Theme.ink)
                Text("Hold the hotkey, ask why, and let the proof sit one glance away.")
                    .font(.system(size: 13)).foregroundStyle(Theme.muted)
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 6) {
                pill("hold ⌥ Right Option", filled: true)
                pill("GitHub · \(status.repo ?? "not connected")", filled: false)
                if let s = status.status, s.isReady {
                    pill(s.repositoryVisibilityName, filled: false)
                }
            }
        }
    }

    /// The hero was a black slab on a light page — `background(Theme.ink)` with
    /// `Theme.card` text, i.e. deliberately inverted against the palette. Inverting
    /// a DARK palette the same way produces a glaring white slab, so the emphasis
    /// moved from a reversed fill to a serif headline on an ordinary card. This is
    /// the one place the repaint is a redesign rather than a value swap.
    private var heroCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text("Hold ⌥ (Right Option) to ask Icarus")
                .font(Theme.display(25, .medium)).foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)
            Text("Ask in the middle of work. Icarus answers like a teammate, then shows the PRs, issues, and exact files behind the answer. Press ⌘⇧I to type instead.")
                .font(.system(size: 13)).foregroundStyle(Theme.muted)
                .padding(.top, 12).fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 12) {
                Button(action: onTryQuestion) { Text("Try a question") }.buttonStyle(LightButton())
                Text("never always-listening")
                    .font(Theme.mono(11)).foregroundStyle(Theme.muted)
                    .padding(.horizontal, 10).padding(.vertical, 6)
                    .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
            }
            .padding(.top, 22)
        }
        .padding(24)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.card)
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(Theme.border, lineWidth: 1))
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

    /// The filled pill used to be ink-on-card. A solid pale block reads as a
    /// button on a dark page, so the emphasised state is now the accent as a
    /// tint + border, which says "active" without offering to be clicked.
    private func pill(_ text: String, filled: Bool) -> some View {
        Text(text)
            .font(Theme.mono(11))
            .foregroundStyle(filled ? Theme.accent : Theme.muted)
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(filled ? Theme.accent.opacity(0.14) : Color.clear)
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(filled ? Theme.accent : Theme.border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

/// The "Try a question" button on the hero card: ink fill, surface-coloured
/// label. On the dark palette that is a pale button with dark text — still the
/// brightest thing in the card, which is the job it was doing before.
struct LightButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(Theme.surface)
            .padding(.horizontal, 16).padding(.vertical, 9)
            .background(Theme.ink.opacity(configuration.isPressed ? 0.85 : 1))
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
                            // The SAME caveat the overlay applies. Found live on
                            // facebook/react 2026-07-29: the overlay correctly
                            // said "still indexing" while this drawer said "No
                            // one wrote this down" about the very same ask — the
                            // false claim survived because only one of the two
                            // render paths was fixed. Two surfaces stating
                            // different things about one answer is worse than
                            // either being wrong alone.
                            MonoLabel(entry.response.unknownHeadline, Theme.unknown)
                            Text(entry.response.unknownMessage)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Theme.ink).padding(.top, 5)
                            Text(entry.response.compactTrail).font(Theme.mono(11)).foregroundStyle(Theme.unknown).padding(.top, 5)
                        }
                    }
                } else {
                    Text("Ask a question and the receipts behind the answer land here.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                }
            }
        }
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
