import Foundation

/// The five surfaces of the app shell's sidebar, in display order. Kept in
/// IcarusKit (not the view layer) so its titles/order are unit-testable.
public enum ShellSurface: String, CaseIterable, Sendable, Identifiable {
    case home
    case askByVoice
    case decisionHistory
    case unknowns
    case privacyBoundary

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .home: return "Home"
        case .askByVoice: return "Ask by voice"
        case .decisionHistory: return "Decision history"
        case .unknowns: return "Unknowns"
        case .privacyBoundary: return "Privacy boundary"
        }
    }
}
