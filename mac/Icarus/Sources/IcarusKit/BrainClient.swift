import Foundation

/// Why a brain request failed, when the brain actually ANSWERED and said no.
///
/// Kept distinct from a transport failure (a thrown `URLError`: the request never
/// got an answer at all) on purpose. Conflating the two is exactly what made a
/// slow-but-SUCCEEDING first-time connect render as "check your internet
/// connection" — the host cut the request open at its ingress ceiling while the
/// server kept working and finished, and the app reported a network problem that
/// did not exist. "The server said no" and "we never heard back" demand different
/// words and different recovery, so they get different types.
public enum BrainError: Error, Equatable, Sendable {
    case unauthorized       // 401 — signed out, or the token was rejected
    case forbidden          // 403 — this GitHub account can't read that repo (or it's private)
    case rateLimited        // 429 — too many requests from this identity
    case memoryRateLimited(retryAfter: Int?)
    /// 429 on a request that asked to RE-READ the repository. Same status code,
    /// different budget: the ordinary connect allowance clears in about a
    /// minute, the refresh allowance is 2 per hour (demo/server.py), because a
    /// refresh re-reads the whole repository — 283 seconds measured on
    /// production. Telling that user to "wait a minute" would be a confident
    /// claim about a wait we know is longer. Distinguished by what we SENT,
    /// not by parsing the body: the client knows whether it asked to refresh.
    case refreshRateLimited
    case server(Int)        // any other non-2xx

    /// Plain-language copy for a refusal the brain actually sent us. Every one of
    /// these used to reach the user as "check your internet connection", sending
    /// them to debug a network that was never the problem. Lives here (not in the
    /// view) so it is unit-testable.
    public var userMessage: String {
        switch self {
        case .unauthorized:
            return "You're signed out. Sign in with GitHub again to continue."
        case .forbidden:
            return "That repo doesn't exist, or your GitHub account can't read it."
        case .rateLimited:
            return "Too many attempts in a row. Wait a minute, then try again."
        case .memoryRateLimited(let seconds):
            guard let seconds, seconds > 0 else {
                return "Too many decision proposals. Try again later."
            }
            let minutes = seconds / 60 + (seconds % 60 == 0 ? 0 : 1)
            return "Too many decision proposals. Try again in \(minutes) \(minutes == 1 ? "minute" : "minutes")."
        case .refreshRateLimited:
            return "Icarus re-reads a whole repository on a refresh, so it allows a couple an hour. Try again later."
        case .server(let code):
            return "Icarus's brain had a problem (error \(code)). Try again in a moment."
        }
    }
}

public struct AgentSession: Codable, Equatable, Sendable {
    public let token: String
    public let expiresAt: TimeInterval
    public let repo: String

    enum CodingKeys: String, CodingKey {
        case token
        case expiresAt = "expires_at"
        case repo
    }
}

/// Talks to the local Python brain over HTTP (demo/server.py). The app is a thin
/// client: it sends the question and renders whatever the brain returns. It does
/// NOT judge grounding — that's the brain's deterministic honesty gate.
public struct BrainClient: Sendable {
    public let base: URL
    /// Supplies the current GitHub token (from the Keychain) for the Authorization
    /// header. Read lazily at request time so a fresh sign-in takes effect at once.
    /// Defaults to no token — the open web-demo mode needs none.
    private let token: @Sendable () -> String?
    /// Read lazily at request time, same as `token` -- flipping the Settings
    /// toggle takes effect on the very next request, not just after relaunch.
    /// Defaults to sharing ON, matching the server's own default when the
    /// header is absent.
    private let shareContent: @Sendable () -> Bool
    /// Injectable so tests can capture the outgoing request via a URLProtocol stub.
    private let session: URLSession
    /// Delay before the one cold-start retry (see `dataWithRetry`). Injectable so
    /// tests prove the retry happens without a real multi-second sleep.
    private let retryDelay: Duration

    public init(base: URL = URL(string: "http://127.0.0.1:8000")!,
                token: @Sendable @escaping () -> String? = { nil },
                // Defaults to NOT sharing: a caller that forgets to wire the
                // reader must not opt a user in on their behalf.
                shareContent: @Sendable @escaping () -> Bool = { false },
                session: URLSession = .shared,
                retryDelay: Duration = .seconds(3)) {
        self.base = base
        self.token = token
        self.shareContent = shareContent
        self.session = session
        self.retryDelay = retryDelay
    }

    /// Attach `Authorization: Bearer <token>` when a token is available, plus
    /// which client is calling -- the server's product-analytics capture
    /// (demo/server.py's `_capture_product_event`) uses this to tell the Mac
    /// app apart from the browser extension; both authenticate identically
    /// via GitHub, so there's no other signal available server-side. Also the
    /// content-sharing choice. The header is sent on EVERY request, stating
    /// the choice either way, because the server shares content only on an
    /// exact "1" and is counts-only otherwise (CLAUDE.md, 2026-08-14). Sending
    /// it only to opt OUT -- as this did -- meant the Settings toggle's ON
    /// position shared nothing at all. Stating it explicitly also means this
    /// client keeps doing what the user chose if the server's default ever
    /// moves again, rather than inheriting whatever that default becomes.
    private func authorize(_ request: inout URLRequest) {
        if let t = token(), !t.isEmpty {
            request.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        }
        request.setValue("mac-app", forHTTPHeaderField: "X-Icarus-Client")
        request.setValue(shareContent() ? "1" : "0",
                         forHTTPHeaderField: "X-Icarus-Share-Content")
    }

    /// Retries the transport call ONCE after a short delay if it throws --
    /// absorbs a cloud host's cold-start hiccup rather than surfacing a scary
    /// error on a blip that resolves itself moments later. Live-observed on
    /// Azure Container Apps' min-replicas=0 consumption plan: a scaled-to-zero
    /// container's first request after idle can transiently fail while the
    /// platform spins up a replica, then succeed cleanly on the very next
    /// attempt with zero code involved -- exactly the shape a brief retry
    /// fixes for free, instead of paying to keep a replica always warm
    /// (~$24/mo at this app's size, verified against Azure's own pricing).
    /// Does NOT retry a real HTTP response (4xx/5xx) -- only a transport-level
    /// throw (unreachable / timed out), since a definitive answer isn't a blip.
    private func dataWithRetry(for request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch {
            try await Task.sleep(for: retryDelay)
            return try await session.data(for: request)
        }
    }

    /// Convert a non-2xx HTTP response into a typed `BrainError`. Deliberately does
    /// NOT touch transport failures: those stay `URLError` throws from
    /// `dataWithRetry`, so a caller can distinguish "answered, and refused" from
    /// "never answered" (see `BrainError`).
    private func check(_ response: URLResponse, accepting: ClosedRange<Int> = 200...200) throws {
        guard let http = response as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard accepting.contains(http.statusCode) else {
            switch http.statusCode {
            case 401: throw BrainError.unauthorized
            case 403: throw BrainError.forbidden
            case 429: throw BrainError.rateLimited
            default:  throw BrainError.server(http.statusCode)
            }
        }
    }

    /// POST /ask {question} -> AskResponse. Throws on transport/HTTP/decoding error.
    public func ask(_ question: String) async throws -> AskResponse {
        var request = URLRequest(url: base.appending(path: "ask"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["question": question])
        authorize(&request)

        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(AskResponse.self, from: data)
    }

    /// POST /investigate: a multi-step, evidence-backed investigation rather
    /// than a single ask.
    ///
    /// Conversational continuity is held SERVER-SIDE, keyed on the caller's
    /// identity and connected repo (demo/investigations.py), so the app sends
    /// only the question — it never tracks or transmits what "it" refers to.
    /// That keeps one subject-resolution rule for every client instead of each
    /// one inventing its own, and it means a follow-up cannot be aimed at a
    /// subject the server never agreed to.
    ///
    /// `fresh` abandons the current conversation and starts a new enquiry.
    public func investigate(_ question: String,
                            fresh: Bool = false) async throws -> InvestigationResponse {
        var request = URLRequest(url: base.appending(path: "investigate"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(
            withJSONObject: ["question": question, "fresh": fresh])
        authorize(&request)

        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(InvestigationResponse.self, from: data)
    }

    /// POST /explain for one GitHub line selection. Used by the Mac-owned
    /// native extension bridge so the GitHub credential remains in Keychain.
    public func explain(
        repo: String,
        path: String,
        start: Int,
        end: Int,
        question: String? = nil
    ) async throws -> AskResponse {
        var request = URLRequest(url: base.appending(path: "explain"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = [
            "repo": repo,
            "path": path,
            "start": start,
            "end": end,
        ]
        if let question, !question.isEmpty {
            body["question"] = question
        }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(AskResponse.self, from: data)
    }

    /// POST /connect {repo} -> start indexing/switching to that public repo. The
    /// brain ingests in the background; poll `status()` until ready. 2xx = accepted.
    /// `refresh: true` asks the brain to RE-INGEST a repo it already has cached,
    /// rather than serving the existing corpus. Only send it when the user asked:
    /// it costs minutes of server CPU and republishes a corpus other entitled
    /// readers may be mid-question on. The key is omitted entirely when false —
    /// the server's default — so an ordinary connect cannot spend that budget.
    public func connect(repo: String, refresh: Bool = false) async throws {
        var request = URLRequest(url: base.appending(path: "connect"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var body: [String: Any] = ["repo": repo]
        if refresh { body["refresh"] = true }
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        authorize(&request)
        let (_, response) = try await dataWithRetry(for: request)
        do {
            try check(response, accepting: 200...299)
        } catch BrainError.rateLimited where refresh {
            // Same 429, different budget — see BrainError.refreshRateLimited.
            throw BrainError.refreshRateLimited
        }
    }

    /// POST /disconnect -> the brain deletes the caller's own on-disk corpus and
    /// resets their library to the public default, replying with the fresh
    /// status snapshot. Requires the bearer in hosted (auth-required) mode.
    @discardableResult
    public func disconnect() async throws -> RepoStatus {
        var request = URLRequest(url: base.appending(path: "disconnect"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(RepoStatus.self, from: data)
    }

    /// POST /auth/github/begin -> the GitHub authorize URL to open in the sheet.
    /// No bearer needed (this is how you get one).
    /// `privateAccess` asks GitHub for the `repo` scope instead of identity
    /// alone. Kept OFF for an ordinary sign-in: `repo` is read AND write on
    /// every private repository, and asking for it before the user has
    /// connected anything is what makes a stranger close the window. The
    /// upgrade is offered at the moment a private repository is actually being
    /// connected, and GitHub keeps the union of granted scopes, so it is
    /// additive rather than a re-authorisation.
    public func beginGitHubLogin(privateAccess: Bool = false) async throws -> URL {
        var request = URLRequest(url: base.appending(path: "auth/github/begin"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body = privateAccess ? #"{"mode":"app-private"}"# : "{}"
        request.httpBody = Data(body.utf8)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        struct Begin: Decodable { let authorize_url: String }
        let url = try JSONDecoder().decode(Begin.self, from: data).authorize_url
        guard let authorizeURL = URL(string: url) else { throw URLError(.badURL) }
        return authorizeURL
    }

    /// POST /auth/github/redeem -> the access token for a one-time session id.
    public func redeemGitHubSession(_ sessionID: String) async throws -> String {
        var request = URLRequest(url: base.appending(path: "auth/github/redeem"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["session": sessionID])
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        struct Redeem: Decodable { let token: String }
        return try JSONDecoder().decode(Redeem.self, from: data).token
    }

    /// Exchange the app-owned GitHub bearer for a short-lived, read-only
    /// credential suitable for a coding-agent process. The GitHub token remains
    /// behind this client boundary and is never part of the returned value.
    public func createAgentSession() async throws -> AgentSession {
        var request = URLRequest(url: base.appending(path: "auth/agent/session"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(AgentSession.self, from: data)
    }

    /// GET /status -> the active repo + switch state. MUST carry the bearer:
    /// in the hosted auth-required mode the brain resolves the caller's own
    /// library by identity, so an unauthenticated /status returns the shared
    /// public default instead of the caller's connected (possibly private) repo
    /// — which would make the connect poll never see its repo go ready.
    /// GET /ledger?gaps=1 — the server-owned engineering-memory lifecycle.
    ///
    /// The server owns identity and lifecycle because it sees the repository's
    /// shared chronological record.
    public func memoryGaps(includeResolved: Bool = true) async throws -> MemoryGapsResponse {
        var items = [URLQueryItem(name: "gaps", value: "1")]
        if includeResolved {
            items.append(URLQueryItem(name: "resolved", value: "1"))
        }
        var request = URLRequest(
            url: base.appendingPathComponent("ledger").appending(queryItems: items)
        )
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(MemoryGapsResponse.self, from: data)
    }

    /// Propose one human-authored record for an existing actionable Memory Gap.
    /// The brain bounds the GitHub write to one branch, one new file, and one
    /// pull request; this client renders success only after decoding the
    /// observed pull-request URL.
    public func recordEngineeringMemory(
        gapID: String,
        rationale: String,
        tradeoffs: String = "",
        references: [String] = []
    ) async throws -> MemoryRecordResult {
        var request = URLRequest(url: base.appending(path: "memory-gaps/record"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: [
            "gap_id": gapID,
            "rationale": rationale,
            "tradeoffs": tradeoffs,
            "references": references,
        ])
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        if !(200...299).contains(http.statusCode) {
            switch http.statusCode {
            case 401: throw BrainError.unauthorized
            case 403: throw BrainError.forbidden
            case 429: throw BrainError.memoryRateLimited(
                retryAfter: http.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init))
            default:
                struct FailureBody: Decodable {
                    let error: String?
                    let recoveryURL: URL?

                    enum CodingKeys: String, CodingKey {
                        case error
                        case recoveryURL = "recovery_url"
                    }
                }
                let body = try? JSONDecoder().decode(FailureBody.self, from: data)
                throw MemoryRecordFailure(
                    status: http.statusCode,
                    message: body?.error ?? "GitHub could not create the memory proposal",
                    recoveryURL: body?.recoveryURL
                )
            }
        }
        return try JSONDecoder().decode(MemoryRecordResult.self, from: data)
    }

    /// Pending Agent Mode recommendations for the connected repository. The
    /// response contains no raw transcript or session correlation identifier.
    public func decisionCandidates() async throws -> DecisionCandidatesResponse {
        var request = URLRequest(url: base.appending(path: "agent-mode/candidates"))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(DecisionCandidatesResponse.self, from: data)
    }

    /// Every confirmed decision for the connected repo — proposals whose PR
    /// exists but is not yet indexed, and merged decisions cited from the
    /// corpus. This is the human-facing history, distinct from the pending
    /// inbox (`decisionCandidates`). Served on the same `/agent-mode/context`
    /// projection a fresh coding session reads; a GitHub identity is allowed.
    public func agentDecisions() async throws -> AgentDecisionsResponse {
        var request = URLRequest(url: base.appending(path: "agent-mode/context"))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(AgentDecisionsResponse.self, from: data)
    }

    /// One lightweight human choice. Only recommended/alternative/Other can
    /// create a reviewed GitHub proposal; Not sure and reject remain outside
    /// fresh-session project intent.
    public func confirmDecision(
        candidateID: String,
        selection: DecisionSelection
    ) async throws -> DecisionConfirmationResult {
        var body: [String: Any] = ["candidate_id": candidateID]
        switch selection {
        case .recommended:
            body["selection"] = "recommended"
        case .alternative(let index):
            body["selection"] = "alternative"
            body["alternative_index"] = index
        case .other(let text):
            body["selection"] = "other"
            body["other_text"] = text
        case .notSure:
            body["selection"] = "not_sure"
        case .reject:
            body["selection"] = "reject"
        }
        var request = URLRequest(url: base.appending(path: "agent-mode/confirm"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw URLError(.badServerResponse)
        }
        guard (200...299).contains(http.statusCode) else {
            switch http.statusCode {
            case 401: throw BrainError.unauthorized
            case 403: throw BrainError.forbidden
            case 429: throw BrainError.memoryRateLimited(
                retryAfter: http.value(forHTTPHeaderField: "Retry-After").flatMap(Int.init))
            default:
                struct FailureBody: Decodable {
                    let error: String?
                    let recoveryURL: URL?
                    enum CodingKeys: String, CodingKey {
                        case error
                        case recoveryURL = "recovery_url"
                    }
                }
                let failure = try? JSONDecoder().decode(FailureBody.self, from: data)
                throw MemoryRecordFailure(
                    status: http.statusCode,
                    message: failure?.error ?? "Icarus could not confirm this decision",
                    recoveryURL: failure?.recoveryURL
                )
            }
        }
        return try JSONDecoder().decode(DecisionConfirmationResult.self, from: data)
    }

    public func status() async throws -> RepoStatus {
        var request = URLRequest(url: base.appending(path: "status"))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(RepoStatus.self, from: data)
    }

    /// GET /onboarding -> the guided tour's PLAN. Costs no writer call, so it
    /// is safe to fetch the moment a repo connects.
    public func onboardingPlan() async throws -> OnboardingPlan {
        var request = URLRequest(url: base.appending(path: "onboarding"))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(OnboardingPlan.self, from: data)
    }

    /// POST /onboarding {step} -> one cited tour step. Reaches the same billed
    /// writer as `ask`, and shares its rate limit on the brain's side.
    public func onboardingStep(_ step: String) async throws -> TourStepAnswer {
        var request = URLRequest(url: base.appending(path: "onboarding"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["step": step])
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(TourStepAnswer.self, from: data)
    }

    /// GET /briefing -> what changed since this user was last here.
    ///
    /// PURE: reading a briefing does not consume it. Acknowledging is a
    /// separate POST, so a client that crashes mid-render does not lose the
    /// briefing permanently.
    public func briefing() async throws -> Briefing {
        var request = URLRequest(url: base.appending(path: "briefing"))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(Briefing.self, from: data)
    }

    /// POST /briefing -> acknowledge it, moving the anchor to the current
    /// commit. Call this only once the user has actually SEEN the briefing.
    public func acknowledgeBriefing() async throws {
        var request = URLRequest(url: base.appending(path: "briefing"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)
        authorize(&request)
        let (_, response) = try await dataWithRetry(for: request)
        try check(response)
    }

    /// GET /map -> what Icarus has INDEXED for the connected repo. Deterministic
    /// and writer-free, which is why the tour opens with it.
    public func repoMap() async throws -> RepoMap {
        var request = URLRequest(url: base.appending(path: "map"))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(RepoMap.self, from: data)
    }
}
