import SwiftUI
import IcarusKit

/// Full session history — every real ask, newest first. Honest empty state.
struct DecisionHistoryView: View {
    let history: AskHistory
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle("Decision history", "Every question you've asked this session, and what the record answered.")
            ShellCard {
                if history.entries.isEmpty {
                    Text("Nothing asked yet this session. Hold ⌥ or press ⌘⇧I to ask — real asks show up here.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                } else {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(history.entries.enumerated()), id: \.element.id) { i, entry in
                            if i > 0 { Divider().background(Theme.border).padding(.vertical, 14) }
                            HistoryRow(entry: entry)
                        }
                    }
                }
            }
        }
    }
}

/// The map of what this codebase never wrote down — the repo's SHARED ledger,
/// not this session's history.
///
/// This is the artifact no competitor can produce, because producing it requires
/// being willing to say "I don't know" in the first place. It is also the only
/// loop that compounds with use WITHOUT training on customer code: the more the
/// team asks, the sharper the picture of their own documentation debt.
///
/// Ranked by how OFTEN a gap was hit and never by how many DISTINCT people hit
/// it — the server records no asker, deliberately. That is memory for a team
/// rather than surveillance of one, and the cost is stated on screen rather than
/// hidden, so nobody reads the ranking as more than it is.
struct UnknownsView: View {
    let ledger: LedgerModel
    @State private var selectedGap: MemoryGap?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle("Engineering memory",
                         "Open gaps, recurring questions, and knowledge the team has recovered.")
            ShellCard {
                switch ledger.state {
                case .idle, .loading:
                    Text("Reading the record…")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                case .failed(let message):
                    // NEVER render a failure as an empty list: "no gaps" and
                    // "we couldn't look" appear identically and mean opposite
                    // things, and one of them is a claim about their codebase.
                    VStack(alignment: .leading, spacing: 8) {
                        MonoLabel("COULDN'T LOAD", Theme.unknown)
                        Text(message).font(.system(size: 13)).foregroundStyle(Theme.ink)
                        Text("This is not the same as having no gaps — we couldn't read the record.")
                            .font(.system(size: 12)).foregroundStyle(Theme.muted)
                    }
                case .loaded(let repo, let gaps) where gaps.isEmpty:
                    VStack(alignment: .leading, spacing: 6) {
                        Text("No engineering-memory gaps recorded yet in \(repo).")
                            .font(.system(size: 13)).foregroundStyle(Theme.ink)
                        Text("When a question has no recorded answer, it lands here — honestly.")
                            .font(.system(size: 12)).foregroundStyle(Theme.muted)
                    }
                case .loaded(let repo, let gaps):
                    let open = gaps.filter { $0.status == .open }
                    let recurring = open.filter { $0.unknownCount > 1 }
                    let proposed = gaps.filter { $0.status == .proposed }
                    let resolved = gaps.filter { $0.status == .resolved }
                    VStack(alignment: .leading, spacing: 0) {
                        HStack {
                            MonoLabel("ENGINEERING MEMORY · \(repo.uppercased())", Theme.unknown)
                            Spacer()
                            Text(
                                "\(open.count) open · \(proposed.count) proposed · "
                                + "\(recurring.count) recurring · \(resolved.count) resolved"
                            )
                                .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                        }
                        .padding(.bottom, 12)
                        ForEach(Array(gaps.enumerated()), id: \.element.id) { i, gap in
                            if i > 0 { Divider().background(Theme.border).padding(.vertical, 12) }
                            MemoryGapRow(gap: gap, recordDisabled: ledger.isRecording) {
                                ledger.resetRecordState()
                                selectedGap = gap
                            }
                        }
                    }
                }
            }
            Text("Ranked by how often each was asked, never by how many people asked — Icarus doesn't record who asks.")
                .font(.system(size: 11)).foregroundStyle(Theme.muted)
        }
        .onAppear { ledger.load() }
        .sheet(item: $selectedGap, onDismiss: ledger.resetRecordState) { gap in
            MemoryRecordSheet(ledger: ledger, gap: gap)
        }
    }
}

/// One documentation gap: the question, and how many times the team hit it.
private struct MemoryGapRow: View {
    let gap: MemoryGap
    let recordDisabled: Bool
    let onRecord: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline, spacing: 12) {
                Text(gap.question)
                    .font(.system(size: 14)).foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 12)
                if gap.status == .resolved {
                    Text("resolved")
                        .font(Theme.mono(10)).foregroundStyle(Theme.accent)
                } else if gap.status == .proposed {
                    Text("proposal open")
                        .font(Theme.mono(10)).foregroundStyle(Theme.accent)
                } else if gap.kind == "not_in_repo" {
                    Text("not in this repo")
                        .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                } else if !gap.actionable {
                    Text("reason unclear")
                        .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                }
                if gap.unknownCount > 1 {
                    Text("asked \(gap.unknownCount)x")
                        .font(Theme.mono(11)).foregroundStyle(Theme.unknown)
                }
            }
            if gap.status == .resolved, !gap.resolutionCitations.isEmpty {
                Text("Confirmed by \(gap.resolutionCitations.joined(separator: " · "))")
                    .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                    .lineLimit(2)
            }
            if gap.status == .proposed, let proposal = gap.proposal {
                Link("Open memory proposal", destination: proposal.pullRequestURL)
                    .font(.system(size: 12, weight: .semibold))
                    .padding(.top, 4)
            }
            if gap.status == .open, gap.actionable {
                Button("Record engineering memory", action: onRecord)
                    .buttonStyle(PrimaryButton())
                    .padding(.top, 4)
                    .disabled(recordDisabled)
            }
        }
    }
}

private struct MemoryRecordSheet: View {
    let ledger: LedgerModel
    let gap: MemoryGap
    @Environment(\.dismiss) private var dismiss
    @State private var rationale = ""
    @State private var tradeoffs = ""
    @State private var references = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle(
                "Record engineering memory",
                "Propose a reviewed record in GitHub. Icarus never merges it."
            )
            Text(gap.question)
                .font(.system(size: 15, weight: .semibold))
                .foregroundStyle(Theme.ink)
                .fixedSize(horizontal: false, vertical: true)

            field("Recorded rationale", text: $rationale, prompt: "What decision was made, and why?")
            field("Accepted tradeoffs", text: $tradeoffs, prompt: "What cost or constraint did the team accept?")
            field(
                "Related evidence · one reference per line",
                text: $references,
                prompt: "PR #418\nIncident report\nRFC link"
            )

            switch ledger.recordState {
            case .idle:
                EmptyView()
            case .submitting:
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Creating a branch, Markdown record, and pull request…")
                }
                .font(.system(size: 12)).foregroundStyle(Theme.muted)
            case .succeeded(let url):
                VStack(alignment: .leading, spacing: 6) {
                    Text("Proposal created. The gap stays proposed until the record is merged, the repo is re-read, and a cited answer confirms it.")
                        .font(.system(size: 12)).foregroundStyle(Theme.ink)
                    Link("Open pull request", destination: url)
                        .font(.system(size: 13, weight: .semibold))
                }
            case .failed(let message, let recoveryURL):
                VStack(alignment: .leading, spacing: 6) {
                    Text(message)
                        .font(.system(size: 12)).foregroundStyle(Theme.unknown)
                    if let recoveryURL {
                        Link("Open the recoverable GitHub work", destination: recoveryURL)
                            .font(.system(size: 12, weight: .semibold))
                    }
                }
            }

            HStack {
                Button("Cancel") { dismiss() }
                Spacer()
                Button("Create reviewed memory proposal") {
                    ledger.record(
                        gap: gap,
                        rationale: rationale,
                        tradeoffs: tradeoffs,
                        references: references
                            .split(whereSeparator: \.isNewline)
                            .map { String($0).trimmingCharacters(in: .whitespaces) }
                            .filter { !$0.isEmpty }
                    )
                }
                .buttonStyle(PrimaryButton())
                .disabled(
                    rationale.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                    || !canSubmit
                )
            }
        }
        .padding(24)
        .frame(width: 560)
    }

    private var canSubmit: Bool {
        switch ledger.recordState {
        case .idle, .failed:
            return true
        case .submitting, .succeeded:
            return false
        }
    }

    private func field(
        _ label: String,
        text: Binding<String>,
        prompt: String
    ) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(Theme.mono(10)).foregroundStyle(Theme.muted)
            TextEditor(text: text)
                .font(.system(size: 13))
                .frame(minHeight: 72)
                .overlay(alignment: .topLeading) {
                    if text.wrappedValue.isEmpty {
                        Text(prompt)
                            .font(.system(size: 13))
                            .foregroundStyle(Theme.muted.opacity(0.7))
                            .padding(.horizontal, 5)
                            .padding(.vertical, 8)
                            .allowsHitTesting(false)
                    }
                }
                .overlay(
                    RoundedRectangle(cornerRadius: 6)
                        .stroke(Theme.border, lineWidth: 1)
                )
        }
    }
}

/// Shared surface heading (title + one-line subhead).
@ViewBuilder
func surfaceTitle(_ title: String, _ subhead: String) -> some View {
    VStack(alignment: .leading, spacing: 4) {
        Text(title).font(Theme.display(24, .medium)).foregroundStyle(Theme.ink)
        Text(subhead).font(.system(size: 13)).foregroundStyle(Theme.muted)
    }
}
