import SwiftUI

@main
struct IcarusApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    var body: some Scene {
        Settings { EmptyView() }   // no window; the menu-bar item lives in the delegate
    }
}
