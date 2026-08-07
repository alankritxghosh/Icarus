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

    /// `index:` evidence is Icarus reporting what it READ — file counts,
    /// languages, what got indexed — measured from the repository rather than
    /// written by anyone (see evals/index_facts.py). Every other citation
    /// points at something a person authored, so this one must not look the
    /// same: `index:overview` sitting in a row beside `pr:1482` reads as a
    /// document somebody wrote, which is precisely the claim it may not make.
    public var isIndex: Bool { ref.hasPrefix("index:") }

    /// What a reader should SEE on the chip. Words for the index, the raw ref
    /// for everything else (a ref is genuinely the most useful label there —
    /// it is what a reader would search for).
    public var displayLabel: String { isIndex ? "Icarus's own index" : ref }

    /// The URL to open, or nil when there is nothing to open. Index evidence is
    /// nil unconditionally — the server already sends no URL for it
    /// (demo/links.ref_to_url), and this makes that a property of the client
    /// too rather than trust in the server's restraint.
    public var linkURL: URL? {
        guard !isIndex, let url, let parsed = URL(string: url) else { return nil }
        return parsed
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

/// Server-owned lifecycle state for one exact-text engineering-memory gap.
/// Unknown values fail decoding: rendering an invented "open" or "resolved"
/// state would be a product claim without evidence.
public enum MemoryGapStatus: String, Decodable, Sendable {
    case open
    case proposed
    case resolved
}

public struct MemoryGap: Decodable, Sendable, Equatable, Identifiable {
    public let id: String
    public let question: String
    public let unknownCount: Int
    public let lastAsked: Double
    public let status: MemoryGapStatus
    public let kind: String
    public let actionable: Bool
    public let resolutionCitations: [String]
    public let proposal: MemoryRecordResult?

    enum CodingKeys: String, CodingKey {
        case id, question
        case unknownCount = "unknown_count"
        case lastAsked = "last_asked"
        case status
        case kind
        case actionable
        case resolutionCitations = "resolution_citations"
        case proposal
    }
}

public struct MemoryGapsResponse: Decodable, Sendable, Equatable {
    public let repo: String
    public let gaps: [MemoryGap]

    public var open: [MemoryGap] { gaps.filter { $0.status == .open } }
    public var proposed: [MemoryGap] { gaps.filter { $0.status == .proposed } }
    public var resolved: [MemoryGap] { gaps.filter { $0.status == .resolved } }
}

/// GitHub artifacts observed after one explicit memory-record proposal.
/// A pull-request URL is required: without it the client must not claim the
/// proposal succeeded.
public struct MemoryRecordResult: Decodable, Sendable, Equatable {
    public let repo: String
    public let question: String
    public let branch: String
    public let path: String
    public let fileURL: URL?
    public let pullRequestURL: URL

    enum CodingKeys: String, CodingKey {
        case repo, question, branch, path
        case fileURL = "file_url"
        case pullRequestURL = "pull_request_url"
    }
}

public struct MemoryRecordFailure: Error, Sendable, Equatable {
    public let status: Int
    public let message: String
    public let recoveryURL: URL?

    public init(status: Int, message: String, recoveryURL: URL?) {
        self.status = status
        self.message = message
        self.recoveryURL = recoveryURL
    }
}
