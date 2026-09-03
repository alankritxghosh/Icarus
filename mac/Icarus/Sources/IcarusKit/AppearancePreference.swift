import Foundation

/// The UserDefaults key backing the app's Light/Dark switch -- shared so the
/// Settings control and `AppearancePreference`'s reader never drift onto two
/// keys.
public let icarusAppearanceDefaultsKey = "icarus.appearance"

/// Icarus shipped dark-only (Theme.swift). This is the explicit, app-level
/// override that reverses that -- deliberately just two cases, no "system":
/// every colour here (the cited green, the honest-unknown amber, the
/// brutalist offset shadow) was tuned as one deliberate palette per mode, not
/// inherited from macOS, so the app repaints from ITS OWN choice.
public enum AppAppearance: String, Sendable {
    case dark, light
}

/// Reads/writes the appearance choice. A fresh install with no key set must
/// render EXACTLY as before this existed -- dark -- so the default is `.dark`,
/// never inferred from `NSApp.effectiveAppearance` or any other OS signal.
public struct AppearancePreference {
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public var appearance: AppAppearance {
        get { defaults.string(forKey: icarusAppearanceDefaultsKey).flatMap(AppAppearance.init) ?? .dark }
        nonmutating set { defaults.set(newValue.rawValue, forKey: icarusAppearanceDefaultsKey) }
    }
}
