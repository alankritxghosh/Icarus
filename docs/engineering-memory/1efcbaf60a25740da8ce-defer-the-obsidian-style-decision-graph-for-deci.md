<!-- icarus-agent-mode-decision:v1 id=1efcbaf60a25740da8ced8ff492891233ea764c4b132d857e9b05685fbe57ca6 -->

# Defer the Obsidian-style decision graph for Decision history until after launch and until there are ~15-20 confirmed decisions to visualize.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Defer the Obsidian-style decision graph for Decision history until after launch and until there are ~15-20 confirmed decisions to visualize.

## Confirmed rationale

The 2026-08-29 capture-loop decision explicitly defers the eventual graph UI until the loop's capture and accept rates are observed in real use. The loop only closed for the first time today (PR #17) with about one confirmed decision, so a graph would render as a few nodes with no edges, worse than the list. It is also from-scratch SwiftUI work, since the graph infra is in the web app not the Mac app, and is inappropriate the night before launch. When built: edges from shared affected_paths (no new data or model calls), nodes colored by status, web app first to reuse EvidenceGraph then ported.

## Alternatives considered

- Build the decision graph now in the web app reusing EvidenceGraph
- Build a minimal SwiftUI decision graph now in the surface as asked

## Affected paths

- `mac/Icarus/Sources/Icarus/Shell/ShellSurfaces.swift`
- `web/src/components/EvidenceGraph.tsx`

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
