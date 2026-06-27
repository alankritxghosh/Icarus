# Project State

This file records the current state of JARVIS Engineering Intelligence so agents do not hallucinate progress.

## Current Stage

The product is at the first brick only: a read-only repository evidence collector for documented engineering decisions.

## What Works

- Accepts a public GitHub URL, explicit local checkout, repository root, and engineering question.
- Validates the checkout is inside the configured repository root.
- Pins inspection to immutable Git `HEAD`.
- Reads committed Git blobs instead of dirty working-tree files.
- Produces a JSON report with repository metadata, evidence items, findings, warnings, and errors.
- Produces a human-readable text report for terminal use, with JSON still available through `--format json`.
- Refuses missing rationale as unknown when explicit decision-and-reason evidence is not found.
- Supports a natural command layer: from inside a Git checkout, the CLI can infer the checkout, repository root, and GitHub URL from `remote.origin.url`.
- Supports repo chat mode: running `jarvis-engineering` with no question opens an interactive CLI loop for the current repo.
- Has a large-repo benchmark file covering 5 public repositories and 31 benchmark questions.
- Has a benchmark runner: `jarvis-benchmark` executes the large-repo benchmark and returns JSON-serializable pass/fail results.
- Has a benchmark scoreboard: `jarvis-benchmark --format text` prints readable totals, per-repo grouping, failure reasons, filters, and durations.
- Existing tests cover basic documented rationale, undocumented rationale, remote mismatch, root containment, dirty worktree isolation, confidence fields, and JSON serialization.

## Repaired In The Safety And Honesty Pass

- Library-level inspection now fails closed when personal-root protection is unconfigured.
- The CLI and benchmark runner now require an explicit `JARVIS_PROTECTED_ROOT` safety boundary instead of deriving one from the package layout.
- Evidence excerpts redact common committed secret formats before leaving the system.
- Inline Stripe-style `sk_live_...` and `sk_test_...` keys are redacted in prose, source strings, and bearer headers.
- Change-impact and dependency-tracing questions are unsupported in v1; the gate refuses common impact/dependency phrasings on a best-effort basis (heuristic, not exhaustive).
- Common reverse-dependency and impact phrasings such as "what uses X", "what relies on/upon X", "what is dependent on X", "what consumes X", "what calls X", "what depends on/upon X", "what is affected when X is deleted", "what is the ripple effect of removing X", and "what breaks if/when I remove X" are also rejected as unsupported.
- Impact/dependency refusal now uses normalized intent checks rather than one brittle regex. Forward-looking phrasings such as "what breaks after removing X", "what is impacted by removing X", "what is relying on X", "what modules import X", and "after removing X, what stops working?" are refused.
- Retrospective decision questions remain supported, including "why was X removed/deleted/dropped?", "why does X use Y?", and "what is the rationale for X using Y?". The gate is biased toward answering: a question containing an explicit decision/rationale cue (why, rationale, reason, chose/chosen, decided, motivated) is never refused by the impact/dependency heuristics, and reverse-"uses" tracing ("what uses X") is refused only when the use verb is governed by the leading interrogative, so "why does X use Y" is not caught. Borderline mixed questions are answered with cited evidence or an honest-unknown rather than refused. The gate is pinned to the benchmark's supported/unsupported labels by a consistency test.
- Git submodule/gitlink entries are skipped during evidence collection instead of being treated as readable blobs.
- The benchmark CLI exits non-zero when a benchmark run completes with failed questions, so CI can catch regressions.
- JARVIS warns in both one-shot and benchmark output when the configured protected root is a descendant of `repositories_root`, because that usually means the privacy boundary is too narrow. Benchmark text output promotes safety warnings separately from routine informational warnings. Absence of this warning is not proof that the boundary is correct; operators must still configure `JARVIS_PROTECTED_ROOT` as the private workspace root that must not be inspected.
- Relevant decision records with rationale are preserved even when another file has stronger lexical overlap.
- Truncated scans qualify rationale-unknown findings so "not inspected" is not confused with "absent."
- Benchmarks include unsupported impact-question coverage and match v1 behavior.

## Evidence-Quality And Eval Loop (This Session)

This session worked the evaluation/development loop on answer **honesty**, not new
capability. No model calls, no new dependencies, standard library only.

- The benchmark grader (`benchmark._evaluate_success`) gained four optional,
  backward-compatible `expected.*` assertions on top of the existing
  classification / `must_not_be_unknown` / `likely_evidence` checks:
  - `confidence` — the emitted confidence level must match.
  - `min_keyword_hits` — at least N of `expected.keywords` must appear in the
    excerpts a finding actually cites (this activates the previously-dead
    `keywords` field).
  - `forbidden_evidence` — the answer must not rest *solely* on a forbidden path
    (guards README-only citations; passes if any corroborating path is cited).
  - `max_confidence` — no rationale-bearing finding may exceed a confidence
    ceiling. Scoped to findings whose statement mentions "rationale" so it does
    not trip on the always-present `observed/high` infrastructure findings
    (HEAD resolution, evidence-collection counts).
  Covered by `tests/test_benchmark_output_quality.py` (synthetic reports).
- **§7 P1 false-confidence (partially fixed).** The inspector emitted a
  repo-wide `observed/high` finding "Decision and rationale language occur near
  each other in the cited text" whenever decision+rationale words appeared
  *anywhere* in the repo — even for a "why" question whose rationale was
  declared unknown. That produced a self-contradiction (honest-unknown verdict
  beside a high-confidence rationale claim). Fix in `inspector.py`: when the
  question asks "why" and no *relevant* rationale was matched
  (`rationale_unknown`), the repo-wide rationale finding is suppressed. The
  question-relevant rationale finding is unchanged, so documented decisions
  still answer at high confidence. Proven by
  `tests/test_rationale_confidence_honesty.py`.
- The grader's new ability is wired to exactly one real question so far:
  `govuk-color-palette-unknown` now carries `max_confidence: low`. It went
  red (proving the bug), then green after the source fix — a complete loop turn.

## Known Real-Repo Benchmark Failures (Next Session)

Running the full real-repo benchmark (`jarvis-benchmark`, all 5 checkouts) now
reports **29/31 passed, 2 failed**. Both failures are **pre-existing** evidence-
quality gaps, confirmed independent of this session's changes (reproduced with
the new gate reverted), now visible because the full real-repo run was executed:

- `backstage/backstage` / `backstage-msw-mocking`
- `alphagov/govuk-design-system` / `govuk-node-lts`

Both fail with "expected documented rationale, but rationale was reported
unknown": the rationale genuinely exists in those repos but the inspector's
relevance matching does not surface it. This is the inverse of the §7 P1 bug
(over-confidence) — here the product is under-finding real evidence. These are
the planned next lap. Do not fix by weakening the benchmark.

Note: the unit suite stays green because the real-repo integration tests skip
when checkouts are absent; these 2 failures only appear on a full
`jarvis-benchmark` run against `~/jarvis_test_repos`.

## Remaining Gaps

- Secret redaction is defensive but not a substitute for a dedicated secrets scanner.
- V1 still does not perform dependency graph tracing, change-impact prediction, organization-wide ingestion, or semantic retrieval.
- Findings are still deterministic evidence summaries, not a full reasoning layer.
- Evidence relevance matching can miss real rationale that exists in a repo (the 2 known failures above). The output-quality `expected.*` checks are built but only wired to one real question; wiring them to more real questions is unfinished.

## Current Next Brick

Improve benchmark speed. The runner and text scoreboard exist, but full large-repo runs are slow because each question re-inspects real large checkouts. The next brick should reduce repeated work without weakening local-first evidence, citations, or JSON output.

## Do Not Build Yet

- No coding agent.
- No UI.
- No organization-wide ingestion.
- No Slack, Linear, Notion, email, or GitHub API integration.
- No vector database.
- No model calls.
- No commercial use of personal JARVIS memory.

## Verification

Primary test command:

```sh
PYTHONPATH=src python3 -m unittest discover tests -v
```

Current baseline: 211 tests pass and 1 real-public-repo smoke test is skipped
unless its local clone is available (was 196 before this session's eval-loop
work added `test_benchmark_output_quality.py` and
`test_rationale_confidence_honesty.py`).

Full real-repo benchmark baseline (requires `~/jarvis_test_repos`):

```sh
JARVIS_PROTECTED_ROOT="$(cd .. && pwd)" PYTHONPATH=src python3 -m jarvis_engineering.benchmark --format text
```

Currently 29/31 pass; the 2 failures are the known evidence-quality gaps listed
above and are the next session's work.
