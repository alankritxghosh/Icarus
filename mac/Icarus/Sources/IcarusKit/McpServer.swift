import Foundation

/// The MCP tool server, in Swift, so a user who installed the DMG needs no
/// Python checkout to give their coding agent access to Icarus.
///
/// This mirrors `demo/mcp_server.py` exactly. The tool NAMES and DESCRIPTIONS
/// are not duplicated here -- they come from `McpContract`, generated from the
/// Python source (`scripts/gen_mcp_tools.py`) and drift-checked by
/// `demo/test_mcp_tools_generated.py`. Only the BEHAVIOUR is reimplemented, and
/// the behaviour that matters is the refusal: a call names the repository it
/// expects, and if Icarus is connected to a different one the call is refused
/// rather than silently answered about whatever happens to be active.
///
/// Payloads are passed through as decoded JSON objects rather than through the
/// app's typed models. That is deliberate: `AskResponse` decodes only what a
/// view renders, so routing an answer through it would silently drop fields the
/// agent is told to act on -- `claims`, `rests_on_unlanded`, `rejected_attempts`
/// -- and the loss would be invisible.
public struct McpServer: Sendable {

    /// One request to the brain. `body == nil` means GET.
    public typealias Transport = @Sendable (
        _ path: String, _ body: [String: Any]?
    ) async throws -> [String: Any]

    public struct ToolError: Error {
        public let message: String
        public init(_ message: String) { self.message = message }
    }

    private let transport: Transport

    public init(transport: @escaping Transport) {
        self.transport = transport
    }

    // MARK: - JSON-RPC

    /// Handle one decoded message. Returns nil for a notification (no `id`),
    /// matching the Python server, which stays silent rather than replying to
    /// something that asked for no reply.
    public func handle(_ message: Any) async -> [String: Any]? {
        guard let message = message as? [String: Any] else {
            return Self.response(id: nil,
                                 error: ["code": -32600, "message": "Invalid Request"])
        }
        guard let id = message["id"], !(id is NSNull) else { return nil }
        let method = message["method"] as? String

        switch method {
        case "initialize":
            let params = message["params"] as? [String: Any] ?? [:]
            let protocolVersion = params["protocolVersion"] as? String
                ?? McpContract.defaultProtocolVersion
            return Self.response(id: id, result: [
                "protocolVersion": protocolVersion,
                "capabilities": ["tools": ["listChanged": false]],
                "serverInfo": ["name": McpContract.serverName,
                               "version": McpContract.serverVersion],
                "instructions": McpContract.instructions,
            ])
        case "ping":
            return Self.response(id: id, result: [:])
        case "tools/list":
            return Self.response(id: id, result: ["tools": Self.tools])
        case "tools/call":
            return await callTool(message: message, id: id)
        default:
            return Self.response(id: id, error: [
                "code": -32601, "message": "Method not found: \(method ?? "")",
            ])
        }
    }

    /// The generated contract, decoded once. A malformed generated file would
    /// be a build-time mistake, and an empty tool list is a louder failure than
    /// a crash in a stdio server whose stderr nobody is reading.
    /// Computed rather than stored: a JSON dictionary is not `Sendable`, and
    /// caching it would need an actor to satisfy strict concurrency. Parsing 8KB
    /// on the one `tools/list` call per session is not worth that.
    public static var tools: [[String: Any]] {
        guard let data = McpContract.toolsJSON.data(using: .utf8),
              let parsed = try? JSONSerialization.jsonObject(with: data),
              let tools = parsed as? [[String: Any]] else { return [] }
        return tools
    }

    private func callTool(message: [String: Any], id: Any) async -> [String: Any] {
        let params = message["params"] as? [String: Any] ?? [:]
        let name = params["name"] as? String
        guard let arguments = (params["arguments"] as? [String: Any]) ?? [:] as [String: Any]?
        else {
            return Self.response(id: id, result: Self.toolError("arguments must be an object"))
        }
        do {
            let payload: [String: Any]
            switch name {
            case "get_change_context": payload = try await getChangeContext(arguments)
            case "explain_code_context": payload = try await explainCodeContext(arguments)
            case "get_task_context": payload = try await getTaskContext(arguments)
            default:
                return Self.response(id: id,
                                     result: Self.toolError("unknown tool: \(name ?? "")"))
            }
            return Self.response(id: id, result: Self.toolResult(payload))
        } catch let error as ToolError {
            return Self.response(id: id, result: Self.toolError(error.message))
        } catch {
            return Self.response(id: id,
                                 result: Self.toolError("Icarus could not be reached"))
        }
    }

    // MARK: - Tools

    /// Return the active repo, refusing only a MISMATCH with what was asked.
    private func checkedRepo(_ expected: String) async throws -> String {
        let status = try await transport("/status", nil)
        guard let active = status["repo"] as? String, !active.isEmpty else {
            throw ToolError(
                "Icarus has no connected repository; connect one in the Icarus app")
        }
        guard expected.lowercased() == active.lowercased() else {
            throw ToolError("Icarus is connected to \(active), not \(expected); "
                            + "connect the intended repository in Icarus first")
        }
        return active
    }

    private func required(_ arguments: [String: Any], _ key: String) throws -> String {
        guard let value = arguments[key] as? String,
              !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw ToolError("\(key) is required")
        }
        return value.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private func requiredLine(_ arguments: [String: Any], _ key: String) throws -> Int {
        // A Bool is an NSNumber in JSON, and `true as? Int` succeeds -- so a
        // caller passing `start: true` would otherwise be read as line 1.
        if let number = arguments[key] as? NSNumber,
           CFGetTypeID(number) != CFBooleanGetTypeID(),
           number.intValue >= 1, Double(number.intValue) == number.doubleValue {
            return number.intValue
        }
        throw ToolError("\(key) must be a positive integer line number")
    }

    /// The payload is authoritative about which corpus answered, and the repo
    /// can change between the preflight and the answer.
    private func confirm(_ payload: [String: Any], matches repo: String) async throws {
        guard payload["repo"] as? String == repo else {
            throw ToolError("Icarus changed repositories while answering; retry the request")
        }
        _ = try await checkedRepo(repo)
    }

    private func getChangeContext(_ arguments: [String: Any]) async throws -> [String: Any] {
        let question = try required(arguments, "question")
        let expected = try required(arguments, "repo")
        let active = try await checkedRepo(expected)
        // per_claim is always on for the agent interface: a coding agent acts on
        // this answer, so it needs to know which sentences merge several sources
        // and which rest only on pull requests that never landed.
        let payload = try await transport("/ask", [
            "question": question, "include_evidence": true, "per_claim": true,
        ])
        try await confirm(payload, matches: active)
        return payload
    }

    private func getTaskContext(_ arguments: [String: Any]) async throws -> [String: Any] {
        let task = try required(arguments, "task")
        let expected = try required(arguments, "repo")
        let active = try await checkedRepo(expected)
        let payload = try await transport("/context", ["task": task])
        try await confirm(payload, matches: active)
        return payload
    }

    private func explainCodeContext(_ arguments: [String: Any]) async throws -> [String: Any] {
        let expected = try required(arguments, "repo")
        let path = try required(arguments, "path")
        let start = try requiredLine(arguments, "start")
        let end = try requiredLine(arguments, "end")
        guard end >= start else {
            throw ToolError("end must be greater than or equal to start")
        }
        let active = try await checkedRepo(expected)
        var body: [String: Any] = [
            "repo": active, "path": path, "start": start, "end": end,
            "include_evidence": true, "per_claim": true,
        ]
        if let question = arguments["question"] {
            guard let question = question as? String else {
                throw ToolError("question must be a string")
            }
            let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty { body["question"] = trimmed }
        }
        let payload = try await transport("/explain", body)
        try await confirm(payload, matches: active)
        return payload
    }

    // MARK: - Framing

    public static func toolResult(_ payload: [String: Any]) -> [String: Any] {
        let text = (try? JSONSerialization.data(withJSONObject: payload,
                                                options: [.sortedKeys]))
            .flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
        return [
            "content": [["type": "text", "text": text]],
            "structuredContent": payload,
            "isError": false,
        ]
    }

    public static func toolError(_ message: String) -> [String: Any] {
        ["content": [["type": "text", "text": message]], "isError": true]
    }

    public static func response(id: Any?, result: [String: Any]? = nil,
                         error: [String: Any]? = nil) -> [String: Any] {
        var out: [String: Any] = ["jsonrpc": "2.0", "id": id ?? NSNull()]
        if let error { out["error"] = error } else { out["result"] = result ?? [:] }
        return out
    }
}
