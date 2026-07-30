import Foundation

/// `GET /briefing` — what changed since this user was last here.
///
/// Backed by `demo/visits.py`, which stores exactly four facts about a
/// returning user (identity, repository, last-seen commit, last-visit time)
/// and deliberately nothing else. See
/// `docs/decisions/2026-07-30-returning-user-state.md`.
///
/// `stored` is the whole record held about the caller, returned so a user can
/// SEE it rather than be told about it — a privacy promise nobody can verify
/// is marketing.
public struct Briefing: Decodable, Equatable, Sendable {
    public let repo: String?
    public let firstVisit: Bool
    public let lastVisitAt: Double?
    public let lastSeenCommit: String?
    public let currentCommit: String?
    /// How many commits landed since the last visit. **nil means UNKNOWN and
    /// must never be rendered as "nothing changed"** — zero is a real answer
    /// and arrives as `0`. `change` enforces the distinction.
    public let commitsSince: Int?
    public let stored: StoredRecord?

    private enum CodingKeys: String, CodingKey {
        case repo, stored
        case firstVisit = "first_visit"
        case lastVisitAt = "last_visit_at"
        case lastSeenCommit = "last_seen_commit"
        case currentCommit = "current_commit"
        case commitsSince = "commits_since"
    }

    /// Everything Icarus holds about this user for this repo. Four fields, and
    /// there is no fifth to show.
    public struct StoredRecord: Decodable, Equatable, Sendable {
        public let repo: String
        public let commit: String
        public let at: Double

        public init(repo: String, commit: String, at: Double) {
            self.repo = repo
            self.commit = commit
            self.at = at
        }
    }

    public init(repo: String?, firstVisit: Bool, lastVisitAt: Double?,
                lastSeenCommit: String?, currentCommit: String?,
                commitsSince: Int?, stored: StoredRecord?) {
        self.repo = repo
        self.firstVisit = firstVisit
        self.lastVisitAt = lastVisitAt
        self.lastSeenCommit = lastSeenCommit
        self.currentCommit = currentCommit
        self.commitsSince = commitsSince
        self.stored = stored
    }

    public var change: BriefingChange {
        if firstVisit { return .firstVisit }
        guard let n = commitsSince else { return .unknown }
        return n == 0 ? .nothingChanged : .changed(n)
    }
}

/// What a briefing can say, as a closed set.
///
/// Same reasoning as `IndexFreshness`: `commitsSince` is an optional Int on
/// the wire, and `?? 0` at a call site would turn "Icarus couldn't work out
/// what changed" into "nothing changed" — a reassuring falsehood. An enum
/// leaves no default to fall into.
public enum BriefingChange: Equatable, Sendable {
    case firstVisit
    case nothingChanged
    case changed(Int)
    /// The comparison did not complete. Not "nothing changed".
    case unknown

    public var summary: String {
        switch self {
        case .firstVisit:
            return "First time you’ve looked at this repository here."
        case .nothingChanged:
            return "Nothing has changed since you were last here."
        case .changed(let n):
            return "\(n) commit\(n == 1 ? "" : "s") since you were last here."
        case .unknown:
            return "Icarus couldn’t work out what has changed since your last visit."
        }
    }
}
