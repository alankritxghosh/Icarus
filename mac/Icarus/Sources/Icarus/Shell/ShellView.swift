import SwiftUI
import IcarusKit

/// The full app shell: sidebar + a content area that routes between the
/// sidebar's surfaces. Data comes from the shared AskHistory + StatusModel (real values),
/// and asking is delegated to the existing overlay via `onTryQuestion`.
struct ShellView: View {
    let auth: AuthModel
    let connect: ConnectModel
    let history: AskHistory
    let status: StatusModel
    /// The repo's SHARED ask ledger (server-side), distinct from `history`,
    /// which is this session's in-memory record only.
    let ledger: LedgerModel
    let decisions: DecisionInboxModel
    let briefing: BriefingModel
    let investigation: InvestigationModel
    let onTryQuestion: () -> Void

    @State private var selected: ShellSurface = .home

    var body: some View {
        HStack(spacing: 0) {
            SidebarView(selected: $selected, auth: auth, connect: connect)
            Divider()
            ScrollView {
                content.padding(26).frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .frame(minWidth: 1040, minHeight: 680)
        .background(Theme.surface)
        .onAppear { status.start() }
        // Feed every /status poll to the connect model so a server-side drop of
        // the session (restart / eviction) is surfaced explicitly, never hidden.
        .onChange(of: status.status) { _, new in
            if let new {
                connect.noteStatus(new)
                investigation.noteConnectedRepo(new.repo)
            }
        }
        .onChange(of: auth.isSignedIn) { _, signedIn in
            if !signedIn { investigation.noteConnectedRepo(nil) }
        }
    }

    @ViewBuilder private var content: some View {
        switch selected {
        case .home: HomeView(auth: auth, connect: connect, history: history, status: status,
                             briefing: briefing, onTryQuestion: onTryQuestion)
        case .startHere: OnboardingView(status: status, onTryQuestion: onTryQuestion)
        case .investigate: InvestigationView(model: investigation)
        case .decisionHistory: DecisionGraphView(decisions: decisions)
        case .engineeringMemory: UnknownsView(ledger: ledger, decisions: decisions)
        }
    }
}
