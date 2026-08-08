import XCTest
@testable import IcarusKit

/// Decoding and display rules for an investigation.
///
/// The load-bearing tests are the ones that keep the app from making a finding
/// look stronger than the server said it was. Every citation under an inference
/// is just as real as one under a quoted reason, so the honesty gate cannot
/// catch a client that renders them alike — only these can.
final class InvestigationTests: XCTestCase {

    private func decode(_ json: String) throws -> InvestigationResponse {
        try JSONDecoder().decode(InvestigationResponse.self, from: Data(json.utf8))
    }

    private func payload(findings: String = "[]") -> String {
        """
        {"repo":"simonw/llm","commit":"94769b8","verdict":"answer",
         "answer":"Because retrieval degraded.",
         "citations":[{"ref":"pr:1525","url":"https://github.com/simonw/llm/pull/1525"}],
         "searched":["pr:1525"],"anchored":["pr:1525"],"indexing":false,"reason":null,
         "investigation":{"objective":"Why was PR #1525 introduced?",
          "subject":["pr:1525"],"findings":\(findings),
          "hypotheses":[{"statement":"it fixed a bug","status":"supported"}],
          "unknowns":[],"contradictions":[],
          "trail":[{"step":"a1","primitive":"inspect","args":{"ref":"pr:1525"},
                    "reason":"read the subject itself"}],
          "stopped_because":"nothing left to investigate",
          "incomplete_because":null}}
        """
    }

    private let oneExplicit = """
        [{"text":"It fixed a transaction bug.","support":"explicit",
          "citations":[{"ref":"pr:1525","url":"https://github.com/simonw/llm/pull/1525"}]}]
        """

    // MARK: - the answer stays an ordinary answer

    func testTheAnswerDecodesThroughTheEXISTINGAskResponse() throws {
        // The trace is additive. If the answer needed its own decoding path,
        // there would be two ways to render a verdict and they would drift.
        let response = try decode(payload(findings: oneExplicit))
        XCTAssertEqual(response.answer.verdict, .answer)
        XCTAssertEqual(response.answer.citations.first?.ref, "pr:1525")
        XCTAssertEqual(response.answer.anchored, ["pr:1525"])
    }

    func testTheSubjectIsExposedSoAFollowUpCanBeSeenToBeUnderstood() throws {
        XCTAssertEqual(try decode(payload(findings: oneExplicit)).trace.subject, ["pr:1525"])
    }

    // MARK: - support classes

    func testEachSupportClassDescribesTheEVIDENCECited() {
        // These describe what was CITED, never what the repository asserts.
        XCTAssertEqual(Support.explicit.headline, "Cites evidence that records a reason")
        XCTAssertEqual(Support.weak.headline,
                       "Cites one piece of evidence, or code alone")
        XCTAssertTrue(Support.explicit.citesRecordedReason)
        XCTAssertFalse(Support.strong.citesRecordedReason)
        XCTAssertFalse(Support.weak.citesRecordedReason)
    }

    /// The conscience test for the UI's half of the honesty boundary.
    ///
    /// Marker matching proves a cited chunk records SOME reason. It cannot
    /// prove that reason is the reason for this finding -- evidence reading
    /// "changed because logging was noisy" under a finding about database
    /// scalability is indistinguishable to it. AGENTS.md places that entailment
    /// outside what the deterministic path proves, so no wording here may
    /// assert the repository states the finding.
    func testNoSupportWordingClaimsTheRepositoryASSERTSTheFinding() {
        let banned = ["states this", "proves", "confirms", "guarantees",
                      "establishes this", "verified by the repository"]
        for support: Support in [.explicit, .strong, .weak, .unsupported, .unrecognised] {
            let headline = support.headline.lowercased()
            for phrase in banned {
                XCTAssertFalse(headline.contains(phrase),
                               "\(support.rawValue): \(support.headline)")
            }
        }
    }

    /// The wording must MIRROR evals/investigation.py's SUPPORT_HEADLINES.
    /// Two surfaces describing the same class differently is how one of them
    /// quietly starts claiming more than the other.
    func testTheWordingMirrorsTheServersCanonicalHeadlines() {
        XCTAssertEqual(Support.explicit.headline, "Cites evidence that records a reason")
        XCTAssertEqual(Support.strong.headline, "Cites several independent kinds of evidence")
        XCTAssertEqual(Support.weak.headline, "Cites one piece of evidence, or code alone")
        XCTAssertEqual(Support.unsupported.headline, "Not backed by evidence Icarus retrieved")
    }

    func testAnUnrecognisedSupportClassDecodesToTheMostCautiousVoice() throws {
        // A newer brain adding a class must not make an older app unable to
        // show the answer -- and must never be rendered as the boldest one.
        let findings = """
            [{"text":"Something new.","support":"overwhelming","citations":[]}]
            """
        let trace = try decode(payload(findings: findings)).trace
        XCTAssertEqual(trace.findings.first?.support, .unrecognised)
        XCTAssertFalse(trace.findings.first!.support.citesRecordedReason)
    }

    func testWhatTheRepositoryRECORDSIsOrderedBeforeWhatWasInferred() throws {
        let findings = """
            [{"text":"inferred","support":"weak","citations":[]},
             {"text":"corroborated","support":"strong","citations":[]},
             {"text":"recorded","support":"explicit","citations":[]}]
            """
        let trace = try decode(payload(findings: findings)).trace
        XCTAssertEqual(trace.orderedFindings.map(\.text),
                       ["recorded", "corroborated", "inferred"])
    }

    func testFindingsAreGroupedSoKnownAndInferredAreNeverOneList() throws {
        let findings = """
            [{"text":"a","support":"explicit","citations":[]},
             {"text":"b","support":"weak","citations":[]},
             {"text":"c","support":"explicit","citations":[]}]
            """
        let groups = try decode(payload(findings: findings)).trace.findingsBySupport
        XCTAssertEqual(groups.map(\.support), [.explicit, .weak])
        XCTAssertEqual(groups[0].findings.map(\.text), ["a", "c"])
    }

    func testOrderingIsStableWithinASupportClass() throws {
        // The order the investigation found them in is meaningful; reshuffling
        // it on every render would make the same answer look different twice.
        let findings = """
            [{"text":"first","support":"weak","citations":[]},
             {"text":"second","support":"weak","citations":[]},
             {"text":"third","support":"weak","citations":[]}]
            """
        let trace = try decode(payload(findings: findings)).trace
        XCTAssertEqual(trace.orderedFindings.map(\.text), ["first", "second", "third"])
    }

    // MARK: - what a reader must be told

    func testATruncatedInvestigationIsFlaggedAsNeedingACaveat() throws {
        let json = payload(findings: oneExplicit).replacingOccurrences(
            of: "\"incomplete_because\":null",
            with: "\"incomplete_because\":\"reached the maximum number of investigation steps\"")
        let trace = try decode(json).trace
        XCTAssertTrue(trace.needsCaveat)
        XCTAssertEqual(trace.incompleteBecause,
                       "reached the maximum number of investigation steps")
    }

    func testACompleteInvestigationNeedsNoCaveat() throws {
        XCTAssertFalse(try decode(payload(findings: oneExplicit)).trace.needsCaveat)
    }

    func testConflictingEvidenceAlsoDemandsACaveat() throws {
        let json = payload(findings: oneExplicit).replacingOccurrences(
            of: "\"contradictions\":[]",
            with: "\"contradictions\":[{\"claims\":[\"c1\",\"c2\"],"
                + "\"about\":\"it was a scalability change\"}]")
        let trace = try decode(json).trace
        XCTAssertTrue(trace.needsCaveat)
        XCTAssertEqual(trace.contradictions.first?.about, "it was a scalability change")
    }

    // MARK: - the trail

    func testAStepRendersWhatItActuallyDid() throws {
        let json = payload(findings: oneExplicit).replacingOccurrences(
            of: "\"primitive\":\"inspect\",\"args\":{\"ref\":\"pr:1525\"}",
            with: "\"primitive\":\"trace\","
                + "\"args\":{\"ref\":\"pr:1525\",\"edge\":\"linked_issues\"}")
        let step = try decode(json).trace.trail.first
        XCTAssertEqual(step?.summary, "trace pr:1525 → linked_issues")
        XCTAssertEqual(step?.reason, "read the subject itself")
    }

    func testANumericStepArgumentDoesNotBreakTheDecode() throws {
        // `k: 6` on a retrieve step is a number. Arguments are only ever
        // displayed, so a scalar shape must never cost the whole answer.
        let json = payload(findings: oneExplicit).replacingOccurrences(
            of: "{\"ref\":\"pr:1525\"}", with: "{\"query\":\"chunking\",\"k\":6}")
        let step = try decode(json).trace.trail.first
        XCTAssertEqual(step?.args["k"], "6")
        XCTAssertEqual(step?.summary, "inspect chunking")
    }

    func testAStepWithNoReasonStillDecodes() throws {
        // A brain that omits the field entirely must not cost the whole answer.
        let json = payload(findings: oneExplicit).replacingOccurrences(
            of: "\"reason\":\"read the subject itself\"", with: "\"unused\":1")
        XCTAssertEqual(try decode(json).trace.trail.first?.reason, "")
    }
}
