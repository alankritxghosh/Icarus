import AppKit

/// Headless renderer that writes the `IconArt` app icon to an `.iconset` folder,
/// so the bundler can turn it into a static `AppIcon.icns`. Without a baked icon
/// the Dock/Finder/DMG show a blank tile until the app launches and sets its icon
/// in code (`AppDelegate` → `NSApp.applicationIconImage`). This reuses the exact
/// same `IconArt.appIcon()` drawing, so the file icon can never drift from it.
///
/// Invoked by `scripts/bundle.sh` as: `Icarus --render-iconset <dir>` (see the
/// `Main` entry point, which intercepts this before the app UI ever launches).
enum IconExport {
    /// The `<dir>` after `--render-iconset` on the command line, else nil.
    static func iconsetDirArg() -> String? {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--render-iconset"), i + 1 < args.count else { return nil }
        return args[i + 1]
    }

    /// `--render-png <path> <pixels>` — one square PNG of the same mark, for the
    /// browser extension's `icons/` (Chrome wants real files, not a drawing).
    /// Same source as the Dock icon, so the two can never drift apart.
    static func pngArgs() -> (path: String, pixels: Int)? {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--render-png"), i + 2 < args.count,
              let px = Int(args[i + 2]), px > 0 else { return nil }
        return (args[i + 1], px)
    }

    /// Write one square PNG of `IconArt.appIcon` at `pixels`.
    static func writeIcon(to path: String, pixels: Int) {
        writePNG(IconArt.appIcon(size: CGFloat(pixels)), pixels: pixels, to: path)
    }

    /// Write every PNG `iconutil` expects into `dir` (an `.iconset` folder).
    static func writeIconset(to dir: String) {
        let fm = FileManager.default
        try? fm.createDirectory(atPath: dir, withIntermediateDirectories: true)
        // (point size, scale) — the full set macOS wants from 16pt @1x to 512pt @2x.
        let specs: [(pt: Int, scale: Int)] = [
            (16, 1), (16, 2), (32, 1), (32, 2), (128, 1),
            (128, 2), (256, 1), (256, 2), (512, 1), (512, 2),
        ]
        for spec in specs {
            let px = spec.pt * spec.scale
            let name = spec.scale == 1 ? "icon_\(spec.pt)x\(spec.pt).png"
                                       : "icon_\(spec.pt)x\(spec.pt)@2x.png"
            writePNG(IconArt.appIcon(size: CGFloat(px)), pixels: px, to: "\(dir)/\(name)")
        }
    }

    private static func writePNG(_ image: NSImage, pixels: Int, to path: String) {
        guard let rep = NSBitmapImageRep(
            bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels,
            bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
            colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0) else { return }
        rep.size = NSSize(width: pixels, height: pixels)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
        image.draw(in: NSRect(x: 0, y: 0, width: pixels, height: pixels))
        NSGraphicsContext.restoreGraphicsState()
        if let data = rep.representation(using: .png, properties: [:]) {
            try? data.write(to: URL(fileURLWithPath: path))
        }
    }
}
