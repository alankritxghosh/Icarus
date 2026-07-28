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

/// A gap is only documentation debt if the thing actually EXISTS and nobody
/// wrote down why. Presenting "you asked about something that isn't here" as
/// debt overstates a team's problem — and this surface makes a claim about
/// their codebase, so it has to get that right.
final class GapKindTests: XCTestCase {
    private func entry(_ q: String, reason: String?, ts: Double = 0) -> LedgerEntry {
        LedgerEntry(ts: ts, question: q, verdict: .unknown, citations: [], reason: reason)
    }

    func testAnUndocumentedWhyIsRealDebt() {
        XCTAssertEqual(GapKind(reason: "no_recorded_reason"), .undocumented)
        XCTAssertNil(GapKind.undocumented.label, "the normal case needs no badge")
    }

    func testAFabricatedSymbolIsNotDebt() {
        XCTAssertEqual(GapKind(reason: "entity_absent"), .notInThisRepo)
        XCTAssertEqual(GapKind.notInThisRepo.label, "not in this repo")
    }

    func testAnEntryFromBeforeReasonsExistedIsMarkedUnclear() {
        // Never silently promoted to "documentation debt" — we don't know.
        XCTAssertEqual(GapKind(reason: nil), .unclear)
        XCTAssertNotNil(GapKind.unclear.label)
    }

    func testTheKindReachesTheRankedGap() {
        let l = LedgerResponse(repo: "acme/api", entries: [
            entry("why 30?", reason: "no_recorded_reason"),
            entry("how does Xyzzy work?", reason: "entity_absent"),
        ])
        let byQuestion = Dictionary(uniqueKeysWithValues: l.gaps.map { ($0.question, $0.kind) })
        XCTAssertEqual(byQuestion["why 30?"], .undocumented)
        XCTAssertEqual(byQuestion["how does Xyzzy work?"], .notInThisRepo)
    }

    func testTheMostRecentClassificationWins() {
        // An old entry may predate reasons entirely; letting it win would
        // permanently mark a real gap "unclear".
        let l = LedgerResponse(repo: "acme/api", entries: [
            entry("why 30?", reason: nil, ts: 100),
            entry("why 30?", reason: "no_recorded_reason", ts: 900),
        ])
        XCTAssertEqual(l.gaps.first?.kind, .undocumented)
        XCTAssertEqual(l.gaps.first?.count, 2, "both asks still count")
    }

    func testAnOlderBrainOmittingReasonStillDecodes() {
        let json = Data("""
        {"repo":"a/b","entries":[{"ts":1.0,"question":"q","verdict":"unknown","citations":[]}]}
        """.utf8)
        let l = try! JSONDecoder().decode(LedgerResponse.self, from: json)
        XCTAssertNil(l.entries.first?.reason)
        XCTAssertEqual(l.gaps.first?.kind, .unclear)
    }

    func testDecodesTheReasonWhenPresent() throws {
        let json = Data("""
        {"repo":"a/b","entries":[{"ts":1.0,"question":"q","verdict":"unknown",
          "citations":[],"reason":"entity_absent"}]}
        """.utf8)
        let l = try JSONDecoder().decode(LedgerResponse.self, from: json)
        XCTAssertEqual(l.gaps.first?.kind, .notInThisRepo)
    }
}
