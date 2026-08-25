# C2 re-run — four genuinely fresh sessions

Registered **before any task is run**, per `docs/experiments/PROTOCOL.md` §3.
Nothing above the Result section may be edited after the first task starts.

## Why

C2 (2026-08-11) is the number every public Agent Mode claim rests on: 0/11 → 4
of 4 unprompted calls after the tool description was rewritten. On 2026-08-25 an
availability audit found that C2's **four tasks ran in one continuous session** —
the condition C2's own plan lists under *what would make this run invalid*
("reusing a session across tasks... the first task's tool use contaminates the
rest"). One transcript file, all four prompts, one Icarus call under each.

The calls are real. Their **independence** is not established. Only the first is
an observation of a cold agent reaching for the tool; the other three follow a
call that had just paid off.

This run repeats C2 with **four separate sessions, one task each** — which is
what C2's plan required and did not do.

## What made this runnable at all

7b, 7c and 7d (nine sessions) were invalid because the agents never held the
tool. Root cause found today: a project-scope `.mcp.json` registering a server
**named `icarus`** shadows the working user-scope registration and then is itself
ignored in headless `claude -p`. Remove the project file and the user-scope
server loads normally — verified by an agent calling the tool successfully.

Two conditions are therefore required and both are met here:

- **no project `.mcp.json`** in the clone (the shadowing is the defect);
- **`permissions.defaultMode: bypassPermissions`**, because headless otherwise
  blocks the call on a permission prompt it cannot show. This is the analogue of
  C2's interactive approval, not an extra nudge: it removes a dialog, and it
  says nothing to the agent about whether to call anything.

## Setup

- Clone: `/Users/alankritghosh/JARVIS /experiment-c2r-llm`, `simonw/llm` @
  `94769b8` — C2's commit. Fresh, **no `CLAUDE.md`**, no project MCP config,
  working tree reset between tasks.
- Brain: local `demo.server` on `simonw/llm`, the committed corpus.
- MCP: user-scope `icarus`, running `demo.mcp_server` from a **clean git
  worktree at `853cbb5`** rather than the working tree — the working tree carries
  an uncommitted rewrite of the tool description, and the description is the
  exact variable C2 measured.
- Counting: transcripts only, `scripts/agent_call_audit.py --project
  experiment-c2r-llm`, which now also reports whether each session HELD the tool.

## Prompts — C2's four, verbatim, one per fresh session

1. `In this repo, schema_dsl() crashes with an IndexError when a field has no name before the colon, e.g. "name, : int". Fix it.`
2. `llm logs -f with a fragment filter returns no results on newer SQLite versions. Work out why and fix it.`
3. `When a template defines schema_object, it overwrites the --schema passed on the command line. The command-line one should win. Fix it.`
4. `llm tools prints dynamic toolboxes that have no tools under them, which looks broken. Clean up that output.`

All four are run, including task 2, because this is a replication of C2 and
dropping a task would change what is being replicated. **Task 2's §2a was
inferred from a SQLite version string rather than executed** — C2 recorded this
itself — so a call on task 2 counts as a call, while task 2's validity as a *bug
task* stays exactly as questionable as C2 left it.

Tasks 1, 3 and 4 had their §2a re-executed at the pinned commit earlier today
(see `2026-08-25-agent-mode-7d-repo-vs-harness.md`), and #1544/#1584/#1581
re-confirmed `CLOSED, mergedAt=null`.

## Deviations from C2, stated before the result

None of these can be removed without manual interactive work, so they are
disclosed rather than fixed:

1. **Headless, not interactive.** C2 used interactive sessions. This is the
   variable 7d meant to test and never did.
2. **Tool description has grown since C2** — `claims`, `rests_on_unlanded`,
   `review` and the relevance-noise disclosure were all added after 2026-08-11.
   It is the description as shipped at `853cbb5`, which is what the Work Queue
   asked for, but it is not byte-identical to the one C2 measured.
3. **CLI 2.1.238**, versus C2's 2026-08-11 build.
4. **The corpus was re-ingested since C2**, so if anything MORE prior attempts
   are visible now, not fewer.

## REGISTERED PREDICTION

1. **I expect 3 of 4.** Confidence: low-to-medium.
2. **Reasoning:** exactly one cold, unprimed call has ever been measured — C2's
   task 1 — and it fired. That is real evidence a cold agent will reach for the
   tool, but a single observation cannot carry 4 of 4. I expect the effect to be
   real and not universal, so I expect a majority and not a sweep.
3. **If any task misses, I expect task 4** (`llm tools` output tidying), which
   reads as a cosmetic change where an agent is least likely to think history
   matters.
4. **What each outcome means, fixed now:**
   - **4 of 4** → independence confirmed, and the public claim is *restored to
     full strength* rather than merely defended. The strongest available result.
   - **0 of 4** → C2's number was priming plus interactivity, and every surface
     quoting it needs rewriting, not softening.
   - **1–3 of 4** → the effect is real and partial. Quote the fraction from THIS
     run, since it is the one with independent sessions, and stop quoting 4/4.
5. **A call is counted whatever it returns.** Whether Icarus answers usefully is
   a different measurement; this one is only about whether a cold agent reaches
   for it.
6. **This does not settle interactive-vs-headless.** If this run fires, it shows
   headless agents do call the tool, which retires the operational worry from 7d
   — but the comparison to C2 still crosses a harness boundary.

## Result

*(written after the run — nothing above this line changes)*
