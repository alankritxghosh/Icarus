import XCTest
@testable import IcarusKit

/// Decoding the brain's JSON contract (mirrors demo/payload.py):
///   {verdict, answer, citations:[{ref,url}], searched:[...]}
/// `url` may be null (links.ref_to_url returns None for unknown/malformed refs).
final class ModelsTests: XCTestCase {
    private let decoder = JSONDecoder()

    func testDecodesCitedAnswer() throws {
        let json = Data("""
        {"verdict":"answer",
         "answer":"Because other plugins import the old class.",
         "citations":[{"ref":"pr:1435","url":"https://github.com/simonw/llm/pull/1435"}],
         "searched":["pr:1435","code:llm/x.py"]}
        """.utf8)
        let r = try decoder.decode(AskResponse.self, from: json)
        XCTAssertEqual(r.verdict, .answer)
        XCTAssertEqual(r.answer, "Because other plugins import the old class.")
        XCTAssertEqual(r.citations.count, 1)
        XCTAssertEqual(r.citations.first?.ref, "pr:1435")
        XCTAssertEqual(r.citations.first?.url, "https://github.com/simonw/llm/pull/1435")
        XCTAssertEqual(r.searched, ["pr:1435", "code:llm/x.py"])
    }

    func testDecodesHonestUnknown() throws {
        let json = Data("""
        {"verdict":"unknown","answer":"","citations":[],"searched":["code:llm/x.py"]}
        """.utf8)
        let r = try decoder.decode(AskResponse.self, from: json)
        XCTAssertEqual(r.verdict, .unknown)
        XCTAssertTrue(r.answer.isEmpty)
        XCTAssertTrue(r.citations.isEmpty)
        XCTAssertEqual(r.searched, ["code:llm/x.py"])
    }

    func testDecodesCitationWithNullURL() throws {
        let json = Data("""
        {"verdict":"answer","answer":"x","citations":[{"ref":"pr:1","url":null}],"searched":[]}
        """.utf8)
        let r = try decoder.decode(AskResponse.self, from: json)
        XCTAssertNil(r.citations.first?.url)
    }

    func testDecodesRepoStatusReady() throws {
        // The real payload carries `counts` as an OBJECT — must decode regardless.
        let json = Data(#"{"state":"ready","repo":"simonw/llm","commit":"94769b8","counts":{"pr":141,"issue":84,"code":18},"error":null}"#.utf8)
        let s = try decoder.decode(RepoStatus.self, from: json)
        XCTAssertTrue(s.isReady)
        XCTAssertFalse(s.isError)
        XCTAssertEqual(s.repo, "simonw/llm")
        XCTAssertNil(s.error)
        XCTAssertEqual(s.counts?.pr, 141)
        XCTAssertEqual(s.counts?.issue, 84)
        XCTAssertEqual(s.counts?.code, 18)
    }

    func testCountsNilWhileIndexing() throws {
        let json = Data(#"{"state":"indexing","repo":"o/r","commit":"","error":null}"#.utf8)
        let s = try decoder.decode(RepoStatus.self, from: json)
        XCTAssertNil(s.counts)   // missing/null counts must still decode
    }

    func testDecodesRepoStatusIndexingAndError() throws {
        let indexing = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"indexing","repo":"simonw/llm","commit":"","counts":null,"error":null}"#.utf8))
        XCTAssertFalse(indexing.isReady)
        let failed = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"error","repo":"x/y","commit":"","counts":null,"error":"clone failed"}"#.utf8))
        XCTAssertTrue(failed.isError)
        XCTAssertEqual(failed.error, "clone failed")
    }

    func testDecodesProgressPhase() throws {
        let indexing = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"indexing","repo":"o/r","commit":"","counts":null,"error":null,"phase":"Reading the repository…"}"#.utf8))
        XCTAssertEqual(indexing.phase, "Reading the repository…")
        // Absent phase (older brain) still decodes -> nil.
        let noPhase = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"ready","repo":"o/r","commit":"c","counts":null,"error":null}"#.utf8))
        XCTAssertNil(noPhase.phase)
    }

    func testDecodesTruncatedFlag() throws {
        // Brick 2a/2b: a partially-indexed big repo surfaces `truncated`.
        let partial = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"ready","repo":"o/r","commit":"c","counts":null,"error":null,"truncated":true}"#.utf8))
        XCTAssertTrue(partial.isTruncated)
        let full = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"ready","repo":"o/r","commit":"c","counts":null,"error":null,"truncated":false}"#.utf8))
        XCTAssertFalse(full.isTruncated)
        // Absent (older brain) still decodes -> not truncated.
        let old = try decoder.decode(RepoStatus.self, from: Data(
            #"{"state":"ready","repo":"o/r","commit":"c","counts":null,"error":null}"#.utf8))
        XCTAssertFalse(old.isTruncated)
    }


    /// The excerpt is optional on the wire. A brain deployed before the field existed
    /// omits it entirely, and the app must still decode the answer and show the ref --
    /// a missing quote must never cost the user the whole response.
    func testCitationDecodesWithoutAnExcerpt() throws {
        let json = """
        {"verdict":"answer","answer":"Because of the restart window.",
         "citations":[{"ref":"pr:1482","url":"https://github.com/a/b/pull/1482"}],
         "searched":["pr:1482"]}
        """.data(using: .utf8)!
        let r = try JSONDecoder().decode(AskResponse.self, from: json)
        XCTAssertEqual(r.citations.first?.ref, "pr:1482")
        XCTAssertNil(r.citations.first?.excerpt)
    }

    func testCitationDecodesTheExcerptWhenPresent() throws {
        let json = """
        {"verdict":"answer","answer":"Because of the restart window.",
         "citations":[{"ref":"code:retry.go#L1-L40","url":null,
                       "excerpt":"const maxRetries = 3\\n…"}],
         "searched":["code:retry.go#L1-L40"]}
        """.data(using: .utf8)!
        let r = try JSONDecoder().decode(AskResponse.self, from: json)
        XCTAssertEqual(r.citations.first?.excerpt, "const maxRetries = 3\n…")
    }
}

/// The evidence trail an abstention shows. A flat 20-ref list made a refusal
/// that HAD looked up the named ref first read as one that ignored the question
/// (reported live 2026-07-28) — these pin the distinction.
final class EvidenceTrailTests: XCTestCase {
    private func response(searched: [String], anchored: [String]?) -> AskResponse {
        AskResponse(verdict: .unknown, answer: "", citations: [],
                    searched: searched, anchored: anchored)
    }

    func testNamedRefIsCalledOutSeparately() {
        let r = response(searched: ["issue:6952", "code:a.py", "code:b.py"],
                         anchored: ["issue:6952"])
        XCTAssertEqual(r.anchoredLine, "you named: issue:6952")
        XCTAssertEqual(r.searchedLine, "then searched 2 more: code:a.py · code:b.py")
    }

    func testTheNamedRefIsNeverDoubleCounted() {
        // It is in `searched` too (anchors are a prefix of it) — listing it in
        // both halves would overstate how much was consulted.
        let r = response(searched: ["pr:42", "code:a.py"], anchored: ["pr:42"])
        XCTAssertFalse(r.searchedLine.contains("pr:42"))
        XCTAssertTrue(r.searchedLine.hasPrefix("then searched 1 more"))
    }

    func testAQuestionNamingNothingReadsExactlyAsBefore() {
        let r = response(searched: ["code:a.py", "code:b.py"], anchored: [])
        XCTAssertNil(r.anchoredLine)
        XCTAssertEqual(r.searchedLine, "searched 2 sources: code:a.py · code:b.py")
    }

    func testAnOlderBrainWithoutTheFieldStillRenders() {
        // `anchored` absent from the JSON must degrade to the flat list, not
        // fail to decode the whole answer.
        let json = Data(#"{"verdict":"unknown","answer":"","citations":[],"searched":["code:a.py"]}"#.utf8)
        let r = try! JSONDecoder().decode(AskResponse.self, from: json)
        XCTAssertNil(r.anchored)
        XCTAssertNil(r.anchoredLine)
        XCTAssertEqual(r.searchedLine, "searched 1 source: code:a.py")
    }

    func testAnchoredDecodesWhenPresent() throws {
        let json = Data(#"{"verdict":"unknown","answer":"","citations":[],"searched":["issue:6952","code:a.py"],"anchored":["issue:6952"]}"#.utf8)
        let r = try JSONDecoder().decode(AskResponse.self, from: json)
        XCTAssertEqual(r.anchored, ["issue:6952"])
    }

    func testCompactTrailLeadsWithTheNamedRef() {
        let r = response(searched: ["issue:6952", "code:a.py", "code:b.py"],
                         anchored: ["issue:6952"])
        XCTAssertEqual(r.compactTrail, "you named: issue:6952 · +2 searched")
    }

    func testCompactTrailFallsBackToTheList() {
        let r = response(searched: ["code:a.py"], anchored: nil)
        XCTAssertEqual(r.compactTrail, "searched: code:a.py")
    }

    func testEmptySearchDoesNotCrashOrOverclaim() {
        let r = response(searched: [], anchored: [])
        XCTAssertEqual(r.searchedLine, "searched: —")
        XCTAssertEqual(r.compactTrail, "searched: —")
    }
}

/// A private index shared by a team is a "Company Brain"; a public repo's is a
/// "Repo Brain". The label is read from the brain's /status, never guessed.
final class BrainNameTests: XCTestCase {
    private func status(_ json: String) throws -> RepoStatus {
        try JSONDecoder().decode(RepoStatus.self, from: Data(json.utf8))
    }

    func testPrivateRepoIsTheCompanyBrain() throws {
        let s = try status(#"{"state":"ready","repo":"acme/api","commit":"abc","counts":null,"error":null,"private":true}"#)
        XCTAssertEqual(s.isPrivate, true)
        XCTAssertEqual(s.brainName, "COMPANY BRAIN")
        XCTAssertEqual(s.repositoryVisibilityName, "private repo")
    }

    func testPublicRepoIsTheRepoBrain() throws {
        let s = try status(#"{"state":"ready","repo":"psf/requests","commit":"abc","counts":null,"error":null,"private":false}"#)
        XCTAssertEqual(s.brainName, "REPO BRAIN")
        XCTAssertEqual(s.repositoryVisibilityName, "public repo")
    }

    func testAbsentFlagFallsBackToPublic() throws {
        // Never over-claim privacy: an older brain omitting the field must not
        // make a public repo look like a company's private code.
        let s = try status(#"{"state":"ready","repo":"psf/requests","commit":"abc","counts":null,"error":null}"#)
        XCTAssertNil(s.isPrivate)
        XCTAssertEqual(s.brainName, "REPO BRAIN")
        XCTAssertEqual(s.repositoryVisibilityName, "public repo")
    }
}

/// "No one wrote this down" and "I haven't finished reading" are different
/// claims, and only the first is a statement about the repository. They must
/// never render the same. Measured live 2026-07-28: identical corpus, anchor
/// and writer — abstained 3/3 mid-build, answered 3/3 once the embed finished.
final class IncompleteIndexNoteTests: XCTestCase {
    private func response(_ verdict: Verdict, indexing: Bool?) -> AskResponse {
        AskResponse(verdict: verdict, answer: verdict == .answer ? "because X" : "",
                    citations: [], searched: ["code:a.py"], anchored: nil,
                    indexing: indexing)
    }

    func testAbstentionMidIndexCarriesTheCaveat() {
        XCTAssertNotNil(response(.unknown, indexing: true).incompleteIndexNote)
    }

    func testAbstentionOnACompleteIndexDoesNot() {
        XCTAssertNil(response(.unknown, indexing: false).incompleteIndexNote)
    }

    func testAnAnswerNeverCarriesTheCaveat() {
        // An answer is grounded whenever it is emitted; the caveat would only
        // cast doubt on a citation that is already earned.
        XCTAssertNil(response(.answer, indexing: true).incompleteIndexNote)
    }

    func testAnOlderBrainWithoutTheFieldReadsAsComplete() {
        let json = Data(#"{"verdict":"unknown","answer":"","citations":[],"searched":[]}"#.utf8)
        let r = try! JSONDecoder().decode(AskResponse.self, from: json)
        XCTAssertNil(r.indexing)
        XCTAssertNil(r.incompleteIndexNote)
    }

    func testTheFlagDecodesWhenPresent() throws {
        let json = Data(#"{"verdict":"unknown","answer":"","citations":[],"searched":[],"indexing":true}"#.utf8)
        let r = try JSONDecoder().decode(AskResponse.self, from: json)
        XCTAssertEqual(r.indexing, true)
        XCTAssertNotNil(r.incompleteIndexNote)
    }
}

/// Every surface that renders an abstention must agree about WHAT it is.
///
/// Found live on facebook/react (2026-07-29): the overlay said "still indexing"
/// while the shell's proof drawer said "No one wrote this down" about the same
/// ask, because only one of two render paths had been fixed. Two surfaces
/// stating different things about one answer is worse than either being wrong
/// alone — and one of those statements is a claim about the user's repository.
final class AbstentionSurfaceAgreementTests: XCTestCase {
    private func response(indexing: Bool?) -> AskResponse {
        AskResponse(verdict: .unknown, answer: "", citations: [],
                    searched: ["commit:abc"], anchored: nil, indexing: indexing)
    }

    func testMidIndexAbstentionIsFlaggedForEverySurface() {
        // Both the overlay and the shell drawer branch on this one value, so
        // this is the single check that keeps them in step.
        XCTAssertNotNil(response(indexing: true).incompleteIndexNote)
    }

    func testCompleteIndexAbstentionIsNotFlagged() {
        XCTAssertNil(response(indexing: false).incompleteIndexNote)
        XCTAssertNil(response(indexing: nil).incompleteIndexNote)
    }
}

/// Day 1: a connect takes minutes, and until now the only signal was
/// "Building smart search…". These pin how that becomes legible without
/// becoming a promise -- an ETA is an estimate and has to read like one.
final class IndexingProgressTests: XCTestCase {

    private func status(_ progress: String) throws -> RepoStatus {
        let json = Data("""
        {"state":"ready","repo":"a/b","commit":"c","counts":null,"error":null,
         "phase":"Building smart search…","private":false,"truncated":false,
         "indexing":true,"indexing_progress":\(progress)}
        """.utf8)
        return try JSONDecoder().decode(RepoStatus.self, from: json)
    }

    func testProgressDecodes() throws {
        let s = try status(#"{"done":4200,"total":14000,"eta_seconds":372}"#)
        XCTAssertEqual(s.indexingProgress?.done, 4200)
        XCTAssertEqual(s.indexingProgress?.total, 14000)
        XCTAssertEqual(s.indexingProgress?.etaSeconds, 372)
    }

    func testAnOlderBrainWithoutTheFieldStillDecodes() throws {
        // The deployed brain predates this, and the installed app must keep
        // reading /status or the whole shell goes blank.
        let json = Data("""
        {"state":"ready","repo":"a/b","commit":"c","counts":null,"error":null,
         "phase":null,"private":false,"truncated":false,"indexing":false}
        """.utf8)
        let s = try JSONDecoder().decode(RepoStatus.self, from: json)
        XCTAssertNil(s.indexingProgress)
        XCTAssertNil(s.indexingLine)
    }

    func testTheLineNamesBothTheCountAndTheEstimate() throws {
        let s = try status(#"{"done":4200,"total":14000,"eta_seconds":372}"#)
        let line = try XCTUnwrap(s.indexingLine)
        XCTAssertTrue(line.contains("4,200"), line)
        XCTAssertTrue(line.contains("14,000"), line)
        XCTAssertTrue(line.contains("6 min"), line)
        // An estimate must READ like one -- never "6 minutes left" flat.
        XCTAssertTrue(line.lowercased().contains("about"), line)
    }

    func testAnUnknownEtaSaysSoRatherThanGuessing() throws {
        let s = try status(#"{"done":0,"total":14000,"eta_seconds":null}"#)
        let line = try XCTUnwrap(s.indexingLine)
        XCTAssertTrue(line.contains("14,000"), line)
        XCTAssertFalse(line.lowercased().contains("about"), line)
        XCTAssertFalse(line.contains("0 min"), line)
    }

    func testASubMinuteEstimateReadsInSeconds(){
        let p = IndexingProgress(done: 13900, total: 14000, etaSeconds: 20)
        XCTAssertTrue(p.estimate!.contains("20 sec"), p.estimate!)
    }

    func testTheIndexingFlagIsDecodedFromStatus() throws {
        // The server has always sent this; the app never read it, so it had no
        // way to know the index was still building except by asking a question
        // and seeing a worse answer.
        let s = try status(#"{"done":1,"total":2,"eta_seconds":1}"#)
        XCTAssertTrue(s.isIndexing)
    }

    func testAbsentIndexingFlagReadsAsNotIndexing() throws {
        let json = Data("""
        {"state":"ready","repo":"a/b","commit":"c","counts":null,"error":null,
         "phase":null,"private":false,"truncated":false}
        """.utf8)
        let s = try JSONDecoder().decode(RepoStatus.self, from: json)
        XCTAssertFalse(s.isIndexing)
    }

    func testProgressFraction() {
        let p = IndexingProgress(done: 7000, total: 14000, etaSeconds: nil)
        XCTAssertEqual(p.fraction, 0.5, accuracy: 0.001)
        XCTAssertEqual(IndexingProgress(done: 1, total: 0, etaSeconds: nil).fraction, 0)
    }
}

/// `index:` citations are Icarus reporting what it READ -- measured from the
/// repository, not written by a person. Added 2026-08-06 with the
/// index-as-evidence brick: before this, `index:overview` rendered as a bare
/// chip identical to `pr:1482`, which makes exactly the claim the honesty
/// boundary forbids -- that a human documented it.
final class IndexCitationLabellingTests: XCTestCase {
    func testIndexRefIsRecognised() {
        XCTAssertTrue(Citation(ref: "index:overview", url: nil).isIndex)
    }

    func testOrdinaryRefsAreNotIndex() {
        for ref in ["pr:1482", "code:llm/utils.py#L1-L9", "doc:README.md",
                    "issue:7", "commit:abc1234"] {
            XCTAssertFalse(Citation(ref: ref, url: nil).isIndex, ref)
        }
    }

    func testIndexCitationShowsWordsNotTheRawRef() {
        let label = Citation(ref: "index:overview", url: nil).displayLabel
        XCTAssertEqual(label, "Icarus's own index")
        XCTAssertFalse(label.contains("index:overview"))
    }

    func testOrdinaryCitationStillShowsItsRef() {
        XCTAssertEqual(Citation(ref: "pr:1482", url: nil).displayLabel, "pr:1482")
    }

    func testIndexCitationIsNeverLinkable() {
        // Even if a brain somehow sent a URL: there is no page "what Icarus
        // read" lives on, and a link implies a human-authored source.
        let c = Citation(ref: "index:overview", url: "https://github.com/a/b")
        XCTAssertNil(c.linkURL)
        XCTAssertNotNil(Citation(ref: "pr:1482", url: "https://github.com/a/b/pull/1482").linkURL)
    }

    // MARK: - AgentDecision (Decision history surface)

    func testAgentDecisionsDecodeProposalAndMerged() throws {
        // The real `/agent-mode/context` shape: a proposal carries a PR and no
        // citation; a merged one carries a citation and no PR.
        let json = Data("""
        {"repo":"acme/app","commit":"abc123","decisions":[
          {"id":"a","decision":"Use SQLite","rationale":"Local and simple.",
           "affected_paths":["demo/index.py"],
           "status":"human_confirmed_proposal_not_indexed",
           "pull_request_url":"https://github.com/acme/app/pull/42"},
          {"id":"b","decision":"Sliding window limiter","rationale":"Smoother.",
           "affected_paths":[],"status":"human_confirmed_merged",
           "citation_ref":"doc:docs/engineering-memory/b.md",
           "citation_url":"https://github.com/acme/app/blob/abc123/docs/engineering-memory/b.md"}
        ]}
        """.utf8)
        let r = try JSONDecoder().decode(AgentDecisionsResponse.self, from: json)
        XCTAssertEqual(r.repo, "acme/app")
        XCTAssertEqual(r.decisions.count, 2)
        XCTAssertEqual(r.decisions[0].status, .proposalNotIndexed)
        XCTAssertNotNil(r.decisions[0].pullRequestURL)
        XCTAssertNil(r.decisions[0].citationURL)
        XCTAssertEqual(r.decisions[1].status, .merged)
        XCTAssertNotNil(r.decisions[1].citationURL)
        XCTAssertNil(r.decisions[1].pullRequestURL)
    }

    func testAnUnknownDecisionStatusDecodesCautiouslyNotAsMerged() throws {
        // A newer brain status must not read as merged truth in an older app.
        let json = Data("""
        {"repo":"acme/app","decisions":[
          {"id":"a","decision":"x","rationale":"y","affected_paths":[],
           "status":"some_future_status"}]}
        """.utf8)
        let r = try JSONDecoder().decode(AgentDecisionsResponse.self, from: json)
        XCTAssertEqual(r.decisions[0].status, .unrecognised)
    }
}
