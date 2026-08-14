import Foundation

/// The UserDefaults key backing the "help improve Icarus" toggle, shared so
/// SettingsView's `@AppStorage` and `SharePreferences`'s reader (read off the
/// main actor, at request time in BrainClient) never drift onto two keys.
public let icarusShareContentDefaultsKey = "icarus.shareContent"

/// Whether questions + cited code evidence are shared with PostHog for
/// product-improvement visibility -- sent as demo/server.py's
/// `X-Icarus-Share-Content` header. Defaults OFF, matching the server's
/// counts-only default (CLAUDE.md, 2026-08-14): sharing the questions someone
/// asks and the private code Icarus cites back is not a decision a default
/// gets to make, on either side of the wire. This store makes the choice
/// visible and reversible from the app's Settings; until it is made, nothing
/// but counts leaves.
public struct SharePreferences {
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public var shareContent: Bool {
        get { defaults.object(forKey: icarusShareContentDefaultsKey) as? Bool ?? false }
        nonmutating set { defaults.set(newValue, forKey: icarusShareContentDefaultsKey) }
    }
}
