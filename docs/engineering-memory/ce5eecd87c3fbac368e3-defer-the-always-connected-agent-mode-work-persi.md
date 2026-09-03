<!-- icarus-agent-mode-decision:v1 id=ce5eecd87c3fbac368e3bcf8ce8c2543c7900d546f17f534187533ea541a26f5 -->

# Defer the "always-connected" Agent Mode work (persist the selected repo + rebind the agent grant when the active repo changes) until after the 1 Sept launch.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Defer the "always-connected" Agent Mode work (persist the selected repo + rebind the agent grant when the active repo changes) until after the 1 Sept launch.

## Confirmed rationale

It fixes the real gap behind tonight's capture-tool deadlock (a deploy dropped the connection, the brain reset to simonw/llm, and the agent grant stayed bound to the wrong repo). But the fix modifies the per-tenant isolation / trust boundary that guarantees one tenant's agent grant cannot bind to another tenant's repo — the exact property the product sells. Changing it hours before launch with limited time for red→green isolation tests is the risky kind of change. The decisions-view was shipped instead as the safe, high-value item; the always-connected work is logged for post-launch with the isolation-test requirement.

## Alternatives considered

- Do the full always-connected fix now, including the agent-grant rebinding
- Do only the safe half now (persist + auto-reconnect the selected repo on the agent path), defer the grant rebinding

## Affected paths

- `mac/Icarus/Sources/Icarus/AgentSessionCommand.swift`
- `mac/Icarus/Sources/Icarus/McpCommand.swift`
- `demo/agent_sessions.py`
- `demo/server.py`

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
