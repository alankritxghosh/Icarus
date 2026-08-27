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
| T-toolbox | `/tmp/7d-t3.diff` (confirmed tool absent, `694c6ef8`) | `/tmp/c2r-t4.diff` (confirmed tool present, clean tree) |
| T-crlf | `/tmp/7c-t1.diff` (confirmed tool absent, `2cae0553`) | **NEW** |

**Correction, found while applying these before scoring:** the original file
labels above (written before this doc was committed) had T-toolbox's solo diff
listed as "lost to a tree reset." It was not — `/tmp/7d-t3.diff` is T-toolbox's
solo diff, verified by its content (`llm/cli.py:2774`, the `tools_list`
function), not `/tmp/7d-t4.diff` which never existed. **T-toolbox is a complete
free pair, same as T-template** — only T-schema and T-crlf need a new
with-Icarus session. Scope is unchanged from the registered prediction (2 new
sessions); only which files map to which task was wrong, caught before any
diff was misapplied to the wrong task.

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

## Scoring in progress — logged as it happens

**T-toolbox — both arms FIXED.** Applied cleanly to both a solo checkout
(`/tmp/7d-t3.diff`) and an icarus-available checkout (`/tmp/c2r-t4.diff`).
`llm/cli.py`'s `for toolbox in toolbox_objects:` loop now checks
`method_tools()` before printing the bare `name + ":\n"` heading in both — the
solo fix prints an explanatory line, the icarus fix a differently-worded one;
both correctly stop an empty toolbox printing a heading with nothing under it.

**T-template (bonus pair) — both arms FIXED.** Both diffs add `and not schema`
to `if template_obj.schema_object:` at `llm/cli.py:742` — the exact one-token
fix, byte-identical logic in both arms.

**Setup mistake caught before it corrupted a result.** Launching T-schema's
icarus arm, the user-scope `icarus` MCP server was still pointed at the
PRODUCTION Mac app (restored after the C2 re-run) rather than the local
dev brain — so the session was talking to production, connected to
`world-model-mcp`, not the local `simonw/llm`. Its one Icarus call is visible in
the transcript resolving against the wrong repo (`"connected to
SaravananJaichandar/world-model-mcp"`). **Stopped and discarded before scoring
it as a result.** Re-verified end to end afterward — a fresh scratch probe
confirms the local brain, correct repo, real citations — before either
remaining session launched.

**T-crlf — both arms FIXED.** Solo (`/tmp/7c-t1.diff`) and icarus
(`/tmp/qd-crlf-icarus.diff`, a fresh session run after catching two setup
mistakes below) both make `Text.from_ansi('line one\r\nline two\r\n').plain`
return `'line one\nline two\n'` instead of the bug's `'\n\n'`.

**T-schema — both arms FIXED.** Solo (`/tmp/7d-t1.diff`) and icarus
(`/tmp/qd-schema-icarus.diff`, also a fresh session after the same setup
mistake) both turn `schema_dsl("name, : int")`'s `IndexError` into a clean
`ValueError`.

## Two more setup mistakes caught before they corrupted a result

Both while launching the T-crlf icarus session:

1. **A stale project `.mcp.json` in `/Users/alankritghosh/JARVIS /experiment-7b-rich`**
   still pointed at the live working tree (carrying today's uncommitted tool-
   description rewrite) rather than the clean worktree, and shadowed the fixed
   user-scope registration exactly like the original 7b/7c/7d defect. Session
   `60ac0239` shows `TOOL NOT AVAILABLE`. Removed; re-verified with a direct
   probe (byte-identical repo confirmation) before relaunching.
2. **The brain was switched to `simonw/llm` while T-crlf was still running**
   against `Textualize/rich`, racing a same-repo requirement the tool enforces.
   Caught by reading the live transcript before the agent had made its call
   (it hadn't), reverted immediately, and the two remaining runs were serialized
   one repo-connect at a time rather than run in parallel.

Every diff scored above comes from a session independently verified, by reading
its own transcript, to have resolved against the correct repository before
being trusted.

## Result

**Raw fix rate: 6 of 6, both arms — no measured difference.** Per prediction
§1/§3: this is reported as "no measured difference in raw fix rate at this
sample size," not as a percentage. Six for six is not evidence Icarus makes no
difference; it is evidence that on this small, deliberately-easy-to-fix task
pool, a capable agent solves the *stated* bug whether or not it has the tool.

**The real signal, exactly as predicted in §4: whether the tool was actually
called, not whether it was available.** Of the four icarus-available sessions
across the three headline tasks plus the bonus pair, **two called Icarus, two
did not**:

| Task | Icarus called? | What changed |
|---|---|---|
| T-schema | **Yes** | Reported PRs #1467, #1469, #1487, #1544 closed unmerged and #1471/#1546 still open — **six prior submissions of this exact fix, never merged** — and named the fork in approach (raise vs. silently skip) with no maintainer decision recorded. Ended: *"you'd be filing a seventh duplicate."* |
| T-crlf | **Yes** | Reported #4099/#4103/#4113/#4138/#4145/#4159 closed unmerged and #4091 still open — **seven prior attempts** — and noted several of the rejected ones broke CR-overwrite semantics the same way a naive fix would, which is why this fix deliberately avoided that pattern. |
| T-toolbox | No | Fixed the bug with no visibility into `#1581`, identical blind spot to the solo arm. |
| T-template | No | Same — fixed correctly, zero awareness of any prior attempt. |

**When Icarus was consulted, the deliverable is materially different even
though the code passes the same check either way**: the agent knows it may be
submitting a sixth or seventh duplicate, names the specific unresolved design
disagreement, and in T-crlf's case avoids a failure mode multiple rejected PRs
shared. **When it was available but not called, having it made no difference
at all** — consistent with the ~1-in-4 call rate measured across today's larger
runs; this small sample landed at 2 of 4.

## What this means for the public claim

**No percentage replaces the 25% claim, because none would be honest at this
sample size and this metric never produced a percentage in the first place —
raw pass rate was identical.** What replaces it is a true, checkable sentence:

> Given the Icarus tool, an agent fixing a real bug correctly identified it as
> the sixth or seventh submission of the same fix — including two rejected
> approaches worth avoiding — in two independent trials. Without it, the agent
> had no way to know.

That is the actual, defensible value this dataset supports. It is not a
percentage and it should not be forced into one.

## Disclosed limits

- **n=3 headline tasks (4 including the bonus pair), one repo pool measured
  twice.** Not enough to estimate a call rate precisely; today's larger C2-rerun
  (n=4, independent tasks) already measured 1 of 4, and this run's 2 of 4 is
  consistent with that inside such small samples, not a contradiction.
- **The solo arm cannot receive a call it has no tool to make** — its lack of
  prior-attempt awareness is not a measured behaviour, it is the arm's defining
  condition. What is measured is that the WITH-icarus arm's advantage depends
  entirely on the call happening, which today's other runs already established
  fires roughly 1 in 4 times unprompted.
- **Every task here was chosen because it already had a genuine refused prior
  attempt** (that is what made it usable in earlier PROTOCOL-§2 validation).
  This dataset cannot speak to a bug with no prior history — Icarus would have
  nothing to surface either way.
