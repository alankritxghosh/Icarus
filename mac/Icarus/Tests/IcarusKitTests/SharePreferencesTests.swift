import XCTest
@testable import IcarusKit

/// The "help improve Icarus" toggle's store: defaults OFF (matching the
/// server's counts-only default), persists, and reads the
/// SAME UserDefaults key SettingsView's `@AppStorage` writes -- the two must
/// never drift onto separate keys, or the toggle would silently do nothing.
final class SharePreferencesTests: XCTestCase {
    private var defaults: UserDefaults!
    private var store: SharePreferences!

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "test.icarus.share-preferences")!
        defaults.removePersistentDomain(forName: "test.icarus.share-preferences")
        store = SharePreferences(defaults: defaults)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: "test.icarus.share-preferences")
        super.tearDown()
    }

    func testDefaultsToNotSharingBeforeAnyChoiceIsMade() {
        // Sharing questions and cited private code is not something a default
        // gets to decide -- the same rule the server now enforces. A client
        // defaulting ON would reinstate exactly what that flip removed.
        XCTAssertFalse(store.shareContent)
    }

    func testTurningItOffPersists() {
        store.shareContent = true
        store.shareContent = false
        XCTAssertFalse(store.shareContent)
        XCTAssertFalse(SharePreferences(defaults: defaults).shareContent,
                       "a fresh reader over the same defaults must see the same choice")
    }

    func testTurningItBackOnPersists() {
        store.shareContent = false
        store.shareContent = true
        XCTAssertTrue(store.shareContent)
    }

    func testReadsTheSameKeyAppStorageWrites() {
        // SettingsView binds @AppStorage(icarusShareContentDefaultsKey). Writing
        // through that exact key must be visible to SharePreferences without
        // either side needing to know about the other's implementation.
        defaults.set(false, forKey: icarusShareContentDefaultsKey)
        XCTAssertFalse(store.shareContent)
    }
}
