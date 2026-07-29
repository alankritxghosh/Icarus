import SwiftUI
import IcarusKit

/// "Start here": the guided tour of a connected repository.
///
/// Icarus speaks first here, which makes this the highest-risk surface in the
/// app — a claim volunteered gets less scepticism from a reader than one they
/// asked for. So the rules are stricter, not looser:
///
/// - The question Icarus asked on your behalf is always shown. The tour is
///   never a black box you have to trust.
/// - An abstention is rendered in full, in the same amber honest-unknown
///   palette the overlay uses. It is never skipped, softened, or quietly
///   replaced with the next step that happened to work.
/// - A transport failure is rendered as a FAILURE, never as an abstention:
///   "we couldn't reach the brain" and "nobody wrote this down" are opposite
///   claims and only one of them is about the user's code.
/// - The overview step comes from `/map` and needs no writer, so it stays
///   truthful even while the semantic index is still building.
struct OnboardingView: View {
    let status: StatusModel
    let onTryQuestion: () -> Void

    @State private var tour = TourModel(client: AppConfig.client())
    @State private var map: RepoMap?
    @State private var mapError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            header
            if let plan = tour.plan, plan.semanticIndexingInProgress, !plan.note.isEmpty {
                indexingBanner(plan.note)
            }
            if let error = tour.error, tour.plan == nil {
                planFailed(error)
            } else if tour.plan == nil {
                ShellCard { Text("Loading the tour…").font(.system(size: 13)).foregroundStyle(Theme.muted) }
            } else {
                stepper
                currentCard
                footer
            }
        }
        .task { await tour.start() }
        .task { await loadMap() }
    }

    // MARK: header

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text("Start here").font(.system(size: 22, weight: .semibold)).foregroundStyle(Theme.ink)
                Text("A short guided introduction to \(status.repo ?? "this repository") — every claim cited, and an honest \u{201C}nobody wrote this down\u{201D} where the answer was never recorded.")
                    .font(.system(size: 13)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
        }
    }

    private func indexingBanner(_ note: String) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Text("⏳").font(.system(size: 13))
            Text(note).font(.system(size: 12)).foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(12).frame(maxWidth: .infinity, alignment: .leading)
        .background(Theme.unknownBg)
        .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.unknown.opacity(0.5), lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 9))
    }

    private func planFailed(_ message: String) -> some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 8) {
                MonoLabel("COULDN'T LOAD THE TOUR", Theme.unknown)
                Text(message).font(.system(size: 13)).foregroundStyle(Theme.ink)
                Button("Try again") { Task { tourReset(); await tour.start() } }
                    .buttonStyle(PrimaryButton())
            }
        }
    }

    // MARK: the step rail

    private var stepper: some View {
        FlowLayout(spacing: 8) {
            ForEach(Array(tour.steps.enumerated()), id: \.element.id) { index, step in
                let done = tour.answer(for: step.id) != nil || step.kind == .map
                Text("\(index + 1). \(step.title)")
                    .font(Theme.mono(11, index == tour.currentIndex ? .bold : .regular))
                    .foregroundStyle(index == tour.currentIndex ? Theme.cited : (done ? Theme.ink : Theme.muted))
                    .padding(.horizontal, 9).padding(.vertical, 5)
                    .background(index == tour.currentIndex ? Theme.citedBg : Theme.card)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .overlay(RoundedRectangle(cornerRadius: 8)
                        .stroke(index == tour.currentIndex ? Theme.cited : Theme.border, lineWidth: 1))
            }
        }
    }

    // MARK: the current step

    @ViewBuilder private var currentCard: some View {
        if let step = tour.currentStep {
            switch step.kind {
            case .map: overviewCard(step)
            case .question: questionCard(step)
            case .unsupported: unsupportedCard(step)
            }
        }
    }

    private func overviewCard(_ step: OnboardingStep) -> some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(step.title).font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink)
                Text("Read straight from the index — no model involved, so this is exactly as true while Icarus is still reading as it is afterwards.")
                    .font(.system(size: 12)).foregroundStyle(Theme.muted)

                if let mapError {
                    Text(mapError).font(.system(size: 13)).foregroundStyle(Theme.unknown)
                } else if let map {
                    mapBody(map)
                } else {
                    Text("Reading the index…").font(.system(size: 13)).foregroundStyle(Theme.muted)
                }
            }
        }
    }

    @ViewBuilder private func mapBody(_ map: RepoMap) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("\(map.indexedFileCount) files indexed")
                .font(.system(size: 20, weight: .semibold)).foregroundStyle(Theme.ink)

            // Named, not subtracted. A big committed fixture tree makes a repo
            // look like something it is not (348 of 500 files here), and the
            // totals above stay whole because the map's contract is that it
            // describes what Icarus READ.
            if let aux = map.indexedAuxiliary, aux.fileCount > 0 {
                Text("\(aux.fileCount) of those are tests or committed fixtures, counted above.")
                    .font(.system(size: 12)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if !map.languagesByFileCount.isEmpty {
                labelled("LANGUAGES") {
                    FlowLayout(spacing: 6) {
                        ForEach(map.languagesByFileCount.prefix(6), id: \.name) { lang in
                            tag("\(lang.name) · \(lang.files)")
                        }
                    }
                }
            }
            if !map.directoriesByFileCount.isEmpty {
                labelled("TOP-LEVEL FOLDERS") {
                    FlowLayout(spacing: 6) {
                        ForEach(map.directoriesByFileCount.prefix(8), id: \.name) { dir in
                            tag("\(dir.name) · \(dir.files)")
                        }
                    }
                }
            }
            labelled("DOCUMENTATION") {
                if let readme = map.indexedDocumentation.readme {
                    Text("\(readme), and \(map.indexedDocumentation.files.count) documentation file\(map.indexedDocumentation.files.count == 1 ? "" : "s") indexed.")
                        .font(.system(size: 13)).foregroundStyle(Theme.ink)
                } else {
                    // Stated, never silent: "no README was indexed" is a fact
                    // about the corpus and the user is entitled to know it.
                    Text("No README was indexed for this repository.")
                        .font(.system(size: 13)).foregroundStyle(Theme.unknown)
                }
            }
            labelled("WHERE TO START READING") {
                if map.indexedEntryPoints.isEmpty {
                    Text("No rule matched an entry point here, so Icarus isn't guessing at one.")
                        .font(.system(size: 13)).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    VStack(alignment: .leading, spacing: 8) {
                        ForEach(map.indexedEntryPoints.prefix(5)) { entry in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(entry.path).font(Theme.mono(12, .bold)).foregroundStyle(Theme.cited)
                                ForEach(entry.rules) { rule in
                                    // The RULE is shown, always. An entry point
                                    // without its reason is an opaque score,
                                    // which is exactly what this product refuses.
                                    Text("— \(rule.detail)")
                                        .font(.system(size: 12)).foregroundStyle(Theme.muted)
                                        .fixedSize(horizontal: false, vertical: true)
                                }
                            }
                        }
                    }
                }
            }
            if map.corpusTruncated {
                Text("⚠ This repo hit the index size cap, so some files aren't covered.")
                    .font(.system(size: 12)).foregroundStyle(Theme.unknown)
            }
            ForEach(map.limitations, id: \.self) { line in
                Text(line).font(.system(size: 11)).foregroundStyle(Theme.muted)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private func questionCard(_ step: OnboardingStep) -> some View {
        ShellCard {
            VStack(alignment: .leading, spacing: 12) {
                Text(step.title).font(.system(size: 16, weight: .semibold)).foregroundStyle(Theme.ink)
                if let question = step.question {
                    // Shown on purpose: the user can always see the exact
                    // question Icarus asked on their behalf.
                    Text("Icarus asked: \u{201C}\(question)\u{201D}")
                        .font(.system(size: 12)).foregroundStyle(Theme.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if let error = tour.error {
                    VStack(alignment: .leading, spacing: 8) {
                        MonoLabel("COULDN'T ANSWER THIS STEP", Theme.unknown)
                        Text(error).font(.system(size: 13)).foregroundStyle(Theme.ink)
                        Button("Try again") { Task { await tour.retry() } }.buttonStyle(PrimaryButton())
                    }
                } else if tour.isLoading {
                    Text("Reading…").font(.system(size: 13)).foregroundStyle(Theme.muted)
                } else if let answer = tour.answer(for: step.id) {
                    answerBody(answer.response)
                }
            }
        }
    }

    @ViewBuilder private func answerBody(_ response: AskResponse) -> some View {
        if response.verdict == .answer {
            VStack(alignment: .leading, spacing: 10) {
                Text(response.answer).font(.system(size: 14)).foregroundStyle(Theme.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if !response.citations.isEmpty {
                    labelled("RECEIPTS") {
                        FlowLayout(spacing: 6) {
                            ForEach(response.citations) { CitationChip(citation: $0) }
                        }
                    }
                }
            }
        } else {
            VStack(alignment: .leading, spacing: 8) {
                // The SAME two-way split the overlay and proof drawer make:
                // "I haven't finished reading" is a claim about ICARUS,
                // "no one wrote this down" is a claim about the REPOSITORY.
                // Rendering the first as the second is the bug that shipped on
                // facebook/react (2026-07-29) and it must not come back here.
                if let note = response.incompleteIndexNote {
                    MonoLabel("STILL INDEXING", Theme.unknown)
                    Text(note).font(.system(size: 14)).foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                } else {
                    MonoLabel("NO ONE WROTE THIS DOWN", Theme.unknown)
                    Text("Icarus found nothing recorded that answers this. That is the honest answer, not a failure to search — it looked at \(response.searched.count) source\(response.searched.count == 1 ? "" : "s").")
                        .font(.system(size: 14)).foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(12).frame(maxWidth: .infinity, alignment: .leading)
            .background(Theme.unknownBg)
            .overlay(RoundedRectangle(cornerRadius: 9).stroke(Theme.unknown.opacity(0.5), lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 9))
        }
    }

    private func unsupportedCard(_ step: OnboardingStep) -> some View {
        ShellCard {
            Text("\u{201C}\(step.title)\u{201D} needs a newer version of the app than this one.")
                .font(.system(size: 13)).foregroundStyle(Theme.muted)
        }
    }

    // MARK: footer

    private var footer: some View {
        HStack(spacing: 12) {
            Button("Back") { Task { await tour.back() } }
                .buttonStyle(.plain).disabled(tour.currentIndex == 0)
                .foregroundStyle(tour.currentIndex == 0 ? Theme.muted : Theme.ink)
            if tour.isOnLastStep {
                Button("Done — ask anything", action: onTryQuestion).buttonStyle(PrimaryButton())
            } else {
                Button("Next") { Task { await tour.next() } }.buttonStyle(PrimaryButton())
            }
            Spacer()
            // Interrupting costs nothing: the tour holds no session, so the
            // step you were on is still there when you come back.
            Button("Ask your own question", action: onTryQuestion).buttonStyle(.plain)
                .foregroundStyle(Theme.muted).font(.system(size: 12))
        }
    }

    // MARK: helpers

    private func labelled<C: View>(_ label: String, @ViewBuilder content: () -> C) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            MonoLabel(label)
            content()
        }
    }

    private func tag(_ text: String) -> some View {
        Text(text).font(Theme.mono(11))
            .foregroundStyle(Theme.ink)
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background(Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.border, lineWidth: 1))
    }

    private func tourReset() {
        tour = TourModel(client: AppConfig.client())
    }

    private func loadMap() async {
        guard map == nil else { return }
        let client = AppConfig.client()
        do {
            map = try await client.repoMap()
            mapError = nil
        } catch let error as BrainError {
            mapError = error.userMessage
        } catch {
            mapError = "Couldn't read the index. Check Icarus's brain is running."
        }
    }
}
