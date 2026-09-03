import XCTest
@testable import Icarus
import IcarusKit

final class ClaudeHookCommandTests: XCTestCase {
    private let repo = "acme/app"

    private func data(_ object: [String: Any]) throws -> Data {
        try JSONSerialization.data(withJSONObject: object)
    }

    func testArgumentsRequireAnExplicitRepository() {
        XCTAssertEqual(
            ClaudeHookCommand.request(arguments: ["Icarus", "--claude-hook", "--repo", repo]),
            .init(repo: repo)
        )
        XCTAssertNil(ClaudeHookCommand.request(arguments: ["Icarus", "--claude-hook"]))
        XCTAssertNil(ClaudeHookCommand.request(
            arguments: ["Icarus", "--claude-hook", "--repo", "../../other"]
        ))
    }

    func testSessionStartFetchesOnlyBoundedProjectContext() async throws {
        actor Calls {
            var values: [(String, Bool)] = []
            func add(_ path: String, hadBody: Bool) { values.append((path, hadBody)) }
        }
        let calls = Calls()
        let expectedRepo = repo
        let transport: McpServer.Transport = { path, body in
            let hadBody = body != nil
            await calls.add(path, hadBody: hadBody)
            return ["repo": expectedRepo, "decisions": []]
        }
        let input = try data([
            "hook_event_name": "SessionStart", "session_id": "session-123",
        ])

        let output = try await ClaudeHookCommand.handle(
            request: .init(repo: repo),
            input: input,
            transport: transport,
            transcriptLoader: { _ in XCTFail("SessionStart must not read a transcript"); return Data() }
        )

        let specific = output?["hookSpecificOutput"] as? [String: Any]
        XCTAssertEqual(specific?["hookEventName"] as? String, "SessionStart")
        let seen = await calls.values
        XCTAssertEqual(seen.map(\.0), ["/agent-mode/context"])
        XCTAssertEqual(seen.map(\.1), [false])
    }

    func testStopReadsLocallyAndMakesNoBrainRequest() async throws {
        actor Calls {
            var count = 0
            func hit() { count += 1 }
        }
        let calls = Calls()
        let input = try data([
            "hook_event_name": "Stop",
            "session_id": "session-123",
            "stop_hook_active": false,
            "transcript_path": "/safe/transcript.jsonl",
        ])
        let transcript = try data([
            "type": "user", "message": ["content": "Choose a database"],
        ]) + Data("\n".utf8)

        let output = try await ClaudeHookCommand.handle(
            request: .init(repo: repo),
            input: input,
            transport: { _, _ in await calls.hit(); return [:] },
            transcriptLoader: { path in
                XCTAssertEqual(path, "/safe/transcript.jsonl")
                return transcript
            }
        )

        XCTAssertEqual(output?["decision"] as? String, "block")
        let callCount = await calls.count
        XCTAssertEqual(callCount, 0)
    }

    func testProductionTranscriptLoaderRejectsPathsOutsideClaudeProjects() throws {
        let home = URL(fileURLWithPath: "/Users/example", isDirectory: true)

        XCTAssertNoThrow(try ClaudeHookCommand.validatedTranscriptURL(
            "/Users/example/.claude/projects/-repo/session.jsonl", home: home
        ))
        XCTAssertThrowsError(try ClaudeHookCommand.validatedTranscriptURL(
            "/Users/example/Documents/private.txt", home: home
        ))
        XCTAssertThrowsError(try ClaudeHookCommand.validatedTranscriptURL(
            "/Users/example/.claude/projects/-repo/session.txt", home: home
        ))
    }
}
