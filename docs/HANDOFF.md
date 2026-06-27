# Engineering Handoff — JARVIS Engineering Intelligence

Last updated: 2026-06-26. Branch: `main`. Read this with `docs/PROJECT_STATE.md`,
`docs/AGENT_PROTOCOL.md`, and `CLAUDE.md`.

## 1. What this product is (one paragraph)

Commercial JARVIS Engineering Intelligence — a local-first, read-only engineering brain
over Git checkouts. V1 wedge: **documented-decision retrieval**. Ask "why was this
engineering decision made?" and get cited repository evidence or an honest unknown. It is
**not** an AI coding assistant, has no model calls, no vector DB, no server/UI, standard
library only. It must (1) answer supported retrospective decision questions with cited
evidence, (2) refuse unsupported dependency-tracing / change-impact questions, (3) protect
the personal-JARVIS workspace boundary, (4) stay honest about what it cannot know. Personal
JARVIS data under `../brain/` is strictly off-limits.

## 2. Current state (green)

- Full suite: **196 pass, 1 skipped** (the skip is a real-public-repo smoke test that needs
  a local clone under `~/jarvis_test_repos`).
- Run it:
  ```sh
  JARVIS_PROTECTED_ROOT="$(cd .. && pwd)" PYTHONPATH=src python3 -m unittest discover tests -v
  ```
  `JARVIS_PROTECTED_ROOT` is **required** — the CLI and benchmark fail closed without it.

## 3. How we got here (review → repair history)

The work over this session was a multi-round adversarial review + repair loop on two
guarantees: **privacy isolation** and **honesty (refusal contract)**. Each round a reviewer
found an issue, Codex/the implementer fixed it, the next round verified and found the next
problem. Sequence:

1. **Privacy repair.** Protected root was derived from package layout
   (`Path(__file__).parents[3]`), which silently breaks after `pip install`. Replaced with a
   required `JARVIS_PROTECTED_ROOT` env var; both `cli.py` and `benchmark.py` fail closed if
   unset. Added a warning when the protected root is a descendant of `repositories_root`
   (too-narrow boundary).
2. **Unsupported-question gate, regex era.** The gate was a growing denylist regex
   (`_UNSUPPORTED_REASONING_RE`). It leaked impact/dependency questions on natural phrasing,
   then over-corrected and refused legitimate "why was X removed/deleted/dropped?" questions
   (it broke the supported `govuk-deleted-urls` benchmark question). Multiple rounds of
   regex patching never converged — classic whack-a-mole.
3. **Gate rewrite to an intent gate.** The regex was removed and replaced with a normalized
   stem/word intent gate (`_asks_unsupported_reasoning`). Cleaner and refusal-strong, but it
   **over-refused**: it blocked the canonical supported pattern "Why does the service use an
   in-process queue?" and the supported benchmark question `flask-context-locals`
   ("What is the rationale for Flask using context locals and proxies?"). Root cause: `use`
   was in the dependency stems and the rule fired on any wh-word or graph-subject noun.
4. **Intent-gate recalibration (THIS SESSION's implementation).** Tuned the gate to favor
   answering. Details below. This is the current state.

Benchmark warnings were also split into routine `warnings` and `safety_warnings`; benchmark
text output promotes only `safety_warnings`. Gitlink/submodule entries are filtered to
blob-only in `evidence._tracked_paths` so a submodule cannot crash evidence collection.

## 4. What was implemented this session (the recalibration)

Goal: stop refusing legitimate decision questions while still refusing real
reverse-dependency / change-impact questions. **Design decision (confirmed with the user):
favor answering** — borderline mixed questions are answered with cited evidence or an honest
unknown rather than refused; reverse-"uses" handled by a narrow front-of-question check.

### `src/jarvis_engineering/inspector.py`
- Removed dead `_CONSEQUENCE_STEMS`.
- Removed `use` from `_DEPENDENCY_STEMS` (too common in decision phrasing).
- Added `_DECISION_CUES` (`why, rationale, reason, chose/choose/chosen, decided/decision,
  motivated, …`) and `_REVERSE_INTERROGATIVES = {show, what, which, who}`.
- Rewrote `_asks_unsupported_reasoning` ordering:
  1. **Hard, unconditional** impact/dependency vocabulary still refuses even with "why":
     `dependency/dependencies`, `downstream/upstream`, `ripple effect`, `blast radius`,
     `change impact`, `what will break`.
  2. **Favor-answering exemption:** if the question contains any `_DECISION_CUES` word,
     return `False` (never refused by the heuristics below).
  3. **Impact-stem rule** now requires change framing: an impact stem
     (`affect/break/fail/happen/impact/stop/updat`) must co-occur with a change stem or a
     change cue. Dropped the lone `"by"` and lone graph-subject triggers.
  4. **Impact-noun rule** (`consequence/effect/radius`) now requires a change stem; dropped
     the bare `"of"` trigger (so "consequences of choosing X" is allowed).
  5. Change↔consequence proximity windows unchanged.
  6. **Reverse-dependency**: `what/which/who` + a dependency stem
     (`call/consum/depend/import/reli`).
  7. **Narrow reverse-"uses"**: `what/which/who` + a `use` stem within the first ~4 tokens
     (catches "what uses X" / "which services use X" but not "why does X use Y" or
     "what is the rationale for X using Y").

### `tests/test_adversarial_review_repairs.py`
- Added supported-question regression tests for the previously over-refused shapes.
- Added refusal tests for who-calls and reverse-"uses".
- Added `BenchmarkGateConsistencyTests`: loads `benchmarks/large_repos.json` and asserts the
  gate agrees with each question's `supported` label (supported ⇒ not refused; unsupported
  impact ⇒ refused). The isolation-traversal question is excluded (it is blocked earlier by
  the `brain/` guard, not the reasoning gate). **This test pins the gate to the benchmark
  and would have caught the `flask-context-locals` regression.**

### `docs/PROJECT_STATE.md`
- Softened the blanket "explicitly unsupported" claim to best-effort/heuristic.
- Documented the favor-answering bias and the supported shapes ("why does X use Y?",
  "what is the rationale for X using Y?").
- Updated baseline to 196 tests.

## 5. Verification you can re-run

Gate probe (fast, no full suite):
```sh
PYTHONPATH=src python3 -c "
import json
from jarvis_engineering.inspector import _asks_unsupported_reasoning as bad
d=json.load(open('benchmarks/large_repos.json'))
for r in d['repos']:
  for q in r['questions']:
    if q['id']=='govuk-isolation-traversal': continue
    sup=q.get('supported',True); b=bad(q['question'])
    if sup and b: print('FALSE REFUSAL', q['id'])
    if (not sup) and (not b): print('LEAK', q['id'])
print('done')"
```
Expect only `done`. Then run the full suite (Section 2).

## 6. Key files

- `src/jarvis_engineering/inspector.py` — orchestration + the intent gate
  (`_asks_unsupported_reasoning`, stem sets near the top).
- `src/jarvis_engineering/evidence.py` — evidence collection, secret redaction, gitlink
  filtering (`_tracked_paths`), `_classify` for source-type/decision-record detection.
- `src/jarvis_engineering/isolation.py` — git URL validation, `resolve_target`,
  `repositories_root`/protected-root containment, read-only `run_git`.
- `src/jarvis_engineering/render.py` — one-shot human text report (`render_text_report`).
- `src/jarvis_engineering/benchmark.py` — benchmark runner, `--repo`/`--question` filters,
  `--format text|json`, `duration_seconds`, warning/safety-warning split, exit-nonzero on
  failures.
- `src/jarvis_engineering/cli.py` — CLI, repo chat, `_default_protected_root` (env-based).
- `benchmarks/large_repos.json` — 5 public repos, 31 questions. Treat as the oracle; do not
  weaken it to make code pass.
- `tests/test_adversarial_review_repairs.py` — the safety/honesty regression suite.

## 6a. Eval-loop session (output-quality grader + §7 P1 partial fix)

A later session ran the evaluation/development loop on answer honesty. See
`docs/PROJECT_STATE.md` ("Evidence-Quality And Eval Loop") for detail. Summary:

- `benchmark._evaluate_success` gained four optional `expected.*` checks:
  `confidence`, `min_keyword_hits` (activates the dead `keywords` field),
  `forbidden_evidence` (README-only guard), `max_confidence` (rationale-scoped
  confidence ceiling). Tests: `tests/test_benchmark_output_quality.py`.
- §7 P1 partially fixed in `inspector.py`: the repo-wide
  "Decision and rationale language occur near each other" `observed/high`
  finding is now suppressed when the question asks "why" and no *relevant*
  rationale matched (`rationale_unknown`), removing the honest-unknown ↔
  high-confidence contradiction. Test:
  `tests/test_rationale_confidence_honesty.py`. The lexical
  `_DECISION_RE`/`_RATIONALE_RE` over-firing in `evidence.py` (below) is still
  open — this fix addressed the *contradiction at the finding layer*, not the
  underlying lexical detector.
- One real question wired to the new checks: `govuk-color-palette-unknown` now
  has `max_confidence: low` (red → green via the source fix).
- **Two pre-existing real-repo failures are now visible** (full
  `jarvis-benchmark` = 29/31): `backstage-msw-mocking` and `govuk-node-lts`,
  both "expected documented rationale, but rationale was reported unknown" —
  the inspector under-finds rationale that genuinely exists. **This is the next
  session's lap.** Confirmed independent of this session's changes. Unit suite
  is 211 pass / 1 skip and stays green (integration tests skip without
  checkouts).

## 7. Open issues / recommended next work (Day 4: evidence quality)

These were repeatedly flagged across reviews and are **not yet addressed** — they are the
intended next brick (evidence quality), explicitly out of scope for the gate work:

- **P1 (honesty): lexical decision/rationale false positives.** `_DECISION_RE` /
  `_RATIONALE_RE` in `evidence.py` fire on very common words (`because`, `why`, `adopted`,
  `proposal`) within a 4-line window. Generic prose like "we adopted this because it's
  cleaner" registers as a documented decision+rationale. This can manufacture false
  confidence and can flip honest-unknown cases. Fix toward structural detection (ADR
  headings, `Decision:`/`Consequences:` sections), not bare keyword proximity.
  **Partial progress:** the finding-layer contradiction is fixed (see §6a); the
  lexical detector itself is unchanged.
- **Next lap (concrete):** `backstage-msw-mocking` and `govuk-node-lts` fail because
  relevant-rationale matching misses real evidence. Start by inspecting what each
  question cites vs. where the rationale actually lives in those checkouts; improve
  relevance matching without weakening the benchmark oracle.
- **P2 (honesty): README over-trust.** README is classified with the highest score (100) and
  often surfaces as the cited "relevant evidence" on a single keyword hit.
- **Secret redaction is a denylist** (`evidence.py`): config/`.env` files are collected as
  evidence and non-matching secret formats (Slack `xoxb`, SendGrid `SG.`, Google `AIza`,
  JWTs, generic high-entropy `KEY=VALUE`) can leak in excerpts. Defensive, not a scanner.

Lower priority / watch:
- The intent gate remains a heuristic. The favor-answering bias means a question that says
  "why" but is really about impact ("why does removing X break Y?") is answered with an
  honest-unknown rather than refused — intended, per the user's decision.
- Protected-root warning only detects the "descendant of `repositories_root`" shape; a
  protected root pointed somewhere unrelated still gives no warning. Documented as an
  operator responsibility.
- Full suite takes ~5 min because large-repo inspections re-run per question. A per-repo
  HEAD-pinned scan cache would speed iteration but adds invalidation state — defer until
  evidence-quality work proves it's the bottleneck. `--repo`/`--question` filters already
  make single-question iteration fast.

## 8. Workflow reminders (from CLAUDE.md / AGENT_PROTOCOL.md)

- Before changing code: read `docs/PROJECT_STATE.md`, `docs/AGENT_PROTOCOL.md`, run
  `git status --short`, and scope edits to the task.
- After changing code: run the full suite (Section 2) and report changed files, tests,
  failures, risks, next step.
- Prove gaps with failing tests before changing source behavior.
- Never read/ingest/depend on `../brain/`. Commercial repo context stays isolated.
