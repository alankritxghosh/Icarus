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

}
