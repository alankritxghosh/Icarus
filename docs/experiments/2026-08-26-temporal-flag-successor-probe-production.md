# Temporal `rests_on_deferred` flag, successor probe — production re-run

**Date:** 2026-08-26
**Repo under test:** `SaravananJaichandar/world-model-mcp` @ `5ec7fc63635b11e8375ded29f768dbcb1e9c6ac4`
**Surface:** `get_task_context` (MCP) → `POST /context`, deployed brain
**Deploy under test:** `main` @ `3976bf1` (cherry-pick of `bb836d9`), GitLab pipeline `2792069557`
**Prior run this replicates:** `docs/experiments/2026-08-25-temporal-flag-production-measurement.md`

## What changed, and it is one variable

`deferred_claims(evidence, lookup=)` may now resolve a successor retrieval did
not deliver: a bounded probe of `n+1..n+3`, fired only once a deferral is
already found. Nothing else in the pipeline changed between the two runs — same
repo, same commit, same verbatim task string, same `indexing: false` regime.

## Task string (verbatim, identical to both baselines)

> Add a new evidence_type category with its own decay window, wiring it through
> the model, the decay engine, and the retrieval consumers

## Result — the flag fired in all three trials

| | decisions | false `explicit` decision | `rests_on_deferred` | `later_merged` | unknowns | `prs` gathered |
|---|---|---|---|---|---|---|
| 08-25 T1 (flag, no probe) | 2 | present | **ABSENT** | — | 6 | `["pr:22"]` |
| 08-25 T2 | 3 | present | **ABSENT** | — | 6 | `["pr:22"]` |
| 08-25 T3 | 3 | present | **ABSENT** | — | 6 | `["pr:22"]` |
| **08-26 T1 (probe)** | 2 | present | **TRUE** | `["pr:24","pr:25"]` | 6 | `["pr:22"]` |
| **08-26 T2** | 3 | present | **TRUE** | `["pr:24","pr:25"]` | 6 | `["pr:22"]` |
| **08-26 T3** | 3 | present | **TRUE** | `["pr:24","pr:25"]` | 6 | `["pr:22"]` |

Decision count, unknowns count and gathered evidence are **unchanged**. Only the
flag moved. `prs` is still `["pr:22"]` in all three, which is the point: the
retrieval gap diagnosed on 08-25 is still there, and the probe reaches past it.

The registered prediction's success branch is met on the flag. It is **not** met
on the unknowns clause ("drops from 12") — that drop had already happened in the
prior deploy and belongs to the unknowns dedup, not to this fix. Recorded here
so the two are never merged into one claim.

The prediction named `["pr:24"]`; production returned `["pr:24","pr:25"]`. The
probe window is 23/24/25, `pr:23` is closed and correctly rejected, and both 24
and 25 merged. Broader than predicted and correct.

## What this does NOT fix

The claim is unchanged and still carries support `explicit`:

> "The retrieval consumers do not currently have wiring for the new
> influence_state and expires_at schema fields, as this was deferred to
> follow-up patches."

At `5ec7fc6` the consumers ARE wired, so the claim is still false, its citation
still resolves, and the honesty gate still passes it. The flag **annotates**; it
does not suppress or downgrade. An agent that reads only `support` still reads a
false statement as explicitly recorded.

## Defect found by this run — the probe disclosure never reaches a client

`evals/attempts.py` emits `later_merged_count` and, when the successors came
from a probe rather than from evidence, `later_merged_probed: true`. Its own
comment states why:

> a bounded probe can only ever return a small number, which would read as
> STRONG for an ancient deferral. Say where the count came from rather than let
> a window count pass as a total.

`evals/context_package.py` copies only `rests_on_deferred` and `later_merged`
into the decision entry. Both disclosure fields are dropped before any client
sees them — confirmed absent in all three trials above.

So the shipped surface does exactly what that comment forbids: `later_merged:
["pr:24","pr:25"]` is presented with no way to tell it came from a 3-wide window
rather than being the complete set of later merged work. Deterministic, not a
model behaviour, and not caught by `evals/test_temporal_claims` because that
board tests `deferred_claims` directly rather than through the context package.

Found by running the shipped path and reading the payload, not by a test.

**Fixed same day, red→green, NOT deployed.** `build_context_package` now carries
`later_merged_count` through and sets `later_merged_probed` when any contributing
deferral was probed. Where a decision rests on several deferrals the count is the
LARGEST among them (the count means "how much time passed"; the weakest
contributor is what a reader must judge by) and `probed` is ORed (a caveat true of
part of the set is true of the set). Three tests added to
`evals/test_temporal_claims.py` at the PACKAGE boundary — proven red by reverting
the fix (2 failures), green with it. Suites: evals 1006 OK, demo 664 OK; secrets
scan clean; `check_detailed_index` clean. Effect in production stays UNMEASURED
until it ships, and shipping wipes every connected corpus.

## Protocol notes

- A first trial run at `indexing: true` (semantic upgrade at 77%) was
  **discarded** rather than reported — the baseline was measured at
  `indexing: false` and that is a different retrieval regime. It fired too.
  Noted because discarding it is the rule, not a judgement call.
- The deploy wiped every connected corpus, as expected; the repo was reconnected
  and re-ingested at the same pinned commit before the trials.
