import XCTest
@testable import IcarusKit

final class AskHistoryTests: XCTestCase {
    private func answer(_ q: String, _ v: Verdict, cites: [String] = []) -> AskResponse {
        AskResponse(verdict: v, answer: v == .answer ? "because X" : "",
                    citations: cites.map { Citation(ref: $0, url: nil) }, searched: ["code:a.py"])
    }

    @MainActor func testRecordsMostRecentFirst() {
        let h = AskHistory()
        h.record(question: "why A?", response: answer("why A?", .answer, cites: ["pr:1"]))
        h.record(question: "why B?", response: answer("why B?", .unknown))
        XCTAssertEqual(h.entries.map(\.question), ["why B?", "why A?"])
        XCTAssertEqual(h.mostRecent?.question, "why B?")
    }

    @MainActor func testUnknownsFilter() {
        let h = AskHistory()
        h.record(question: "a", response: answer("a", .answer, cites: ["pr:1"]))
        h.record(question: "b", response: answer("b", .unknown))
        XCTAssertEqual(h.unknowns.map(\.question), ["b"])
    }

    @MainActor func testIsCitedRequiresAnswerAndCitation() {
        let h = AskHistory()
        h.record(question: "no cites", response: answer("no cites", .answer, cites: []))
        XCTAssertFalse(h.entries[0].isCited)  // answer verdict but zero citations
    }

    @MainActor func testCitedRate() {
        let h = AskHistory()
        XCTAssertNil(h.citedRate)                 // no asks yet → nil, never a fake %
        h.record(question: "a", response: answer("a", .answer, cites: ["pr:1"]))
        h.record(question: "b", response: answer("b", .unknown))
        XCTAssertEqual(h.citedRate!, 0.5, accuracy: 0.001)
    }
}
