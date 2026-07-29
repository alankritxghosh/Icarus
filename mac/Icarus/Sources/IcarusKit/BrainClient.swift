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
        case .server(let code):
            return "Icarus's brain had a problem (error \(code)). Try again in a moment."
        }
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
    /// Injectable so tests can capture the outgoing request via a URLProtocol stub.
    private let session: URLSession
    /// Delay before the one cold-start retry (see `dataWithRetry`). Injectable so
    /// tests prove the retry happens without a real multi-second sleep.
    private let retryDelay: Duration

    public init(base: URL = URL(string: "http://127.0.0.1:8000")!,
                token: @Sendable @escaping () -> String? = { nil },
                session: URLSession = .shared,
                retryDelay: Duration = .seconds(3)) {
        self.base = base
        self.token = token
        self.session = session
        self.retryDelay = retryDelay
    }

    /// Attach `Authorization: Bearer <token>` when a token is available.
    private func authorize(_ request: inout URLRequest) {
        if let t = token(), !t.isEmpty {
            request.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        }
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

    /// POST /connect {repo} -> start indexing/switching to that public repo. The
    /// brain ingests in the background; poll `status()` until ready. 2xx = accepted.
    public func connect(repo: String) async throws {
        var request = URLRequest(url: base.appending(path: "connect"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["repo": repo])
        authorize(&request)
        let (_, response) = try await dataWithRetry(for: request)
        try check(response, accepting: 200...299)
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
    public func beginGitHubLogin() async throws -> URL {
        var request = URLRequest(url: base.appending(path: "auth/github/begin"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)
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

    /// GET /status -> the active repo + switch state. MUST carry the bearer:
    /// in the hosted auth-required mode the brain resolves the caller's own
    /// library by identity, so an unauthenticated /status returns the shared
    /// public default instead of the caller's connected (possibly private) repo
    /// — which would make the connect poll never see its repo go ready.
    /// GET /ledger — the repo's shared ask record. `unknownsOnly` asks the
    /// server for just the abstentions: the map of what the team never wrote
    /// down, which is the whole point of keeping the record.
    public func ledger(unknownsOnly: Bool = true) async throws -> LedgerResponse {
        var request = URLRequest(url: base.appendingPathComponent("ledger")
            .appending(queryItems: [URLQueryItem(name: "unknowns",
                                                 value: unknownsOnly ? "1" : "0")]))
        authorize(&request)
        let (data, response) = try await dataWithRetry(for: request)
        try check(response)
        return try JSONDecoder().decode(LedgerResponse.self, from: data)
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
