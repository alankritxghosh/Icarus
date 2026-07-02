import Foundation
import Observation

/// The real, in-session record of questions asked and what the brain returned.
/// Session-scoped (not yet persisted — a later brick), so the UI shows honest
/// empty states rather than seeded history. Powers recent-questions, decision
/// history, unknowns, the proof drawer, and the cited-rate metric.
@MainActor
@Observable
public final class AskHistory {
    public struct Entry: Identifiable, Sendable {
        public let id = UUID()
        public let at: Date
        public let question: String
        public let response: AskResponse
        public var isCited: Bool { response.verdict == .answer && !response.citations.isEmpty }
        public var isUnknown: Bool { response.verdict == .unknown }
    }

    public private(set) var entries: [Entry] = []   // most-recent first
    public init() {}

    /// Append a real ask + its verdict. Inserted at the front so the newest is first.
    public func record(question: String, response: AskResponse) {
        entries.insert(Entry(at: Date(), question: question, response: response), at: 0)
    }

    public var unknowns: [Entry] { entries.filter(\.isUnknown) }
    public var mostRecent: Entry? { entries.first }

    /// Fraction of asks that returned a grounded, cited answer. `nil` until at
    /// least one ask — so the UI never shows a fabricated percentage.
    public var citedRate: Double? {
        guard !entries.isEmpty else { return nil }
        let cited = entries.filter(\.isCited).count
        return Double(cited) / Double(entries.count)
    }
}
