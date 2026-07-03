import SwiftUI

struct IcarusApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    var body: some Scene {
        Settings { EmptyView() }   // no window; the menu-bar item lives in the delegate
    }
}

/// Real entry point. It first handles the bundler's headless icon export
/// (`Icarus --render-iconset <dir>`) and exits; otherwise it launches the app.
@main
struct Main {
    static func main() {
        if let dir = IconExport.iconsetDirArg() {
            IconExport.writeIconset(to: dir)
            exit(0)
        }
        IcarusApp.main()
    }
}
