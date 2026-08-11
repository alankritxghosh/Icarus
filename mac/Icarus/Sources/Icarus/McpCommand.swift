import Foundation
import IcarusKit

/// `Icarus --mcp` — the stdio MCP server a coding agent launches.
///
/// This is how Icarus reaches a user who has not cloned the repository: they
/// install the app they were going to install anyway, and point their agent at
/// the app binary. No Python, no checkout, no separate package (macOS ships no
/// python3 by default, so the Python adapter was reachable only from a dev
/// machine).
///
/// The GitHub credential never leaves this process. Every brain call carries a
/// short-lived, read-only, route-scoped agent session minted the same way
/// `--agent-session` mints one for the Python adapter -- deliberately NOT the
/// Keychain token, so a bug here cannot widen what an agent can reach.
enum McpCommand {
    static var requested: Bool {
        CommandLine.arguments.dropFirst().contains("--mcp")
    }

    static func run() async -> Int32 {
        guard let token = AppConfig.tokenReader(), !token.isEmpty else {
            // stderr, not stdout: stdout is the JSON-RPC channel and a stray
            // line there breaks the client's parser rather than informing it.
            writeError("Icarus is signed out. Open the app, sign in with GitHub, "
                       + "and connect a repository.")
            return 1
        }
        let server = McpServer(transport: makeTransport())
        await serve(server: server)
        return 0
    }

    /// Newline-delimited JSON-RPC, one message per line, until stdin closes.
    ///
    /// Reads with a blocking `readLine` rather than `FileHandle.bytes.lines`:
    /// the latter produced a server that accepted input and never emitted a
    /// byte — verified by driving the real binary, which hung with empty stdout
    /// and empty stderr. A dedicated stdio process is exactly the place where a
    /// blocking read is correct, and `await` on each brain call still lets
    /// URLSession make progress on its own threads.
    ///
    /// `read` and `write` are injected so the loop is testable without a pipe.
    static func serve(server: McpServer,
                      read: @Sendable () -> String? = { readLine(strippingNewline: true) },
                      write: @Sendable @escaping (Data) -> Void = { data in
                          FileHandle.standardOutput.write(data)
                      }) async {
        while let line = read() {
            guard !line.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                continue
            }
            var response: [String: Any]?
            if let data = line.data(using: .utf8),
               let message = try? JSONSerialization.jsonObject(with: data) {
                response = await server.handle(message)
            } else {
                response = McpServer.response(
                    id: nil, error: ["code": -32700, "message": "Parse error"])
            }
            guard let response,
                  let encoded = try? JSONSerialization.data(withJSONObject: response)
            else { continue }
            var payload = encoded
            payload.append(0x0A)
            write(payload)
        }
    }

    /// One agent session, reused until it expires, then re-minted -- the same
    /// lifecycle the Python adapter implements. Minting per request would spend
    /// a round trip and a rate-limit slot on every tool call.
    private static func makeTransport() -> McpServer.Transport {
        let cache = SessionCache()
        return { path, body in
            let session = try await cache.current()
            var request = URLRequest(
                url: AppConfig.brainBaseURL.appending(path: String(path.dropFirst())))
            request.setValue("Bearer \(session.token)", forHTTPHeaderField: "Authorization")
            if let body {
                request.httpMethod = "POST"
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                request.httpBody = try JSONSerialization.data(withJSONObject: body)
            }
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                throw McpServer.ToolError(Self.message(forStatus: code))
            }
            guard let parsed = try JSONSerialization.jsonObject(with: data)
                    as? [String: Any] else {
                throw McpServer.ToolError("Icarus returned an unreadable response")
            }
            return parsed
        }
    }

    /// A refusal is not a connection problem, and saying so sends the user to
    /// debug the wrong thing (the same conflation fixed in InvestigationModel).
    static func message(forStatus code: Int) -> String {
        switch code {
        case 401: return "Icarus sign-in expired. Open the app and sign in again."
        case 403: return "Icarus access is not valid for the active repository."
        case 429: return "Icarus is rate limited; wait a moment and retry."
        case 0:   return "Icarus could not be reached."
        default:  return "Icarus returned an error (HTTP \(code))."
        }
    }

    private actor SessionCache {
        private var session: AgentSession?

        func current() async throws -> AgentSession {
            if let session, session.expiresAt > Date().timeIntervalSince1970 + 30 {
                return session
            }
            let fresh = try await AppConfig.client().createAgentSession()
            session = fresh
            return fresh
        }
    }

    private static func writeError(_ message: String) {
        FileHandle.standardError.write(Data((message + "\n").utf8))
    }
}
