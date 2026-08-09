import XCTest
import SwiftUI
import AppKit
@testable import Icarus

/// The palette's conscience.
///
/// Every other test in this app is a logic test: they all passed, unchanged,
/// while the entire interface was repainted from light to dark. They would pass
/// just as happily if a token edit left muted grey text on a near-black page at
/// 1.4:1 and made whole surfaces unreadable — the one failure mode of a palette
/// change, and the one nobody notices until a user reports it.
///
/// So this measures the thing that matters: the contrast ratio of every pairing
/// the app actually renders, against WCAG 2.1. It is deliberately about ratios
/// and not about hex values — it must keep passing when the palette is retuned,
/// and fail when a retune makes something unreadable.
final class ThemeContrastTests: XCTestCase {

    /// WCAG relative luminance (sRGB), then the standard (L1+0.05)/(L2+0.05).
    private func luminance(_ color: Color) -> Double {
        let ns = NSColor(color).usingColorSpace(.sRGB)!
        func channel(_ c: CGFloat) -> Double {
            let v = Double(c)
            return v <= 0.03928 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
        }
        return 0.2126 * channel(ns.redComponent)
             + 0.7152 * channel(ns.greenComponent)
             + 0.0722 * channel(ns.blueComponent)
    }

    private func ratio(_ a: Color, on b: Color) -> Double {
        let (la, lb) = (luminance(a), luminance(b))
        return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)
    }

    /// Body text must clear AA (4.5:1) on both the page and a raised card.
    func testBodyTextClearsAAOnEverySurface() {
        for surface in [Theme.surface, Theme.card] {
            XCTAssertGreaterThanOrEqual(ratio(Theme.ink, on: surface), 4.5,
                                        "primary text must clear WCAG AA")
        }
    }

    /// Secondary text is still text people have to read. AA-large (3:1) is the
    /// floor — below it, "muted" has become "invisible".
    func testMutedTextClearsLargeTextFloor() {
        for surface in [Theme.surface, Theme.card] {
            XCTAssertGreaterThanOrEqual(ratio(Theme.muted, on: surface), 3.0,
                                        "secondary text must stay legible, not just quiet")
        }
    }

    /// The two semantic tones carry the product's two verdicts. A washed-out
    /// amber on a dark card is a refusal the user cannot read.
    func testSemanticTonesAreLegible() {
        for tone in [Theme.cited, Theme.unknown, Theme.accent] {
            for surface in [Theme.surface, Theme.card] {
                XCTAssertGreaterThanOrEqual(ratio(tone, on: surface), 3.0,
                                           "a verdict tone must be readable on every surface")
            }
        }
    }

    /// The hairline is not text, and there is no accessibility standard for
    /// "a border you can see", so this is a TRIPWIRE, not a standard: it catches
    /// a border token edited to something indistinguishable from the surface it
    /// sits on. The bar is set just under where the website's own hairline
    /// measures (1.29:1 on the page), which is a value already shipping and
    /// visibly present — so this asserts "still a border", not "readable text".
    func testBorderIsActuallyVisible() {
        XCTAssertGreaterThanOrEqual(ratio(Theme.border, on: Theme.surface), 1.25)
        XCTAssertGreaterThanOrEqual(ratio(Theme.border, on: Theme.card), 1.10)
    }

    /// The palette is dark, and several call sites still invert against it
    /// (`LightButton`, `PrimaryButton`) on the assumption that `ink` is the
    /// bright end and `surface` the dark one. If that assumption is ever
    /// reversed, those buttons silently become dark-on-dark.
    func testInkIsBrighterThanSurface() {
        XCTAssertGreaterThan(luminance(Theme.ink), luminance(Theme.surface),
                             "inverted controls assume ink is the bright end of the palette")
    }

    /// The overlay is clear glass, so its worst case is a WHITE window behind
    /// it: the panel tint is all that separates the answer text from someone
    /// else's document. This test is why `GlassPanel.alpha` is 0.65 and not the
    /// 0.55 that was chosen by eye — that value measured 3.56:1 here and failed.
    func testAnswerTextSurvivesGlassOverAWhiteBackdrop() {
        let alpha = GlassPanel.alpha
        let backdrop = NSColor.white.usingColorSpace(.sRGB)!
        let tint = NSColor(Theme.surface).usingColorSpace(.sRGB)!
        // Source-over composite of the panel tint onto the brightest possible backdrop.
        let composited = Color(NSColor(
            srgbRed: tint.redComponent   * alpha + backdrop.redComponent   * (1 - alpha),
            green:   tint.greenComponent * alpha + backdrop.greenComponent * (1 - alpha),
            blue:    tint.blueComponent  * alpha + backdrop.blueComponent  * (1 - alpha),
            alpha: 1))
        XCTAssertGreaterThanOrEqual(ratio(Theme.ink, on: composited), 4.5,
                                    "at this alpha the overlay is unreadable over a white window")
    }
}
