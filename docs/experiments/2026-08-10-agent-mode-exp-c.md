# Experiment C — Claude Code in VS Code

Date: 2026-08-10
Repo under test: `simonw/llm`, cloned to `/Users/alankritghosh/JARVIS /experiment-c-llm`,
pinned to the corpus commit `94769b8b076c`. Icarus's active connected repo
throughout.

Unlike A/B/D, this experiment could not be run autonomously — the brief
itself says "guide Alankrit through actually using this workflow," and points
5–8 (developer experience, where it's awkward) can only be answered by the
person actually using it. Alankrit ran Claude Code in VS Code directly; I set
up the environment, picked each task, and independently verified each result
against the actual code rather than trusting the agent's own summary.

## Setup: a real gap found before any task ran

Alankrit's session was running in the Claude Code **Desktop app**, not VS
Code — worth naming plainly since the brief specifically asks about the VS
Code CLI workflow, and moved there deliberately.

`.mcp.json` in the Icarus repo registers Icarus for Claude Code, but only
**project-scoped** — inside that one repo. Checking the global
`~/.claude.json`, Icarus was **absent** from `mcpServers` (only `posthog`,
`pantheon`, `ares` were there). So a coding agent working on *any other* repo
— which is the entire premise of Agent Mode, a context layer for whatever
you're building — had **zero access to Icarus** until this was fixed by
manually adding a global entry (backed up first).

This is a genuine, disclosed product gap: today, nothing in Icarus's own
distribution registers it globally. A new user following the product as
shipped would hit this before ever reaching the interesting question.

## Task 1 — issue #1397 (self-diagnosed bug)

`embed_multi_with_metadata()` compared user-provided IDs against database row
IDs instead of content hashes, breaking dedup. The issue body itself walked
through the full root cause before Claude Code ever opened the file.

**Result:** correct fix, verified red→green, matches the issue's own
diagnosis. **Zero MCP calls** — confirmed by the transcript's own tool-call
formatting (every `Read`/`Edit`/`Bash` call renders as a distinct block; no
MCP block appeared).

**Why this is a clean, uninteresting result:** the issue already contained
the "why". There was nothing for Icarus to add, and it correctly wasn't
consulted.

## Task 2 — issue #224 (real history, wrong shape)

Deliberately picked to mirror Experiment D's pattern: `Collection.embed()`'s
dedup logic, where the maintainer had **implemented and reverted his own
fix**, explicitly because it "doesn't take the embedding model into account
— a content hash stored for one embedding model will be used in place of
another," then deliberately punted the issue. A second, unrelated PR (#1420)
also never merged.

**Result:** correct fix, verified independently — I traced `Collection
.__init__` myself and confirmed `collection_id` is permanently bound to one
embedding model by construction (`self.model_id = row["model"]` on an
existing collection, ignoring any caller-passed model), so scoping every
reuse query by `collection_id` (which the fix does throughout) structurally
avoids the exact bug the maintainer described. **Zero MCP calls.**

**How it found the history:** not via Icarus, and not via `gh issue view`'s
default output (which shows a comment *count*, not comment *text* — I
verified this directly). It went straight to **`git log`/`git show` on the
reverted commit**, read the actual diff, and derived "reused embeddings
across collections (hence across models), which was the bug" from the code
change itself.

**The flaw in this task's selection, found after the fact:** I picked #224
to test the same thing that mattered in Experiment D — a rejected prior
attempt. But D's decisive fact was a **closed, unmerged pull request**,
which is structurally invisible to `git log` (a merged PR leaves a commit;
a refused one leaves nothing — the exact mechanism behind
`evals/attempts.rejected_attempts`, shipped earlier this session). #224's
prior attempt was **committed, then reverted** — a different case, fully
visible to ordinary git archaeology. I picked a task that looks like D's
pattern on the surface but is actually the one sub-case plain git already
solves. One real gap: no test in the repo protects the
cross-model-safety property my own manual trace verified; if the `Collection`
constructor is ever loosened to allow rebinding an existing name to a
different model, this bug could resurface with nothing to catch it.

## Task 3 — issue #1296 / PR #1327 (already fixed — a second selection miss)

Retargeted at the actual gap: a **closed, unmerged** PR (`#1327`, "Fix `--xl`
and `--extract` options being ignored when using templates") against a
still-**open** issue (`#1296`) on GitHub's live tracker — the git-invisible
shape D's real result turned on.

**Result: Claude Code added a real, verified regression test
(`test_template_extract_options`, 8 parametrized cases including the exact
CLI-vs-template conflict) and made *no* change to `cli.py`.** I checked this
myself: `git diff llm/cli.py` was empty, and I ran the new test against the
unfixed... except it wasn't unfixed. `llm/cli.py:731-733` already reads:

```python
if not (extract or extract_last):
    extract = template_obj.extract
    extract_last = template_obj.extract_last
```

— a **different, more correct implementation** than PR #1327's own proposed
fix (`extract = extract or template_obj.extract`, which can't distinguish
"explicitly `False`" from "unset," a real defect I'd flagged when we picked
this task). The bug was already resolved at the pinned commit, almost
certainly by unrelated work that never referenced the issue number, leaving
`#1296` open on GitHub's live tracker despite the code being correct. I ran
the new test against the actual code and confirmed all 8 cases genuinely
pass, not vacuously.

**Second selection miss, same session:** I verified this task against
GitHub's *live* issue state, not the code at the *pinned commit* — the same
class of error as almost picking the already-superseded fragment-filter
saga earlier, just not caught in time here. Claude Code's own investigation
was more careful than mine: it read the actual code before concluding
anything, found the guard already there, and correctly chose not to touch
working code — locking the existing (correct) behavior in with a test
instead of writing a redundant or regressive "fix." That is the right
engineering call, independent of the Icarus question.

**MCP calls: zero, confirmed explicitly and precisely.** Asked directly,
the agent's own words: *"Everything in that investigation ran through
built-in tools only: Bash (git log/show, grep, pytest), Read, Edit, and one
Write to the scratchpad... No MCP server was contacted, and no subagents or
workflows were launched."* It also volunteered a sharp, well-calibrated
self-assessment: the MCP server's own instructions ask that
`get_change_context` be called "before a meaningful code change," and it
reasoned this didn't apply because its only change was additive test
coverage — offering to run it retroactively if asked. That is evaluating
the instruction correctly, not ignoring it.

## Cross-cutting result

**3 of 3 tasks: zero MCP calls, Icarus never consulted, unprompted.** This
held across a self-diagnosed bug, a real bug with genuine git-visible
history, and a bug already fixed by the time it was picked — three
genuinely different shapes, one consistent result.

The clearest single data point: asked directly why, the agent's own words
were *"none of them were relevant to a local Python bugfix."* That evaluates
MCP tools as a **category**, by task type, not `get_change_context`
**specifically**, against what it could actually offer. The MCP server's own
`_INSTRUCTIONS` field ("before planning or making a meaningful code change,
call get_change_context...") did not survive contact with the model's own
judgment on any of the three runs.

**Task selection was the weak link in this experiment, not the model.** Two
of three picks turned out not to test what they were chosen to test — once
because a revert is git-visible in a way a closed-unmerged PR is not, once
because GitHub's live issue state didn't reflect the pinned commit's actual
code. Both misses were caught by verifying independently rather than trusting
either the task description or the agent's summary — the same discipline
this whole session's Agent Mode work has depended on.

## What's NOT yet answered

Whether Icarus adds real value when a task genuinely has the D-shaped gap
(a closed-unmerged PR, nothing else) remains untested here — neither task 2
nor task 3 turned out to be that case, despite being chosen for it. It also
remains untested whether Icarus's context, *if* consulted, would have
changed either fix — task 1 didn't need it, and tasks 2–3 arrived at correct
answers without it.

## Task 4 — issue #1354 / PR #1366, with a strong repo-level nudge

This time verified against the **pinned commit's actual code**, not
GitHub's live tracker, learning from tasks 2 and 3's misses: `llm/models.py
:1522` inserts into `prompt_attachments` with no `ignore=True`, and the
table's schema (`llm/migrations.py:221-231`) has a composite primary key on
`(response_id, attachment_id)` — confirmed the crash is real and live before
handing it off.

Before this run, a `CLAUDE.md` was added to the target repo, deliberately
much stronger than the MCP server's own `_INSTRUCTIONS` field: *"Before
starting ANY task here... This is not a judgment call... 'this seems like a
simple fix' is not a reason to skip it... Call `get_change_context` before
reading any other file."* No hedging, no scoping to "meaningful" changes,
explicit that task size is not a valid reason to skip it.

**Result: still zero MCP calls.** Asked directly whether an MCP block
preceded the investigation's first action, Alankrit's answer was a flat
"No." The strong, explicit, repo-level instruction did not survive contact
with the model's own judgment any better than the soft MCP-level one did.

**The fix itself, independently verified, was genuinely excellent** — better
than the prior closed-unmerged attempt (`PR #1366`) in a real, checked way:
`#1366`'s actual diff (confirmed via `gh pr diff`) touched only
`prompt_attachments`; this run's fix independently found and fixed a
**second, analogous bug** in `tool_results_attachments` that `#1366` never
addressed, added a test proving each, and specifically verified the fix
preserves model-facing behavior (the model still receives both attachment
copies; only DB persistence dedupes) — a subtlety #1366 never tested for.
All three new tests confirmed genuinely red→green: reverting `models.py`
alone reproduces the exact real `sqlite3.IntegrityError: UNIQUE constraint
failed: prompt_attachments.response_id, prompt_attachments.attachment_id`.

**A verification dead end worth recording in its own right.** Attempting to
confirm this independently (rather than trust a self-report) exhausted every
server-side channel available: the agent-session credential is itself
route-scoped and cannot reach `/ledger`, and even with full access it
wouldn't have settled anything — MCP-originated `/ask` calls are
**deliberately excluded** from the ledger (`demo/server.py`'s ledger-write
is gated on `not include_evidence`, and `get_change_context` always sets
`include_evidence: True`), specifically so agent preflight questions don't
pollute the human documentation-demand signal. That is the right product
decision for what the ledger is for — and a side effect nobody designed for
is that **there is currently no audit trail, for anyone, of whether an agent
actually consulted Icarus.** The only source of truth was Alankrit's own
read of the transcript.

## Updated cross-cutting result: 4 for 4

Across a self-diagnosed bug, a real bug with git-visible history, a bug
already fixed by the time it was picked, and a live bug with an explicit,
strong, repo-level instruction telling it to consult Icarus before touching
anything — **zero MCP calls, four times.** The escalation from a soft nudge
to an unambiguous mandate changed nothing. That is a materially stronger and
more surprising result than "the model doesn't reach for the tool
unprompted" — it says instructing it, at any strength tried so far, is not
a reliable mechanism at all.

Notably, task 4's fix was the best of the four on independent merit — more
thorough than the human-submitted prior attempt — while having consulted
Icarus not at all. Whatever produced that quality, it wasn't engineering
memory.

## Task 5 — issue #1398, Icarus explicitly instructed

Ambient instruction (soft and strong) failed to produce a single Icarus
consultation across four tasks, so task 5 changed the question: stop testing
whether the model volunteers, tell it to consult Icarus directly as part of
the task, and see what a real, directed consultation actually does.

Verified against the pinned commit exactly like task 4 (learning from tasks
2 and 3's misses): `llm/models.py:1579-1580`, inside `_BaseResponse
.log_to_db()`, reads `tool.plugin`/`tool.name` from the *earlier*, already-
finished `for tool in self.prompt.tools:` loop — a classic Python stale-
loop-variable bug, live and confirmed present.

The task instruction specified an explicit, focused question for
`get_change_context`: *why does the `tool_instances` insert use the stale
loop variable instead of the `tool_ids_by_name` dict the surrounding code
already uses correctly?*

**Verified independently from the raw session transcript, not from any
summary.** Claude Code CLI persists full JSONL transcripts under
`~/.claude/projects/<project>/`; the actual `tool_use` blocks were parsed
directly, confirming exactly one real `mcp__icarus__get_change_context`
call, with precisely the specified question, and zero calls in the prior
(task 4) session file — independent confirmation of the "No" already given
for task 4, and hard confirmation task 5's instruction actually worked.

**What Icarus returned, and what happened next, is the clearest positive
result of this whole experiment.** The answer restated the bug mechanism and
cited `pr:1485` — a currently OPEN, unmerged third community attempt at this
same issue that neither Alankrit's task-picking nor mine had found. Separate
from the answer, the `rejected_attempts` field (`evals/attempts.py`, shipped
earlier this session) surfaced `pr:1431` — the same closed-unmerged PR — as
a distinct rejected prior attempt. Its own words in the transcript,
immediately after reading the response: *"Icarus flagged something
important — a prior fix attempt for exactly this was closed without
merging. Let me check what happened there before I write my own."*

It then went further than what Icarus surfaced: checked `#1431` directly
(zero review comments — closed with no stated reason), checked issue `#1398`
itself, which surfaced a *third* independent attempt Icarus never mentioned
(`#1406`), and only then read `class Tool` from the actual source before
writing anything.

**The final fix matches none of the three prior designs:**

| | approach |
|---|---|
| `#1431` (closed, unmerged) | dict-lookup by name |
| `#1485` (open, unmerged) | dict-lookup by name, refined |
| `#1406` (open, unmerged) | dict-lookup, falls back to reading the instance |
| **task 5's fix** | **reads the instance directly — no lookup at all** |

Simpler than all three, and independently verified correct: traced against
`Toolbox.tools()` (`tool.plugin = getattr(self, "plugin", None)`,
`llm/models.py:293`) to confirm `instance.__class__.__name__` and
`getattr(instance, "plugin", None)` are exactly what the surrounding code
already establishes as correct — not a guess. New test
(`test_tool_instances_attributed_to_correct_toolbox`) verified genuinely
red→green against the real bug; a pre-existing test's fixture data
(`"Filesystem"` → `"Memory"`), independently also caught by `#1485`'s own
author, confirms that correction was real, not spurious.

**What this means for the experiment overall:** Icarus's signal was the
*trigger* for deeper investigation, not the source of the final answer. It
did not hand over a fix to copy — it handed over a fact (a rejected attempt
exists) that changed how much verification happened before code was
written, and the agent's own follow-through (checking the issue itself,
finding a third attempt Icarus never named) exceeded what Icarus alone
supplied. That is a materially different, and more interesting, value
proposition than "Icarus tells you the right answer" — it's "Icarus tells
you when the obvious answer already failed twice, and lets you go find out
why yourself."

## Where this leaves the whole experiment

Four tasks with zero MCP calls, one task with exactly one — directed, not
volunteered — and that one task produced the richest, most positive result
of the five. The honest reading is not "Icarus doesn't work" or "Icarus
works great" — it's that **unprompted consultation did not happen at any
instruction strength tried, but a real, directed consultation demonstrably
changed the depth of investigation and, through that, the final design.**
Whether that gap is closeable with a better nudge, a different integration
point, or isn't meant to be closed at all (some tasks explicitly told to use
Icarus vs. relying on the model's own judgment) is the open question this
experiment leaves for whatever comes next.

---

## Appendix — the exact `CLAUDE.md` nudge (preserved 2026-08-11)

Recorded verbatim before the `experiment-c-llm` clone was deleted. This is the
**control condition** for Experiment C2: C got 0 unprompted calls in 4 tasks
WITH this instruction in place, C2 got 4 of 4 with NO instruction and only the
rewritten tool description. Without the exact text, that comparison cannot be
audited or repeated, and "the nudge was strong" would be an unverifiable claim
about a file nobody can read.

```markdown
# Working in this repository

Before starting ANY task here — a bug fix, a refactor, a new feature, even a
one-line change — call the `icarus` MCP server's `get_change_context` tool
first, with a focused question about the code you're about to touch.

This is not a judgment call. Do it regardless of how small, obvious, or
self-contained the task looks. "This seems like a simple fix" is not a
reason to skip it — some of the worst mistakes in this codebase's own
history were simple-looking fixes that reproduced a bug someone had already
found and rejected. Icarus holds exactly that: prior decisions and rejected
attempts (including closed pull requests, which `git log` cannot show you —
a merged change leaves a commit, a refused one leaves nothing) that the code
and commit history alone will not surface.

Call `get_change_context` before reading any other file. If the task is
larger than a single focused question, use `get_task_context` instead.
```

Note what it already contained: the refused-PR asymmetry, an explicit "not a
judgment call", and a pre-emptive answer to "this seems like a simple fix". The
argument that C's nudge simply under-sold the tool is therefore weak — what
changed in C2 was WHERE the instruction lived (the tool's own description,
present at the moment of choosing) and that it triggered on observable events
rather than on the agent's estimate of importance.
