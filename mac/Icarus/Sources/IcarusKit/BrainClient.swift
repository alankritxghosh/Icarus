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

    /// GET /status -> the active repo + switch state.
    public func status() async throws -> RepoStatus {
        let (data, response) = try await session.data(from: base.appending(path: "status"))
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(RepoStatus.self, from: data)
    }
}
