import AppKit

/// The Icarus mark, drawn in code (no asset pipeline): a pair of spread wings
/// rising from a downward V, on a near-black squircle. `appIcon` is the
/// Dock/application icon, `menuBarGlyph` the monochrome menu-bar template, and
/// `markGlyph` the flat mark the shell's sidebar draws.
///
/// `markPath` is the ONE definition of the mark on this platform — the Dock
/// icon, the `.icns` baked by `IconExport`, the browser-extension PNGs written
/// by `--render-png`, and `Shell/ShellComponents.swift`'s `MarkView` are all
/// this same path. The website repeats it as SVG (`site/index.html`, both the
/// header mark and the favicon), generated from these same numbers; change a
/// parameter here and regenerate that.
enum IconArt {
    private static let tile = NSColor(srgbRed: 0x16/255, green: 0x18/255, blue: 0x1D/255, alpha: 1)
    private static let blue = NSColor(srgbRed: 0x3A/255, green: 0x6F/255, blue: 0xF0/255, alpha: 1)

    // The wing, as a fan of feathers from one root. Angles are degrees above the
    // horizontal, lengths and widths in the 0…100 box; the longest feather is
    // the top one, so the fan sweeps up and out.
    private static let featherCount = 6
    private static let rootX: CGFloat = 49, rootY: CGFloat = 54
    private static let angleLow: CGFloat = -2, angleHigh: CGFloat = 34
    private static let lengthLow: CGFloat = 32, lengthHigh: CGFloat = 58
    private static let widthLow: CGFloat = 3, widthHigh: CGFloat = 5.5
    /// How far down the wing the solid leading-edge mass reaches. Without it the
    /// separated feathers read as spikes rather than a wing.
    private static let covertsReach: CGFloat = 0.75

    /// The whole mark — both wings and the V — in a 0…100 box with y measured
    /// DOWN (SVG convention), so these numbers read the same as the website's
    /// `<path d="…">`. `zoom` scales it about its optical centre.
    private static func markPath(in size: CGFloat, zoom: CGFloat) -> NSBezierPath {
        let u = size / 100
        // y is flipped once, here, so everything above can be written SVG-style.
        func p(_ x: CGFloat, _ y: CGFloat) -> NSPoint {
            NSPoint(x: (50 + (x - 50) * zoom) * u,
                    y: size - (48 + (y - 48) * zoom) * u)
        }
        /// A quadratic segment, expressed as the cubic AppKit actually draws.
        func quad(_ path: NSBezierPath, from a: NSPoint, control q: NSPoint, to b: NSPoint) {
            let c1 = NSPoint(x: a.x + 2.0 / 3 * (q.x - a.x), y: a.y + 2.0 / 3 * (q.y - a.y))
            let c2 = NSPoint(x: b.x + 2.0 / 3 * (q.x - b.x), y: b.y + 2.0 / 3 * (q.y - b.y))
            path.curve(to: b, controlPoint1: c1, controlPoint2: c2)
        }
        func tip(_ angle: CGFloat, _ length: CGFloat) -> (x: CGFloat, y: CGFloat) {
            let r = angle * .pi / 180
            return (rootX + length * cos(r), rootY - length * sin(r))
        }

        let path = NSBezierPath()
        path.windingRule = .nonZero   // mirrored halves must union, not cancel

        // Right wing: one tapered feather per step of the fan.
        for i in 0..<featherCount {
            let t = CGFloat(i) / CGFloat(featherCount - 1)
            let angle = angleLow + (angleHigh - angleLow) * t
            let length = lengthLow + (lengthHigh - lengthLow) * t
            let halfWidth = widthLow + (widthHigh - widthLow) * t
            let r = angle * .pi / 180
            let d = (x: cos(r), y: -sin(r)), perp = (x: sin(r), y: cos(r))
            let end = tip(angle, length)
            let mid = (x: rootX + 0.52 * length * d.x, y: rootY + 0.52 * length * d.y)
            path.move(to: p(rootX, rootY))
            quad(path, from: p(rootX, rootY),
                 control: p(mid.x - perp.x * halfWidth, mid.y - perp.y * halfWidth),
                 to: p(end.x, end.y))
            quad(path, from: p(end.x, end.y),
                 control: p(mid.x + perp.x * halfWidth * 0.30, mid.y + perp.y * halfWidth * 0.30),
                 to: p(rootX, rootY))
            path.close()
        }

        // The solid leading edge, filling between the top feather and mid-wing.
        let top = tip(angleHigh, lengthHigh)
        let midAngle = angleLow + (angleHigh - angleLow) * 0.45
        let midLength = lengthLow + (lengthHigh - lengthLow) * 0.45
        let inner = tip(midAngle, midLength * covertsReach)
        let bow = tip((angleHigh + midAngle) / 2, lengthHigh * 0.62)
        path.move(to: p(rootX, rootY))
        path.line(to: p(top.x, top.y))
        quad(path, from: p(top.x, top.y), control: p(bow.x, bow.y), to: p(inner.x, inner.y))
        path.close()

        // Left wing: the same path mirrored about the vertical centre line.
        let mirror = NSAffineTransform()
        mirror.translateX(by: size, yBy: 0)
        mirror.scaleX(by: -1, yBy: 1)
        path.append(mirror.transform(path))

        // The V. Two halves with a hairline gap, so it reads as a figure between
        // the wings rather than a solid wedge.
        for corners in [[p(42, 46), p(49.3, 46), p(49.3, 72)],
                        [p(58, 46), p(50.7, 46), p(50.7, 72)]] {
            path.move(to: corners[0])
            path.line(to: corners[1])
            path.line(to: corners[2])
            path.close()
        }
        return path
    }

    /// Full-colour Dock / application icon.
    static func appIcon(size: CGFloat = 512) -> NSImage {
        NSImage(size: NSSize(width: size, height: size), flipped: false) { _ in
            let inset = size * 0.06
            let rect = NSRect(x: inset, y: inset, width: size - 2 * inset, height: size - 2 * inset)
            tile.setFill()
            NSBezierPath(roundedRect: rect, xRadius: rect.width * 0.2237, yRadius: rect.width * 0.2237).fill()

            blue.setFill()
            // The mark spans the full 0…100 box; the tile is inset, so it is
            // scaled to clear the squircle rather than run off its shoulders.
            markPath(in: size, zoom: 0.82).fill()
            return true
        }
    }

    /// The flat mark on its own (no tile) — for the shell sidebar.
    static func markGlyph(size: CGFloat, color: NSColor) -> NSImage {
        NSImage(size: NSSize(width: size, height: size), flipped: false) { _ in
            color.setFill()
            markPath(in: size, zoom: 0.96).fill()
            return true
        }
    }

    /// Monochrome template glyph for the menu bar. macOS tints a template image,
    /// so this draws in black and lets the system decide light or dark.
    static func menuBarGlyph(size: CGFloat = 18) -> NSImage {
        let image = NSImage(size: NSSize(width: size, height: size), flipped: false) { _ in
            NSColor.black.setFill()
            markPath(in: size, zoom: 0.98).fill()
            return true
        }
        image.isTemplate = true
        return image
    }
}
