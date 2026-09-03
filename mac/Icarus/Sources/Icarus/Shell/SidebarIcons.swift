import SwiftUI
import IcarusKit

/// One hairline-stroked icon per `ShellSurface`, for the collapsed sidebar
/// (`SidebarView.swift`, `NavRow`). Drawn as plain SwiftUI `Path`s in an
/// 18×18 box, matching this app's one established icon precedent
/// (`IconArt.swift`'s logo: parametric, hand-drawn geometry, never a borrowed
/// asset) rather than reaching for SF Symbols — this app has never used one.
/// Stroked, not filled, to read as structure rather than decoration, per
/// `DESIGN_VISION.md`'s "structure is visible" principle; the one exception
/// is the Start-here play triangle, which is conventionally solid.
struct SurfaceIcon: View {
    let surface: ShellSurface
    var color: Color
    var lineWidth: CGFloat = 1.6

    var body: some View {
        Group {
            switch surface {
            case .home:
                homePath.stroke(color, style: strokeStyle)
            case .startHere:
                startHerePath.fill(color)
            case .investigate:
                investigatePath.stroke(color, style: strokeStyle)
            case .decisionHistory:
                decisionHistoryPath.stroke(color, style: strokeStyle)
            case .engineeringMemory:
                engineeringMemoryPath.stroke(color, style: strokeStyle)
            }
        }
        .frame(width: 18, height: 18)
    }

    private var strokeStyle: StrokeStyle {
        StrokeStyle(lineWidth: lineWidth, lineCap: .round, lineJoin: .round)
    }

    /// A roof line over an open-topped box — the simplest unambiguous house.
    private var homePath: Path {
        Path { p in
            p.move(to: CGPoint(x: 1.5, y: 8.5))
            p.addLine(to: CGPoint(x: 9, y: 2))
            p.addLine(to: CGPoint(x: 16.5, y: 8.5))
            p.move(to: CGPoint(x: 4.5, y: 7.5))
            p.addLine(to: CGPoint(x: 4.5, y: 16))
            p.addLine(to: CGPoint(x: 13.5, y: 16))
            p.addLine(to: CGPoint(x: 13.5, y: 7.5))
        }
    }

    /// A solid play triangle — "begin" reads better filled than outlined.
    private var startHerePath: Path {
        Path { p in
            p.move(to: CGPoint(x: 4.5, y: 2.5))
            p.addLine(to: CGPoint(x: 15, y: 9))
            p.addLine(to: CGPoint(x: 4.5, y: 15.5))
            p.closeSubpath()
        }
    }

    /// A magnifying glass: a ring and a handle at the conventional angle.
    private var investigatePath: Path {
        Path { p in
            p.addEllipse(in: CGRect(x: 2, y: 2, width: 10, height: 10))
            p.move(to: CGPoint(x: 10.2, y: 10.2))
            p.addLine(to: CGPoint(x: 16, y: 16))
        }
    }

    /// A clock face with hour/minute hands -- deliberate continuity with the
    /// "◷" glyph HomeView already uses for staleness/freshness, since this
    /// surface is literally a history of past decisions over time.
    private var decisionHistoryPath: Path {
        Path { p in
            p.addEllipse(in: CGRect(x: 1.5, y: 1.5, width: 15, height: 15))
            p.move(to: CGPoint(x: 9, y: 9))
            p.addLine(to: CGPoint(x: 9, y: 4.5))
            p.move(to: CGPoint(x: 9, y: 9))
            p.addLine(to: CGPoint(x: 12.5, y: 9))
        }
    }

    /// An archive box: body, lid seam, and a small carry handle on top.
    private var engineeringMemoryPath: Path {
        Path { p in
            p.addRoundedRect(in: CGRect(x: 2.5, y: 7, width: 13, height: 9), cornerSize: CGSize(width: 1.5, height: 1.5))
            p.move(to: CGPoint(x: 2.5, y: 10.5))
            p.addLine(to: CGPoint(x: 15.5, y: 10.5))
            p.move(to: CGPoint(x: 7, y: 4))
            p.addLine(to: CGPoint(x: 11, y: 4))
        }
    }
}
