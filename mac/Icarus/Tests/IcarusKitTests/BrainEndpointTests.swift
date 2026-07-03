import XCTest
@testable import IcarusKit

final class BrainEndpointTests: XCTestCase {
    func testFallsBackWhenKeyAbsent() {
        XCTAssertEqual(BrainEndpoint.resolve(from: nil), BrainEndpoint.localFallback)
        XCTAssertEqual(BrainEndpoint.resolve(from: [:]), BrainEndpoint.localFallback)
    }

    func testFallsBackOnEmptyOrInvalidURL() {
        XCTAssertEqual(BrainEndpoint.resolve(from: ["ICARUS_BRAIN_URL": ""]), BrainEndpoint.localFallback)
        XCTAssertEqual(BrainEndpoint.resolve(from: ["ICARUS_BRAIN_URL": "   "]), BrainEndpoint.localFallback)
        // Missing scheme/host — not an absolute http(s) URL.
        XCTAssertEqual(BrainEndpoint.resolve(from: ["ICARUS_BRAIN_URL": "not a url"]), BrainEndpoint.localFallback)
        XCTAssertEqual(BrainEndpoint.resolve(from: ["ICARUS_BRAIN_URL": "ftp://example.com"]), BrainEndpoint.localFallback)
    }

    func testUsesHostedURLWhenPresent() {
        let url = BrainEndpoint.resolve(from: ["ICARUS_BRAIN_URL": "https://icarus-brain.onrender.com"])
        XCTAssertEqual(url, URL(string: "https://icarus-brain.onrender.com"))
    }

    func testTrimsWhitespace() {
        let url = BrainEndpoint.resolve(from: ["ICARUS_BRAIN_URL": "  https://x.onrender.com  "])
        XCTAssertEqual(url, URL(string: "https://x.onrender.com"))
    }

    func testHonorsExplicitFallback() {
        let custom = URL(string: "http://localhost:9999")!
        XCTAssertEqual(BrainEndpoint.resolve(from: nil, fallback: custom), custom)
    }
}
