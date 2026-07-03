import Foundation

/// Resolves which brain the app talks to. The URL comes from the app bundle's
/// Info.plist key `ICARUS_BRAIN_URL` — stamped in at package time for a shipped
/// build that points at the hosted brain. When the key is absent (`swift run` /
/// `swift test`, or a locally-built bundle) it falls back to the local brain.
///
/// The resolution is a pure function of an Info-dictionary so it can be unit
/// tested without an app bundle; the app calls it with `Bundle.main.infoDictionary`.
public enum BrainEndpoint {
    public static let infoKey = "ICARUS_BRAIN_URL"
    public static let localFallback = URL(string: "http://127.0.0.1:8000")!

    /// Pick the brain URL from an Info-dictionary, falling back to `fallback`
    /// when the key is missing, empty, or not a valid absolute http(s) URL.
    public static func resolve(from infoDictionary: [String: Any]?,
                               fallback: URL = localFallback) -> URL {
        guard let raw = infoDictionary?[infoKey] as? String else { return fallback }
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              let url = URL(string: trimmed),
              let scheme = url.scheme?.lowercased(),
              scheme == "http" || scheme == "https",
              url.host != nil else {
            return fallback
        }
        return url
    }
}
