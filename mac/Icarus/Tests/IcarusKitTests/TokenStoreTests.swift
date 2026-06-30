import XCTest
@testable import IcarusKit

/// Contract tests for the TokenStore, exercised via the in-memory double.
/// (The real Keychain store is integration-verified, not unit-tested.)
final class TokenStoreTests: XCTestCase {
    func testLoadIsNilWhenEmpty() throws {
        XCTAssertNil(try InMemoryTokenStore().load())
    }

    func testSaveThenLoad() throws {
        let store = InMemoryTokenStore()
        try store.save("gho_abc")
        XCTAssertEqual(try store.load(), "gho_abc")
    }

    func testSaveOverwrites() throws {
        let store = InMemoryTokenStore()
        try store.save("gho_old")
        try store.save("gho_new")
        XCTAssertEqual(try store.load(), "gho_new")
    }

    func testDeleteClears() throws {
        let store = InMemoryTokenStore()
        try store.save("gho_abc")
        try store.delete()
        XCTAssertNil(try store.load())
    }

    func testDeleteWhenEmptyIsHarmless() throws {
        XCTAssertNoThrow(try InMemoryTokenStore().delete())
    }
}
