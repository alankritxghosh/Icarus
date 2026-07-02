import XCTest
@testable import IcarusKit

final class ShellNavTests: XCTestCase {
    func testSurfaceOrderAndTitles() {
        XCTAssertEqual(ShellSurface.allCases.map(\.title),
            ["Home", "Ask by voice", "Decision history", "Unknowns", "Privacy boundary"])
    }

    func testStableIdentity() {
        XCTAssertEqual(ShellSurface.home.id, "home")
        XCTAssertEqual(ShellSurface.privacyBoundary.id, "privacyBoundary")
    }
}
