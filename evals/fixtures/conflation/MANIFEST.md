# Rejection-conflation fixture — provenance

`pr:23` and `pr:24` from `SaravananJaichandar/world-model-mcp` (MIT), fetched via
`gh pr view` on 2026-08-24 and rendered in `evals/ingest.py`'s real PR shape
(`PR #N: title` / `[STATE by author]` / optional `Review: <decision>` / body).

Unlike the fabrication fixture, this one **does reproduce the defect** — the
parser is pure and reads only this text, so nothing about the production corpus
is needed.

- `pr:23` — CLOSED, never merged. Auto-closed by GitHub when its base branch `#22`
  merged and was deleted. Carries no `reviewDecision`, so no `Review:` line, so
  `rejected_attempts` omits the `review` key. That omission is correct and is
  test-pinned.
- `pr:24` — MERGED. Its body states "Replaces #23 (auto-closed when its base
  branch #22 merged and was deleted)". This sentence is the whole disqualifying
  signal, and it is in indexed text.

Do not regenerate against live GitHub without re-reading the test: if either PR
is ever edited upstream, the fixture is the record of what was true on
2026-08-24, and the experiment record depends on it.
