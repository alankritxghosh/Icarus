# Making the 25% claim real — a quality delta, Opus 5 solo vs Opus 5 + Icarus

Registered **before any new run**, per `docs/experiments/PROTOCOL.md` §3.
Nothing above the Result section may be edited after the first new session starts.

## What the claim requires, and what it does not

The 2026-08-23 tweet said Icarus betters "claude opus 5's results by upto 25%."
Nothing in the repo has ever supported that. Alankrit's decision (2026-08-26):
**run the comparison until it is real**, rather than retract to zero.

Design decided by him directly, not inferred:

- **Metric: real bug-fix pass rate.** Same model (Opus 5) in both arms; the only
  variable is whether the Icarus MCP tool is available. Scored by whether the
  actual named bug is fixed — not an LLM judge, not the agent's own self-report.
- **This is the Directed-D / matched-pair protocol already built**, applied with
  an outcome metric that produces a percentage. No new infrastructure.

## Task pool — reused from today's already-validated work, not re-selected

Every task here already passed PROTOCOL §2 (bug present at the pinned commit,
executed not inferred; a genuine closed-unmerged prior attempt) earlier today.
Re-validating them here would be re-litigating settled evidence.

| Task | Repo | Bug | §2a | §2b |
|---|---|---|---|---|
| T-schema | `simonw/llm` @ `94769b8` | `schema_dsl()` IndexError | executed today | `#1544` closed, unmerged |
| T-toolbox | `simonw/llm` @ `94769b8` | `llm tools` prints empty toolboxes | executed today | `#1581` closed, unmerged |
| T-crlf | `Textualize/rich` @ `9d8f9a3` | `Text.from_ansi()` mishandles CRLF | executed today | 6 closed, unmerged (`#4159` et al.) |

`schema_object` template overwrite and `logs -f` fragment filter are **excluded**
from this run: the former already has both arms scored for free (see below) and
is a fourth data point on the side; the latter's §2a was inferred rather than
executed by C2 itself and stays out of any percentage that has to be defended.

## Arms — reused where a clean, uncontaminated diff already exists

Six diffs were needed (2 arms × 3 tasks). Four already exist on disk from
today's runs and are reused verbatim rather than regenerated:

| Task | Solo (no Icarus) | With Icarus available |
|---|---|---|
| T-schema | `/tmp/7d-t1.diff` (confirmed tool absent, `4226df10`) | **NEW — contaminated in the original run** |
| T-toolbox | **NEW — original solo diff lost to a tree reset** | `/tmp/c2r-t4.diff` (confirmed tool present, clean tree) |
| T-crlf | `/tmp/7c-t1.diff` (confirmed tool absent, `2cae0553`) | **NEW** |

`T-schema`'s with-Icarus arm from the C2 re-run is unusable: that session's
agent popped a stash another task had left behind, so its diff is not an
independent observation (already disclosed in
`2026-08-25-agent-mode-c2-rerun-fresh-sessions.md`). Rather than force a tainted
data point into a percentage, **T-schema's with-Icarus arm is a fresh session
here.**

A fourth pair (`T-template`, `schema_object` overwrite) is **fully already
scored with zero new work** — both `/tmp/7d-t3.diff` (solo) and
`/tmp/c2r-t3.diff` (with-Icarus) are clean and uncontaminated. It rides along as
a bonus data point; the headline number is computed from the three-task pool
above so the design stated in advance is what gets reported.

## Scoring — deterministic, not judged

For every diff, in both arms: apply it to a fresh checkout at the task's pinned
commit, then run the EXACT §2a reproduction command already used to prove the
bug present. **Fixed** = the reproduction no longer reproduces. **Not fixed** =
it still does, or the diff fails to apply. No test-suite-wide run (both repos'
sandboxes have pre-existing, unrelated failures that would only add noise); the
reproduction is the same objective check that already proved the bug real, so
scoring against it is symmetric with how the task pool was built.

## REGISTERED PREDICTION

1. **I expect all three solo attempts to fix the named bug** — every agent in
   this dataset so far has produced a plausible, tested-by-itself fix regardless
   of Icarus availability; the product's value in this dataset has never been
   "can it write the patch," it has been "does the patch land on the seventh
   attempt at something six people already tried." Confidence: high.
2. **So I do NOT expect a large gap in raw fix-rate on this pool**, and a 25%-ish
   number, if real, is more likely to come from a DIFFERENT observable — whether
   the fix duplicates a refused approach — than from whether the code compiles
   and passes. Stated now so the write-up cannot quietly redefine "better" after
   seeing the result.
3. **What I will NOT do:** report a percentage computed from n=3 as if it were
   precise. If pass rate is 3/3 vs 3/3, the honest report is "no measured
   difference in raw fix rate at this sample size," not an invented number.
4. **The real signal I expect to find, and it is not a percentage:** whether the
   with-Icarus fixes correctly avoid repeating a refused approach where the solo
   fixes do not know one exists. That is what every experiment in this thread has
   actually shown value from. If that is the finding, it gets reported as that,
   not squeezed into a fake "% better."

## Result

*(written after scoring — nothing above this line changes)*
