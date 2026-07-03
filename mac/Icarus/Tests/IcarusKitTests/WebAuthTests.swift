import XCTest
@testable import IcarusKit

final class WebAuthTests: XCTestCase {
    func testParsesSessionFromCallback() {
        let url = URL(string: "icarus://auth?session=abc123")!
        XCTAssertEqual(parseCallbackSession(url), "abc123")
    }

    func testNilWhenNoSession() {
        XCTAssertNil(parseCallbackSession(URL(string: "icarus://auth?foo=bar")!))
        XCTAssertNil(parseCallbackSession(URL(string: "icarus://auth")!))
    }

    func testNilWhenSessionEmpty() {
        XCTAssertNil(parseCallbackSession(URL(string: "icarus://auth?session=")!))
    }
}
