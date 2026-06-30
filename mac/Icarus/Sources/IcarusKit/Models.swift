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
    public var id: String { ref }
}

/// The `/ask` response, mirroring demo/payload.py:
/// `{verdict, answer, citations:[{ref,url}], searched:[...]}`.
/// `searched` is always present (the retrieved refs) so an abstention is transparent.
public struct AskResponse: Decodable, Sendable {
    public let verdict: Verdict
    public let answer: String
    public let citations: [Citation]
    public let searched: [String]
}

/// The `/health` response: liveness + which repo/commit the brain is serving.
public struct Health: Decodable, Sendable {
    public let ok: Bool
    public let repo: String
    public let commit: String
}

/// The `/status` response (demo/library.py): the active repo + switch state.
/// `state` is one of "idle" | "indexing" | "ready" | "error". (`counts` is an
/// object in the real payload and unused here, so it's intentionally not decoded.)
public struct RepoStatus: Decodable, Sendable {
    public let state: String
    public let repo: String
    public let commit: String
    public let error: String?

    public var isReady: Bool { state == "ready" }
    public var isError: Bool { state == "error" }
}
