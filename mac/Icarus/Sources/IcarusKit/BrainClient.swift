import Foundation

/// Talks to the local Python brain over HTTP (demo/server.py). The app is a thin
/// client: it sends the question and renders whatever the brain returns. It does
/// NOT judge grounding — that's the brain's deterministic honesty gate.
public struct BrainClient: Sendable {
    public let base: URL

    public init(base: URL = URL(string: "http://127.0.0.1:8000")!) {
        self.base = base
    }

    /// POST /ask {question} -> AskResponse. Throws on transport/HTTP/decoding error.
    public func ask(_ question: String) async throws -> AskResponse {
        var request = URLRequest(url: base.appending(path: "ask"))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: ["question": question])

        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode(AskResponse.self, from: data)
    }

    /// GET /health -> true iff the brain is reachable and reports ok. Never throws.
    public func isHealthy() async -> Bool {
        guard
            let (data, _) = try? await URLSession.shared.data(from: base.appending(path: "health")),
            let health = try? JSONDecoder().decode(Health.self, from: data)
        else { return false }
        return health.ok
    }
}
