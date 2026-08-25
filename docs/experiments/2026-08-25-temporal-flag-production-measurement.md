# Temporal `rests_on_deferred` flag — production before/after

**Date:** 2026-08-25
**Repo under test:** `SaravananJaichandar/world-model-mcp` @ `5ec7fc63635b11e8375ded29f768dbcb1e9c6ac4`
**Surface:** `get_task_context` (MCP) → `POST /context`, deployed brain
**Deploy under test:** `main` @ `fba65912`, GitLab pipeline `2786799746`

## Registered prediction

Registered before the run, in the vault's Work Queue § 0 (written 2026-08-25,
pre-deploy), verbatim:

> **What "it worked" looks like:** that decision now carries `rests_on_deferred:
> true` and `later_merged: ["pr:24"]`, and the unknowns count drops from 12.
> **What "it did not" looks like:** the decision reappears unflagged.

## Task string (verbatim, identical to baseline)

> Add a new evidence_type category with its own decay window, wiring it through
> the model, the decay engine, and the retrieval consumers

## Result

**The decision reappeared unflagged in all three trials. The prediction's
failure branch is what happened.**

| | decisions | false `explicit` decision | `rests_on_deferred` | unknowns | `prs` gathered |
|---|---|---|---|---|---|
| 08-24 (pre) | 2 | absent | n/a | 19 | — |
| T1 (pre) | 2 | **present** | n/a | 12 | — |
| T2 (pre) | 3 | **present** | n/a | 12 | — |
| T3 (pre) | 3 | **present** | n/a | 12 | — |
| **T1 (post)** | 2 | **present** | **ABSENT** | **6** | `["pr:22"]` |
| **T2 (post)** | 3 | **present** | **ABSENT** | **6** | `["pr:22"]` |
| **T3 (post)** | 3 | **present** | **ABSENT** | **6** | `["pr:22"]` |

The claim, unchanged from the baseline and still at support `explicit`:

> "The retrieval consumers do not currently have wiring for the new
> influence_state and expires_at schema fields, as this was deferred to
> follow-up patches."

At `5ec7fc6` the consumers ARE wired. The claim is false, its citation
(`pr:22`) resolves perfectly, and the honesty gate passes it — exactly as
before the deploy.

## Why it did not fire — root cause, not symptom

`evals/attempts.deferred_claims` reports a deferral **only when the evidence
also holds a later-numbered MERGED pull request** (`merged_later`, built by
scanning the evidence dict). That conservatism is deliberate and documented.

In all three trials the investigation gathered **`prs: ["pr:22"]` and nothing
else.** `pr:24` was never in evidence, so `merged_later` was empty, so
`later` was empty, so nothing was reported. **The precondition was never met at
runtime.**

Two checks separate a logic bug from a retrieval gap, and both were run:

1. `python3 -m unittest evals.test_temporal_claims` — **16/16 OK.** The logic is
   correct against its fixture board. This is not a regression.
2. `get_change_context("What did PR 24 change, and was it merged?")` — `pr:24`
   returns **anchored, rank 1**, `[MERGED by SaravananJaichandar]`, body opening
   *"Replaces #23 (auto-closed when its base branch #22 merged and was
   deleted)."* **The corpus holds everything the flag needs.**

So: the evidence is ingested and reachable. It was not *retrieved* for this
task. **This is a retrieval gap, not a logic gap.**

## What this is an instance of

The already-measured intent/identifier axis in
`evals/test_description_recall.py`: `identifier` and `task` phrasings rank the
gold ref 1st; `intent` phrasing MISSES.

The sharp version here: `pr:24` is titled *"v0.12.3: universal content-type
routing **consumers**"*, and the task string ends *"...and the retrieval
**consumers**"*. The shared vocabulary did not produce retrieval. The same ref
comes back rank 1 the moment a question names it by number.

**This is a second, independent live case for that board, and a harder one** —
the previous cases were about answering a question. This one is about a
deterministic downstream guard silently not firing because its input never
arrived. A guard whose precondition depends on retrieval inherits retrieval's
recall as its own ceiling, and nothing reports when that ceiling binds.

## What must not be claimed

- **Do not claim the temporal check fixes this class in production.** It is
  deployed, healthy, unit-green, and has never fired on the case it was built
  for. Effect in production remains **unmeasured**, now with three trials of
  evidence that the path is not reached.
- Do not cite the unknowns drop (12 → 6) as the flag working. It is a real,
  reproducible improvement across all three trials and it comes from the
  unknowns dedup (`_restates_a_known_unknown`), which shipped in the same
  deploy. Two changes, one deploy; only this one moved.

## Honest positives from the run

- **Unknowns 12 → 6, stable across all three trials.** The dedup works in
  production.
- **Stability improved.** Pre-deploy the decision count varied 2/3/3 with
  differing text; post-deploy T2 and T3 are identical and T1 differs only by
  omitting one decision. Not measured rigorously here — noted, not claimed.
- **No regression.** Nothing got worse, nothing bluffed, and the `pr:23`
  successor check correctly kept `risks: []` (no false "tried and refused").

## Fix, built the same day

The second option was taken: `deferred_claims` can now resolve a successor it
was not handed. `deferred_claims(evidence, lookup=None)` — with no `lookup` the
behaviour is byte-identical, so nothing else re-baselines.

- Probes only pull-request numbers `n+1 … n+3` (`_SUCCESSOR_PROBE`), and only
  when a deferral has ALREADY been found in that ref's text, so a repository of
  ordinary pull requests costs zero fetches.
- A successor in evidence WINS and is never probed — stronger and free.
- `_merged_pr_number` checks the text says both `PR #N:` (an ISSUE at that
  number is not a landing) and `[MERGED ` (OPEN and CLOSED did not land).
- A raising or failing fetch falls back to today's behaviour — no successor —
  never an exception into a request.
- **`later_merged_probed: true` marks a probed result.** `later_merged_count`
  means "how much time passed": 1 says the resolver is probably named, 154 says
  ancient. A bounded probe can only ever return a small number, which would read
  as STRONG for an ancient deferral. The key says the count came from a window
  rather than letting it pass as a total. Absent when the successors came from
  evidence.

`demo/server.py`'s `/context` supplies the lookup from `fetch_ref_detail` with
the caller's own token.

### Verified

- `evals.test_temporal_claims` — **28 tests OK**, 12 new. The RED half is
  pinned: `test_RED_without_a_lookup_the_production_defect_reproduces` asserts
  the unflagged decision this run measured, so if it ever passes on its own the
  record is stale. The GREEN half uses the REAL fixture text for both pull
  requests, not a hand-made one.
- Full suites: **evals 1009 OK, demo 668 OK.**
- **Live against the real repository**, production shape (`pr:22` alone in
  evidence), probing through the real `fetch_ref_detail`:

  ```
  probed numbers : [23, 24, 25]
  later_merged   : ["pr:24", "pr:25"]
  later_merged_probed: true
  ```

  `pr:23` is probed and correctly rejected (closed, never merged). The flag now
  fires on the exact case it was built for.

### Disclosed cost and remaining ceiling

Three live `gh` calls per deferral, sequential, on a route that already takes
~55s. Deferrals fire on 0.6% of PR chunks in the committed corpus, so this is
a few seconds on a small fraction of calls.

**This does NOT fix intent-phrasing recall.** `pr:24` still is not retrieved for
this task; the flag now works around that rather than through it. The recall
gap stays open, and every OTHER evidence-derived guard still inherits it — see
the Unknowns entry opened by this run. **Effect in production remains
unmeasured until this is deployed and re-run**; the deploy is held because the
Show HN is the same evening and a revision wipes every connected corpus.
