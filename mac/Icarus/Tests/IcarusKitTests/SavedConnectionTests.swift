import XCTest
@testable import IcarusKit

/// The saved-connection store (repo persistence across launches) and the pure
/// lost-connection check behind the eviction/restart downgrade banner: the app
/// remembers what it connected; if /status later reports "ready" on a DIFFERENT
/// repo, the server dropped the session and the user must see it, explicitly.
final class SavedConnectionTests: XCTestCase {
    private var defaults: UserDefaults!
    private var store: SavedConnection!

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "test.icarus.saved-connection")!
        defaults.removePersistentDomain(forName: "test.icarus.saved-connection")
        store = SavedConnection(defaults: defaults)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: "test.icarus.saved-connection")
        super.tearDown()
    }

    private func status(_ json: String) throws -> RepoStatus {
        try JSONDecoder().decode(RepoStatus.self, from: Data(json.utf8))
    }

    // MARK: persistence

    func testLoadIsNilBeforeAnySave() {
        XCTAssertNil(store.load())
    }

    func testSaveThenLoadRoundTrips() {
        store.save(repo: "octo/repo")
        let loaded = store.load()
        XCTAssertEqual(loaded?.repo, "octo/repo")
    }

    func testSaveOverwritesPreviousConnection() {
        store.save(repo: "octo/repo")
        store.save(repo: "simonw/llm")
        let loaded = store.load()
        XCTAssertEqual(loaded?.repo, "simonw/llm")
    }

    func testClearForgetsTheConnection() {
        store.save(repo: "octo/repo")
        store.clear()
        XCTAssertNil(store.load())
    }

    // MARK: the lost-connection check

    func testNotLostWhenNothingSaved() throws {
        let s = try status(#"{"state":"ready","repo":"simonw/llm","commit":"a","counts":null,"error":null}"#)
        XCTAssertFalse(store.isLost(given: s))
    }

    func testNotLostWhenStatusMatchesSavedRepo() throws {
        store.save(repo: "octo/repo")
        let s = try status(#"{"state":"ready","repo":"octo/repo","commit":"a","counts":null,"error":null}"#)
        XCTAssertFalse(store.isLost(given: s))
    }

    func testRepoMatchIsCaseInsensitive() throws {
        store.save(repo: "Octo/Repo")
        let s = try status(#"{"state":"ready","repo":"octo/repo","commit":"a","counts":null,"error":null}"#)
        XCTAssertFalse(store.isLost(given: s))
    }

    func testLostWhenReadyOnADifferentRepo() throws {
        store.save(repo: "octo/repo")
        let s = try status(#"{"state":"ready","repo":"simonw/llm","commit":"a","counts":null,"error":null}"#)
        XCTAssertTrue(store.isLost(given: s))
    }

    func testNotLostWhileIndexing() throws {
        // A connect in flight reports the OLD repo until the new one is ready —
        // an indexing state is never "lost".
        store.save(repo: "octo/repo")
        let s = try status(#"{"state":"indexing","repo":"simonw/llm","commit":"","counts":null,"error":null}"#)
        XCTAssertFalse(store.isLost(given: s))
    }

    func testNotLostOnErrorState() throws {
        // Errors surface through the connect flow, not the downgrade banner.
        store.save(repo: "octo/repo")
        let s = try status(#"{"state":"error","repo":"simonw/llm","commit":"","counts":null,"error":"boom"}"#)
        XCTAssertFalse(store.isLost(given: s))
    }
}
