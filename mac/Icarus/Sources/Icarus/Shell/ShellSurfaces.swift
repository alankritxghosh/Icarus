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

/// Every real abstention — the product's honesty made a first-class surface.
struct UnknownsView: View {
    let history: AskHistory
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle("Unknowns", "Questions the record couldn't answer. Icarus says so instead of guessing.")
            ShellCard {
                if history.unknowns.isEmpty {
                    Text("No unknowns yet. When a question has no recorded answer, it lands here — honestly.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                } else {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(Array(history.unknowns.enumerated()), id: \.element.id) { i, entry in
                            if i > 0 { Divider().background(Theme.border).padding(.vertical, 14) }
                            HistoryRow(entry: entry)
                        }
                    }
                }
            }
        }
    }
}

/// A true, plain-language statement of the privacy model. Every line must be
/// literally true of this build — no fake compliance badges, no invented tenant.
struct PrivacyBoundaryView: View {
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle("Privacy boundary", "What crosses the line off your machine — and what never does.")
            ShellCard {
                VStack(alignment: .leading, spacing: 14) {
                    claim("Voice: on-device when supported", "Speech is transcribed on-device via Apple Speech when your Mac has the local model — then audio never leaves the machine. When the model isn't installed, Icarus falls back to Apple's speech recognition service so voice works with no setup.")
                    claim("Never trained on", "Retrieved evidence goes to the answering model to write one answer, then is discarded. Your code is never used to train anything.")
                    claim("Shared with your team, nobody else", "A repository is indexed once and shared with the people who can already read it on GitHub. Icarus asks GitHub on every request rather than keeping its own list of who works where — when access is revoked there, it's gone here within five minutes.")
                    claim("Questions are recorded, who asked is not", "Each question, its verdict and its citations are recorded against the repository — that's what builds the list of things nobody wrote down. The asker isn't recorded, and answers aren't stored.")
                    claim("Cite or say \"I don't know\"", "Every answer carries the receipts it's built from. When the record doesn't hold the answer, Icarus says so — it never bluffs.")
                }
            }
        }
    }

    private func claim(_ title: String, _ body: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(.system(size: 15, weight: .semibold)).foregroundStyle(Theme.ink)
            Text(body).font(.system(size: 13)).foregroundStyle(Theme.muted).fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Ask by voice: instructions + a button that opens the overlay (the single ask
/// path). Kept thin in Phase B; a live in-window composer can come later.
struct AskByVoiceView: View {
    let onOpenOverlay: () -> Void
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            surfaceTitle("Ask by voice", "Hold the key, speak your question, hear the answer.")
            ShellCard {
                VStack(alignment: .leading, spacing: 14) {
                    Text("Hold ⌥ (Right Option) anywhere and speak. On release, Icarus answers — and reads it aloud, cited or honestly unknown.")
                        .font(.system(size: 14)).foregroundStyle(Theme.ink).fixedSize(horizontal: false, vertical: true)
                    Text("Prefer to type? Press ⌘⇧I to open the overlay.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                    Button(action: onOpenOverlay) { Text("Open the ask overlay") }.buttonStyle(PrimaryButton())
                }
            }
        }
    }
}

/// Shared surface heading (title + one-line subhead).
@ViewBuilder
func surfaceTitle(_ title: String, _ subhead: String) -> some View {
    VStack(alignment: .leading, spacing: 4) {
        Text(title).font(.system(size: 22, weight: .semibold)).foregroundStyle(Theme.ink)
        Text(subhead).font(.system(size: 13)).foregroundStyle(Theme.muted)
    }
}
