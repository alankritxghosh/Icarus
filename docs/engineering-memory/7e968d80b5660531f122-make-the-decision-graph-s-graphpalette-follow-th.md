<!-- icarus-agent-mode-decision:v1 id=7e968d80b5660531f122b34974258807c55dc7ba84b7f1faa6d72490a32ddcf4 -->

# Make the decision graph's GraphPalette follow the app's light/dark mode (white canvas in light, near-black in dark) instead of being hardcoded dark.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Make the decision graph's GraphPalette follow the app's light/dark mode (white canvas in light, near-black in dark) instead of being hardcoded dark.

## Confirmed rationale

Prior commit hardcoded a fixed dark palette regardless of app appearance, so the graph stayed dark even in light mode -- wrong, and Obsidian's own graph view follows its light/dark mode. GraphPalette now reads the same ThemeState.shared.appearance that Theme.* reads. It stays a separate palette (not reused Theme tokens) only because the graph's node/edge/label grays are tuned for a canvas rather than text/surface/border.

## Alternatives considered

- Reuse Theme.surface/ink/border tokens directly for the graph instead of a separate GraphPalette

## Affected paths

- `mac/Icarus/Sources/Icarus/Shell/DecisionGraphView.swift`

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
