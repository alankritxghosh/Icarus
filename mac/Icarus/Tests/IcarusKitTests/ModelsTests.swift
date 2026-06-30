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

    func testDecodesHealth() throws {
        let json = Data(#"{"ok":true,"repo":"simonw/llm","commit":"94769b8"}"#.utf8)
        let h = try decoder.decode(Health.self, from: json)
        XCTAssertTrue(h.ok)
        XCTAssertEqual(h.repo, "simonw/llm")
    }
}
