import XCTest
@testable import IcarusKit

final class ClaudeHookTests: XCTestCase {
    private let repo = "acme/app"

    private func input(_ event: String, active: Bool = false) -> [String: Any] {
        [
            "hook_event_name": event,
            "session_id": "session-123",
            "stop_hook_active": active,
        ]
    }

    private func transcript(_ messages: [[String: Any]]) throws -> Data {
        let lines = try messages.map {
            String(data: try JSONSerialization.data(withJSONObject: $0), encoding: .utf8)!
        }
        return Data((lines.joined(separator: "\n") + "\n").utf8)
    }

    private func user(_ text: String) -> [String: Any] {
        ["type": "user", "message": ["content": text]]
    }

    private func assistant(tool: String? = nil, text: String = "done") -> [String: Any] {
        var content: [[String: Any]] = [["type": "text", "text": text]]
        if let tool {
            content.append(["type": "tool_use", "name": tool, "input": [:]])
        }
        return ["type": "assistant", "message": ["content": content]]
    }

    func testSessionStartInjectsConfirmedProposalNotIndexedWithItsReceipt() throws {
        let output = try ClaudeHook.sessionStart(
            input: input("SessionStart"),
            expectedRepo: repo,
            context: [
                "repo": repo,
                "decisions": [[
                    "id": String(repeating: "a", count: 64),
                    "decision": "Use SQLite for the local index",
                    "rationale": "It keeps the first version local.",
                    "affected_paths": ["demo/index.py"],
                    "status": "human_confirmed_proposal_not_indexed",
                    "pull_request_url": "https://github.com/acme/app/pull/42",
                ]],
            ]
        )

        let specific = output["hookSpecificOutput"] as? [String: Any]
        XCTAssertEqual(specific?["hookEventName"] as? String, "SessionStart")
        let text = specific?["additionalContext"] as? String ?? ""
        XCTAssertTrue(text.contains("session-123"))
        XCTAssertTrue(text.contains("Use SQLite for the local index"))
        XCTAssertTrue(text.contains("HUMAN-CONFIRMED · PROPOSAL · NOT INDEXED"))
        XCTAssertTrue(text.contains("https://github.com/acme/app/pull/42"))
        XCTAssertTrue(text.contains("not present in indexed project truth"))
        XCTAssertTrue(text.contains("Verify the pull request's current state"))
    }

    func testSessionStartInjectsMergedIntentOnlyWithIndexedCitationReceipt() throws {
        let output = try ClaudeHook.sessionStart(
            input: input("SessionStart"),
            expectedRepo: repo,
            context: [
                "repo": repo,
                "commit": "abc123",
                "decisions": [[
                    "id": String(repeating: "b", count: 64),
                    "decision": "Use SQLite for the local index",
                    "rationale": "It keeps the first version local.",
                    "affected_paths": ["demo/index.py"],
                    "status": "human_confirmed_merged",
                    "citation_ref": "doc:docs/engineering-memory/sqlite.md",
                    "citation_url": "https://github.com/acme/app/blob/abc123/docs/engineering-memory/sqlite.md",
                    "commit": "abc123",
                ]],
            ]
        )

        let specific = output["hookSpecificOutput"] as? [String: Any]
        let text = specific?["additionalContext"] as? String ?? ""
        XCTAssertTrue(text.contains("HUMAN-CONFIRMED · MERGED · CITED"))
        XCTAssertTrue(text.contains("doc:docs/engineering-memory/sqlite.md"))
        XCTAssertTrue(text.contains("/blob/abc123/"))
        XCTAssertTrue(text.contains("repository truth at indexed commit abc123"))
        XCTAssertFalse(text.contains("not merged project truth"))
    }

    func testSessionStartRefusesMergedIntentWithoutCitationReceipt() {
        XCTAssertThrowsError(try ClaudeHook.sessionStart(
            input: input("SessionStart"),
            expectedRepo: repo,
            context: [
                "repo": repo,
                "decisions": [[
                    "decision": "Use SQLite",
                    "status": "human_confirmed_merged",
                ]],
            ]
        ))
    }

    func testSessionStartWithNoDecisionsStatesBoundedUnknownNotFalseAbsence() throws {
        let output = try ClaudeHook.sessionStart(
            input: input("SessionStart"),
            expectedRepo: repo,
            context: ["repo": repo, "decisions": []]
        )

        let specific = output["hookSpecificOutput"] as? [String: Any]
        let text = specific?["additionalContext"] as? String ?? ""
        XCTAssertTrue(text.contains("No human-confirmed Agent Mode proposals"))
        XCTAssertTrue(text.contains("does not prove that no project decisions exist"))
    }

    func testSessionStartRefusesContextForAnotherRepository() {
        XCTAssertThrowsError(try ClaudeHook.sessionStart(
            input: input("SessionStart"),
            expectedRepo: repo,
            context: ["repo": "other/app", "decisions": []]
        ))
    }

    func testCurrentTurnDecisionCandidateAllowsStop() throws {
        let data = try transcript([
            user("Choose the database"),
            assistant(tool: "mcp__icarus__record_decision_candidate"),
        ])

        let output = try ClaudeHook.stop(
            input: input("Stop"), expectedRepo: repo, transcript: data)

        XCTAssertNil(output)
    }

    func testCurrentTurnNoDecisionAllowsStop() throws {
        let data = try transcript([
            user("Rename the typo"),
            assistant(tool: "mcp__icarus__record_no_decision"),
        ])

        XCTAssertNil(try ClaudeHook.stop(
            input: input("Stop"), expectedRepo: repo, transcript: data))
    }

    func testPriorTurnCaptureDoesNotSatisfyTheCurrentTurn() throws {
        let data = try transcript([
            user("Choose the database"),
            assistant(tool: "mcp__icarus__record_decision_candidate"),
            user("Now choose the cache"),
            assistant(text: "Use an in-memory cache."),
        ])

        let output = try ClaudeHook.stop(
            input: input("Stop"), expectedRepo: repo, transcript: data)

        XCTAssertEqual(output?["decision"] as? String, "block")
        let reason = output?["reason"] as? String ?? ""
        XCTAssertTrue(reason.contains("record_decision_candidate"))
        XCTAssertTrue(reason.contains("record_no_decision"))
        XCTAssertTrue(reason.contains("session-123"))
        XCTAssertTrue(reason.contains(repo))
    }

    func testStopHookActiveNeverBlocksAgain() throws {
        let data = try transcript([user("Choose the cache"), assistant()])

        XCTAssertNil(try ClaudeHook.stop(
            input: input("Stop", active: true), expectedRepo: repo, transcript: data))
    }

    func testBlockReasonNeverEchoesPromptOrAssistantContent() throws {
        let secretPrompt = "Use password hunter2 for the database"
        let secretAnswer = "The internal endpoint is corp.example/private"
        let data = try transcript([user(secretPrompt), assistant(text: secretAnswer)])

        let output = try ClaudeHook.stop(
            input: input("Stop"), expectedRepo: repo, transcript: data)
        let reason = output?["reason"] as? String ?? ""

        XCTAssertFalse(reason.contains(secretPrompt))
        XCTAssertFalse(reason.contains(secretAnswer))
        XCTAssertFalse(reason.contains("hunter2"))
    }

    func testTwoCaptureToolsInOneTurnAreRejectedAsNonAtomic() throws {
        let data = try transcript([
            user("Choose the database"),
            assistant(tool: "mcp__icarus__record_decision_candidate"),
            assistant(tool: "mcp__icarus__record_no_decision"),
        ])

        let output = try ClaudeHook.stop(
            input: input("Stop"), expectedRepo: repo, transcript: data)

        XCTAssertEqual(output?["decision"] as? String, "block")
        XCTAssertTrue((output?["reason"] as? String ?? "").contains("exactly one"))
    }
}
