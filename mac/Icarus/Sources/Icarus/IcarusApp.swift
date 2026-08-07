import SwiftUI

struct IcarusApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    var body: some Scene {
        Settings { EmptyView() }   // no window; the menu-bar item lives in the delegate
    }
}

/// Real entry point. It first handles the two bounded headless commands and
/// exits; otherwise it launches the app.
@main
struct Main {
    @MainActor
    static func main() async {
        if ExtensionBridgeCommand.requestedOrigin != nil {
            exit(await ExtensionBridgeCommand.run())
        }
        if AgentSessionCommand.requested {
            exit(await AgentSessionCommand.run())
        }
        if let dir = IconExport.iconsetDirArg() {
            IconExport.writeIconset(to: dir)
            exit(0)
        }
        IcarusApp.main()
    }
}
