<!-- icarus-agent-mode-decision:v1 id=fc8fa753a1fa47ea3833e99418915d02cd3b5e4f94b2e9e3ca3f0f061dc1d7aa -->

# Ship the decision-graph work as Sparkle release Icarus 0.1.12 (build 15), built from codex/launch-main-merge before it's merged into main via a PR.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Ship the decision-graph work as Sparkle release Icarus 0.1.12 (build 15), built from codex/launch-main-merge before it's merged into main via a PR.

## Confirmed rationale

Same pattern as the earlier 0.1.11 release: cut a Sparkle update directly from the working branch so users get the fix now, independent of when the branch's PR gets reviewed and merged to main. All gates passed first (315/315 tests, scripts/check_release.py clean against the real published GitHub release assets) before the appcast went live on both served domains.

## Alternatives considered

- Wait for codex/launch-main-merge's PR to merge into main before cutting a release

## Affected paths

- `mac/Icarus/Icarus-Info.plist`
- `release.json`
- `web/public/appcast.xml`
- `web/public/install.sh`

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
