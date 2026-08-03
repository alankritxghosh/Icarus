import Foundation

/// The brain's verdict. `answer` = grounded, cited reply; `unknown` = the honest
/// "no one wrote this down". The app renders this verbatim and NEVER recomputes
/// it — the deterministic honesty gate lives in the Python brain, not here.
public enum Verdict: String, Decodable, Sendable {
    case answer
    case unknown
}

/// One citation: a `source:ref` token and the GitHub URL the brain resolved for
/// it. `url` is optional because the brain returns null for unknown/malformed refs.
public struct Citation: Decodable, Identifiable, Hashable, Sendable {
    public let ref: String
    public let url: String?
    /// A bounded quote of the cited evidence, sent by the brain so the overlay can
    /// show the PROOF rather than a pointer to it. Optional on purpose: a brain
    /// deployed before this field existed simply omits it, and the app falls back
    /// to showing the ref alone instead of failing to decode the whole answer.
    /// Truncation is already marked with '…' server-side (demo/payload.excerpt).
    public let excerpt: String?
    public var id: String { ref }

    /// `excerpt` defaults to nil so a citation can still be constructed from just a ref
    /// and URL — the shape older code and tests already use.
    public init(ref: String, url: String?, excerpt: String? = nil) {
        self.ref = ref
        self.url = url
        self.excerpt = excerpt
    }
}

/// The `/ask` response, mirroring demo/payload.py:
/// `{verdict, answer, citations:[{ref,url}], searched:[...], anchored:[...]}`.
/// `searched` is always present (the retrieved refs) so an abstention is transparent.
public struct AskResponse: Decodable, Sendable {
    public let verdict: Verdict
    public let answer: String
    public let citations: [Citation]
    public let searched: [String]
    /// The refs looked up because the QUESTION named them ("PR 6952"), as
    /// opposed to the ones search suggested. Always a prefix of `searched`.
    /// Optional so a brain deployed before this field existed still decodes —
    /// the UI then falls back to the flat list, exactly as it read before.
    public let anchored: [String]?
    /// True when this answer was produced while the search index was still
    /// being built (lexical only, semantic pending). Optional so a brain
    /// without the field still decodes; absent reads as "index complete",
    /// which is the pre-existing behaviour.
    public let indexing: Bool?

    public init(verdict: Verdict, answer: String, citations: [Citation],
                searched: [String], anchored: [String]? = nil,
                indexing: Bool? = nil) {
        self.verdict = verdict
        self.answer = answer
        self.citations = citations
        self.searched = searched
        self.anchored = anchored
        self.indexing = indexing
    }
}

public extension AskResponse {
    /// The caveat an abstention MUST carry while the index is still building.
    ///
    /// "No one wrote this down" and "I have not finished reading" are different
    /// claims, and only the first one is this product's promise. Measured live
    /// 2026-07-28: the same question abstained 3/3 mid-build and answered 3/3
    /// once the embed finished — identical corpus, anchor and writer. Showing
    /// the honest-unknown hero in that window states something the brain does
    /// not yet know to be true.
    ///
    /// nil for answers (an answer is grounded whenever it is emitted, so the
    /// caveat would only add doubt to a citation that is already earned) and
    /// nil once the index is complete.
    var incompleteIndexNote: String? {
        guard indexing == true, verdict == .unknown else { return nil }
        return "Still reading this repository — ask again once indexing finishes."
    }
}

public extension AskResponse {
    /// What the brain looked up because you NAMED it — nil when the question
    /// named nothing resolvable, which is the common case.
    ///
    /// This line exists because a flat list of twenty refs made a correctly
    /// anchored abstention ("PR 6952" read FIRST, exactly as asked) read as
    /// "ignored the question and searched blindly" (reported live 2026-07-28).
    var anchoredLine: String? {
        let named = anchored ?? []
        guard !named.isEmpty else { return nil }
        return "you named: " + named.joined(separator: " · ")
    }

    /// Everything else that was consulted. Still lists every remaining ref —
    /// "all of them shown" is a transparency claim this product has to keep,
    /// not a summary — but leads with the count so it reads at a glance.
    var searchedLine: String {
        let named = Set(anchored ?? [])
        let rest = searched.filter { !named.contains($0) }
        guard !rest.isEmpty else {
            return named.isEmpty ? "searched: —" : "nothing else searched"
        }
        let noun = rest.count == 1 ? "source" : "sources"
        let lead = named.isEmpty ? "searched \(rest.count) \(noun): "
                                 : "then searched \(rest.count) more: "
        return lead + rest.joined(separator: " · ")
    }

    /// The same trail for a one-line dashboard row: the named ref wins the
    /// space when there is one, since it is the part that answers "did it even
    /// look at what I asked about?".
    var compactTrail: String {
        if let named = anchoredLine {
            let rest = searched.count - (anchored ?? []).count
            return rest > 0 ? "\(named) · +\(rest) searched" : named
        }
        let shown = searched.isEmpty ? "—" : searched.prefix(4).joined(separator: " · ")
        return "searched: " + shown
    }
}

/// The corpus's real index counts (demo/library.py `counts`): how many PRs,
/// issues, and code files were ingested. Powers the metrics card with true
/// numbers — never a fabricated total.
public struct IndexCounts: Decodable, Equatable, Sendable {
    public let pr: Int
    public let issue: Int
    public let code: Int
}

/// How far the semantic embed has got, and roughly how much longer.
///
/// A connect takes minutes -- measured 185s on a small repo and 987s on a
/// large one -- and "Building smart search…" alone cannot be told apart from a
/// hang. `etaSeconds` is an ESTIMATE derived from the rate observed in that
/// run, and is nil until there is a rate to measure: there is no honest
/// estimate before the first chunk is embedded.
public struct IndexingProgress: Decodable, Equatable, Sendable {
    public let done: Int
    public let total: Int
    public let etaSeconds: Int?

    private enum CodingKeys: String, CodingKey {
        case done, total
        case etaSeconds = "eta_seconds"
    }

    public init(done: Int, total: Int, etaSeconds: Int?) {
        self.done = done
        self.total = total
        self.etaSeconds = etaSeconds
    }

    public var fraction: Double {
        total > 0 ? min(1, Double(done) / Double(total)) : 0
    }

    /// The estimate in words, or nil when there isn't one. Always hedged --
    /// "about 6 min" rather than "6 min" -- because it is a projection from a
    /// rate that varies with chunk length and how busy the host is.
    public var estimate: String? {
        guard let eta = etaSeconds, eta > 0 else { return nil }
        if eta < 60 { return "about \(eta) sec left" }
        return "about \(Int((Double(eta) / 60).rounded())) min left"
    }
}

/// The `/status` response (demo/library.py): the active repo + switch state.
/// `state` is one of "idle" | "indexing" | "ready" | "error". `counts` is an
/// object in the real payload (null while indexing), decoded for the metrics card.
public struct RepoStatus: Decodable, Equatable, Sendable {
    public let state: String
    public let repo: String
    public let commit: String
    public let counts: IndexCounts?
    public let error: String?
    /// Human-readable progress line while a connect is in flight (e.g.
    /// "Reading the repository…"). Optional so an older brain without the field
    /// still decodes; nil means nothing specific to show.
    public let phase: String?
    /// True when a size cap stopped the code walk early, so the corpus is
    /// PARTIAL — some files aren't covered. Surfaced so a dropped file's honest
    /// "no one wrote this down" is explainable, never mistaken for full coverage.
    /// Optional so an older brain without the field still decodes.
    public let truncated: Bool?
    /// True when the connected repo is PRIVATE (demo/library.py's `private`).
    /// Drives the "Company Brain" vs "Repo Brain" naming: a shared private
    /// index is a company's memory, a public one is just a repo's. Optional so
    /// an older brain still decodes; absent reads as public, the safer default
    /// (it never labels a public repo as company-private code).
    public let isPrivate: Bool?
    /// Embed progress while a connect is in flight. Optional so a brain
    /// deployed before this field existed still decodes -- absent means
    /// "no progress to report", never zero.
    public let indexingProgress: IndexingProgress?
    /// True ONLY between lexical search going live and the semantic index
    /// being installed -- the window where search is real but measurably
    /// worse. The server has always sent this on /status; the app simply
    /// never decoded it. Optional so an older brain still decodes; absent
    /// reads as "not indexing", which is the pre-existing behaviour.
    public let indexing: Bool?
    /// Whether the index still matches the repository (`demo/freshness.py`).
    /// Optional so an older brain still decodes; absent means UNKNOWN, which
    /// `indexFreshness` renders as unknown rather than as up to date.
    public let freshness: Freshness?

    private enum CodingKeys: String, CodingKey {
        case state, repo, commit, counts, error, phase, truncated, indexing
        case isPrivate = "private"
        case indexingProgress = "indexing_progress"
        case freshness
    }

    public var isReady: Bool { state == "ready" }
    public var isError: Bool { state == "error" }
    public var isTruncated: Bool { truncated == true }
    /// Is the semantic index still building? Absent reads as no.
    public var isIndexing: Bool { indexing == true }
    /// The brain's own name for this connection, shown in the sidebar.
    public var brainName: String { isPrivate == true ? "COMPANY BRAIN" : "REPO BRAIN" }
    /// The repository visibility label shown beside the active repo.
    public var repositoryVisibilityName: String {
        isPrivate == true ? "private repo" : "public repo"
    }

    /// Staleness as a CLOSED SET of cases rather than an optional Bool.
    ///
    /// This is the whole reason the type exists. `Freshness.upToDate` is
    /// three-valued on the wire, and a `Bool?` in Swift invites `?? false` --
    /// which would silently render "I could not check" as "up to date", the
    /// one thing the server side of this feature was built to never do. An
    /// enum has no such default: every call site must name the unknown case.
    public var indexFreshness: IndexFreshness { freshness?.state ?? .unknown }

    /// One line a waiting user can act on: how far in, and roughly how long.
    /// nil when there is nothing real to report -- never a fabricated 0%.
    public var indexingLine: String? {
        guard let p = indexingProgress, p.total > 0 else { return nil }
        let done = Self.grouped(p.done), total = Self.grouped(p.total)
        guard let estimate = p.estimate else { return "read \(done) of \(total)" }
        return "read \(done) of \(total) · \(estimate)"
    }

    private static func grouped(_ n: Int) -> String {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        return f.string(from: NSNumber(value: n)) ?? String(n)
    }
}

/// One recorded ask from the repo's shared ledger (`demo/ledger.py`).
///
/// Deliberately carries NO identity. The server never records who asked, so a
/// gap can be ranked by how OFTEN it was hit and never by how many DISTINCT
/// people hit it — that is memory for a team rather than surveillance of one,
/// and the absence is guarded by a test on the server.
public struct LedgerEntry: Decodable, Sendable {
    public let ts: Double
    public let question: String
    public let verdict: Verdict
    public let citations: [String]
    /// WHY the gate abstained (evals/gate.py's ABSTAIN_* constants). Optional:
    /// entries written before this field existed carry no reason, and an
    /// answer never has one.
    public let reason: String?

    public init(ts: Double, question: String, verdict: Verdict,
                citations: [String], reason: String? = nil) {
        self.ts = ts
        self.question = question
        self.verdict = verdict
        self.citations = citations
        self.reason = reason
    }
}

/// What an abstention actually MEANT, for the unknowns map.
///
/// Only `undocumented` is a documentation gap the team can act on. Rendering
/// the others as one would overstate their debt — a fabricated symbol is not a
/// missing decision record, it is a question about something that isn't there.
public enum GapKind: String, Sendable {
    case undocumented       // the thing exists; nobody wrote down why
    case notInThisRepo      // the named thing isn't in what we indexed
    case unclear            // recorded before reasons existed, or a defect

    public init(reason: String?) {
        switch reason {
        case "no_recorded_reason", "writer_abstained", "self_disclaimed", "no_evidence":
            self = .undocumented
        case "entity_absent":
            self = .notInThisRepo
        default:
            self = .unclear
        }
    }

    public var label: String? {
        switch self {
        case .undocumented: return nil          // the default case needs no badge
        case .notInThisRepo: return "not in this repo"
        case .unclear: return "reason not recorded"
        }
    }
}

/// The `GET /ledger` response: the repo's shared ask record.
public struct LedgerResponse: Decodable, Sendable {
    public let repo: String
    public let entries: [LedgerEntry]

    public init(repo: String, entries: [LedgerEntry]) {
        self.repo = repo
        self.entries = entries
    }
}

/// One documentation gap: a question the record could not answer, and how many
/// times the team hit it.
public struct Gap: Identifiable, Sendable, Equatable {
    public let question: String
    public let count: Int
    public let lastAsked: Double
    /// What this gap actually is. A `.notInThisRepo` gap is NOT documentation
    /// debt and must not be presented as if it were.
    public let kind: GapKind
    public var id: String { question }
}

public extension LedgerResponse {
    /// Unknowns collapsed into ranked gaps — the map of what this codebase
    /// never wrote down.
    ///
    /// Ranked by FREQUENCY, because that is the honest signal available: the
    /// ledger stores no asker, so "asked nine times" cannot be distinguished
    /// between one frustrated person and nine different ones. Ties break on
    /// most-recent, so an equally-common gap that is live outranks a stale one.
    ///
    /// Questions are matched case-insensitively on trimmed text — deliberately
    /// literal, never fuzzy: clustering near-identical phrasings would merge
    /// two genuinely different questions and silently overstate a gap.
    var gaps: [Gap] {
        var counts: [String: (display: String, n: Int, last: Double, kind: GapKind)] = [:]
        for e in entries where e.verdict == .unknown {
            let text = e.question.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { continue }
            let key = text.lowercased()
            let kind = GapKind(reason: e.reason)
            let prior = counts[key]
            // The most RECENT classification wins for a repeated question: an
            // older entry may predate reasons entirely, and treating that as
            // authoritative would permanently mark a real gap "unclear".
            let resolved = (prior == nil || e.ts >= prior!.last) ? kind : prior!.kind
            counts[key] = (prior?.display ?? text,
                           (prior?.n ?? 0) + 1,
                           max(prior?.last ?? 0, e.ts),
                           resolved)
        }
        return counts.values
            .map { Gap(question: $0.display, count: $0.n, lastAsked: $0.last, kind: $0.kind) }
            .sorted { $0.count == $1.count ? $0.lastAsked > $1.lastAsked : $0.count > $1.count }
    }
}
