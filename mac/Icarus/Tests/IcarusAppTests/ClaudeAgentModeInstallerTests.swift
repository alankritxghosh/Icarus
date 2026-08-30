import XCTest
@testable import Icarus

final class ClaudeAgentModeInstallerTests: XCTestCase {
    private func temporaryProject() throws -> (TemporaryDirectory, URL) {
        let temp = try TemporaryDirectory()
        return (temp, temp.url)
    }

    func testInstallCreatesRepoScopedMCPAndExplicitHooks() throws {
        let (temp, project) = try temporaryProject()
        _ = temp
        let executable = URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")

        let result = try ClaudeAgentModeInstaller.install(
            project: project, repo: "acme/app", executable: executable)

        XCTAssertTrue(result.changed)
        let mcp = try object(project.appendingPathComponent(".mcp.json"))
        let servers = mcp["mcpServers"] as? [String: Any]
        let icarus = servers?["icarus"] as? [String: Any]
        XCTAssertEqual(icarus?["command"] as? String, executable.path)
        XCTAssertEqual(icarus?["args"] as? [String], ["--mcp"])

        let settings = try object(
            project.appendingPathComponent(".claude/settings.local.json"))
        let hooks = settings["hooks"] as? [String: Any]
        for event in ["SessionStart", "Stop"] {
            let matchers = hooks?[event] as? [[String: Any]]
            let commands = matchers?.flatMap { $0["hooks"] as? [[String: Any]] ?? [] }
            XCTAssertEqual(commands?.count, 1)
            let command = commands?.first?["command"] as? String ?? ""
            XCTAssertTrue(command.contains("--claude-hook"))
            XCTAssertTrue(command.contains("--repo 'acme/app'"))
        }
    }

    func testInstallPreservesExistingSettingsAndOtherMCPServers() throws {
        let (temp, project) = try temporaryProject()
        _ = temp
        try Data(#"{"mcpServers":{"other":{"command":"other"}},"custom":true}"#.utf8)
            .write(to: project.appendingPathComponent(".mcp.json"))
        let claude = project.appendingPathComponent(".claude", isDirectory: true)
        try FileManager.default.createDirectory(at: claude, withIntermediateDirectories: true)
        try Data(#"{"permissions":{"allow":["Read"]},"hooks":{"Stop":[{"hooks":[{"type":"command","command":"existing"}]}]}}"#.utf8)
            .write(to: claude.appendingPathComponent("settings.local.json"))

        _ = try ClaudeAgentModeInstaller.install(
            project: project,
            repo: "acme/app",
            executable: URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")
        )

        let mcp = try object(project.appendingPathComponent(".mcp.json"))
        let servers = mcp["mcpServers"] as? [String: Any]
        XCTAssertNotNil(servers?["other"])
        XCTAssertNotNil(servers?["icarus"])
        XCTAssertEqual(mcp["custom"] as? Bool, true)
        let settings = try object(claude.appendingPathComponent("settings.local.json"))
        XCTAssertNotNil(settings["permissions"])
        let stop = (settings["hooks"] as? [String: Any])?["Stop"] as? [[String: Any]]
        XCTAssertEqual(stop?.count, 2)
    }

    func testInstallIsIdempotent() throws {
        let (temp, project) = try temporaryProject()
        _ = temp
        let executable = URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")
        _ = try ClaudeAgentModeInstaller.install(
            project: project, repo: "acme/app", executable: executable)

        let second = try ClaudeAgentModeInstaller.install(
            project: project, repo: "acme/app", executable: executable)

        XCTAssertFalse(second.changed)
        let settings = try object(
            project.appendingPathComponent(".claude/settings.local.json"))
        let hooks = settings["hooks"] as? [String: Any]
        for event in ["SessionStart", "Stop"] {
            XCTAssertEqual((hooks?[event] as? [[String: Any]])?.count, 1)
        }
    }

    func testInvalidExistingJSONIsRefusedWithoutOverwrite() throws {
        let (temp, project) = try temporaryProject()
        _ = temp
        let path = project.appendingPathComponent(".mcp.json")
        let original = Data("not json\n".utf8)
        try original.write(to: path)

        XCTAssertThrowsError(try ClaudeAgentModeInstaller.install(
            project: project,
            repo: "acme/app",
            executable: URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")
        ))
        XCTAssertEqual(try Data(contentsOf: path), original)
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: project.appendingPathComponent(".claude/settings.local.json").path
        ))
    }

    func testSymlinkedClaudeDirectoryIsRefusedWithoutWritingOutsideProject() throws {
        let (temp, project) = try temporaryProject()
        _ = temp
        let outside = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: outside, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: outside) }
        try FileManager.default.createSymbolicLink(
            at: project.appendingPathComponent(".claude"),
            withDestinationURL: outside
        )

        XCTAssertThrowsError(try ClaudeAgentModeInstaller.install(
            project: project,
            repo: "acme/app",
            executable: URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus")
        ))
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: outside.appendingPathComponent("settings.local.json").path
        ))
        XCTAssertFalse(FileManager.default.fileExists(
            atPath: project.appendingPathComponent(".mcp.json").path
        ))
    }

    private func object(_ url: URL) throws -> [String: Any] {
        try XCTUnwrap(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any]
        )
    }
}

private final class TemporaryDirectory {
    let url: URL

    init() throws {
        url = FileManager.default.temporaryDirectory
            .appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    }

    deinit { try? FileManager.default.removeItem(at: url) }
}
