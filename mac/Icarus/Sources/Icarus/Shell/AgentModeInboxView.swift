import SwiftUI
import AppKit
import IcarusKit

/// Low-friction confirmation for one atomic agent recommendation at a time.
/// The normal path is one click; text is required only when the person chooses
/// Other because the model's proposed intent was wrong.
struct AgentModeInboxView: View {
    let model: DecisionInboxModel
    @State private var setupMessage: String?
    @State private var setupFailed = false

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .top, spacing: 12) {
                surfaceTitle(
                    "Agent Mode confirmations",
                    "Review choices your coding agent made. Nothing becomes project intent without you."
                )
                Spacer(minLength: 12)
                Button("Refresh") { model.load() }
                    .buttonStyle(.plain)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Theme.accent)
                    .disabled(model.state == .loading)
            }
            if let repo = loadedRepo {
                ShellCard {
                    HStack(alignment: .top, spacing: 14) {
                        VStack(alignment: .leading, spacing: 5) {
                            MonoLabel("EXPLICIT SESSION OBSERVATION", Theme.accent)
                            Text("Enable Claude Agent Mode for one local checkout of \(repo).")
                                .font(.system(size: 12)).foregroundStyle(Theme.ink)
                            Text("Icarus checks the local session for capture-tool use, but sends and stores only structured candidates—not the raw transcript.")
                                .font(.system(size: 11)).foregroundStyle(Theme.muted)
                                .fixedSize(horizontal: false, vertical: true)
                            if let setupMessage {
                                Text(setupMessage)
                                    .font(.system(size: 11))
                                    .foregroundStyle(setupFailed ? Theme.unknown : Theme.accent)
                            }
                        }
                        Spacer(minLength: 12)
                        Button("Choose Claude project…") { enable(repo: repo) }
                            .buttonStyle(PrimaryButton())
                    }
                }
            }
            if let outcome = model.latestOutcome {
                ShellCard {
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 5) {
                            MonoLabel("CONFIRMATION SAVED", Theme.accent)
                            Text(outcome.message)
                                .font(.system(size: 12)).foregroundStyle(Theme.ink)
                            if let url = outcome.pullRequestURL {
                                Link("Open review proposal", destination: url)
                                    .font(.system(size: 12, weight: .semibold))
                            }
                        }
                        Spacer()
                        Button("Dismiss") { model.dismissOutcome() }
                            .buttonStyle(.plain)
                            .font(.system(size: 11))
                            .foregroundStyle(Theme.muted)
                    }
                }
            }
            switch model.state {
            case .idle, .loading:
                ShellCard {
                    Text("Reading decision candidates…")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                }
            case .failed(let message):
                ShellCard {
                    VStack(alignment: .leading, spacing: 7) {
                        MonoLabel("COULDN'T LOAD", Theme.unknown)
                        Text(message).font(.system(size: 13)).foregroundStyle(Theme.ink)
                    }
                }
            case .loaded(let repo, let candidates) where candidates.isEmpty:
                ShellCard {
                    VStack(alignment: .leading, spacing: 6) {
                        MonoLabel("AGENT MODE · \(repo.uppercased())", Theme.accent)
                        Text("No decisions need confirmation.")
                            .font(.system(size: 13)).foregroundStyle(Theme.ink)
                        Text("Icarus does not treat this as proof that the project has no decisions.")
                            .font(.system(size: 11)).foregroundStyle(Theme.muted)
                    }
                }
            case .loaded(let repo, let candidates):
                VStack(alignment: .leading, spacing: 12) {
                    MonoLabel(
                        "AGENT MODE · \(repo.uppercased()) · \(candidates.count) PENDING",
                        Theme.unknown
                    )
                    ForEach(candidates) { candidate in
                        DecisionCandidateCard(model: model, candidate: candidate)
                    }
                }
            }
        }
        .onAppear { model.load() }
    }

    private var loadedRepo: String? {
        if case .loaded(let repo, _) = model.state { return repo }
        return nil
    }

    private func enable(repo: String) {
        let panel = NSOpenPanel()
        panel.title = "Enable Icarus Agent Mode"
        panel.message = "Choose the local checkout for \(repo). Icarus will merge project-local Claude MCP and hook settings."
        panel.prompt = "Enable Agent Mode"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK,
              let project = panel.url,
              let executable = Bundle.main.executableURL else { return }
        do {
            let result = try ClaudeAgentModeInstaller.install(
                project: project, repo: repo, executable: executable)
            setupFailed = false
            setupMessage = result.changed
                ? "Enabled for this checkout. Start a fresh Claude session."
                : "Already enabled for this checkout."
        } catch let error as ClaudeAgentModeInstaller.InstallError {
            setupFailed = true
            setupMessage = error.message
        } catch {
            setupFailed = true
            setupMessage = "Icarus could not update this project's Claude settings."
        }
    }
}

private struct DecisionCandidateCard: View {
    let model: DecisionInboxModel
    let candidate: DecisionCandidate
    @State private var showOther = false
    @State private var otherText = ""

    var body: some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 14) {
                MonoLabel("AGENT RECOMMENDATION · NOT PROJECT TRUTH", Theme.unknown)
                VStack(alignment: .leading, spacing: 5) {
                    Text(candidate.decision)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(candidate.rationale)
                        .font(.system(size: 12)).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Button("Accept recommendation") {
                    model.confirm(candidate, selection: .recommended)
                }
                .buttonStyle(PrimaryButton())
                .disabled(model.isSubmitting(candidate.id))

                if !candidate.alternatives.isEmpty {
                    VStack(alignment: .leading, spacing: 7) {
                        Text("Or choose one")
                            .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                        ForEach(Array(candidate.alternatives.enumerated()), id: \.offset) { index, alternative in
                            Button {
                                model.confirm(candidate, selection: .alternative(index))
                            } label: {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(alternative.decision)
                                        .font(.system(size: 13, weight: .semibold))
                                        .foregroundStyle(Theme.ink)
                                    Text(alternative.rationale)
                                        .font(.system(size: 11)).foregroundStyle(Theme.muted)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .padding(10)
                                .background(Theme.surface)
                                .overlay(RoundedRectangle(cornerRadius: 7)
                                    .stroke(Theme.border, lineWidth: 1))
                            }
                            .buttonStyle(.plain)
                            .disabled(model.isSubmitting(candidate.id))
                        }
                    }
                }

                HStack(spacing: 14) {
                    Button("Other") { showOther.toggle() }
                        .buttonStyle(.plain)
                        .font(.system(size: 12, weight: .semibold))
                    Button("Not sure") {
                        model.confirm(candidate, selection: .notSure)
                    }
                    .buttonStyle(.plain)
                    .font(.system(size: 12, weight: .semibold))
                    Spacer()
                    if model.isSubmitting(candidate.id) {
                        ProgressView().controlSize(.small)
                    }
                }
                .foregroundStyle(Theme.muted)

                if showOther {
                    HStack(spacing: 8) {
                        TextField("What intent should Icarus preserve?", text: $otherText)
                            .textFieldStyle(.roundedBorder)
                        Button("Use this intent") {
                            model.confirm(candidate, selection: .other(otherText))
                        }
                        .buttonStyle(PrimaryButton())
                        .disabled(
                            otherText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                            || model.isSubmitting(candidate.id)
                        )
                    }
                }

                if !candidate.affectedPaths.isEmpty {
                    Text("Affects: " + candidate.affectedPaths.joined(separator: " · "))
                        .font(Theme.mono(10)).foregroundStyle(Theme.muted)
                        .lineLimit(2)
                }
                if case .failed(let message, let recoveryURL) = model.confirmation[candidate.id] {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(message).font(.system(size: 11)).foregroundStyle(Theme.unknown)
                        if let recoveryURL {
                            Link("Open recoverable GitHub work", destination: recoveryURL)
                                .font(.system(size: 11, weight: .semibold))
                        }
                    }
                }
            }
        }
    }
}
