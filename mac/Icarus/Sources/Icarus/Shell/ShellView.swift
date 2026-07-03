import SwiftUI
import IcarusKit

/// The full app shell: sidebar + a content area that routes between the five
/// surfaces. Data comes from the shared AskHistory + StatusModel (real values),
/// and asking is delegated to the existing overlay via `onTryQuestion`.
struct ShellView: View {
    let auth: AuthModel
    let connect: ConnectModel
    let history: AskHistory
    let status: StatusModel
    let onTryQuestion: () -> Void

    @State private var selected: ShellSurface = .home

    var body: some View {
        HStack(spacing: 0) {
            SidebarView(selected: $selected, status: status, auth: auth)
            Divider()
            ScrollView {
                content.padding(26).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(minWidth: 1040, minHeight: 680)
        .background(Theme.surface)
        .onAppear { status.start() }
    }

    @ViewBuilder private var content: some View {
        switch selected {
        case .home: HomeView(auth: auth, connect: connect, history: history, status: status, onTryQuestion: onTryQuestion)
        case .askByVoice: AskByVoiceView(onOpenOverlay: onTryQuestion)
        case .decisionHistory: DecisionHistoryView(history: history)
        case .unknowns: UnknownsView(history: history)
        case .privacyBoundary: PrivacyBoundaryView()
        }
    }
}
