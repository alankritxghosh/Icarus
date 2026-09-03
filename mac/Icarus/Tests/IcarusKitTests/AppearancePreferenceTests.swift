import XCTest
@testable import IcarusKit

/// The Light/Dark store: defaults to dark (matching the app's shipped
/// behavior before this existed), persists, and reads the SAME UserDefaults
/// key the Settings control writes.
final class AppearancePreferenceTests: XCTestCase {
    private var defaults: UserDefaults!
    private var store: AppearancePreference!

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "test.icarus.appearance-preference")!
        defaults.removePersistentDomain(forName: "test.icarus.appearance-preference")
        store = AppearancePreference(defaults: defaults)
    }

    override func tearDown() {
        defaults.removePersistentDomain(forName: "test.icarus.appearance-preference")
        super.tearDown()
    }

    func testDefaultsToDarkBeforeAnyChoiceIsMade() {
        // A fresh install must render exactly as it did before this feature
        // existed -- dark -- never inferred from the OS appearance.
        XCTAssertEqual(store.appearance, .dark)
    }

    func testSwitchingToLightPersists() {
        store.appearance = .light
        XCTAssertEqual(store.appearance, .light)
        XCTAssertEqual(AppearancePreference(defaults: defaults).appearance, .light,
                       "a fresh reader over the same defaults must see the same choice")
    }

    func testSwitchingBackToDarkPersists() {
        store.appearance = .light
        store.appearance = .dark
        XCTAssertEqual(store.appearance, .dark)
    }

    func testGarbageValueFallsBackToDark() {
        defaults.set("sepia", forKey: icarusAppearanceDefaultsKey)
        XCTAssertEqual(store.appearance, .dark)
    }
}
