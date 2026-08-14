import XCTest
@testable import Icarus

final class ClaudeConnectorTests: XCTestCase {
    func testParsesTheShippedAppAsConnected() {
        let status = ClaudeConnector.parseStatus(
            """
            icarus:
              Scope: User config (available in all your projects)
              Status: ✔ Connected
              Type: stdio
              Command: /Applications/Icarus.app/Contents/MacOS/Icarus
              Args: --mcp
            """,
            expectedExecutable: "/Applications/Icarus.app/Contents/MacOS/Icarus")

        XCTAssertEqual(status, .connected)
    }

    func testRecognisesTheCheckoutOnlyPythonAdapterAsRepairableLegacyState() {
        let status = ClaudeConnector.parseStatus(
            """
            icarus:
              Scope: User config (available in all your projects)
              Status: ✔ Connected
              Type: stdio
              Command: /tmp/Icarus/.venv/bin/python
              Args: -m demo.mcp_server
            """,
            expectedExecutable: "/Applications/Icarus.app/Contents/MacOS/Icarus")

        XCTAssertEqual(status, .legacyUserRegistration)
    }

    func testDoesNotOverwriteAnUnrelatedServerNamedIcarus() {
        let status = ClaudeConnector.parseStatus(
            """
            icarus:
              Scope: Project config (shared via .mcp.json)
              Status: ✔ Connected
              Type: stdio
              Command: /usr/local/bin/company-icarus
              Args: serve
            """,
            expectedExecutable: "/Applications/Icarus.app/Contents/MacOS/Icarus")

        guard case .conflict = status else {
            return XCTFail("Expected a conflict, got \(status)")
        }
    }

    func testProjectScopedAppRegistrationIsNotClaimedAsUniversal() {
        let status = ClaudeConnector.parseStatus(
            """
            icarus:
              Scope: Project config (shared via .mcp.json)
              Status: ✔ Connected
              Type: stdio
              Command: /Applications/Icarus.app/Contents/MacOS/Icarus
              Args: --mcp
            """,
            expectedExecutable: "/Applications/Icarus.app/Contents/MacOS/Icarus")

        guard case .conflict = status else {
            return XCTFail("Expected a conflict, got \(status)")
        }
    }

    func testRepairRemovesOnlyTheLegacyUserEntryThenAddsTheApp() async throws {
        let recorder = CommandRecorder(results: [
            .init(exitCode: 0, output: Self.legacyOutput),
            .init(exitCode: 0, output: ""),
            .init(exitCode: 0, output: ""),
            .init(exitCode: 0, output: Self.connectedOutput),
        ])
        let connector = ClaudeConnector(
            claudeExecutable: URL(fileURLWithPath: "/usr/local/bin/claude"),
            appExecutable: URL(fileURLWithPath: "/Applications/Icarus.app/Contents/MacOS/Icarus"),
            run: { arguments in try await recorder.run(arguments) })

        let status = try await connector.installOrRepair()

        XCTAssertEqual(status, .connected)
        let commands = await recorder.commands
        XCTAssertEqual(commands, [
            ["mcp", "get", "icarus"],
            ["mcp", "remove", "icarus", "--scope", "user"],
            ["mcp", "add", "--transport", "stdio", "--scope", "user", "icarus", "--",
             "/Applications/Icarus.app/Contents/MacOS/Icarus", "--mcp"],
            ["mcp", "get", "icarus"],
        ])
    }

    private static let legacyOutput = """
    icarus:
      Scope: User config (available in all your projects)
      Command: /tmp/Icarus/.venv/bin/python
      Args: -m demo.mcp_server
    """

    private static let connectedOutput = """
    icarus:
      Scope: User config (available in all your projects)
      Command: /Applications/Icarus.app/Contents/MacOS/Icarus
      Args: --mcp
    """
}

private actor CommandRecorder {
    private var results: [ClaudeConnector.CommandResult]
    private(set) var commands: [[String]] = []

    init(results: [ClaudeConnector.CommandResult]) { self.results = results }

    func run(_ command: [String]) throws -> ClaudeConnector.CommandResult {
        commands.append(command)
        return results.removeFirst()
    }
}
