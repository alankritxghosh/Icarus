import Foundation

/// Does the connected index still match the repository? (`demo/freshness.py`)
///
/// A connected corpus is frozen at the commit it was ingested. Nothing used to
/// say so, and this repo's own index once sat nine commits behind HEAD while
/// answering with complete confidence — the product's own failure mode moved
/// out of citations and into time.
///
/// **The one rule: "I could not check" must never render as "up to date".**
/// The wire format makes `up_to_date` three-valued for exactly that reason,
/// and this type keeps it three-valued all the way to the view via
/// `IndexFreshness` — see that enum for why a `Bool?` would not have been good
/// enough.
public struct Freshness: Decodable, Equatable, Sendable {
    /// True, false, or **nil for unknown**. Read `state`, not this, unless you
    /// have a reason to care about the raw wire value.
    public let upToDate: Bool?
    /// How many commits the repository has moved since the indexed commit.
    /// nil means the count is unavailable — which is NOT the same as zero.
    public let behindBy: Int?
    /// The built-in demo corpus is frozen deliberately (it is the reproducible
    /// eval board), so it is permanently behind upstream. Absent reads as
    /// false, which is correct for every real connected repo.
    public let pinned: Bool?

    private enum CodingKeys: String, CodingKey {
        case pinned
        case upToDate = "up_to_date"
        case behindBy = "behind_by"
    }

    public init(upToDate: Bool?, behindBy: Int?, pinned: Bool? = nil) {
        self.upToDate = upToDate
        self.behindBy = behindBy
        self.pinned = pinned
    }

    public var state: IndexFreshness {
        if pinned == true { return .pinned(behindBy) }
        switch upToDate {
        case true: return .matches
        case false: return .behind(behindBy)
        default: return .unknown
        }
    }
}

/// Index staleness as a closed set of cases.
///
/// Deliberately an enum rather than the `Bool?` it decodes from. An optional
/// Bool invites `?? false` at the call site, which would render "I could not
/// check" as "up to date" — a confident claim the evidence does not support,
/// and the same class of failure as a bluffed citation. With an enum there is
/// no default to fall into: every view must name `.unknown` explicitly.
public enum IndexFreshness: Equatable, Sendable {
    /// The index is at the repository's current head.
    case matches
    /// The index is behind. The count is nil when it could not be determined —
    /// we know it differs, we just cannot say by how much, and that remains
    /// more honest than pretending it matches.
    case behind(Int?)
    /// The check did not complete. NOT "up to date", NOT an error — a third
    /// state, and it must look like one.
    case unknown
    /// The built-in demo corpus, frozen on purpose and not refreshable.
    /// Reporting its real distance from upstream as ordinary staleness would
    /// describe a deliberate decision as neglect.
    case pinned(Int?)

    /// One line a user can act on. Never claims currency it has not verified.
    public var summary: String {
        switch self {
        case .matches:
            return "Index matches the repository."
        case .behind(let n?):
            return "\(n) commit\(n == 1 ? "" : "s") behind the repository."
        case .behind(nil):
            return "Behind the repository — Icarus couldn’t work out by how much."
        case .unknown:
            return "Icarus couldn’t check whether this index is current."
        case .pinned(let n?):
            return "Built-in demo corpus, frozen on purpose — \(n) commits behind upstream."
        case .pinned(nil):
            return "Built-in demo corpus, frozen on purpose."
        }
    }

    /// Should a client offer to refresh? Never for the pinned demo corpus,
    /// whose refresh is forbidden by design and would do nothing.
    public var offersRefresh: Bool {
        switch self {
        case .behind: return true
        case .matches, .unknown, .pinned: return false
        }
    }
}
