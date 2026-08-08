import Foundation

/// How strongly the repository backs one finding.
///
/// This is the whole reason the investigation surface exists. A conclusion that
/// says "the repository states X" and one that says "the implementation suggests
/// X" are different claims, and rendering them in the same confident voice is a
/// bluff the honesty gate structurally cannot catch — every citation underneath
/// both is real.
///
/// The value is COMPUTED server-side (evals/investigation.classify_support) from
/// the evidence's own source kind and rationale markers. The app renders it and
/// never recomputes or upgrades it, exactly as it renders `Verdict` verbatim.
///
/// An unrecognised value decodes to `.unrecognised` rather than failing: a newer
/// brain that adds a class must not make an older app unable to show the answer
/// at all. It renders in the most cautious voice available, never the boldest.
public enum Support: String, Decodable, Sendable {
    case explicit
    case strong
    case weak
    case unsupported
    case unrecognised

    public init(from decoder: Decoder) throws {
        let raw = try decoder.singleValueContainer().decode(String.self)
        self = Support(rawValue: raw) ?? .unrecognised
    }

    /// What a reader should be told this finding IS. Deliberately prose rather
    /// than a bare label: "weak" alone reads as a quality score of the answer
    /// when it is actually a statement about what the repository recorded.
    public var headline: String {
        switch self {
        case .explicit: return "The repository states this"
        case .strong: return "Several pieces of evidence indicate this"
        case .weak: return "Suggested by the implementation, not recorded"
        case .unsupported, .unrecognised: return "Not established by the repository"
        }
    }

    /// Ordering for display: what the repository actually says comes before what
    /// was inferred from it, so a reader meets the strongest ground first.
    public var rank: Int {
        switch self {
        case .explicit: return 0
        case .strong: return 1
        case .weak: return 2
        case .unsupported, .unrecognised: return 3
        }
    }

    /// Whether this finding may be presented as something the repository RECORDS
    /// rather than something Icarus concluded. Only one class earns that.
    public var isRecorded: Bool { self == .explicit }
}

/// One evidence-backed finding, with the citations that support it.
public struct Finding: Decodable, Identifiable, Sendable {
    public let text: String
    public let support: Support
    public let citations: [Citation]
    public var id: String { text }
}

/// One hypothesis the investigation weighed, and where it landed.
public struct InvestigationHypothesis: Decodable, Identifiable, Sendable {
    public let statement: String
    public let status: String
    public var id: String { statement }
}

/// One step the investigation actually ran — the audit trail. `args` is decoded
/// as strings because the server sends a small, closed set of scalar arguments
/// (a ref, an edge name, a query) and a renderer only ever shows them.
public struct InvestigationStep: Decodable, Identifiable, Sendable {
    public let step: String
    public let primitive: String
    public let args: [String: String]
    public let reason: String
    public var id: String { step }

    private enum CodingKeys: String, CodingKey { case step, primitive, args, reason }

    public init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        step = try c.decode(String.self, forKey: .step)
        primitive = try c.decode(String.self, forKey: .primitive)
        reason = (try? c.decode(String.self, forKey: .reason)) ?? ""
        // Arguments arrive as a small JSON object whose values are strings or
        // numbers. Rendered, never interpreted, so both are read as text and an
        // unexpected shape is dropped rather than failing the whole decode.
        var decoded: [String: String] = [:]
        if let raw = try? c.decode([String: LenientScalar].self, forKey: .args) {
            for (key, value) in raw { decoded[key] = value.text }
        }
        args = decoded
    }

    /// A one-line description of what this step did, for the trail.
    public var summary: String {
        let detail = ["ref", "pr", "query", "edge"].compactMap { key in
            args[key].map { key == "edge" ? "→ \($0)" : $0 }
        }.joined(separator: " ")
        return detail.isEmpty ? primitive : "\(primitive) \(detail)"
    }
}

/// A JSON scalar read as text. Exists so a numeric argument (`k: 6`) does not
/// fail the decode of a step whose only purpose is to be displayed.
struct LenientScalar: Decodable {
    let text: String

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { text = s }
        else if let i = try? c.decode(Int.self) { text = String(i) }
        else if let d = try? c.decode(Double.self) { text = String(d) }
        else if let b = try? c.decode(Bool.self) { text = String(b) }
        else { text = "" }
    }
}

/// The `investigation` block of a `POST /investigate` response
/// (demo/payload.build_investigation_payload).
public struct InvestigationTrace: Decodable, Sendable {
    public let objective: String
    /// What the investigation took "it" to mean. Shown so a reader can SEE that
    /// a follow-up was understood, rather than discovering it was not from an
    /// answer about the wrong change.
    public let subject: [String]
    public let findings: [Finding]
    public let hypotheses: [InvestigationHypothesis]
    public let unknowns: [String]
    public let contradictions: [Contradiction]
    public let trail: [InvestigationStep]
    public let stoppedBecause: String?
    /// Non-nil only when a ceiling cut the investigation short. A view MUST
    /// surface this: a truncated investigation presented as a complete one is
    /// the same class of failure as a bluffed citation.
    public let incompleteBecause: String?

    private enum CodingKeys: String, CodingKey {
        case objective, subject, findings, hypotheses, unknowns, contradictions, trail
        case stoppedBecause = "stopped_because"
        case incompleteBecause = "incomplete_because"
    }

    /// Findings with what the repository RECORDS first, then what was inferred.
    /// Stable within a class, so the order the investigation found them in is
    /// preserved rather than reshuffled on every render.
    public var orderedFindings: [Finding] {
        findings.enumerated()
            .sorted { ($0.element.support.rank, $0.offset) < ($1.element.support.rank, $1.offset) }
            .map(\.element)
    }

    /// Findings grouped by support class, strongest ground first — the shape a
    /// view needs to show "what we know" apart from "what we infer".
    public var findingsBySupport: [(support: Support, findings: [Finding])] {
        var seen: [Support] = []
        for finding in orderedFindings where !seen.contains(finding.support) {
            seen.append(finding.support)
        }
        return seen.map { support in
            (support, orderedFindings.filter { $0.support == support })
        }
    }

    /// True when this investigation has something a reader must be told beyond
    /// the answer itself: it was cut short, or the evidence disagrees with itself.
    public var needsCaveat: Bool { incompleteBecause != nil || !contradictions.isEmpty }
}

/// Evidence that pulls both ways on one hypothesis. Reported, never resolved —
/// silently picking a side is how a confident wrong answer gets made.
public struct Contradiction: Decodable, Identifiable, Sendable {
    public let claims: [String]
    public let about: String
    public var id: String { about + claims.joined() }
}

/// A full `/investigate` response: an ordinary answer plus how it was reached.
///
/// `answer` is decoded by reusing `AskResponse`, so the cited-answer and
/// honest-unknown rendering the app already has works unchanged — the trace is
/// additive, never a second way of presenting a verdict.
public struct InvestigationResponse: Decodable, Sendable {
    public let answer: AskResponse
    public let trace: InvestigationTrace

    private enum CodingKeys: String, CodingKey { case investigation }

    public init(from decoder: Decoder) throws {
        answer = try AskResponse(from: decoder)
        trace = try decoder.container(keyedBy: CodingKeys.self)
            .decode(InvestigationTrace.self, forKey: .investigation)
    }
}
