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

    public init(verdict: Verdict, answer: String, citations: [Citation],
                searched: [String], anchored: [String]? = nil) {
        self.verdict = verdict
        self.answer = answer
        self.citations = citations
        self.searched = searched
        self.anchored = anchored
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

    private enum CodingKeys: String, CodingKey {
        case state, repo, commit, counts, error, phase, truncated
        case isPrivate = "private"
    }

    public var isReady: Bool { state == "ready" }
    public var isError: Bool { state == "error" }
    public var isTruncated: Bool { truncated == true }
    /// The brain's own name for this connection, shown in the sidebar.
    public var brainName: String { isPrivate == true ? "COMPANY BRAIN" : "REPO BRAIN" }
}
