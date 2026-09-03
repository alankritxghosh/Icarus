import AppKit

/// Registers the three bundled fonts (Schibsted Grotesk, Spectral, JetBrains
/// Mono — all SIL Open Font License, `Resources/Fonts/OFL-*.txt`) so
/// `Theme.swift` can name them directly instead of falling back to the system
/// face. Uses `CTFontManagerRegisterFontsForURL` rather than Info.plist's
/// `ATSApplicationFontsPath`: SwiftPM ships resources inside a separately
/// named `.bundle` (e.g. `Icarus_Icarus.bundle`), not directly under
/// `Contents/Resources`, so a static plist path can't point at them reliably.
///
/// Fails safe: a missing or already-registered font is silently skipped, same
/// as `Theme.display`'s existing probe-and-fall-back-to-system-serif pattern
/// — a font that didn't ship must degrade quietly, never crash launch.
enum FontLoader {
    static func registerBundledFonts() {
        guard let dir = Bundle.module.url(forResource: "Fonts", withExtension: nil) else { return }
        let files = (try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? []
        for url in files where url.pathExtension.lowercased() == "ttf" {
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
    }
}
