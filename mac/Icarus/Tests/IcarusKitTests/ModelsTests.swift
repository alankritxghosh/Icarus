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
    }

    func testPublicRepoIsTheRepoBrain() throws {
        let s = try status(#"{"state":"ready","repo":"psf/requests","commit":"abc","counts":null,"error":null,"private":false}"#)
        XCTAssertEqual(s.brainName, "REPO BRAIN")
    }

    func testAbsentFlagFallsBackToPublic() throws {
        // Never over-claim privacy: an older brain omitting the field must not
        // make a public repo look like a company's private code.
        let s = try status(#"{"state":"ready","repo":"psf/requests","commit":"abc","counts":null,"error":null}"#)
        XCTAssertNil(s.isPrivate)
        XCTAssertEqual(s.brainName, "REPO BRAIN")
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
