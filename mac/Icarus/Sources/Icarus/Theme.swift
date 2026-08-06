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
        // Truncate the MIDDLE, not the tail: a ref's meaning lives at both ends
        // (`commit:` / `code:path` identifies the source, the tail
        // disambiguates), so `commit:8384…45779` stays readable where a
        // tail-truncated `commit:83840902c890f0eb85decda…` does not.
        //
        // `displayLabel` (IcarusKit) shows the raw ref for anything a person
        // wrote and words — "Icarus's own index" — for `index:` evidence, which
        // is measured from the repository rather than authored. Rendering that
        // as a bare `index:overview` chip beside `pr:1482` implied a document
        // somebody wrote, which is the one claim it must not make.
        let pill = Text(citation.displayLabel)
            .font(Theme.mono(11, .bold))
            .lineLimit(1)
            .truncationMode(.middle)
            .foregroundStyle(citation.isIndex ? Theme.muted : Theme.cited)
            .padding(.horizontal, 9).padding(.vertical, 5)
            .background(Theme.card)
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8)
                .strokeBorder(citation.isIndex ? Theme.muted : Theme.cited,
                              style: StrokeStyle(lineWidth: 1,
                                                 dash: citation.isIndex ? [3, 2] : [])))
        // linkURL is nil for index evidence, so it can never become a link.
        if let url = citation.linkURL {
            Link(destination: url) { pill }.buttonStyle(.plain)
        } else {
            pill
        }
    }
}

/// Frosted "glass" backing for the floating overlay — Option A's vibrancy.
///
/// `NSVisualEffectView`, not SwiftUI's `.ultraThinMaterial`: the panel's window is
/// transparent (`backgroundColor = .clear`), so a SwiftUI material would blur nothing and
/// read as flat translucency. `.behindWindow` blending samples what is actually BEHIND
/// the panel — the user's editor, browser, desktop — which is what makes it read as glass
/// floating over their work.
///
/// `state = .active` is load-bearing: the default follows the window's active state, and
/// this is a NON-ACTIVATING panel that is usually not key, so the frost would otherwise
/// drop out exactly when the overlay is in use.
struct VisualEffectBackground: NSViewRepresentable {
    var material: NSVisualEffectView.Material = .popover

    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = material
        view.blendingMode = .behindWindow
        view.state = .active
        return view
    }

    func updateNSView(_ view: NSVisualEffectView, context: Context) {
        view.material = material
    }
}

/// The listening waveform: one bar per measured microphone level, oldest at the left.
///
/// Every bar is REAL — `levels` comes from the audio buffers the recognizer is
/// transcribing (see `AppleSpeechRecognizer.normalizedLevel`). There is deliberately no
/// idle animation and no synthetic motion: silence renders as flat minimum-height bars,
/// so a moving waveform is honest evidence the mic is actually hearing something.
/// Drawn in a single `Canvas`, not as 40 stacked `Capsule` views.
///
/// The view-per-bar version rebuilt and animated 40 view identities on every level
/// update — with implicit animation on an array whose every index shifts each tick, that
/// is ~1,700 view animations a second, on top of a live vibrancy blur. Canvas is one draw
/// call with no view identity to diff.
///
/// There is deliberately NO implicit animation here either: the data arrives ~14x/sec and
/// IS the motion. Interpolating between real measurements would smooth the mic reading
/// into something prettier than the truth, which is the one thing this waveform exists not
/// to do.
struct WaveformView: View {
    let levels: [Float]
    var barWidth: CGFloat = 3
    var spacing: CGFloat = 2
    var height: CGFloat = 22

    private var width: CGFloat {
        CGFloat(VoiceModel.levelWindow) * (barWidth + spacing) - spacing
    }

    var body: some View {
        Canvas(opaque: false, rendersAsynchronously: false) { context, size in
            // Pad the left with silence so bars fill from the right as speech arrives.
            let pad = max(0, VoiceModel.levelWindow - levels.count)
            for index in 0..<VoiceModel.levelWindow {
                let level = index < pad ? 0 : levels[index - pad]
                let barHeight = max(2, CGFloat(level) * size.height)
                let rect = CGRect(x: CGFloat(index) * (barWidth + spacing),
                                  y: (size.height - barHeight) / 2,
                                  width: barWidth,
                                  height: barHeight)
                context.fill(Path(roundedRect: rect, cornerRadius: barWidth / 2),
                             with: .color(Theme.cited))
            }
        }
        .frame(width: width, height: height)
        .accessibilityLabel("Microphone level")
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

    // A subview wider than the row (a 40-hex-char `commit:` ref, or a long
    // `code:` path) must be CLAMPED to the available width, not placed at its
    // full intrinsic width -- unclamped it overflowed the parent card and was
    // clipped mid-ref with the pill border sliced off. Found live 2026-07-20 in
    // HomeView's narrow proof drawer; the wide ask overlay never revealed it.
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, rowHeight: CGFloat = 0
        for sub in subviews {
            let size = sub.sizeThatFits(.unspecified)
            let width = min(size.width, maxWidth)
            if x + width > maxWidth { x = 0; y += rowHeight + spacing; rowHeight = 0 }
            x += width + spacing
            rowHeight = max(rowHeight, size.height)
        }
        return CGSize(width: maxWidth == .infinity ? x : maxWidth, height: y + rowHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowHeight: CGFloat = 0
        for sub in subviews {
            let size = sub.sizeThatFits(.unspecified)
            let width = min(size.width, bounds.width)
            if x - bounds.minX + width > bounds.width { x = bounds.minX; y += rowHeight + spacing; rowHeight = 0 }
            sub.place(at: CGPoint(x: x, y: y), anchor: .topLeading,
                      proposal: ProposedViewSize(width: width, height: size.height))
            x += width + spacing
            rowHeight = max(rowHeight, size.height)
        }
    }
}
