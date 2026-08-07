import Foundation

/// The surfaces of the app shell's sidebar, in display order. Kept in
/// IcarusKit (not the view layer) so its titles/order are unit-testable.
public enum ShellSurface: String, CaseIterable, Sendable, Identifiable {
    case home
    /// The guided onboarding tour -- the first experience with a new repo.
    case startHere
    case decisionHistory
    case engineeringMemory

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .home: return "Home"
        case .startHere: return "Start here"
        case .decisionHistory: return "Decision history"
        case .engineeringMemory: return "Engineering memory"
        }
    }
}
