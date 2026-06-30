import SwiftUI
import IcarusKit

/// Honest-Brutalism "Quiet Native Memory v2" tokens, from the Figma wireframe.
/// Geist / JetBrains Mono aren't installed, so we use the system sans and SF Mono
/// (.monospaced) as close stand-ins; bundle the real fonts later for a pixel match.
enum Theme {
    static let ink = Color(hex: 0x26252A)        // primary text
    static let muted = Color(hex: 0x6F6B65)       // secondary text
    static let surface = Color(hex: 0xF7F5EF)     // page / window
    static let card = Color(hex: 0xFBFAF7)        // raised card
    static let border = Color(hex: 0xE3DCD2)      // hairline border
    static let accent = Color(hex: 0x2F6BFF)      // citation accent blue
    static let cited = Color(hex: 0x157A5B)       // cited / receipts green
    static let citedBg = Color(hex: 0xDDEFE7)
    static let unknown = Color(hex: 0xB76E00)     // honest-unknown amber
    static let unknownBg = Color(hex: 0xFFF1CD)

    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }
}

extension Color {
    init(hex: UInt32) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255)
    }
}

/// Uppercase mono section label (e.g. RECEIPTS, HONEST UNKNOWN).
struct MonoLabel: View {
    let text: String
    let color: Color
    init(_ text: String, _ color: Color = Theme.muted) { self.text = text; self.color = color }
    var body: some View {
        Text(text).font(Theme.mono(11, .bold)).tracking(0.9).foregroundStyle(color)
    }
}

/// A clickable citation pill: mono, green-bordered. Opens the ref's GitHub URL.
struct CitationChip: View {
    let citation: Citation
    var body: some View {
        let pill = Text(citation.ref)
            .font(Theme.mono(11, .bold))
            .foregroundStyle(Theme.cited)
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background(Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(Theme.cited, lineWidth: 1))
        if let urlString = citation.url, let url = URL(string: urlString) {
            Link(destination: url) { pill }.buttonStyle(.plain)
        } else {
            pill
        }
    }
}

/// Filled ink primary button (Sign in / Connect / Ask).
struct PrimaryButton: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(Theme.card)
            .padding(.horizontal, 16).padding(.vertical, 10)
            .background(Theme.ink.opacity(configuration.isPressed ? 0.82 : 1))
            .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

/// Wrapping row (chips, searched files) — SwiftUI has no native flow layout.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for sub in subviews {
            let size = sub.sizeThatFits(.unspecified)
            if x + size.width > maxWidth { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: maxWidth == .infinity ? x : maxWidth, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for sub in subviews {
            let size = sub.sizeThatFits(.unspecified)
            if x - bounds.minX + size.width > bounds.width { x = bounds.minX; y += rowHeight + spacing; rowHeight = 0 }
            sub.place(at: CGPoint(x: x, y: y), anchor: .topLeading, proposal: ProposedViewSize(size))
            x += size.width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}
