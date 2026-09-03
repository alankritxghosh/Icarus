import Foundation

/// Explicit, per-project opt-in for Claude Agent Mode. Existing JSON is parsed
/// and merged; invalid configuration is refused rather than overwritten.
enum ClaudeAgentModeInstaller {
    struct Result: Equatable, Sendable {
        let changed: Bool
        let mcpPath: String
        let settingsPath: String
    }

    struct InstallError: Error, Equatable, Sendable {
        let message: String
        init(_ message: String) { self.message = message }
    }

    static func install(
        project: URL,
        repo: String,
        executable: URL,
        fileManager: FileManager = .default
    ) throws -> Result {
        guard repo.range(
            of: #"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"#,
            options: .regularExpression
        ) != nil, !repo.contains("..") else {
            throw InstallError("repo must look like owner/name")
        }
        var isDirectory: ObjCBool = false
        guard fileManager.fileExists(atPath: project.path, isDirectory: &isDirectory),
              isDirectory.boolValue else {
            throw InstallError("project directory does not exist")
        }
        let root = project.standardizedFileURL
        let rootValues = try root.resourceValues(forKeys: [.isSymbolicLinkKey])
        if rootValues.isSymbolicLink == true {
            throw InstallError("refusing to configure a symbolic-link project directory")
        }
        let mcpURL = root.appendingPathComponent(".mcp.json")
        let claudeURL = root.appendingPathComponent(".claude", isDirectory: true)
        let settingsURL = claudeURL.appendingPathComponent("settings.local.json")

        var claudeIsDirectory: ObjCBool = false
        if fileManager.fileExists(
            atPath: claudeURL.path, isDirectory: &claudeIsDirectory
        ) {
            let values = try claudeURL.resourceValues(
                forKeys: [.isSymbolicLinkKey])
            guard values.isSymbolicLink != true, claudeIsDirectory.boolValue else {
                throw InstallError(
                    "refusing to rewrite configuration through (claudeURL.path)")
            }
        }

        let existingMCP = try loadObject(mcpURL, fileManager: fileManager)
        let existingSettings = try loadObject(settingsURL, fileManager: fileManager)
        var mcp = existingMCP.object
        var settings = existingSettings.object

        var servers = try dictionary(mcp["mcpServers"], name: "mcpServers")
        servers["icarus"] = [
            "type": "stdio",
            "command": executable.standardizedFileURL.path,
            "args": ["--mcp"],
        ]
        mcp["mcpServers"] = servers

        var hooks = try dictionary(settings["hooks"], name: "hooks")
        let command = [
            shellQuote(executable.standardizedFileURL.path),
            "--claude-hook", "--repo", shellQuote(repo),
        ].joined(separator: " ")
        for event in ["SessionStart", "Stop"] {
            var matchers: [[String: Any]]
            if let value = hooks[event] {
                guard let existing = value as? [[String: Any]] else {
                    throw InstallError("hooks.\(event) must be an array")
                }
                matchers = existing
            } else {
                matchers = []
            }
            let alreadyInstalled = matchers.contains { matcher in
                guard let commands = matcher["hooks"] as? [[String: Any]] else { return false }
                return commands.contains { $0["command"] as? String == command }
            }
            if !alreadyInstalled {
                matchers.append([
                    "hooks": [[
                        "type": "command",
                        "command": command,
                        "timeout": event == "SessionStart" ? 30 : 5,
                    ]],
                ])
            }
            hooks[event] = matchers
        }
        settings["hooks"] = hooks

        let mcpData = try encoded(mcp)
        let settingsData = try encoded(settings)
        let mcpChanged = existingMCP.data != mcpData
        let settingsChanged = existingSettings.data != settingsData
        if mcpChanged || settingsChanged {
            // Both inputs were parsed and both outputs encoded before the first
            // write, so malformed user configuration can never be half-replaced.
            try fileManager.createDirectory(
                at: claudeURL, withIntermediateDirectories: true)
            if mcpChanged { try mcpData.write(to: mcpURL, options: .atomic) }
            if settingsChanged {
                try settingsData.write(to: settingsURL, options: .atomic)
            }
        }
        return Result(
            changed: mcpChanged || settingsChanged,
            mcpPath: mcpURL.path,
            settingsPath: settingsURL.path
        )
    }

    private struct Loaded {
        let data: Data?
        let object: [String: Any]
    }

    private static func loadObject(
        _ url: URL, fileManager: FileManager
    ) throws -> Loaded {
        guard fileManager.fileExists(atPath: url.path) else {
            return Loaded(data: nil, object: [:])
        }
        let values = try url.resourceValues(forKeys: [.isSymbolicLinkKey])
        if values.isSymbolicLink == true {
            throw InstallError("refusing to rewrite symbolic-link configuration at \(url.path)")
        }
        let data = try Data(contentsOf: url)
        guard let object = try? JSONSerialization.jsonObject(with: data)
                as? [String: Any] else {
            throw InstallError("existing configuration is not a JSON object: \(url.path)")
        }
        return Loaded(data: data, object: object)
    }

    private static func dictionary(_ value: Any?, name: String) throws -> [String: Any] {
        guard let value else { return [:] }
        guard let object = value as? [String: Any] else {
            throw InstallError("\(name) must be a JSON object")
        }
        return object
    }

    private static func encoded(_ object: [String: Any]) throws -> Data {
        guard JSONSerialization.isValidJSONObject(object) else {
            throw InstallError("merged Claude configuration is not valid JSON")
        }
        var data = try JSONSerialization.data(
            withJSONObject: object,
            options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        )
        data.append(0x0A)
        return data
    }

    private static func shellQuote(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }
}

enum ClaudeAgentModeInstallCommand {
    struct Request: Equatable, Sendable {
        let repo: String
        let project: String
    }

    static var isRequested: Bool {
        CommandLine.arguments.dropFirst().contains("--install-claude-agent-mode")
    }

    static func request(arguments: [String] = CommandLine.arguments) -> Request? {
        guard arguments.dropFirst().contains("--install-claude-agent-mode"),
              let repoFlag = arguments.firstIndex(of: "--repo"),
              let projectFlag = arguments.firstIndex(of: "--project"),
              arguments.indices.contains(repoFlag + 1),
              arguments.indices.contains(projectFlag + 1) else { return nil }
        return Request(repo: arguments[repoFlag + 1], project: arguments[projectFlag + 1])
    }

    static func run() -> Int32 {
        guard let request = request(), let executable = Bundle.main.executableURL else {
            writeError(
                "Usage: Icarus --install-claude-agent-mode --repo owner/name --project /path")
            return 2
        }
        do {
            let result = try ClaudeAgentModeInstaller.install(
                project: URL(fileURLWithPath: request.project, isDirectory: true),
                repo: request.repo,
                executable: executable
            )
            let verb = result.changed ? "Enabled" : "Already enabled"
            let message = (
                "\(verb) Claude Agent Mode for \(request.repo).\n"
                + "Session observation is explicit and local; raw transcripts are not stored by Icarus.\n"
            )
            FileHandle.standardOutput.write(Data(message.utf8))
            return 0
        } catch let error as ClaudeAgentModeInstaller.InstallError {
            writeError(error.message)
            return 1
        } catch {
            writeError("Icarus could not update the project configuration.")
            return 1
        }
    }

    private static func writeError(_ message: String) {
        FileHandle.standardError.write(Data((message + "\n").utf8))
    }
}
