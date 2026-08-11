import XCTest
@testable import IcarusKit

/// The Swift MCP server's contract, weighted toward what must NOT happen.
///
/// The dangerous failures here are silent ones: answering about a repository
/// the caller did not ask about, or dropping a field the agent was told to act
/// on while still returning a perfectly valid-looking answer.
final class McpServerTests: XCTestCase {

    /// Records every brain call so a test can prove one did NOT happen.
    ///
    /// Stores JSON as `Data`, not `[String: Any]`: a dictionary is not
    /// `Sendable` and cannot cross an actor boundary under strict concurrency.
    /// Tests decode at the assertion site.
    private actor Spy {
        private(set) var paths: [String] = []
        private var bodies: [String: Data] = [:]
        private var responses: [String: Data] = [:]

        func set(_ path: String, _ value: Data) { responses[path] = value }

        /// Takes `Data`, not a dictionary: the caller serializes on its own side
        /// so nothing non-`Sendable` is sent ACROSS the actor boundary either.
        func record(_ path: String, _ body: Data?) -> Data {
            paths.append(path)
            if let body { bodies[path] = body }
            return responses[path] ?? Data("{}".utf8)
        }

        func bodyData(for path: String) -> Data? { bodies[path] }
    }

    private func object(_ data: Data?) -> [String: Any] {
        guard let data,
              let parsed = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return [:] }
        return parsed
    }

    private func makeServer(
        status: [String: Any] = ["repo": "simonw/llm"],
        answer: [String: Any] = ["repo": "simonw/llm", "verdict": "answer"]
    ) async -> (McpServer, Spy) {
        let spy = Spy()
        // Serialize on this side of the boundary; only Data crosses it.
        let statusData = (try? JSONSerialization.data(withJSONObject: status)) ?? Data()
        let answerData = (try? JSONSerialization.data(withJSONObject: answer)) ?? Data()
        await spy.set("/status", statusData)
        for path in ["/ask", "/explain", "/context"] { await spy.set(path, answerData) }
        let server = McpServer { path, body in
            let encoded = body.flatMap { try? JSONSerialization.data(withJSONObject: $0) }
            let data = await spy.record(path, encoded)
            return ((try? JSONSerialization.jsonObject(with: data)) as? [String: Any]) ?? [:]
        }
        return (server, spy)
    }

    private func call(_ server: McpServer, _ name: String,
                      _ arguments: [String: Any]) async -> [String: Any] {
        let response = await server.handle([
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": ["name": name, "arguments": arguments],
        ])
        return response?["result"] as? [String: Any] ?? [:]
    }

    // MARK: - protocol

    func testInitializeCarriesTheGeneratedInstructions() async {
        let (server, _) = await makeServer()
        let response = await server.handle([
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": ["protocolVersion": "2025-06-18"],
        ])
        let result = response?["result"] as? [String: Any]
        XCTAssertEqual(result?["protocolVersion"] as? String, "2025-06-18")
        let instructions = result?["instructions"] as? String ?? ""
        // The measured wording, not a paraphrase (see C2).
        XCTAssertTrue(instructions.contains("you are about to"))
        XCTAssertFalse(instructions.contains("meaningful code change"))
    }

    func testToolsListServesTheThreeGeneratedTools() async {
        let (server, _) = await makeServer()
        let response = await server.handle([
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
        ])
        let tools = (response?["result"] as? [String: Any])?["tools"] as? [[String: Any]]
        XCTAssertEqual(Set((tools ?? []).compactMap { $0["name"] as? String }),
                       ["get_change_context", "explain_code_context", "get_task_context"])
    }

    func testNotificationGetsNoReply() async {
        let (server, _) = await makeServer()
        let response = await server.handle([
            "jsonrpc": "2.0", "method": "notifications/initialized",
        ])
        XCTAssertNil(response)
    }

    func testUnknownMethodIsMethodNotFound() async {
        let (server, _) = await makeServer()
        let response = await server.handle([
            "jsonrpc": "2.0", "id": 3, "method": "resources/list",
        ])
        XCTAssertEqual((response?["error"] as? [String: Any])?["code"] as? Int, -32601)
    }

    // MARK: - the refusal that matters

    func testRepoMismatchRefusesWithoutEverAsking() async {
        let (server, spy) = await makeServer(status: ["repo": "simonw/llm"])
        let result = await call(server, "get_change_context",
                                ["repo": "astral-sh/uv", "question": "why?"])
        XCTAssertEqual(result["isError"] as? Bool, true)
        // The point is not the error -- it is that no writer call was spent and
        // no evidence about the WRONG repository was returned.
        let paths = await spy.paths
        XCTAssertFalse(paths.contains("/ask"))
    }

    func testNoConnectedRepoIsRefusedNotAnswered() async {
        let (server, spy) = await makeServer(status: [:])
        let result = await call(server, "get_change_context",
                                ["repo": "simonw/llm", "question": "why?"])
        XCTAssertEqual(result["isError"] as? Bool, true)
        let paths = await spy.paths
        XCTAssertFalse(paths.contains("/ask"))
    }

    func testRepoChangingMidAnswerIsRefused() async {
        // Answer comes back stamped with a DIFFERENT corpus than was checked.
        let (server, _) = await makeServer(
            status: ["repo": "simonw/llm"],
            answer: ["repo": "astral-sh/uv", "verdict": "answer"])
        let result = await call(server, "get_change_context",
                                ["repo": "simonw/llm", "question": "why?"])
        XCTAssertEqual(result["isError"] as? Bool, true)
    }

    // MARK: - what gets sent and returned

    func testAskAlwaysRequestsPerClaimAndEvidence() async {
        let (server, spy) = await makeServer()
        _ = await call(server, "get_change_context",
                       ["repo": "simonw/llm", "question": "why?"])
        let body = object(await spy.bodyData(for: "/ask"))
        XCTAssertEqual(body["per_claim"] as? Bool, true)
        XCTAssertEqual(body["include_evidence"] as? Bool, true)
        XCTAssertEqual(body["question"] as? String, "why?")
    }

    func testPayloadIsPassedThroughVerbatim() async {
        // The regression this guards: routing the answer through the app's typed
        // models would drop `claims`/`rests_on_rejected`/`rejected_attempts`,
        // which are exactly what the tool description tells an agent to act on.
        let rich: [String: Any] = [
            "repo": "simonw/llm", "verdict": "answer",
            "claims": [["text": "x", "label": "quoted", "rests_on_rejected": true]],
            "rejected_attempts": [["ref": "pr:1549", "title": "t"]],
        ]
        let (server, _) = await makeServer(answer: rich)
        let result = await call(server, "get_change_context",
                                ["repo": "simonw/llm", "question": "why?"])
        let structured = result["structuredContent"] as? [String: Any]
        let claims = structured?["claims"] as? [[String: Any]]
        XCTAssertEqual(claims?.first?["rests_on_rejected"] as? Bool, true)
        XCTAssertNotNil(structured?["rejected_attempts"])
        XCTAssertEqual(result["isError"] as? Bool, false)
    }

    // MARK: - argument validation

    func testExplainRejectsAnInvertedRange() async {
        let (server, spy) = await makeServer()
        let result = await call(server, "explain_code_context",
                                ["repo": "simonw/llm", "path": "llm/cli.py",
                                 "start": 50, "end": 10])
        XCTAssertEqual(result["isError"] as? Bool, true)
        let paths = await spy.paths
        XCTAssertFalse(paths.contains("/explain"))
    }

    func testExplainRejectsABooleanLineNumber() async {
        // JSON booleans bridge to NSNumber, so `true as? Int` is 1 -- without an
        // explicit check this would silently explain line 1.
        let (server, _) = await makeServer()
        let result = await call(server, "explain_code_context",
                                ["repo": "simonw/llm", "path": "llm/cli.py",
                                 "start": true, "end": 10])
        XCTAssertEqual(result["isError"] as? Bool, true)
    }

    func testExplainOmitsAnEmptyQuestionRatherThanSendingIt() async {
        let (server, spy) = await makeServer()
        _ = await call(server, "explain_code_context",
                       ["repo": "simonw/llm", "path": "llm/cli.py",
                        "start": 1, "end": 5, "question": "   "])
        let body = object(await spy.bodyData(for: "/explain"))
        XCTAssertNil(body["question"])
    }

    func testMissingRequiredArgumentIsAToolErrorNotACrash() async {
        let (server, _) = await makeServer()
        let result = await call(server, "get_change_context", ["repo": "simonw/llm"])
        XCTAssertEqual(result["isError"] as? Bool, true)
    }

    func testUnknownToolIsRejected() async {
        let (server, _) = await makeServer()
        let result = await call(server, "delete_everything", ["repo": "simonw/llm"])
        XCTAssertEqual(result["isError"] as? Bool, true)
    }
}
