import Foundation
import IcarusKit

/// `Icarus --claude-hook --repo owner/name` — deterministic Claude Code hooks.
///
/// SessionStart fetches only the bounded confirmed-decision projection. Stop
/// reads Claude's local JSONL solely to check for the two capture tool names;
/// transcript content is never sent to the brain or written by Icarus.
enum ClaudeHookCommand {
    struct Request: Equatable, Sendable {
        let repo: String
    }

    typealias TranscriptLoader = @Sendable (String) throws -> Data

    static var isRequested: Bool {
        CommandLine.arguments.dropFirst().contains("--claude-hook")
    }

    static func request(arguments: [String] = CommandLine.arguments) -> Request? {
        guard arguments.dropFirst().contains("--claude-hook"),
              let marker = arguments.firstIndex(of: "--repo"),
              arguments.indices.contains(marker + 1) else { return nil }
        let repo = arguments[marker + 1]
        guard repo.range(
            of: #"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"#,
            options: .regularExpression
        ) != nil, !repo.contains("..") else { return nil }
        return Request(repo: repo)
    }

    static func handle(
        request: Request,
        input: Data,
        transport: @escaping McpServer.Transport,
        transcriptLoader: @escaping TranscriptLoader
    ) async throws -> [String: Any]? {
        guard let decoded = try JSONSerialization.jsonObject(with: input)
                as? [String: Any],
              let event = decoded["hook_event_name"] as? String else {
            throw ClaudeHook.HookError("Claude returned an invalid hook event")
        }
        switch event {
        case "SessionStart":
            let context = try await transport("/agent-mode/context", nil)
            return try ClaudeHook.sessionStart(
                input: decoded, expectedRepo: request.repo, context: context)
        case "Stop":
            guard let path = decoded["transcript_path"] as? String, !path.isEmpty else {
                throw ClaudeHook.HookError("Stop hook did not provide a transcript path")
            }
            let transcript = try transcriptLoader(path)
            return try ClaudeHook.stop(
                input: decoded, expectedRepo: request.repo, transcript: transcript)
        default:
            throw ClaudeHook.HookError("unsupported Claude hook event")
        }
    }

    static func run() async -> Int32 {
        guard let request = request() else {
            writeError("Usage: Icarus --claude-hook --repo owner/name")
            return 2
        }
        let input = FileHandle.standardInput.readDataToEndOfFile()
        do {
            let output = try await handle(
                request: request,
                input: input,
                transport: McpCommand.makeTransport(),
                transcriptLoader: { path in
                    let url = try validatedTranscriptURL(
                        path,
                        home: FileManager.default.homeDirectoryForCurrentUser
                    )
                    return try Data(contentsOf: url, options: [.mappedIfSafe])
                }
            )
            if let output {
                var encoded = try JSONSerialization.data(withJSONObject: output)
                encoded.append(0x0A)
                FileHandle.standardOutput.write(encoded)
            }
            return 0
        } catch let error as McpServer.ToolError {
            writeError(error.message)
            return 1
        } catch let error as ClaudeHook.HookError {
            writeError(error.message)
            return 1
        } catch {
            writeError("Icarus Agent Mode hook failed without exporting session content.")
            return 1
        }
    }

    static func validatedTranscriptURL(_ path: String, home: URL) throws -> URL {
        let root = home
            .appendingPathComponent(".claude", isDirectory: true)
            .appendingPathComponent("projects", isDirectory: true)
            .standardizedFileURL.resolvingSymlinksInPath()
        let candidate = URL(fileURLWithPath: path)
            .standardizedFileURL.resolvingSymlinksInPath()
        guard candidate.pathExtension == "jsonl",
              candidate.path.hasPrefix(root.path + "/") else {
            throw ClaudeHook.HookError(
                "Claude transcript path is outside ~/.claude/projects or is not JSONL")
        }
        return candidate
    }

    private static func writeError(_ message: String) {
        FileHandle.standardError.write(Data((message + "\n").utf8))
    }
}
