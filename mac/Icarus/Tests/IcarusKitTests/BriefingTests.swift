import XCTest
@testable import IcarusKit

/// Briefing decoding, and its own version of the freshness rule:
/// **`commits_since: null` means UNKNOWN and must never render as "nothing
/// changed".** Zero is a real answer and arrives as 0.
final class BriefingTests: XCTestCase {

    private func decode(_ json: String) throws -> Briefing {
        try JSONDecoder().decode(Briefing.self, from: Data(json.utf8))
    }

    func testFirstVisitDecodes() throws {
        let b = try decode("""
        {"repo":"o/r","first_visit":true,"last_visit_at":null,"last_seen_commit":null,
         "current_commit":"abc","commits_since":null,"stored":null}
        """)
        XCTAssertEqual(b.change, .firstVisit)
        XCTAssertNil(b.stored)
    }

    func testAReturningVisitReportsTheCount() throws {
        let b = try decode("""
        {"repo":"o/r","first_visit":false,"last_visit_at":1000.0,"last_seen_commit":"old",
         "current_commit":"new","commits_since":9,
         "stored":{"repo":"o/r","commit":"old","at":1000.0}}
        """)
        XCTAssertEqual(b.change, .changed(9))
        XCTAssertEqual(b.stored, Briefing.StoredRecord(repo: "o/r", commit: "old", at: 1000.0))
    }

    func testZeroIsNothingChangedAndIsARealAnswer() throws {
        let b = try decode("""
        {"repo":"o/r","first_visit":false,"last_visit_at":1000.0,"last_seen_commit":"abc",
         "current_commit":"abc","commits_since":0,
         "stored":{"repo":"o/r","commit":"abc","at":1000.0}}
        """)
        XCTAssertEqual(b.change, .nothingChanged)
    }

    func testAnUnknownCountIsUnknownAndNotNothingChanged() throws {
        // The whole point. A failed comparison reading as "you're all caught
        // up" is the same class of failure as a bluffed citation.
        let b = try decode("""
        {"repo":"o/r","first_visit":false,"last_visit_at":1000.0,"last_seen_commit":"old",
         "current_commit":"new","commits_since":null,
         "stored":{"repo":"o/r","commit":"old","at":1000.0}}
        """)
        XCTAssertEqual(b.change, .unknown)
        XCTAssertNotEqual(b.change, .nothingChanged)
    }

    func testUnknownWordingNeverSaysNothingChanged() {
        let text = BriefingChange.unknown.summary.lowercased()
        XCTAssertFalse(text.contains("nothing has changed"))
        XCTAssertTrue(text.contains("couldn’t") || text.contains("couldn't"))
    }

    func testSingularAndPluralCommits() {
        XCTAssertTrue(BriefingChange.changed(1).summary.contains("1 commit since"))
        XCTAssertTrue(BriefingChange.changed(4).summary.contains("4 commits since"))
    }

    func testTheStoredRecordHasExactlyTheFourApprovedFields() throws {
        // docs/decisions/2026-07-30-returning-user-state.md: user identity is
        // implicit (it is the caller), leaving repo + commit + timestamp on
        // the wire. If the server ever grows a fifth field, this decode still
        // succeeds -- so the guard that matters is on the SERVER
        // (demo/test_visits.py). This pins the client's half: it asks for no
        // more than those, and exposes no question or answer history.
        let mirror = Mirror(reflecting:
            Briefing.StoredRecord(repo: "o/r", commit: "abc", at: 1.0))
        XCTAssertEqual(Set(mirror.children.compactMap(\.label)), ["repo", "commit", "at"])
    }
}
