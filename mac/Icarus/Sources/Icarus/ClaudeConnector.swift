import Foundation

/// Installs and diagnoses the shipped app as Claude Code's user-scoped MCP
/// server. All configuration changes go through Claude's own CLI; Icarus never
/// edits another application's configuration file directly.
struct ClaudeConnector: Sendable {
    struct CommandResult: Sendable {
        let exitCode: Int32
        let output: String
    }

    enum Status: Equatable, Sendable {
        case unavailable
        case notConfigured
        case connected
        case legacyUserRegistration
        case conflict(String)
        case failed(String)
    }

    struct ConnectorError: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    typealias Runner = @Sendable ([String]) async throws -> CommandResult

    let claudeExecutable: URL
    let appExecutable: URL
    let run: Runner

    static func live(appExecutable: URL? = Bundle.main.executableURL) -> ClaudeConnector? {
        guard let appExecutable, let claude = locateClaude() else { return nil }
        return ClaudeConnector(
            claudeExecutable: claude,
            appExecutable: appExecutable,
            run: { arguments in
                try await runProcess(executable: claude, arguments: arguments)
            })
    }

    /// GUI apps inherit a minimal PATH, so checking PATH alone misses Claude's
    /// native installer (`~/.local/bin/claude`) and Homebrew on Apple Silicon.
    static func locateClaude(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        home: URL = FileManager.default.homeDirectoryForCurrentUser,
        fileManager: FileManager = .default
    ) -> URL? {
        var candidates: [URL] = []
        if let path = environment["PATH"] {
            candidates += path.split(separator: ":").map {
                URL(fileURLWithPath: String($0)).appending(path: "claude")
            }
        }
        candidates += [
            home.appending(path: ".local/bin/claude"),
            home.appending(path: ".volta/bin/claude"),
            home.appending(path: ".npm-global/bin/claude"),
            home.appending(path: ".asdf/shims/claude"),
            URL(fileURLWithPath: "/opt/homebrew/bin/claude"),
            URL(fileURLWithPath: "/usr/local/bin/claude"),
        ]
        var seen = Set<String>()
        return candidates.first { candidate in
            let path = candidate.standardizedFileURL.path
            return seen.insert(path).inserted && fileManager.isExecutableFile(atPath: path)
        }?.standardizedFileURL
    }

    func status() async -> Status {
        do {
            let result = try await run(["mcp", "get", "icarus"])
            if result.exitCode != 0 {
                if result.output.localizedCaseInsensitiveContains("No MCP server named") {
                    return .notConfigured
                }
                return .failed(clean(result.output, fallback: "Claude Code could not read its MCP configuration."))
            }
            return Self.parseStatus(result.output, expectedExecutable: appExecutable.path)
        } catch {
            return .failed(error.localizedDescription)
        }
    }

    /// Explicit user action only. A known checkout-only registration is safe to
    /// migrate; any other server named `icarus` is left untouched.
    func installOrRepair() async throws -> Status {
        let path = appExecutable.standardizedFileURL.path
        guard !path.contains("/AppTranslocation/"), !path.hasPrefix("/Volumes/") else {
            throw ConnectorError(
                message: "Move Icarus to Applications and open it there before connecting Claude Code.")
        }
        switch await status() {
        case .connected:
            return .connected
        case .notConfigured:
            break
        case .legacyUserRegistration:
            let removed = try await run(["mcp", "remove", "icarus", "--scope", "user"])
            guard removed.exitCode == 0 else {
                throw ConnectorError(message: clean(
                    removed.output, fallback: "Claude Code could not remove the legacy Icarus connector."))
            }
        case .conflict(let detail):
            throw ConnectorError(message: detail)
        case .unavailable:
            throw ConnectorError(message: "Claude Code is not installed on this Mac.")
        case .failed(let message):
            throw ConnectorError(message: message)
        }

        let added = try await run([
            "mcp", "add", "--transport", "stdio", "--scope", "user", "icarus", "--",
            appExecutable.path, "--mcp",
        ])
        guard added.exitCode == 0 else {
            throw ConnectorError(message: clean(
                added.output, fallback: "Claude Code could not add the Icarus connector."))
        }
        let final = await status()
        guard final == .connected else {
            throw ConnectorError(message: "Claude Code saved Icarus, but the connector did not become healthy.")
        }
        return final
    }

    static func parseStatus(_ output: String, expectedExecutable: String) -> Status {
        let fields = output.split(separator: "\n").reduce(into: [String: String]()) { fields, raw in
            let line = raw.trimmingCharacters(in: .whitespaces)
            guard let colon = line.firstIndex(of: ":") else { return }
            let key = String(line[..<colon]).lowercased()
            fields[key] = String(line[line.index(after: colon)...]).trimmingCharacters(in: .whitespaces)
        }
        guard let command = fields["command"], let arguments = fields["args"] else {
            return .failed("Claude Code returned an unreadable MCP registration.")
        }
        let actual = URL(fileURLWithPath: command).standardizedFileURL.path
        let expected = URL(fileURLWithPath: expectedExecutable).standardizedFileURL.path
        let isUserScope = fields["scope"]?.localizedCaseInsensitiveContains("User config") == true
        if isUserScope && actual == expected
                && arguments.split(separator: " ").contains("--mcp") {
            return .connected
        }
        if isUserScope && arguments.contains("demo.mcp_server") {
            return .legacyUserRegistration
        }
        let scope = fields["scope"] ?? "unknown scope"
        return .conflict(
            "Claude Code already has a different server named ‘icarus’ at \(scope). "
            + "Icarus will not overwrite it automatically.")
    }

    private static func runProcess(executable: URL, arguments: [String]) async throws -> CommandResult {
        try await Task.detached(priority: .userInitiated) {
            let process = Process()
            let pipe = Pipe()
            process.executableURL = executable
            process.arguments = arguments
            process.standardOutput = pipe
            process.standardError = pipe
            try process.run()
            do {
                let deadline = Date().addingTimeInterval(20)
                while process.isRunning && Date() < deadline {
                    try await Task.sleep(for: .milliseconds(50))
                }
            } catch {
                if process.isRunning {
                    process.terminate()
                    process.waitUntilExit()
                }
                throw error
            }
            guard !process.isRunning else {
                process.terminate()
                process.waitUntilExit()
                throw ConnectorError(
                    message: "Claude Code did not answer within 20 seconds.")
            }
            process.waitUntilExit()
            let data = pipe.fileHandleForReading.readDataToEndOfFile()
            return CommandResult(
                exitCode: process.terminationStatus,
                output: String(decoding: data, as: UTF8.self))
        }.value
    }

    private func clean(_ value: String, fallback: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? fallback : trimmed
    }
}
