import Foundation

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

    public init(base: URL = URL(string: "http://127.0.0.1:8000")!,
                token: @Sendable @escaping () -> String? = { nil },
                session: URLSession = .shared) {
        self.base = base
        self.token = token
        self.session = session
    }

    /// Attach `Authorization: Bearer <token>` when a token is available.
    private func authorize(_ request: inout URLRequest) {
        if let t = token(), !t.isEmpty {
            request.setValue("Bearer \(t)", forHTTPHeaderField: "Authorization")
        }
    }

    /// POST /ask {question} -> AskResponse. Throws on transport/HTTP/decoding error.
    public func ask(_ question: String) async throws -> AskResponse {
        var request = URLRequest(url: base.appending(path: "ask"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["question": question])
        authorize(&request)

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
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
        let (_, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
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
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(RepoStatus.self, from: data)
    }

    /// POST /auth/github/begin -> the GitHub authorize URL to open in the sheet.
    /// No bearer needed (this is how you get one).
    public func beginGitHubLogin() async throws -> URL {
        var request = URLRequest(url: base.appending(path: "auth/github/begin"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = Data("{}".utf8)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
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
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        struct Redeem: Decodable { let token: String }
        return try JSONDecoder().decode(Redeem.self, from: data).token
    }

    /// GET /status -> the active repo + switch state. MUST carry the bearer:
    /// in the hosted auth-required mode the brain resolves the caller's own
    /// library by identity, so an unauthenticated /status returns the shared
    /// public default instead of the caller's connected (possibly private) repo
    /// — which would make the connect poll never see its repo go ready.
    public func status() async throws -> RepoStatus {
        var request = URLRequest(url: base.appending(path: "status"))
        authorize(&request)
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(RepoStatus.self, from: data)
    }
}
