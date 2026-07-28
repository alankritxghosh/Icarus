import XCTest
@testable import IcarusKit

/// The unknowns map: the repo's SHARED record collapsed into ranked gaps.
///
/// This surface makes a claim about someone's codebase — "you never wrote this
/// down, nine times" — so its arithmetic has to be exactly right, and its
/// ranking has to mean what it says it means.
final class LedgerGapsTests: XCTestCase {
    private func entry(_ q: String, _ v: Verdict, ts: Double = 0) -> LedgerEntry {
        LedgerEntry(ts: ts, question: q, verdict: v, citations: [])
    }

    private func ledger(_ entries: [LedgerEntry]) -> LedgerResponse {
        LedgerResponse(repo: "acme/api", entries: entries)
    }

    func testAnsweredQuestionsAreNotGaps() {
        // A gap is something the record could NOT answer. Counting an answered
        // question would overstate a team's documentation debt.
        let l = ledger([entry("why retries?", .answer), entry("why 30?", .unknown)])
        XCTAssertEqual(l.gaps.map(\.question), ["why 30?"])
    }

    func testRepeatedGapsAreCountedNotDuplicated() {
        let l = ledger([entry("why 30?", .unknown), entry("why 30?", .unknown),
                        entry("why 30?", .unknown)])
        XCTAssertEqual(l.gaps.count, 1)
        XCTAssertEqual(l.gaps.first?.count, 3)
    }

    func testRankedByFrequency() {
        let l = ledger([entry("rare", .unknown),
                        entry("common", .unknown), entry("common", .unknown)])
        XCTAssertEqual(l.gaps.map(\.question), ["common", "rare"])
    }

    func testEqualCountsBreakOnMostRecent() {
        // A live gap outranks a stale one asked exactly as often.
        let l = ledger([entry("stale", .unknown, ts: 100),
                        entry("fresh", .unknown, ts: 900)])
        XCTAssertEqual(l.gaps.map(\.question), ["fresh", "stale"])
    }

    func testMatchingIsCaseInsensitiveOnTrimmedText() {
        let l = ledger([entry("Why 30?", .unknown), entry("  why 30?  ", .unknown)])
        XCTAssertEqual(l.gaps.count, 1)
        XCTAssertEqual(l.gaps.first?.count, 2)
    }

    func testTheDisplayedQuestionKeepsItsOriginalCasing() {
        // We collapse on a lowercased key but must never SHOW the mangled key.
        let l = ledger([entry("Why is DEFAULT_REDIRECT_LIMIT 30?", .unknown)])
        XCTAssertEqual(l.gaps.first?.question, "Why is DEFAULT_REDIRECT_LIMIT 30?")
    }

    func testNearlyIdenticalQuestionsStaySeparate() {
        // Deliberately literal, never fuzzy: merging two genuinely different
        // questions would invent a gap that nobody actually has.
        let l = ledger([entry("why 30 redirects?", .unknown),
                        entry("why 30 retries?", .unknown)])
        XCTAssertEqual(l.gaps.count, 2)
    }

    func testBlankQuestionsAreDropped() {
        let l = ledger([entry("   ", .unknown), entry("real", .unknown)])
        XCTAssertEqual(l.gaps.map(\.question), ["real"])
    }

    func testAnEmptyLedgerHasNoGaps() {
        XCTAssertTrue(ledger([]).gaps.isEmpty)
    }

    func testDecodesTheServerShape() throws {
        // Mirrors demo/ledger.py's record exactly — including that it carries
        // NO identity field, which is a deliberate privacy property.
        let json = Data("""
        {"repo":"acme/api","entries":[
          {"ts":1753000000.0,"question":"why 30?","verdict":"unknown","citations":[]},
          {"ts":1753000001.0,"question":"why retries?","verdict":"answer","citations":["pr:12"]}]}
        """.utf8)
        let l = try JSONDecoder().decode(LedgerResponse.self, from: json)
        XCTAssertEqual(l.repo, "acme/api")
        XCTAssertEqual(l.entries.count, 2)
        XCTAssertEqual(l.entries.first?.verdict, .unknown)
        XCTAssertEqual(l.gaps.map(\.question), ["why 30?"])
    }
}
