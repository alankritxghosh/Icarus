import XCTest
@testable import IcarusKit

/// Staleness decoding, and the one property it exists to protect:
/// **"I could not check" must never render as "up to date".**
///
/// Every test here is about that boundary. The wire format is three-valued on
/// purpose and `IndexFreshness` keeps it three-valued to the view, so there is
/// no optional Bool for a call site to `?? false` into a reassuring lie.
final class FreshnessTests: XCTestCase {

    private func decode(_ json: String) throws -> Freshness {
        try JSONDecoder().decode(Freshness.self, from: Data(json.utf8))
    }

    func testUpToDateDecodesAsMatches() throws {
        let f = try decode("""
        {"up_to_date": true, "behind_by": 0, "head_commit": "abc", "checked_at": 1.0, "pinned": false}
        """)
        XCTAssertEqual(f.state, .matches)
    }

    func testBehindCarriesTheCount() throws {
        let f = try decode("""
        {"up_to_date": false, "behind_by": 9, "head_commit": "abc", "checked_at": 1.0, "pinned": false}
        """)
        XCTAssertEqual(f.state, .behind(9))
    }

    func testUnknownIsUnknownAndNotUpToDate() throws {
        let f = try decode("""
        {"up_to_date": null, "behind_by": null, "head_commit": null, "checked_at": null, "pinned": false}
        """)
        XCTAssertEqual(f.state, .unknown)
        XCTAssertNotEqual(f.state, .matches)
    }

    func testBehindWithAnUnknownCountStaysBehind() throws {
        // We know it differs even though the count failed. Downgrading this to
        // .unknown would discard a fact we actually hold.
        let f = try decode("""
        {"up_to_date": false, "behind_by": null, "head_commit": "abc", "checked_at": 1.0, "pinned": false}
        """)
        XCTAssertEqual(f.state, .behind(nil))
    }

    func testPinnedOutranksBehind() throws {
        // The demo corpus is frozen deliberately. Showing its real distance as
        // ordinary staleness would describe a decision as neglect.
        let f = try decode("""
        {"up_to_date": false, "behind_by": 68, "head_commit": "abc", "checked_at": 1.0, "pinned": true}
        """)
        XCTAssertEqual(f.state, .pinned(68))
    }

    func testAnOlderBrainWithoutTheBlockReadsAsUnknown() {
        // Absent must not read as fresh either.
        let status = RepoStatus(state: "ready", repo: "o/r", commit: "abc", counts: nil,
                                error: nil, phase: nil, truncated: nil, isPrivate: nil,
                                indexingProgress: nil, indexing: nil, freshness: nil)
        XCTAssertEqual(status.indexFreshness, .unknown)
    }

    func testStatusDecodesTheFreshnessBlock() throws {
        let status = try JSONDecoder().decode(RepoStatus.self, from: Data("""
        {"state":"ready","repo":"o/r","commit":"abc","counts":null,"error":null,
         "phase":null,"truncated":false,"private":false,"indexing":false,
         "indexing_progress":null,
         "freshness":{"up_to_date":false,"behind_by":4,"head_commit":"def",
                      "checked_at":1.0,"pinned":false}}
        """.utf8))
        XCTAssertEqual(status.indexFreshness, .behind(4))
    }

    // MARK: - what a user is actually told

    func testUnknownNeverClaimsCurrency() {
        let text = IndexFreshness.unknown.summary.lowercased()
        XCTAssertTrue(text.contains("couldn’t check") || text.contains("couldn't check"))
        XCTAssertFalse(text.contains("up to date"))
        XCTAssertFalse(text.contains("matches"))
    }

    func testSingularAndPluralCommits() {
        XCTAssertTrue(IndexFreshness.behind(1).summary.contains("1 commit behind"))
        XCTAssertTrue(IndexFreshness.behind(2).summary.contains("2 commits behind"))
    }

    func testRefreshIsOfferedOnlyWhenItWouldDoSomething() {
        XCTAssertTrue(IndexFreshness.behind(3).offersRefresh)
        XCTAssertTrue(IndexFreshness.behind(nil).offersRefresh)
        XCTAssertFalse(IndexFreshness.matches.offersRefresh)
        // Never for unknown: offering a refresh implies we know it is stale.
        XCTAssertFalse(IndexFreshness.unknown.offersRefresh)
        // Never for the pinned corpus: the server forbids refreshing it, so
        // the button would be a lie about what it does.
        XCTAssertFalse(IndexFreshness.pinned(68).offersRefresh)
    }
}
