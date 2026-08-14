import AppKit
import SwiftUI
import IcarusKit

/// Honest-Brutalism tokens, dark — the same names the light "Quiet Native Memory
/// v2" palette used, with only the values moved, so every call site flipped
/// without being touched. Values are the website's (`site/index.html`), so the
/// app and the marketing page are one product: `--paper`, `--card`, `--hair`,
/// `--ink`, `--muted`, `--signal`, `--cited`, `--unknown`.
///
/// Dark only, deliberately. Following the system appearance would mean deciding
/// every semantic tone twice and verifying every surface twice, and there is no
/// second palette to fall back to — the site commits to this one.
enum Theme {
    static let ink = Color(hex: 0xECEAE3)         // primary text
    static let muted = Color(hex: 0x948F86)       // secondary text
    static let surface = Color(hex: 0x0D0D10)     // page / window
    static let card = Color(hex: 0x15151A)        // raised card
    static let border = Color(hex: 0x26262C)      // hairline border
    static let accent = Color(hex: 0x8098FF)      // citation accent blue
    static let cited = Color(hex: 0x6FD3A8)       // cited / receipts green
    static let unknown = Color(hex: 0xE0A23C)     // honest-unknown amber
    /// The two semantic backgrounds are TINTS of their own tone, not separate
    /// colours. On the light palette they were opaque pastels; a pastel has no
    /// dark equivalent, and a merely darker pastel reads as mud.
    static let citedBg = cited.opacity(0.10)
    static let unknownBg = unknown.opacity(0.09)

    static func mono(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        .system(size: size, weight: weight, design: .monospaced)
    }

    /// The serif display face, resolved once against what the Mac actually has.
    /// `Font.custom` falls back SILENTLY to the system face when a family is
    /// missing, so a missing font would look like a styling bug rather than a
    /// missing font — hence the explicit probe and the explicit `.serif` fallback.
    private static let displayFamily: String? =
        ["Hoefler Text", "Iowan Old Style", "Palatino"].first { NSFont(name: $0, size: 12) != nil }

    /// Serif, for hero moments ONLY — the Home headline, "No one wrote this
    /// down.", surface titles. Body stays sans and evidence stays mono: serif at
    /// 13pt in a dense list costs scanning speed and buys nothing.
    static func display(_ size: CGFloat, _ weight: Font.Weight = .regular) -> Font {
        if let family = displayFamily { return .custom(family, size: size).weight(weight) }
        return .system(size: size, weight: weight, design: .serif)
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

/// CLEAR glass for the floating overlay — transparent, not frosted.
///
/// There is deliberately no `NSVisualEffectView` here any more. Vibrancy BLURS
/// what is behind it; this material does not, so the user's code stays in focus
/// and readable through the panel. That makes this the simpler implementation of
/// the two: a fill, a sheen, an edge, a shadow.
///
/// **The alpha is a measured value, not a taste one.** Judged by eye over a dark
/// editor, 0.55 looked right; measured against the worst case it is 3.56:1 for
/// the answer text, under WCAG AA. The worst case is a pure-white window behind
/// the panel — a browser, a document — because clear glass has nothing but this
/// tint between the answer and someone else's page. 0.62 is where AA is reached;
/// 0.65 is used for headroom, and `ThemeContrastTests` pins it so the number
/// cannot drift back down because a screenshot looked nicer.
///
/// It cannot adapt to the backdrop: choosing an alpha from what is behind the
/// window means sampling the screen, and Icarus never reads the screen without
/// an explicit, opt-in gesture. One fixed value, picked for the worst case.
struct GlassPanel: ViewModifier {
    /// Pinned by `ThemeContrastTests.testAnswerTextSurvivesGlassOverAWhiteBackdrop`.
    ///
    /// `nonisolated` because it is a plain constant, not main-actor state.
    /// `ViewModifier` is `@MainActor` in Swift 6, so this static inherited that
    /// isolation and the contrast test -- an ordinary nonisolated XCTest method
    /// -- could not read it: "main actor-isolated static property 'alpha' can
    /// not be referenced from a nonisolated context". Xcode 16 (CI) rejected it
    /// while Swift 6.2 locally did not, so the Swift job was red on every branch
    /// and green on every laptop. Marking the CONSTANT nonisolated is the fix
    /// rather than pushing the test onto the main actor, because the number
    /// genuinely has no isolation requirement and any other caller would hit
    /// the same wall.
    nonisolated static let alpha: Double = 0.65

    var cornerRadius: CGFloat

    func body(content: Content) -> some View {
        content
            .background {
                ZStack {
                    Theme.surface.opacity(Self.alpha)
                    // Sheen: brightest at the top, where light would catch a real edge.
                    LinearGradient(colors: [.white.opacity(0.13), .white.opacity(0.04), .white.opacity(0.06)],
                                   startPoint: .top, endPoint: .bottom)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                    .strokeBorder(
                        LinearGradient(colors: [.white.opacity(0.42), .white.opacity(0.13), .white.opacity(0.20)],
                                       startPoint: .top, endPoint: .bottom),
                        lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.5), radius: 25, y: 11)
    }
}

extension View {
    /// Clear glass — see `GlassPanel` for why the alpha is what it is.
    func glassPanel(cornerRadius: CGFloat) -> some View {
        modifier(GlassPanel(cornerRadius: cornerRadius))
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
