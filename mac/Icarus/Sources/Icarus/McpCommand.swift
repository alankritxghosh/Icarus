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
        // Always complete the MCP handshake, even while signed out. Otherwise
        // Claude hides every Icarus tool and the user sees only a generic
        // "server failed" status. Authentication is deferred to the first tool
        // call, where it can be returned as an actionable MCP tool error.
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
    static func makeTransport(
        baseURL: URL = AppConfig.brainBaseURL,
        sessionFactory: @Sendable @escaping () async throws -> AgentSession = {
            try await AppConfig.client().createAgentSession()
        },
        urlSession: URLSession = mcpURLSession
    ) -> McpServer.Transport {
        let cache = SessionCache(create: sessionFactory)
        return { path, body in
            var previousRepo: String?
            for attempt in 0..<2 {
                let agentSession: AgentSession
                do {
                    agentSession = try await cache.current()
                } catch BrainError.unauthorized {
                    throw McpServer.ToolError(
                        "Icarus is signed out. Open the app and sign in with GitHub.")
                } catch BrainError.forbidden {
                    throw McpServer.ToolError(
                        "Connect a repository you can read in the Icarus app.")
                } catch BrainError.rateLimited {
                    throw McpServer.ToolError("Icarus is rate limited; wait a moment and retry.")
                } catch {
                    throw McpServer.ToolError(
                        "Icarus could not create an agent session. Open the app and try again.")
                }

                // A retry is only ever meant to replace an EXPIRED grant for
                // the same repository. If reminting landed on a DIFFERENT one
                // -- the user switched the app between the preflight and now
                // -- resending the body would run retrieval, the writer and
                // analytics inside a repository the caller never asked about,
                // and on a private repo that is evidence crossing a boundary
                // meant to be fail-closed. The tool's postflight catches the
                // wrong ANSWER; this catches the wrong WORK, before it runs.
                //
                // Scoped to requests that CARRY A BODY (/ask, /context,
                // /explain). `/status` has none: it asks what is connected
                // right now, and a deliberate switch A -> B is exactly when it
                // must be allowed to remint. Guarding it too failed the user's
                // first correctly-named call after every intentional switch.
                //
                // Compared case-insensitively, as GitHub repository names are
                // everywhere else here -- refusing `Octo/Repo` -> `octo/repo`
                // was a pure false positive. Both found in review.
                //
                // Costs no extra request: the grant already names its repo.
                if attempt > 0, body != nil, let previousRepo,
                   agentSession.repo.caseInsensitiveCompare(previousRepo) != .orderedSame {
                    throw McpServer.ToolError(
                        "Icarus switched to \(agentSession.repo) while answering "
                        + "about \(previousRepo); retry the request.")
                }

                var request = URLRequest(
                    url: baseURL.appending(path: String(path.dropFirst())))
                request.timeoutInterval = timeout(forPath: path)
                request.setValue("application/json", forHTTPHeaderField: "Accept")
                // Never share question/answer/evidence content from the agent
                // surface. Stated explicitly rather than left to the server's
                // default: there is no consent surface here -- the person
                // running a coding agent never saw the Settings toggle in this
                // context -- and MCP serves private repositories. Counts still
                // flow, exactly as they do with the toggle off.
                request.setValue("0", forHTTPHeaderField: "X-Icarus-Share-Content")
                request.setValue(
                    "Bearer \(agentSession.token)", forHTTPHeaderField: "Authorization")
                if let body {
                    request.httpMethod = "POST"
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.httpBody = try JSONSerialization.data(withJSONObject: body)
                }
                let data: Data
                let response: URLResponse
                do {
                    (data, response) = try await urlSession.data(for: request)
                } catch let error as URLError where error.code == .timedOut {
                    // A slow answer and a broken adapter must not read the
                    // same. The Python adapter surfaced this as "-32603
                    // Internal error" and this one as "could not be reached";
                    // both sent the one user who hit it to debug the wrong
                    // thing (docs/experiments/2026-08-14-dogfood-*.md).
                    throw McpServer.ToolError(
                        "Icarus took longer than \(Int(timeout(forPath: path)))s "
                        + "to answer; retry, or ask a narrower question.")
                }
                let code = (response as? HTTPURLResponse)?.statusCode ?? 0
                // Sessions are repository-bound and process-local. Expiry, a
                // server restart, or switching repos can invalidate a cached
                // grant before its wall-clock expiry. Remint once, then surface
                // a real persistent refusal instead of looping.
                if (code == 401 || code == 403), attempt == 0 {
                    previousRepo = agentSession.repo
                    await cache.invalidate()
                    continue
                }
                guard code == 200 else {
                    throw McpServer.ToolError(Self.message(forStatus: code))
                }
                guard let parsed = try JSONSerialization.jsonObject(with: data)
                        as? [String: Any] else {
                    throw McpServer.ToolError("Icarus returned an unreadable response")
                }
                return parsed
            }
            throw McpServer.ToolError("Icarus could not refresh its agent session")
        }
    }

    /// How long a route is allowed to take, by how much work it does.
    ///
    /// `/context` runs a bounded investigation -- several writer calls -- where
    /// `/ask` runs one, so URLSession's flat 60s default made the most
    /// expensive tool the least reliable one. Measured live on
    /// meilisearch-swift (2026-08-14): `get_task_context` succeeded in 16.1s
    /// and failed twice at exactly the 60s cut, i.e. the old ceiling sat inside
    /// the normal spread. 240s matches the Azure Container Apps ingress
    /// ceiling; waiting past it cannot succeed. Kept in step with
    /// `demo/mcp_server.py`'s `_TIMEOUTS`.
    static func timeout(forPath path: String) -> TimeInterval {
        switch path {
        case "/context", "/investigate": return 240
        case "/status": return 20
        default: return 60
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
        private let create: @Sendable () async throws -> AgentSession

        init(create: @Sendable @escaping () async throws -> AgentSession) {
            self.create = create
        }

        func current() async throws -> AgentSession {
            if let session, session.expiresAt > Date().timeIntervalSince1970 + 30 {
                return session
            }
            let fresh = try await create()
            session = fresh
            return fresh
        }

        func invalidate() { session = nil }
    }

    /// Never follow an HTTP redirect with an agent bearer attached. The brain
    /// URL is release-stamped, but refusing redirect forwarding keeps a bad
    /// deployment or compromised origin from turning into token exfiltration.
    private final class NoRedirects: NSObject, URLSessionTaskDelegate, @unchecked Sendable {
        func urlSession(
            _ session: URLSession,
            task: URLSessionTask,
            willPerformHTTPRedirection response: HTTPURLResponse,
            newRequest request: URLRequest,
            completionHandler: @escaping (URLRequest?) -> Void
        ) {
            completionHandler(nil)
        }
    }

    private static let mcpURLSession = URLSession(
        configuration: .ephemeral, delegate: NoRedirects(), delegateQueue: nil)
}
