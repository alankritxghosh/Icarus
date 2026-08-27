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

## Discovery — closed at n=17, logged honestly rather than padded to 20

Target was 20-30. Discovery found **17 valid tasks** before the acceptance
rate on remaining candidates dropped enough that forcing more in would mean
weaker validation, not a bigger honest number. Reported as 17, not stretched.

**4 already scored, both arms, from the smaller run** (T-schema, T-toolbox,
T-crlf, T-template) — reused rather than re-run.

**13 new, §2a executed today:**

| Task | Repo | Bug | Validation |
|---|---|---|---|
| T-keys | `llm` | `load_keys()` crashes on empty/malformed `keys.json` | Executed: `JSONDecodeError` on empty file |
| T-dedupe | `llm` | `schema_dsl()` puts duplicate field names in `required` twice | Executed: `required=['name','name']` |
| T-jsonschema-types | `llm` | `schema_dsl()` doesn't map full JSON Schema type names (`integer`, `boolean`...) | Executed: `"age integer"` → type `string`, wrong |
| T-fenced-code | `llm` | `extract_fenced_code_block` misses a language tag with non-word chars (e.g. `c++`) | Executed: returns `None` for a real fenced block |
| T-mimetype | `llm` | `mimetype_from_path` returns `''` instead of `None` when detection fails | Executed with a faked empty-string return |
| T-braced-vars | `llm` | `Template.extract_vars` only reads the `named` regex group, drops `${braced}` vars | Executed: `string.Template`'s own match groups confirm `braced` is a separate, ignored group |
| T-nonascii-keys | `llm` | `llm keys set` accepts non-ASCII values with no upfront rejection | Read: no ASCII guard exists in `keys_set` |
| T-noBreakSpace | `rich` | Word-wrap regex treats U+00A0 (no-break space) as a break point | Executed: `words('hello\xa0world')` splits at the NBSP |
| T-deadweakref | `rich` | `rich_cast` raises uncaught `ReferenceError` on a dead `weakref.proxy` | Executed: `rich_cast(dead_proxy)` raises |
| T-elapsed | `rich` | `stop_task()` then `reset(start=True)` leaves a stale `stop_time`, producing negative/frozen elapsed | Executed with a fake clock: elapsed = -10.0 |
| T-consoleinput-end | `rich` | `Console.input()` hardcodes `end=""`, ignoring a custom `end` on the prompt `Text` | Read: `self.print(prompt, ..., end="")` is unconditional |
| T-notes-leak | `rich` | `__notes__` captured once, applied to every stack in a chained-exception traceback | Read: one `notes` variable reused at two separate stack-construction sites |
| T-forcecolor | `rich` | `FORCE_COLOR` alone makes `is_terminal` return `True` even for a non-interactive stream | Executed: `Console(file=StringIO())` with `FORCE_COLOR=1` reports `is_terminal=True` |

**§2b, all 13**: closed, `mergedAt: null`, human-authored, checked via
`gh pr view --json state,mergedAt`.

## Rejected during discovery, and why — logged per PROTOCOL discipline

- **`_guess_lexer`'s `str.index()` bug (rich #4009)** — the described function
  name/pattern doesn't exist in this file at the pinned commit at all; the code
  has been refactored past whatever version the PR was written against.
- **`console.print()` ignoring `end` on empty args (rich #3983)** — tested
  directly against the pinned commit: `c.print(end='!')` already outputs `'!'`
  correctly. The bug is already fixed here by different code.
- **`split_graphemes` infinite loop on ANSI escapes (rich #4002)** — the
  linked issue says the regression is specific to Rich 14.3.2; tested with a
  3-second alarm-based timeout against the actual reported input
  (`'\x1b[31mred\x1b[0m'`), and it completes normally at this pinned commit.
- **The tool-call-argument-parsing family (llm #1130, #1164, #1170)** — all
  three describe a simpler direct-concatenation bug; the actual code at this
  commit is a substantially different event-based streaming aggregator
  (`args_str = "".join(e.chunk for e in evs if e.type == "tool_call_args")`)
  that already guards the empty/falsy case. Set aside as too ambiguous to
  validate quickly rather than forced in.
- **`embed-multi`'s masked ValueError (llm #1578) and the attachment-integrity
  crash (llm #1366)** — both need real database/migration state to reproduce
  cleanly; deprioritized for time rather than rejected outright. Candidates for
  a future batch if the pool needs to grow past 17.

## Execution — solo arms launching now, in parallel, no brain required

## Disclosed: the "solo" arm was not actually tool-free

All 13 solo-arm sessions show `TOOL AVAILABLE` under the new check —
`mcp__icarus__` appears in each transcript's tool catalogue. Root cause: the
user-scope `icarus` MCP server (pointed at production, restored after the
smaller run) loads by default in any session with no project-level override,
which none of these 13 clones had.

**Zero of the 13 sessions made an actual call.** So behaviourally these are
still valid observations of "an agent that did not consult Icarus," and the
fix-rate scoring below is unaffected by this — a call that never happened
can't have changed the diff. What is NOT valid: citing these 13 as "0 of 13,
tool unavailable" for any pooled call-rate statistic across this run, since the
tool was in fact reachable (against production, which was connected to an
unrelated repository — any attempted call would have refused on repo mismatch,
which may be part of why none fired, though that can't be established either
way from a call that didn't happen).

Fixed for the with-Icarus arm, which must be right: same swap-and-verify
procedure as the smaller run (remove production registration, point user-scope
`icarus` at the local dev brain, confirm a real call resolves against the
correct repo before trusting anything).

## All 13 solo-arm sessions VOID — a systemic setup failure, caught before scoring

None of the 13 clones had `.claude/settings.local.json` with
`defaultMode: bypassPermissions`. Headless `claude -p` cannot show an edit
approval prompt, so every session that tried to write a fix was silently
blocked and fell back to describing the fix in prose without ever touching
disk. Confirmed across all 13: every diff is 0 lines.

This is not a partial result to salvage — a "not fixed" verdict from a session
that was never allowed to write is not a measurement of anything. All 13 are
discarded in full. The missing config has been added to all 13 clones and
every task is being re-run from a clean checkout.

Caught by checking every diff before scoring the first one, rather than
scoring T-keys' empty result and moving on — the same discipline that found
the wrong-repo and stale-`.mcp.json` mistakes in the smaller run.

## The re-run's own unplanned finding: 4 of 13 reached for it anyway

All 13 re-run sessions held the (production, wrong-repo) Icarus tool by the
same inheritance as before. This time **4 of 13 (31%) called it unprompted**
— T-keys, T-mimetype, T-nonascii, T-inputend — each with a real, on-topic
question ("has this been proposed or rejected before", "why does this
function return X directly"). Every call was correctly refused on repo
mismatch (`"Icarus is connected to SaravananJaichandar/world-model-mcp, not
simonw/llm"`), so no information reached any diff and the fix-rate scoring
below is unaffected.

This is disclosed as its own data point, separate from the scaled run's
primary metric: a call rate observed with NO deliberate task design behind it
(these were meant to be pure solo baselines), on a tool pointed at a repo with
nothing to do with the task, landed at 31% — inside the range this week's
other measurements already found (25%, 50%). Not proof of anything on its own;
one more observation in the same neighborhood.

## Solo-arm result: 13 of 13 fixed the named bug

Every one of the 13 new tasks scored deterministically against its executed
reproduction:

| Task | Verdict | Check |
|---|---|---|
| T-keys | Fixed | `load_keys()` on an empty file returns `{}` instead of raising |
| T-dedupe | Fixed | `required` no longer contains the duplicate |
| T-jsonschema-types | Fixed | `"age integer"` now maps to type `integer` |
| T-fenced-code | Fixed | `c++`-tagged block extracts correctly |
| T-mimetype | Fixed | Returns `None`, not `''` |
| T-braced-vars | Fixed | `${braced}` now appears in `extract_vars()`'s output |
| T-nonascii-keys | Fixed | Real `validate_key_value` guard added, with its own test |
| T-noBreakSpace | Fixed | `'hello\xa0world'` no longer splits at the NBSP |
| T-deadweakref | Fixed | `rich_cast` on a dead proxy no longer raises |
| T-elapsed | Fixed | Elapsed after stop→reset is `5.0`, not negative |
| T-consoleinput-end | Fixed | A `Text` prompt's own `end` is now respected |
| T-notes-leak | Fixed | `__notes__` now appears on exactly one stack in the chain |
| T-forcecolor | Fixed | `is_terminal` correctly `False` for a non-interactive stream under `FORCE_COLOR` |

**13 of 13, combined with the 4 already-scored solo diffs from the smaller
run: 17 of 17 solo-arm fixes correct.** Consistent with the smaller run's own
6/6 and with the registered prediction of a high, tightly-clustered fix rate
in both arms.

Next: the with-Icarus arm, batched by repository (7 `llm` tasks, 6 `rich`
tasks), MCP config verified against the local dev brain — not production —
before any task launches, learning directly from today's two contamination
findings.
