import AppKit

/// The Icarus "Signal Spine" mark, drawn in code (no asset pipeline): vertical
/// signal bars (center tallest/brightest), a blue citation accent, and a green
/// proof dot, on a near-black squircle. `appIcon` is the full-colour Dock icon;
/// `menuBarGlyph` is a bolder monochrome template for the menu bar.
enum IconArt {
    private static let tile = NSColor(srgbRed: 0x16/255, green: 0x18/255, blue: 0x1D/255, alpha: 1)
    private static let blue = NSColor(srgbRed: 0x3A/255, green: 0x6F/255, blue: 0xF0/255, alpha: 1)
    private static let green = NSColor(srgbRed: 0x1F/255, green: 0x7A/255, blue: 0x52/255, alpha: 1)
    private static let grays: [NSColor] = [
        NSColor(white: 0x6E/255, alpha: 1), NSColor(white: 0x9A/255, alpha: 1),
        NSColor(white: 0xC9/255, alpha: 1), NSColor(white: 1.0, alpha: 1),
        NSColor(white: 0xC9/255, alpha: 1), NSColor(white: 0x9A/255, alpha: 1),
        NSColor(white: 0x6E/255, alpha: 1),
    ]
    private static let heights: [CGFloat] = [0.13, 0.28, 0.20, 0.40, 0.22, 0.28, 0.13]

    /// Full-colour Dock / application icon.
    static func appIcon(size: CGFloat = 512) -> NSImage {
        NSImage(size: NSSize(width: size, height: size), flipped: false) { _ in
            let inset = size * 0.06
            let rect = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
            tile.setFill()
            NSBezierPath(roundedRect: rect, xRadius: rect.width * 0.2237, yRadius: rect.width * 0.2237).fill()

            let cx = size / 2, spacing = size * 0.072, barW = size * 0.045, yBase = size * 0.50
            for i in 0..<7 {
                let x = cx + CGFloat(i - 3) * spacing - barW / 2
                pill(NSRect(x: x, y: yBase, width: barW, height: heights[i] * size), grays[i])
            }
            pill(NSRect(x: cx - barW / 2, y: yBase - size * 0.105, width: barW, height: size * 0.075), blue)
            let r = size * 0.05
            green.setFill()
            NSBezierPath(ovalIn: NSRect(x: cx - r, y: size * 0.27 - r, width: 2 * r, height: 2 * r)).fill()
            return true
        }
    }

    /// Monochrome template glyph for the menu bar (bolder, simpler so it reads at ~18pt).
    static func menuBarGlyph(size: CGFloat = 18) -> NSImage {
        let image = NSImage(size: NSSize(width: size, height: size), flipped: false) { _ in
            let cx = size / 2, spacing = size * 0.17, barW = size * 0.10, yBase = size * 0.40
            let hs: [CGFloat] = [0.30, 0.50, 0.72, 0.50, 0.30]
            for i in 0..<5 {
                let x = cx + CGFloat(i - 2) * spacing - barW / 2
                pill(NSRect(x: x, y: yBase, width: barW, height: hs[i] * size), .black)
            }
            let r = size * 0.08
            NSColor.black.setFill()
            NSBezierPath(ovalIn: NSRect(x: cx - r, y: size * 0.20 - r, width: 2 * r, height: 2 * r)).fill()
            return true
        }
        image.isTemplate = true   // let macOS tint it for light/dark menu bars
        return image
    }

    private static func pill(_ r: NSRect, _ c: NSColor) {
        c.setFill()
        NSBezierPath(roundedRect: r, xRadius: r.width / 2, yRadius: r.width / 2).fill()
    }
}
