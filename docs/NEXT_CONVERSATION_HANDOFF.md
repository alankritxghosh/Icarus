# Next Conversation Handoff

This file is for the next Codex or Claude session. Read this first, then read
`CLAUDE.md`, `docs/PRODUCT.md`, and `docs/PROJECT_STATE.md`.

## Product

JARVIS Engineering Intelligence is the commercial product, separate from
personal JARVIS.

The current product promise is narrow:

> Ask a local Git checkout why an engineering decision was made, and JARVIS
> answers with cited repository evidence or says it does not know.

V1 is not a coding agent. It is not doing dependency graph reasoning, impact
prediction, semantic retrieval, organization-wide ingestion, or model calls.

## Hard Boundaries

- Do not touch personal `brain/` files.
- Do not import from personal JARVIS.
- Do not scan personal memory stores.
- Do not add agents, UI, voice, Mac app, vector database, integrations, or model calls yet.
- Keep the commercial product local-first, read-only, evidence-cited, and honest.

## Current State

The safety and honesty repair is complete enough to move to the next brick.

Current verified baseline, per `docs/PROJECT_STATE.md`:

```text
196 tests pass
1 real-public-repo smoke test skipped unless its local clone is available
```

Primary verification command:

```sh
PYTHONPATH=src python3 -m unittest discover tests -v
```

## Important Recent History

There was a repeated review loop around unsupported question handling.

The original problem:

- JARVIS was answering dependency/change-impact questions even though V1 cannot support them.
- Examples: "what uses X", "what breaks if I remove X", "what is impacted by removing X".

The first Codex fixes were too reactive:

- A regex denylist was repeatedly patched.
- Claude kept finding new phrasing bypasses.
- One fix over-blocked valid retrospective decision questions like "why was X removed?"

The current accepted repair, implemented by Claude after review:

- The gate now uses normalized intent checks instead of the old brittle regex.
- It refuses common reverse-dependency and impact phrasing.
- It preserves valid retrospective decision/rationale questions.
- It is biased toward answering when there is a clear decision/rationale cue such as:
  - `why`
  - `rationale`
  - `reason`
  - `chose`
  - `chosen`
  - `decided`
  - `motivated`
- Borderline mixed questions are answered with cited evidence or honest unknown rather than refused.
- Benchmark questions now pin the gate through a consistency test.

Examples that should be refused:

- "What uses the payment service?"
- "Which modules are impacted by removing the queue?"
- "What is relying on the event bus?"
- "What modules import the queue?"
- "What breaks after removing node-fetch?"
- "Show me everything affected by dropping Node 14."

Examples that should remain supported:

- "Why does Flask use context locals?"
- "Why did the team remove Python 2 support?"
- "Why does the project redirect deleted URLs?"
- "Why did they drop support for Node 14?"
- "What is the rationale for X using Y?"

## Current Files To Know

- `src/jarvis_engineering/inspector.py`
  - Main inspection flow.
  - Question safety and unsupported-intent gate.
  - Report generation.

- `src/jarvis_engineering/evidence.py`
  - Reads committed Git blobs only.
  - Redacts common secrets in excerpts.
  - Skips gitlinks/submodules by filtering `git ls-tree` rows to blob entries.

- `src/jarvis_engineering/benchmark.py`
  - Runs benchmark scenarios.
  - Supports JSON and text scoreboard output.
  - Exits non-zero when benchmark questions fail.
  - Carries both ordinary `warnings` and promoted `safety_warnings`.

- `benchmarks/large_repos.json`
  - Large-repo scenario set.
  - Supported/unsupported labels are now part of the contract.

- `tests/test_adversarial_review_repairs.py`
  - Captures recent safety and intent-gate regressions.

- `tests/test_day2_safety.py`
  - Safety, path, unsupported-question, and public-repo smoke tests.

- `tests/test_benchmark_runner.py`
  - Benchmark schema and runner behavior.

## Current Safety Behavior

- `inspect_repository` fails closed if `protected_root` is missing.
- CLI and benchmark require `JARVIS_PROTECTED_ROOT`.
- Personal/private root protection is explicit, not inferred from package layout.
- JARVIS warns if `JARVIS_PROTECTED_ROOT` is configured inside `repositories_root`, because that usually means the protected boundary is too narrow.
- No warning does not prove the boundary is correctly scoped.

## Current Limitations

- The unsupported-question gate is still heuristic, not true code understanding.
- Secret redaction is defensive, not a replacement for a real secrets scanner.
- Evidence ranking is still lexical/deterministic.
- The system can cite nearby evidence, but it does not yet deeply understand architecture.
- Full large-repo benchmark runs are slow because each question re-inspects the checkout.
- README over-trust and lexical decision/rationale false positives are still open Day-4 evidence-quality work.

## Recommended Next Brick

Do not build voice, Mac app, UI, agents, integrations, or coding features yet.

The next best brick is evidence quality and benchmark usefulness:

1. Reduce false positives from README or generic docs.
2. Prefer ADRs/RFCs/decision records when the question asks why.
3. Improve evidence ranking for supported decision questions.
4. Keep refusal behavior stable with the benchmark consistency test.
5. Improve benchmark speed only if it does not weaken evidence quality.

## Suggested Day-4 Work Plan

Use Claude Sonnet first:

- Write adversarial tests for evidence quality.
- Focus on cases where README has many matching words but ADR has the real rationale.
- Add tests for generic documentation being over-trusted.
- Add tests for "rationale unknown" when no explicit reason exists.
- Do not edit source in the test-writing pass.

Then use Codex:

- Make the tests pass with narrow source changes.
- Keep the implementation stdlib-only.
- Do not add model calls or vector search.
- Run full suite.

Then use Claude Opus:

- Review for honesty regressions.
- Findings first.
- Verdict: GO / CHANGE / STOP.

## Standard For Future Changes

Do not make broad logic changes without tests first.

For the unsupported-question gate specifically:

- Any change must pass the benchmark consistency test.
- Add both refusal examples and supported decision examples.
- Never only test the blocked side.
- Always test against benchmark-supported questions before claiming success.

## User Preference

Alankrit does not want heavy technical command-line friction. The eventual UX should feel like:

```text
Open repo
Call JARVIS
Ask in natural language
Get cited answer or honest unknown
```

But do not jump to Mac app or voice before the evidence engine is strong.

