# Agent Mode — same task, three trials (variance floor)

**REGISTERED BEFORE RUNNING**, per PROTOCOL §3. Registered 2026-08-25.
Directed (§6): the operator makes every call. This measures OUTPUT STABILITY,
not unprompted call rate, and is not a C2 replication.

## Why

`coding-agent-memory-benchmark` (2026-08-24 study) found the baseline arm's pass
rate swinging **+41 points between two seeds on the same 17 instances**, with no
methodology change, which erased a +10.2-point headline. Its author published
the retraction.

Icarus's own evidence base has never been exposed to that test. Checked, not
assumed: `docs/experiments/` describes "three runs" and "four tasks" — those are
**different tasks, one trial each**. The single case of the SAME task repeated
(`2026-08-14-get-task-context-timeout-reproduction.md`, three replays: 52.1s /
62.0s / 50.8s) immediately found one-in-three variance that mattered.

So: how much of an Agent Mode result is the tool, and how much is the draw?

## Design

Repo `SaravananJaichandar/world-model-mcp` @ `5ec7fc6`, corpus already built
(`indexing: false`), unchanged between trials. Same question, three consecutive
calls. The ONLY varying input is the writer's sampling.

- **Primary — `get_task_context`**, the multi-model-call tool, same task string
  as the 2026-08-24 run: "Add a new evidence_type category with its own decay
  window, wiring it through the model, the decay engine, and the retrieval
  consumers."
- **Contrast — `get_change_context`**, one model call, the `delete()` question.
  Two prior trials already returned BYTE-IDENTICAL answers under two different
  retrieval regimes, so this is trial 3 of an existing pair.

Scored per trial: verdict; count and text of `decisions`; `risks`; `prs`;
`citations`; `unknowns` count. Stability is judged on the DECISION-RELEVANT
fields — what an agent would act on — not on prose wording.

## Predictions

| # | prediction | confidence |
|---|---|---|
| V1 | `get_change_context` is stable across all three trials — same verdict, same citation set | 75% |
| V2 | `get_task_context` is NOT stable: at least one `decisions` entry appears in some trials and not others | 70% |
| V3 | `risks` is `[]` in all three (the `pr:23` selection miss is durable, and now correctly so after the successor fix) | 85% |
| V4 | `unknowns` count varies by ≥3 between the lowest and highest trial | 60% |
| V5 | No trial bluffs: every emitted citation resolves | 90% |

**V2 is the one that matters.** If the structured field an agent is told to read
before starting work is unstable across identical calls, then any single-trial
claim about `get_task_context` — including mine from 2026-08-24 — is worth less
than it reads.

## What this does NOT do

It does not run SWE-bench, and Icarus is not a candidate for that benchmark: at a
task's pinned base commit the fixing PR does not exist, so the evidence Icarus
reads is what the benchmark holds out. This measures Icarus's own variance on its
own axis, which is the transferable lesson from that study.

---

# RESULTS

Run 2026-08-25. Corpus unchanged, `indexing: false` on every call, commit
`5ec7fc6` reported by all. The 2026-08-24 re-run is included as a fourth data
point since it was the same tool, question and corpus state.

## `get_task_context` — four trials

| trial | decisions | FALSE decision present? | unknowns | citations |
|---|---|---|---|---|
| 08-24 (semantic re-run) | 2 — decay module; constants not centrally configurable | **no** | 19 | 4 |
| 08-25 T1 | 2 — decay module; **consumers not wired** | **YES** | 12 | 5 |
| 08-25 T2 | 3 — decay module; schema has `evidence_type`; **consumers not wired** | **YES** | 12 | 4 |
| 08-25 T3 | 3 — identical to T2 | **YES** | 12 | 4 |

The false decision is *"The retrieval consumers do **not currently** have wiring
for the new `influence_state` and `expires_at` schema fields"* — support
`explicit`, cited `pr:22`. At `5ec7fc6` the consumers ARE wired
(`knowledge_graph.py:927/940/960`, plus `server.py`, `models.py`, `tools.py`,
`hermes_memory_provider/`).

## This REFUTES the 2026-08-24 conclusion

That record states C1 was "FIXED — and by retrieval, not by the gate", and built
its headline on it:

> "Both doc-contamination defects were RETRIEVAL artifacts of the lexical-only
> window. Neither was a writer defect."

**That is wrong, and this is the correction.** The comparison was ONE lexical
trial against ONE semantic trial. The false decision appears in **3 of 4** trials
at `indexing: false`. Its absence on 08-24 was the outlier — a single lucky draw,
attributed to a mechanism.

I made the exact error the benchmark study was written about: a one-trial
difference read as a fix. Saravanan's +10.2 points came from an unlucky baseline
draw; my "retrieval fixed it" came from a lucky one. Same mistake, same day I
wrote it up as his lesson.

**What survives from 08-24:** the null-arm README contamination did also vanish
under semantic retrieval — but that is now a ONE-TRIAL observation with no
replication, and must be labelled as such rather than as a mechanism.

**What is now unsupported:** the clean "retrieval defects vs writer defects"
split. Retrieval quality may still matter; this run cannot show it, because
sampling alone reproduces the whole effect.

## `get_change_context` — three trials, perfectly stable

Byte-identical answer, citations and claim labels on all three, across two
retrieval regimes. **The `signed events` migration is now 3/3 deterministic.**

The contrast is the finding: the one-model-call tool is stable; the
multi-model-call tool is not.

## Predictions vs. outcome

| # | prediction | outcome |
|---|---|---|
| V1 | `get_change_context` stable across three trials | **HIT** — byte-identical |
| V2 | `get_task_context` NOT stable; a decision appears in some trials and not others | **HIT** — 2 vs 3 decisions, different membership, and a FALSE one in 3 of 4 |
| V3 | `risks: []` in all three | **HIT** |
| V4 | `unknowns` varies by ≥3 across the three trials | **MISS** — 12 / 12 / 12. Variance was 0 *within* the registered run; the 19 was a different day |
| V5 | no trial bluffs — every citation resolves | **HIT** — and that is the point: the false decision cites `pr:22`, which resolves perfectly |

V4 is recorded as a miss rather than quietly rescored against the 08-24 run,
which is what "varies by ≥3" would have needed to be written as in advance.

## Caveat that bounds all of this

**The deployed brain does not have yesterday's dedup fix.** These calls hit Azure;
`_restates_a_known_unknown` is committed locally on
`experiment/agent-mode-matched-pair` and never deployed. So the unknowns counts
here are PRE-fix, and this run says nothing about whether that fix works in
production.

# What this changes

1. **Single-trial Agent Mode results are not evidence about the tool.** Not the
   08-24 run, not C2's 4/4, not Experiment D's flips. They are evidence about one
   draw. Where a claim rests on one trial, the write-up has to say so.
2. **`get_task_context` needs a stability gate before it is sold as
   pre-implementation context.** An agent told to call it before starting work
   receives a different `decisions` list run to run, and in 3 of 4 draws one of
   them is false at HEAD.
3. **The honest headline for this feature is the stable half.** `get_change_context`
   is byte-stable; the deterministic fields (`rejected_attempts`, `unlanded_prs`,
   citation resolution) cannot vary at all. Those are claimable. Anything derived
   from a multi-call investigation is not, at n=1.
