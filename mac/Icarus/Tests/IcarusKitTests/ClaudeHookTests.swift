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

    /// The real transcript shape: a tool_use carries an id, and its outcome
    /// arrives as a tool_result block inside the NEXT user event.
    private func assistant(tool: String, id: String) -> [String: Any] {
        [
            "type": "assistant",
            "message": ["content": [
                ["type": "text", "text": "calling"],
                ["type": "tool_use", "name": tool, "id": id, "input": [:]],
            ]],
        ]
    }

    /// `error` nil reproduces the clients that omit `is_error` entirely on
    /// success; both shapes appear in one real transcript.
    private func toolResult(id: String, error: Bool?) -> [String: Any] {
        var block: [String: Any] = [
            "type": "tool_result", "tool_use_id": id, "content": "…",
        ]
        if let error { block["is_error"] = error }
        return ["type": "user", "message": ["content": [block]]]
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

    // MARK: - A failed capture call recorded nothing (live bug, 2026-08-31)

    func testAFailedCaptureCallDoesNotCountAndTheRetryResolvesTheTurn() throws {
        // Reproduces a real session: record_decision_candidate errored twice
        // on a server bug, the agent retried with record_no_decision, and the
        // hook blocked it for calling "more than one" capture tool.
        let output = try ClaudeHook.stop(
            input: input("Stop"),
            expectedRepo: repo,
            transcript: transcript([
                user("fix agent mode"),
                assistant(tool: "mcp__icarus__record_decision_candidate", id: "t1"),
                toolResult(id: "t1", error: true),
                assistant(tool: "mcp__icarus__record_decision_candidate", id: "t2"),
                toolResult(id: "t2", error: true),
                assistant(tool: "mcp__icarus__record_no_decision", id: "t3"),
                toolResult(id: "t3", error: nil),
            ])
        )

        XCTAssertNil(output)
    }

    func testAFailedCaptureCallWithNoRetryStillBlocksAsNothingRecorded() throws {
        let output = try ClaudeHook.stop(
            input: input("Stop"),
            expectedRepo: repo,
            transcript: transcript([
                user("fix agent mode"),
                assistant(tool: "mcp__icarus__record_no_decision", id: "t1"),
                toolResult(id: "t1", error: true),
            ])
        )

        XCTAssertEqual(
            (output?["reason"] as? String)?.hasPrefix("No Agent Mode capture tool"), true)
    }

    func testTwoSUCCESSFULCaptureCallsAreStillRefused() throws {
        // The guard this fix must not weaken.
        let output = try ClaudeHook.stop(
            input: input("Stop"),
            expectedRepo: repo,
            transcript: transcript([
                user("fix agent mode"),
                assistant(tool: "mcp__icarus__record_no_decision", id: "t1"),
                toolResult(id: "t1", error: false),
                assistant(tool: "mcp__icarus__record_decision_candidate", id: "t2"),
                toolResult(id: "t2", error: nil),
            ])
        )

        XCTAssertEqual(
            (output?["reason"] as? String)?.hasPrefix("More than one"), true)
    }

    func testSuccessIsRecognisedWhetherIsErrorIsFalseOrAbsent() throws {
        for error in [false, nil] as [Bool?] {
            let output = try ClaudeHook.stop(
                input: input("Stop"),
                expectedRepo: repo,
                transcript: transcript([
                    user("fix agent mode"),
                    assistant(tool: "mcp__icarus__record_no_decision", id: "t1"),
                    toolResult(id: "t1", error: error),
                ])
            )
            XCTAssertNil(output, "is_error \(String(describing: error)) must count as success")
        }
    }
}
