# Temporal-claim fixture — provenance

`pr:22` and `pr:24` from `SaravananJaichandar/world-model-mcp` (MIT), fetched via
`gh pr view` on 2026-08-25 and rendered in `evals/ingest.py`'s real PR shape.

- **`pr:22`** — MERGED, "v0.12.2: influence_state + expires_at schema additions".
  Carries a literal `## Consumer wiring — deferred` section: the planning-query
  filter and expiry sweep "land in follow-up patches", following the pattern that
  "defers routing consumers to v0.12.3". Every word true when written.
- **`pr:24`** — MERGED, later-numbered, titled "v0.12.3: universal content-type
  routing consumers". The thing `pr:22` deferred to.

Together they are the shape that produced the recorded failure: a claim indexed
to a moment, cited perfectly, describing a repository that has since changed.

Unlike the fabrication fixture, this one **reproduces**: `deferred_claims` is
pure and reads only this text.

Do not regenerate against live GitHub without re-reading the test — if either
body is edited upstream, this is the record of what was true on 2026-08-25.
