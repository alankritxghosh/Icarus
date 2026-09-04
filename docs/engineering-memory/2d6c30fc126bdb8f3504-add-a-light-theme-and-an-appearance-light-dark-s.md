<!-- icarus-agent-mode-decision:v1 id=2d6c30fc126bdb8f3504ea6afc526a1ec2fc350a8510ae30260fee2ed64bca17 -->

# Add a light theme and an Appearance (Light/Dark) switch to the Mac app, reversing Theme.swift's deliberate dark-only stance; drive it from one token set with a paper-and-ink light palette, exposed under a General → Appearance settings control.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Add a light theme and an Appearance (Light/Dark) switch to the Mac app, reversing Theme.swift's deliberate dark-only stance; drive it from one token set with a paper-and-ink light palette, exposed under a General → Appearance settings control.

## Confirmed rationale

Operator asked for both light and dark with a switch. This reverses Theme.swift's explicit dark-only decision, which was made precisely to avoid deciding every semantic tone twice and verifying every surface in two themes — so the real cost is that doubled palette + verification work, not the switch itself. The mockup demonstrates a proper paper-and-ink light palette (warm off-white, ink text, darker accent/green/amber for contrast) rather than a naive invert, all driven from one set of CSS tokens with a light override, which maps to tokenizing Theme.swift and adding an @AppStorage-backed appearance setting. Also produced (separately) a decision-graph prototype and the light/dark itself is the consequential atomic choice recorded here.

## Alternatives considered

- Stay dark-only per Theme.swift.
- Follow the system appearance automatically instead of an explicit in-app switch.

## Affected paths

No affected paths were recorded.

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
