<!-- icarus-agent-mode-decision:v1 id=2b105d447480518d831b6b47b894a7159e3ef33b2ecd3829d2634958015b23bd -->

# Do not make Agent Mode the hero of the 1 Sept Product Hunt launch; ship it labelled beta and lead with the proven cite-or-unknown retrieval product.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Do not make Agent Mode the hero of the 1 Sept Product Hunt launch; ship it labelled beta and lead with the proven cite-or-unknown retrieval product.

## Confirmed rationale

Agent Mode plumbing is deployed and green (64/64 focused tests, /agent-mode/* routes live, hooks fire this session), but the full capture->confirm->GitHub PR->re-index->projection loop has never run end to end for any real repo (no docs/engineering-memory/ exists), production storage is ephemeral so unmerged proposals evaporate on deploy, and the 2026-08-25 before/after showed it did not fire unprompted. It is not measured to improve agent output. One real end-to-end run, filmed, is the minimum bar before it can be a hero.

## Alternatives considered

- Spend 31 Aug running the Agent Mode loop for real once, then hero it
- Hero Agent Mode as-is on the strength of the deployed plumbing

## Affected paths

No affected paths were recorded.

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
