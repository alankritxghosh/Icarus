import XCTest
@testable import IcarusKit

final class MemoryGapLifecycleContractTests: XCTestCase {
    func testDecodesOpenAndResolvedMemoryGaps() throws {
        let json = Data("""
        {"repo":"acme/api","gaps":[
          {"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
           "question":"Why auth?","unknown_count":8,"last_asked":10.0,
           "status":"open","kind":"undocumented","actionable":true,
           "resolution_citations":[]},
          {"id":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
           "question":"Why Redis?","unknown_count":5,"last_asked":9.0,
           "status":"resolved","kind":"undocumented","actionable":false,
           "resolution_citations":["doc:docs/engineering-memory/redis.md#L1-L12"]}
        ]}
        """.utf8)

        let response = try JSONDecoder().decode(MemoryGapsResponse.self, from: json)

        XCTAssertEqual(response.repo, "acme/api")
        XCTAssertEqual(response.open.count, 1)
        XCTAssertEqual(response.resolved.count, 1)
        XCTAssertEqual(response.open.first?.unknownCount, 8)
        XCTAssertTrue(response.open.first?.actionable == true)
        XCTAssertEqual(
            response.resolved.first?.resolutionCitations,
            ["doc:docs/engineering-memory/redis.md#L1-L12"]
        )
    }

    func testUnknownLifecycleStatusFailsRatherThanPretendingOpenOrResolved() {
        let json = Data("""
        {"repo":"acme/api","gaps":[
          {"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
           "question":"Why auth?","unknown_count":1,"last_asked":10.0,
           "status":"maybe","kind":"unclear","actionable":false,
           "resolution_citations":[]}
        ]}
        """.utf8)

        XCTAssertThrowsError(try JSONDecoder().decode(MemoryGapsResponse.self, from: json))
    }

    func testDecodesProposedGapWithTheExistingPullRequest() throws {
        let json = Data("""
        {"repo":"acme/api","gaps":[{
          "id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "question":"Why auth?","unknown_count":1,"last_asked":10.0,
          "status":"proposed","kind":"undocumented","actionable":false,
          "resolution_citations":[],
          "proposal":{"repo":"acme/api","question":"Why auth?",
            "branch":"icarus/memory-aaaaaaaaaaaaaaaaaaaa",
            "path":"docs/engineering-memory/auth.md",
            "file_url":null,
            "pull_request_url":"https://github.com/acme/api/pull/42"}
        }]}
        """.utf8)

        let response = try JSONDecoder().decode(MemoryGapsResponse.self, from: json)

        XCTAssertEqual(response.proposed.count, 1)
        XCTAssertEqual(
            response.proposed[0].proposal?.pullRequestURL.absoluteString,
            "https://github.com/acme/api/pull/42"
        )
    }
}
