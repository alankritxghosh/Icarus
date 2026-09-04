<!-- icarus-agent-mode-decision:v1 id=56ffa07ce054c6e8c56c363806f7c4bf35f40ddbaea61243cca7570b3cf59227 -->

# Resolve PR #25's merge conflicts by taking the branch's side entirely, since main had stale 0.1.11 release data superseded by the branch's 0.1.12.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Resolve PR #25's merge conflicts by taking the branch's side entirely, since main had stale 0.1.11 release data superseded by the branch's 0.1.12.

## Confirmed rationale

PR #24's earlier squash-merge captured more commits than its title suggested (including a 0.1.11 release bump), so main's release.json/appcast.xml/install.sh/Icarus-Info.plist conflicted with the branch's later 0.1.12 work. Purely mechanical conflict, not a real content disagreement -- verified clean by re-running scripts/check_release.py against the real published GitHub release after resolution.

## Alternatives considered

- Manually reconcile each conflicted line instead of taking one side wholesale

## Affected paths

- `mac/Icarus/Icarus-Info.plist`
- `release.json`
- `web/public/appcast.xml`
- `web/public/install.sh`
- `web/src/generated/release.json`

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
