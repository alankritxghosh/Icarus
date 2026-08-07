import XCTest
@testable import IcarusKit

final class ShellNavTests: XCTestCase {
    func testSurfaceOrderAndTitles() {
        XCTAssertEqual(ShellSurface.allCases.map(\.title),
            ["Home", "Start here", "Decision history", "Engineering memory"])
    }

    /// The tour sits directly under Home: it is the first experience a new
    /// user should have with a repo, so it must not be buried at the bottom of
    /// the sidebar under the surfaces you only need once you know your way
    /// around.
    func testTheTourSitsDirectlyUnderHome() {
        XCTAssertEqual(ShellSurface.allCases.map(\.id).prefix(2), ["home", "startHere"])
    }

    func testStableIdentity() {
        XCTAssertEqual(ShellSurface.home.id, "home")
        XCTAssertEqual(ShellSurface.engineeringMemory.id, "engineeringMemory")
    }
}
