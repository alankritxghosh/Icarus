import XCTest
@testable import IcarusKit

/// Decode the brain's REAL responses, byte for byte.
///
/// Every other decoding test in this suite reads a hand-written fixture, which
/// proves the decoder is self-consistent and proves nothing about the server.
/// A renamed key, a field that turns out to be null in practice, or a shape
/// that only appears on a real repository would pass all of them and fail in a
/// user's hands — silently, because a decode failure surfaces as "couldn't
/// reach the brain", which reads like a network problem.
///
/// The fixtures in `Fixtures/` were captured from a running brain
/// (`python3 -m demo.server`) connected to `simonw/sqlite-utils`, on
/// 2026-07-29, by curling the four endpoints the tour depends on. Re-capture
/// them the same way if the payload shape ever changes deliberately; do not
/// hand-edit them, because their whole value is that no human wrote them.
final class BrainContractTests: XCTestCase {

    private func fixture(_ name: String) throws -> Data {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent()
            .appendingPathComponent("Fixtures/\(name).json")
        return try Data(contentsOf: url)
    }

    // MARK: the tour plan

    func testTheRealPlanDecodes() throws {
        let plan = try JSONDecoder().decode(OnboardingPlan.self, from: fixture("plan"))
        XCTAssertEqual(plan.repo, "simonw/sqlite-utils")
        XCTAssertEqual(plan.steps.map(\.id),
                       ["overview", "purpose", "stack", "decisions", "conventions", "recent"])
    }

    func testTheRealPlanOpensWithAWriterFreeStep() throws {
        // The overview needs no retrieval, so it stays true while the index is
        // still building -- which is exactly when a first-time user sees it.
        let plan = try JSONDecoder().decode(OnboardingPlan.self, from: fixture("plan"))
        XCTAssertEqual(plan.steps.first?.kind, .map)
        XCTAssertEqual(plan.steps.dropFirst().map(\.kind), Array(repeating: .question, count: 5))
    }

    func testEveryRealQuestionStepShowsTheQuestionItAsks() throws {
        // The tour is never a black box: the user can always read the exact
        // question Icarus asked on their behalf.
        let plan = try JSONDecoder().decode(OnboardingPlan.self, from: fixture("plan"))
        for step in plan.steps where step.kind == .question {
            XCTAssertFalse(step.question?.isEmpty ?? true, step.id)
            XCTAssertFalse(step.title.isEmpty, step.id)
        }
    }

    // MARK: the repository map

    func testTheRealMapDecodes() throws {
        let map = try JSONDecoder().decode(RepoMap.self, from: fixture("map"))
        XCTAssertEqual(map.repo, "simonw/sqlite-utils")
        XCTAssertGreaterThan(map.indexedFileCount, 0)
        XCTAssertFalse(map.indexedLanguages.isEmpty)
        XCTAssertFalse(map.limitations.isEmpty)
        XCTAssertFalse(map.exclusionRules.isEmpty)
    }

    func testTheRealMapNeverPublishesARepositoryTotal() throws {
        // The map describes what Icarus READ. If the brain ever starts sending
        // a total-file or excluded-file count, this app must not have been
        // silently rendering it as though Icarus had observed it.
        let raw = try JSONSerialization.jsonObject(with: fixture("map")) as? [String: Any]
        let keys = Set(raw?.keys ?? [:].keys)
        for forbidden in ["total_files", "total_file_count", "excluded_files",
                          "excluded_file_count", "repository_file_count"] {
            XCTAssertFalse(keys.contains(forbidden), forbidden)
        }
    }

    func testEveryRealEntryPointCarriesItsRule() throws {
        // An entry point without its reason is an opaque score, which is the
        // one thing this product refuses to render.
        let map = try JSONDecoder().decode(RepoMap.self, from: fixture("map"))
        for entry in map.indexedEntryPoints {
            XCTAssertFalse(entry.path.isEmpty)
            XCTAssertFalse(entry.rules.isEmpty, entry.path)
            for rule in entry.rules {
                XCTAssertFalse(rule.rule.isEmpty)
                XCTAssertFalse(rule.detail.isEmpty)
            }
        }
    }

    // MARK: a real answered step, and a real abstention

    func testARealAnsweredStepDecodesWithItsCitations() throws {
        let step = try JSONDecoder().decode(TourStepAnswer.self, from: fixture("step_answer"))
        XCTAssertEqual(step.step, "purpose")
        XCTAssertEqual(step.response.verdict, .answer)
        XCTAssertFalse(step.response.answer.isEmpty)
        XCTAssertFalse(step.response.citations.isEmpty)
    }

    func testTheRealPurposeStepCitesTheRepositorysOwnReadme() throws {
        // The measured fix (2/10 -> 10/10 across ten repos): `purpose` reads
        // the README instead of searching for it. If that regressed, this
        // citation would come back from history instead.
        let step = try JSONDecoder().decode(TourStepAnswer.self, from: fixture("step_answer"))
        XCTAssertTrue(step.response.citations.contains { $0.ref.hasPrefix("doc:") },
                      step.response.citations.map(\.ref).joined(separator: ", "))
    }

    func testARealAbstentionDecodesAsAnHonestUnknown() throws {
        let step = try JSONDecoder().decode(TourStepAnswer.self, from: fixture("step_unknown"))
        XCTAssertEqual(step.response.verdict, .unknown)
        XCTAssertTrue(step.response.answer.isEmpty)
        XCTAssertTrue(step.response.citations.isEmpty)
        // The searched trail is what makes an abstention transparent rather
        // than a shrug -- it must survive the wire.
        XCTAssertFalse(step.response.searched.isEmpty)
    }

    func testARealAbstentionWithACompleteIndexCarriesNoStillIndexingCaveat() throws {
        // Both are abstentions on the wire and they mean opposite things: one
        // is a claim about the user's repository, the other about Icarus.
        let step = try JSONDecoder().decode(TourStepAnswer.self, from: fixture("step_unknown"))
        XCTAssertEqual(step.response.indexing, false)
        XCTAssertNil(step.response.incompleteIndexNote)
    }

    // MARK: an investigation

    /// `investigation.json` was captured on 2026-08-08 from the REAL engine --
    /// the committed `simonw/llm` corpus, real retrieval, and the production
    /// `gemini-paid` writer -- by running `Why was PR #1525 introduced?` through
    /// `investigate()`/`conclude()` and `demo.payload.build_investigation_payload`,
    /// the exact function `POST /investigate` returns. No human wrote it, which
    /// is the entire point.
    func testTheRealInvestigationDecodes() throws {
        let response = try JSONDecoder().decode(InvestigationResponse.self,
                                                from: fixture("investigation"))
        XCTAssertEqual(response.answer.verdict, .answer)
        XCTAssertFalse(response.answer.answer.isEmpty)
        XCTAssertEqual(response.trace.subject, ["pr:1525"])
        XCTAssertFalse(response.trace.findings.isEmpty)
        XCTAssertFalse(response.trace.trail.isEmpty)
    }

    /// Every finding the real engine published carries a support class the app
    /// recognises. An unrecognised one renders in the most cautious voice, so a
    /// silent drift here would quietly understate real findings forever.
    func testEveryRealFindingCarriesARecognisedSupportClass() throws {
        let response = try JSONDecoder().decode(InvestigationResponse.self,
                                                from: fixture("investigation"))
        for finding in response.trace.findings {
            XCTAssertNotEqual(finding.support, .unrecognised, finding.text)
        }
    }

    /// The real trail names real primitives from the closed vocabulary. If the
    /// server ever emitted something else, the summary line would render a bare
    /// primitive name and nobody would notice.
    func testTheRealTrailUsesTheClosedPrimitiveVocabulary() throws {
        let response = try JSONDecoder().decode(InvestigationResponse.self,
                                                from: fixture("investigation"))
        let allowed: Set<String> = ["retrieve", "inspect", "trace", "compare", "verify"]
        for step in response.trace.trail {
            XCTAssertTrue(allowed.contains(step.primitive), step.primitive)
            XCTAssertFalse(step.summary.isEmpty)
        }
    }

    /// The captured run really did stop on a budget ceiling, and the app must
    /// surface that -- a truncated investigation presented as a complete one is
    /// the same class of failure as a bluffed citation.
    func testARealBudgetTruncationSurvivesIntoTheCaveat() throws {
        let response = try JSONDecoder().decode(InvestigationResponse.self,
                                                from: fixture("investigation"))
        XCTAssertNotNil(response.trace.incompleteBecause)
        XCTAssertTrue(response.trace.needsCaveat)
    }
}
