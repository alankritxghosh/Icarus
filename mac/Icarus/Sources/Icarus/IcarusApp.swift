import SwiftUI

struct IcarusApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    var body: some Scene {
        Settings { SettingsView() }
    }
}

/// Real entry point. It first handles the two bounded headless commands and
/// exits; otherwise it launches the app.
@main
struct Main {
    @MainActor
    static func main() async {
        if ClaudeAgentModeInstallCommand.isRequested {
            exit(ClaudeAgentModeInstallCommand.run())
        }
        if ClaudeHookCommand.isRequested {
            exit(await ClaudeHookCommand.run())
        }
        if ExtensionBridgeCommand.requestedOrigin != nil {
            exit(await ExtensionBridgeCommand.run())
        }
        if AgentSessionCommand.requested {
            exit(await AgentSessionCommand.run())
        }
        // Before the app ever launches a window: an MCP client starts this
        // process expecting a clean JSON-RPC channel on stdout.
        if McpCommand.requested {
            exit(await McpCommand.run())
        }
        if let dir = IconExport.iconsetDirArg() {
            IconExport.writeIconset(to: dir)
            exit(0)
        }
        if let (path, px) = IconExport.pngArgs() {
            IconExport.writeIcon(to: path, pixels: px)
            exit(0)
        }
        IcarusApp.main()
    }
}
