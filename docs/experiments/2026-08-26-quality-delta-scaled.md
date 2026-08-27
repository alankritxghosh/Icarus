# Quality delta at scale — 20-30 tasks, for a real percentage

Registered **before task discovery begins**, per `docs/experiments/PROTOCOL.md`
§3. Nothing above the Result section may be edited once the task pool is
finalized.

## Why this run exists

`2026-08-26-quality-delta-vs-baseline.md` measured 6 of 6 raw fix rate at n=3-4
and explicitly refused to convert that into a percentage — the sample was too
small to support one honestly, and Alankrit was told so directly rather than
handed a number that didn't exist. His response: run it at real scale instead
of manufacturing a number from too few trials.

**This is the same design, same metric, same discipline — only n changes.**
Nothing about the method is different because the target got bigger; a
percentage computed from 20-30 tasks the same honest way is not the same
category of thing as one computed from 4.

## Design — unchanged from the smaller run

- **Metric: real bug-fix pass rate.** Same model (Opus 5) both arms. Only
  variable: whether the Icarus MCP tool is available.
- **Scored deterministically**: apply each diff to a clean checkout at the
  pinned commit, run the exact reproduction that proved the bug present. Fixed
  = reproduction no longer reproduces. Not fixed = it still does, or the diff
  fails to apply. No LLM judge, no self-report.
- **Every task must pass PROTOCOL §2 before use**: bug present at the pinned
  commit, EXECUTED not inferred; a genuine closed-unmerged prior attempt,
  checked via `gh pr view --json state,mergedAt`.

## Task pool — target 20-30, built incrementally and logged as found

Drawn from repositories already proven to have this shape in real numbers:
`simonw/llm` and `Textualize/rich`, both already carrying multiple genuine
closed-unmerged duplicate-fix PRs per bug in today's smaller run. Widened by
`gh` search to new issues/PRs neither repo's prior tasks have touched.

**Discovery method, mechanical and disclosed:**
1. `gh pr list --repo <repo> --state closed --search "<topic>" --json number,title,mergedAt,closedAt,author`
   across topic sweeps (error handling, CLI output, parsing, edge cases).
2. Filter to `mergedAt: null`, human-authored (not a bot), and a title
   referencing a bug rather than a feature.
3. Read the linked issue/PR body to identify the specific reproducible defect.
4. **§2a, executed**: write the smallest possible repro at the pinned commit
   and run it. Reject anything that does not reproduce.
5. **§2b, checked**: confirm the referenced PR(s) are genuinely closed-unmerged,
   not reverted-then-recommitted.

**A task is added to the pool only after passing both checks — never before.**
Rejected candidates are logged with the reason, same discipline as every prior
run in this thread, so the pool's real acceptance rate is visible rather than
hidden.

## Execution order — solo arm first, for a structural reason

The solo arm needs no Icarus tool and therefore no connected brain at all — it
can run for every task, across both repositories, **fully in parallel**, with
zero serialization. The with-Icarus arm needs the shared local brain connected
to the right repository, so those tasks are batched by repository: connect
once, run all of that repository's Icarus-arm sessions, then switch.

This ordering was decided after two near-miss setup mistakes in the smaller
run (brain switched mid-session, wrong MCP server registered) — running solo
arms first and in bulk removes the entire class of repo-mismatch risk for half
of every task, and the with-Icarus arms are grouped to minimize how many times
the brain switches at all.

Every with-Icarus session is verified, from its own transcript, to have
resolved against the correct repository before its diff is trusted — same
check as the smaller run, applied to every task rather than spot-checked.

## REGISTERED PREDICTION

1. **I expect the raw fix rate to stay high in both arms — likely 85%+ each —
   and NOT to diverge much.** Confidence: medium-high. The smaller run's 6/6
   was not a fluke of an easy pool; capable agents solve well-specified,
   reproducible bugs whether or not they have Icarus. If a real percentage gap
   exists, I expect it to be single digits to low tens, not large.
2. **I expect the Icarus-call rate across all with-Icarus sessions to land
   somewhere between the two numbers already measured this week — 1 of 4
   (25%) and 2 of 4 (50%)** — so roughly a third to a half of sessions actually
   consult it when available. This is the number that will end up mattering
   more than the fix-rate delta.
3. **What I will report as "percent better," if anything:** the fix-rate delta
   between arms, IF one exists and is large enough at this n to say so
   honestly with a real confidence interval — not a single point estimate
   dressed up as certain. If the delta is smaller than the sampling noise at
   this n, I will say that plainly rather than round it into a headline number.
4. **The finding I expect to matter more than any percentage**: among tasks
   where Icarus was actually consulted, what fraction of those fixes would
   have been a duplicate of an already-refused approach without it. That
   number, unlike a fix-rate percentage, is the one this product's whole
   premise is built on.
5. **A call is counted whatever it returns**; whether the fix succeeds is
   scored separately from whether the tool was used.
6. **This will take real wall-clock time.** Discovery + validation for
   20-30 tasks, then 40-60 agent sessions (2 arms each), is measured in hours,
   not minutes. Progress is reported as batches complete, not held until the
   end.

## Result

*(written after scoring — nothing above this line changes)*
