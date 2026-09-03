import SwiftUI
import Combine
import Foundation
import IcarusKit

/// Obsidian's graph view is the explicit visual reference (2026-09-04):
/// uniform nodes sized only by connection count, thin low-opacity edges, and
/// plain gray labels — no legend, no colored status coding, no chrome on the
/// canvas. Obsidian's graph follows the app's light/dark mode (white canvas in
/// light, near-black in dark), so this does too — it reads the SAME
/// `ThemeState.shared.appearance` as `Theme.*`, rather than being hardcoded
/// dark. It stays a separate palette (not `Theme.*` tokens) only because the
/// graph's grays are its own — node/edge/label values tuned for a canvas, not
/// the reused text/surface/border tokens.
@MainActor
private enum GraphPalette {
    private static var isDark: Bool { ThemeState.shared.appearance == .dark }
    static var background: Color { isDark ? Color(white: 0.09) : Color(white: 1.0) }
    static var node: Color { isDark ? Color(white: 0.82) : Color(white: 0.34) }
    static var nodeSelected: Color { isDark ? .white : .black }
    static var edge: Color { (isDark ? Color.white : Color.black).opacity(isDark ? 0.14 : 0.16) }
    static var label: Color { isDark ? Color(white: 0.6) : Color(white: 0.42) }
    /// The floating detail card over the canvas — a raised surface, so it
    /// lifts off the canvas in both modes rather than blending into it.
    static var panel: Color { isDark ? Color(white: 0.14) : Color(white: 0.98) }
    static var panelBorder: Color { (isDark ? Color.white : Color.black).opacity(0.12) }
    static var panelText: Color { isDark ? .white : Color(hex: 0x1B1B22) }
}

/// The Decision history surface, rendered as a force-directed graph — pending
/// Agent Mode candidates and confirmed decisions from the SAME
/// `DecisionInboxModel` every other Agent Mode surface already uses (no new
/// data path, no new confirm logic). An edge means two decisions share an
/// affected path. Ported from the web app's DecisionGraph.tsx (2026-09-03)
/// then restyled to match Obsidian's graph view exactly (2026-09-04) — node
/// hit-testing and dragging use real overlaid views instead of manual Canvas
/// math, and the simulation stops itself once it settles rather than
/// redrawing forever.
struct DecisionGraphView: View {
    let decisions: DecisionInboxModel
    @State private var nodes: [GraphNode] = []
    @State private var edges: [(String, String)] = []
    @State private var selectedID: String?
    @State private var pan: CGSize = .zero
    @State private var zoom: CGFloat = 1
    @State private var frame = 0
    @State private var draggingID: String?

    private let maxFrames = 240 // ~4s at 60fps — plenty to settle a few dozen nodes

    // Full-bleed: no title, no legend, no toolbar sitting on top of the
    // canvas — just the graph, matching Obsidian's graph pane exactly. This
    // surface owns the whole content pane instead of sitting inside
    // ShellView's normal card-stack ScrollView (see ShellView.swift's special
    // case for .decisionHistory).
    var body: some View {
        ZStack(alignment: .topLeading) {
            canvasArea
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            if let id = selectedID, let node = nodes.first(where: { $0.id == id }) {
                HStack {
                    Spacer()
                    detailPanel(for: node)
                        .frame(width: 360)
                        .padding(20)
                }
            }
        }
        .background(GraphPalette.background)
        .onAppear { reload() }
        .onChange(of: decisions.state) { _, _ in rebuild() }
        .onChange(of: decisions.logState) { _, _ in rebuild() }
    }

    private func reload() {
        decisions.load()
        decisions.loadLog()
    }

    @ViewBuilder
    private var canvasArea: some View {
        if isLoading {
            centeredMessage { Text("Reading decisions…").font(.system(size: 13)).foregroundStyle(GraphPalette.label) }
        } else if let failure {
            centeredMessage {
                VStack(alignment: .leading, spacing: 7) {
                    Text("COULDN'T LOAD").font(Theme.mono(11, .bold)).tracking(0.9).foregroundStyle(Theme.unknown)
                    Text(failure).font(.system(size: 13)).foregroundStyle(GraphPalette.panelText)
                }
            }
        } else if nodes.isEmpty {
            centeredMessage {
                Text("No decisions yet. When your agent proposes one, it appears here.")
                    .font(.system(size: 13)).foregroundStyle(GraphPalette.label)
            }
        } else {
            GeometryReader { geo in
                let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
                ZStack {
                    Canvas { context, _ in
                        for (a, b) in edges {
                            guard let na = nodes.first(where: { $0.id == a }),
                                  let nb = nodes.first(where: { $0.id == b }) else { continue }
                            var path = Path()
                            path.move(to: project(na.pos, center: center))
                            path.addLine(to: project(nb.pos, center: center))
                            context.stroke(path, with: .color(GraphPalette.edge), lineWidth: 1)
                        }
                    }
                    ForEach(nodes) { node in
                        nodeView(node, center: center)
                            .position(project(node.pos, center: center))
                    }
                }
                .frame(width: geo.size.width, height: geo.size.height)
                .contentShape(Rectangle())
                .gesture(
                    DragGesture()
                        .onChanged { value in
                            guard draggingID == nil else { return }
                            pan = CGSize(width: pan.width + value.translation.width - lastPanTranslation.width,
                                         height: pan.height + value.translation.height - lastPanTranslation.height)
                            lastPanTranslation = value.translation
                        }
                        .onEnded { _ in lastPanTranslation = .zero }
                )
                .gesture(
                    MagnificationGesture()
                        .onChanged { value in zoom = min(2.5, max(0.4, zoom * value / lastMagnification)); lastMagnification = value }
                        .onEnded { _ in lastMagnification = 1 }
                )
            }
            .onReceive(Timer.publish(every: 1.0 / 60.0, on: .main, in: .common).autoconnect()) { _ in
                tick()
            }
        }
    }

    /// The three non-graph states (loading/error/empty) still need to read as
    /// a page, not a stray card in a corner — centered in the full pane.
    private func centeredMessage<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        VStack {
            Spacer()
            HStack {
                Spacer()
                content()
                    .frame(maxWidth: 420)
                Spacer()
            }
            Spacer()
        }
    }

    @State private var lastPanTranslation: CGSize = .zero
    @State private var lastMagnification: CGFloat = 1
    @State private var dragStartNodePos: CGPoint?

    private func project(_ p: CGPoint, center: CGPoint) -> CGPoint {
        CGPoint(x: center.x + pan.width + p.x * zoom, y: center.y + pan.height + p.y * zoom)
    }

    private func nodeView(_ node: GraphNode, center: CGPoint) -> some View {
        let radius = (5 + CGFloat(node.degree) * 2.4) * zoom
        return Circle()
            .fill(selectedID == node.id ? GraphPalette.nodeSelected : GraphPalette.node)
            .frame(width: radius * 2, height: radius * 2)
            .overlay(alignment: .top) {
                if zoom > 0.55 {
                    Text(node.title)
                        .font(.system(size: 10))
                        .foregroundStyle(GraphPalette.label)
                        .lineLimit(1)
                        .frame(width: 100)
                        .offset(y: radius + 3)
                }
            }
            .onTapGesture { selectedID = (selectedID == node.id) ? nil : node.id }
            // highPriorityGesture so a drag starting on a node moves the node,
            // not the background pan gesture underneath it.
            .highPriorityGesture(
                DragGesture(minimumDistance: 2)
                    .onChanged { value in
                        if draggingID != node.id {
                            draggingID = node.id
                            dragStartNodePos = node.pos
                        }
                        guard let start = dragStartNodePos,
                              let idx = nodes.firstIndex(where: { $0.id == node.id }) else { return }
                        // translation is a screen-space delta since drag start;
                        // dividing by zoom converts it to graph space (pan is a
                        // pure offset, so it cancels out of a delta).
                        nodes[idx].pos = CGPoint(
                            x: start.x + value.translation.width / zoom,
                            y: start.y + value.translation.height / zoom
                        )
                        nodes[idx].vel = .zero
                    }
                    .onEnded { _ in draggingID = nil; dragStartNodePos = nil }
            )
    }

    // MARK: - Detail panel (reuses the same confirm/reject path as the inbox card)

    @ViewBuilder
    private func detailPanel(for node: GraphNode) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            switch node.kind {
            case .candidate(let c):
                Text("AGENT RECOMMENDATION · NOT PROJECT TRUTH")
                    .font(Theme.mono(11, .bold)).tracking(0.9).foregroundStyle(Theme.unknown)
                Text(c.decision).font(.system(size: 15, weight: .semibold)).foregroundStyle(GraphPalette.panelText)
                if !c.rationale.isEmpty {
                    Text(c.rationale).font(.system(size: 12)).foregroundStyle(GraphPalette.label)
                }
                if c.status == .pending {
                    HStack(spacing: 10) {
                        Button("Accept") { decisions.confirm(c, selection: .recommended) }
                            .buttonStyle(PrimaryButton())
                            .disabled(decisions.isSubmitting(c.id))
                        Button("Reject") { decisions.confirm(c, selection: .reject) }
                            .buttonStyle(.plain)
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(GraphPalette.panelText)
                            .disabled(decisions.isSubmitting(c.id))
                        if decisions.isSubmitting(c.id) { ProgressView().controlSize(.small) }
                    }
                } else {
                    Text("Status: \(c.status.rawValue)").font(Theme.mono(10)).foregroundStyle(GraphPalette.label)
                }
            case .confirmed(let d):
                switch d.status {
                case .merged:
                    Text("HUMAN-CONFIRMED · MERGED · CITED")
                        .font(Theme.mono(11, .bold)).tracking(0.9).foregroundStyle(Theme.cited)
                case .proposalNotIndexed:
                    Text("HUMAN-CONFIRMED · PROPOSAL · NOT INDEXED")
                        .font(Theme.mono(11, .bold)).tracking(0.9).foregroundStyle(Theme.accent)
                case .unrecognised:
                    Text("HUMAN-CONFIRMED")
                        .font(Theme.mono(11, .bold)).tracking(0.9).foregroundStyle(GraphPalette.label)
                }
                Text(d.decision).font(.system(size: 15, weight: .semibold)).foregroundStyle(GraphPalette.panelText)
                if !d.rationale.isEmpty {
                    Text(d.rationale).font(.system(size: 12)).foregroundStyle(GraphPalette.label)
                }
                if let url = d.citationURL {
                    Link("Cited in the repo", destination: url).font(.system(size: 12, weight: .semibold))
                } else if let url = d.pullRequestURL {
                    Link("Open review proposal", destination: url).font(.system(size: 12, weight: .semibold))
                }
            }
            if !node.affectedPaths.isEmpty {
                Text("Affects: " + node.affectedPaths.joined(separator: " · "))
                    .font(Theme.mono(10)).foregroundStyle(GraphPalette.label).lineLimit(2)
            }
        }
        .padding(16)
        .background(GraphPalette.panel)
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(GraphPalette.panelBorder, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }

    private var isLoading: Bool {
        if case .loading = decisions.state { return true }
        if case .loading = decisions.logState { return true }
        if case .idle = decisions.state { return true }
        if case .idle = decisions.logState { return true }
        return false
    }

    private var failure: String? {
        if case .failed(let m) = decisions.state { return m }
        if case .failed(let m) = decisions.logState { return m }
        return nil
    }

    // MARK: - Graph construction

    private func rebuild() {
        guard case .loaded(_, let candidates) = decisions.state,
              case .loaded(let confirmed) = decisions.logState else { return }

        var built: [GraphNode] = []
        for (i, c) in candidates.enumerated() {
            built.append(GraphNode(id: c.id, kind: .candidate(c), pos: seedPosition(i, of: candidates.count + confirmed.count)))
        }
        for (i, d) in confirmed.enumerated() {
            built.append(GraphNode(id: d.id, kind: .confirmed(d), pos: seedPosition(candidates.count + i, of: candidates.count + confirmed.count)))
        }

        var builtEdges: [(String, String)] = []
        for i in 0..<built.count {
            for j in (i + 1)..<built.count {
                let a = Set(built[i].affectedPaths), b = Set(built[j].affectedPaths)
                guard !a.isEmpty, !b.isEmpty, !a.isDisjoint(with: b) else { continue }
                builtEdges.append((built[i].id, built[j].id))
                built[i].degree += 1
                built[j].degree += 1
            }
        }

        nodes = built
        edges = builtEdges
        frame = 0
    }

    private func seedPosition(_ index: Int, of total: Int) -> CGPoint {
        // Golden-angle spiral seeding: avoids the symmetric-collapse starting
        // point a grid or pure-random scatter can settle into.
        let goldenAngle = Double.pi * (3 - 2.236) // pi * (3 - sqrt(5))
        let angle = Double(index) * goldenAngle
        let radius = 12.0 * Double(index).squareRoot()
        return CGPoint(x: radius * cos(angle), y: radius * sin(angle))
    }

    private func tick() {
        guard frame < maxFrames, !nodes.isEmpty else { return }
        frame += 1

        for i in 0..<nodes.count {
            guard nodes[i].id != draggingID else { continue }
            var fx = 0.0, fy = 0.0
            for j in 0..<nodes.count where j != i {
                let dx = nodes[i].pos.x - nodes[j].pos.x
                let dy = nodes[i].pos.y - nodes[j].pos.y
                let d2 = max(dx * dx + dy * dy, 4)
                let d = d2.squareRoot()
                let f = 2600.0 / d2
                fx += (dx / d) * f
                fy += (dy / d) * f
            }
            // Gentle center gravity so disconnected nodes don't drift off.
            fx += -nodes[i].pos.x * 0.01
            fy += -nodes[i].pos.y * 0.01
            nodes[i].vel = CGVector(dx: (nodes[i].vel.dx + fx * 0.01) * 0.82,
                                     dy: (nodes[i].vel.dy + fy * 0.01) * 0.82)
        }
        for (a, b) in edges {
            guard let ai = nodes.firstIndex(where: { $0.id == a }),
                  let bi = nodes.firstIndex(where: { $0.id == b }) else { continue }
            let dx = nodes[bi].pos.x - nodes[ai].pos.x
            let dy = nodes[bi].pos.y - nodes[ai].pos.y
            let d = max((dx * dx + dy * dy).squareRoot(), 1)
            let idealLength = 90.0
            let f = (d - idealLength) * 0.02
            let fx = (dx / d) * f, fy = (dy / d) * f
            if nodes[ai].id != draggingID { nodes[ai].vel.dx += fx * 0.01; nodes[ai].vel.dy += fy * 0.01 }
            if nodes[bi].id != draggingID { nodes[bi].vel.dx -= fx * 0.01; nodes[bi].vel.dy -= fy * 0.01 }
        }
        for i in 0..<nodes.count where nodes[i].id != draggingID {
            nodes[i].pos.x += nodes[i].vel.dx
            nodes[i].pos.y += nodes[i].vel.dy
        }
    }
}

private struct GraphNode: Identifiable {
    enum Kind {
        case candidate(DecisionCandidate)
        case confirmed(AgentDecision)
    }
    let id: String
    let kind: Kind
    var pos: CGPoint
    var vel: CGVector = .zero
    var degree: Int = 0

    var title: String {
        let text: String
        switch kind {
        case .candidate(let c): text = c.decision
        case .confirmed(let d): text = d.decision
        }
        return text.count > 40 ? String(text.prefix(37)) + "…" : text
    }

    var affectedPaths: [String] {
        switch kind {
        case .candidate(let c): return c.affectedPaths
        case .confirmed(let d): return d.affectedPaths
        }
    }
}
