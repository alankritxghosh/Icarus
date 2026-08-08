import SwiftUI
import IcarusKit

/// The Investigate surface: a multi-step, evidence-backed answer, and the trail
/// that produced it.
///
/// The layout follows one rule the rest of the shell does not need: findings are
/// grouped by **what kind of evidence they cite**, under headings that say so.
/// Presenting a finding that cites recorded rationale and one drawn from code
/// alone in the same voice is a bluff the honesty gate structurally cannot
/// catch, because the citations under both are just as real.
///
/// The headings describe the EVIDENCE, never entailment: marker matching proves
/// a cited chunk records some reason, not that it is the reason for this
/// finding (see IcarusKit.Support). The class is computed server-side; nothing
/// here upgrades it.
///
/// Two things are shown even when it would be tidier not to: what is still
/// unknown, and the fact that an investigation stopped early. A conclusion that
/// hides its gaps is worse than a short one.
struct InvestigationView: View {
    let model: InvestigationModel
    @State private var question: String = ""

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            header
            askBox
            if case let .failed(message) = model.state { transportFailure(message) }
            ForEach(model.turns) { turn in
                turnView(turn)
            }
            if model.turns.isEmpty && model.state == .idle { emptyState }
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Investigate").font(.system(size: 26, weight: .semibold))
                .foregroundStyle(Theme.ink)
            Text("Icarus follows the evidence — the pull request, its linked "
                 + "issues, the code it changed, and what happened afterwards — "
                 + "and shows you every step it took.")
                .font(.system(size: 14)).foregroundStyle(Theme.muted)
        }
    }

    private var askBox: some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 12) {
                TextField("Why was PR #400 introduced?", text: $question)
                    .textFieldStyle(.plain)
                    .font(.system(size: 15))
                    .disabled(model.isBusy)
                    .onSubmit(submit)
                HStack(spacing: 10) {
                    Button(model.turns.isEmpty ? "Investigate" : "Ask a follow-up",
                           action: submit)
                        .buttonStyle(PrimaryButton())
                        .disabled(model.isBusy || question.trimmingCharacters(
                            in: .whitespacesAndNewlines).isEmpty)
                    if !model.turns.isEmpty {
                        Button("Start over") { model.startOver() }
                            .buttonStyle(.plain)
                            .font(Theme.mono(12))
                            .foregroundStyle(Theme.muted)
                    }
                    if model.isBusy {
                        Text("investigating…").font(Theme.mono(12))
                            .foregroundStyle(Theme.muted)
                    }
                    Spacer()
                    if !model.turns.isEmpty {
                        // A follow-up says "it" and means something specific.
                        // Showing what that resolved to is how a reader catches
                        // a misunderstanding BEFORE reading a confident answer
                        // about the wrong change.
                        subjectLabel
                    }
                }
            }
        }
    }

    @ViewBuilder private var subjectLabel: some View {
        if let subject = model.latest?.response.trace.subject, !subject.isEmpty {
            Text("about \(subject.joined(separator: ", "))")
                .font(Theme.mono(12)).foregroundStyle(Theme.muted)
        }
    }

    private var emptyState: some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 8) {
                MonoLabel("NOTHING INVESTIGATED YET")
                Text("Ask about a change — \"talk to me about PR #400\" — then "
                     + "follow up with \"why did it change?\" or \"what did it "
                     + "affect?\". Icarus keeps track of what you're asking about.")
                    .font(.system(size: 14)).foregroundStyle(Theme.muted)
            }
        }
    }

    private func transportFailure(_ message: String) -> some View {
        // Deliberately NOT styled as an honest unknown. A failure to reach the
        // brain and "no one wrote this down" mean opposite things.
        ShellCard {
            VStack(alignment: .leading, spacing: 6) {
                MonoLabel("COULDN'T INVESTIGATE", Theme.unknown)
                Text(message).font(.system(size: 14)).foregroundStyle(Theme.ink)
            }
        }
    }

    @ViewBuilder private func turnView(_ turn: InvestigationModel.Turn) -> some View {
        let trace = turn.response.trace
        let answer = turn.response.answer
        VStack(alignment: .leading, spacing: 14) {
            Text(turn.question).font(.system(size: 16, weight: .semibold))
                .foregroundStyle(Theme.ink)

            if answer.verdict == .answer {
                ShellCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text(answer.answer).font(.system(size: 15)).foregroundStyle(Theme.ink)
                        if !answer.citations.isEmpty {
                            MonoLabel("RECEIPTS", Theme.cited)
                            FlowLayout(spacing: 6) {
                                ForEach(answer.citations) { CitationChip(citation: $0) }
                            }
                        }
                    }
                }
            } else {
                ShellCard {
                    VStack(alignment: .leading, spacing: 6) {
                        MonoLabel(answer.unknownHeadline, Theme.unknown)
                        Text(answer.unknownMessage)
                            .font(.system(size: 15)).foregroundStyle(Theme.ink)
                    }
                }
            }

            if trace.needsCaveat { caveats(trace) }
            if !trace.findings.isEmpty { findings(trace) }
            if !trace.unknowns.isEmpty { unknowns(trace) }
            trail(trace)
        }
    }

    /// What a reader must be told beyond the answer: it was cut short, or the
    /// evidence disagrees with itself. Placed ABOVE the findings on purpose —
    /// after them it reads as a footnote to a conclusion already accepted.
    private func caveats(_ trace: InvestigationTrace) -> some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 8) {
                if let incomplete = trace.incompleteBecause {
                    MonoLabel("INCOMPLETE", Theme.unknown)
                    Text("This investigation stopped early: it \(incomplete). "
                         + "There may be evidence it never looked at.")
                        .font(.system(size: 14)).foregroundStyle(Theme.ink)
                }
                ForEach(trace.contradictions) { conflict in
                    MonoLabel("CONFLICTING EVIDENCE", Theme.unknown)
                    Text("The repository disagrees with itself about: \(conflict.about)")
                        .font(.system(size: 14)).foregroundStyle(Theme.ink)
                }
            }
        }
    }

    private func findings(_ trace: InvestigationTrace) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(trace.findingsBySupport, id: \.support) { group in
                ShellCard {
                    VStack(alignment: .leading, spacing: 10) {
                        MonoLabel(group.support.headline.uppercased(),
                                  group.support.citesRecordedReason ? Theme.cited : Theme.muted)
                        ForEach(group.findings) { finding in
                            VStack(alignment: .leading, spacing: 6) {
                                Text(finding.text).font(.system(size: 14))
                                    .foregroundStyle(Theme.ink)
                                if !finding.citations.isEmpty {
                                    FlowLayout(spacing: 6) {
                                        ForEach(finding.citations) {
                                            CitationChip(citation: $0)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    private func unknowns(_ trace: InvestigationTrace) -> some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 8) {
                MonoLabel("STILL UNKNOWN", Theme.unknown)
                ForEach(trace.unknowns, id: \.self) { unknown in
                    Text("— " + unknown).font(.system(size: 14))
                        .foregroundStyle(Theme.muted)
                }
            }
        }
    }

    /// The step trail. This is the product: not only what Icarus concluded, but
    /// how the repository led it there.
    private func trail(_ trace: InvestigationTrace) -> some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 8) {
                MonoLabel("HOW IT GOT THERE")
                ForEach(trace.trail) { step in
                    HStack(alignment: .top, spacing: 12) {
                        Text(step.summary).font(Theme.mono(12))
                            .foregroundStyle(Theme.ink)
                            .frame(width: 320, alignment: .leading)
                        Text(step.reason).font(Theme.mono(12))
                            .foregroundStyle(Theme.muted)
                        Spacer(minLength: 0)
                    }
                }
                if let stopped = trace.stoppedBecause {
                    Text("stopped: \(stopped)").font(Theme.mono(12))
                        .foregroundStyle(Theme.muted).padding(.top, 4)
                }
            }
        }
    }

    private func submit() {
        guard !model.isBusy else { return }
        model.investigate(question)
        question = ""
    }
}
