# Experiment C2 — does a rewritten tool description get Icarus called on its own?

Registered **before** any task is run, per `docs/experiments/PROTOCOL.md` §3.
Nothing below may be edited after the first task starts; results go in a
separate write-up.

## What is being tested

Experiment C measured **0 unprompted Icarus calls across 4 real tasks**, under
a strong, explicit `CLAUDE.md` instruction to call it before any change. The
conclusion drawn was that agents don't consult unless directed.

Alankrit's call for Priority 2 was to keep the discretionary model and make the
tool worth reaching for, rather than adding a deterministic trigger. So
`demo/mcp_server.py`'s `_INSTRUCTIONS` and `get_change_context`'s description
were rewritten (`064879a`) to:
- lead with the capability the agent CANNOT get from its own tools (a refused
  pull request leaves no commit; git log/blame/worktree are blind to it),
- state the measured cost of skipping it (3 verified trials, materially worse
  conclusion every time),
- and trigger on OBSERVABLE events ("you are about to edit a file / open a PR /
  conclude a bug is fixed / call a behaviour intentional") instead of on the
  agent's own estimate of whether a change is "meaningful".

**C2 is C with one variable changed.** No `CLAUDE.md` nudge this time — that is
deliberate and makes this a HARDER test than C. If a nudge were present we
could not tell whether the description or the nudge caused a call.

## Registered prediction

**I expect 0–1 of 4 tasks to produce an unprompted call, and I expect this to
fail to reach the bar.** Reasoning: a description competes for attention with
every other tool at the moment of choosing, whereas the failure in C was that
the agent never reached the point of considering consultation at all. If it
does fire, I expect it on tasks 2 and 3 (where the code alone looks ambiguous)
rather than 1 and 4 (where the fix looks obvious from the traceback).

Alankrit's position is that the C nudge may simply have been badly written.
That is what the run decides. **A 0/4 result is a real finding, not a wasted
run:** it is the evidence that the trigger has to be deterministic, and it
should be reported as plainly as a positive would be.

## Setup

- Clone: `/Users/alankritghosh/JARVIS /experiment-c2-llm`, `simonw/llm` @
  `94769b8` — the SAME commit the Icarus corpus is pinned to
  (`evals/corpus/meta.json`). Fresh, no task branches, **no `CLAUDE.md`**.
- `.mcp.json` copied in, so the three Icarus tools are available.
- Brain connected to `simonw/llm` (verified via `/health`).
- **The corpus code is pinned at 2026-06-21, but its PRs/issues were ingested
  2026-08-06.** That asymmetry is what makes these tasks work: the fixes are
  NOT in the code the agent reads, while the refused attempts ARE in the
  evidence Icarus holds.

## Tasks — all four validated per PROTOCOL §2 before selection

Every one has a real closed-WITHOUT-merge pull request (§2b, verified via
`gh pr view --json mergedAt` — all `mergedAt: null`) and a bug genuinely
present at the pinned commit (§2a). Issue close dates are all late July /
August 2026, i.e. **after** the 2026-06-21 pin.

| # | issue | refused PR(s) | §2a evidence |
|---|---|---|---|
| 1 | #1466 `schema_dsl()` IndexError when a field has no name before the colon | #1544 | **Executed** the function from the pinned source: `schema_dsl("name, : int")` raises `IndexError: list index out of range`; control input works |
| 2 | #1511 `llm logs -f` fragment filter returns nothing on SQLite 3.51.0+ | **#1549 and #1571** | local sqlite is 3.53.3, so the version-dependent bug is reachable here |
| 3 | #1583 template `schema_object` overwrites `--schema` instead of yielding to it | #1584 | `llm/cli.py:742-743` unconditionally reassigns `schema` from the template |
| 4 | #1580 `llm tools` looks broken when listing dynamic toolboxes | #1581 | `llm/cli.py:2775-2777` prints a toolbox name with no tools under it |

Task 2 is the strongest case: **two** separate refused attempts at the same
fix, mirroring the 7-attempt pattern from directed-D.

## Prompts — to be given VERBATIM, one per fresh session

They must never name Icarus, MCP, or a tool (PROTOCOL §6), and must not hint
that history matters. Each is what an ordinary user would type.

1. `In this repo, schema_dsl() crashes with an IndexError when a field has no name before the colon, e.g. "name, : int". Fix it.`
2. `llm logs -f with a fragment filter returns no results on newer SQLite versions. Work out why and fix it.`
3. `When a template defines schema_object, it overwrites the --schema passed on the command line. The command-line one should win. Fix it.`
4. `llm tools prints dynamic toolboxes that have no tools under them, which looks broken. Clean up that output.`

## Measurement — transcripts only, never self-report (PROTOCOL §1)

    python3 scripts/agent_call_audit.py --project experiment-c2-llm

Recorded per task: unprompted Icarus calls (0 or more), which tool, and whether
the resulting change differs from what the agent would have written without it.
**Do not ask the agent whether it used Icarus.** That question has produced a
wrong answer twice.

Baseline for comparison, measured under the OLD descriptions before this
change landed: 58 sessions, 12 undirected, 1 called Icarus — and that one was
the session doing the Icarus work itself, so the honest baseline is **0/11**.

## What would make this run invalid

- Any prompt mentioning Icarus, MCP, engineering memory, or prior attempts.
- Reusing a session across tasks (each task gets a fresh session, or the first
  task's tool use contaminates the rest).
- Reading the linked PR/issue thread while writing the task prompt into the
  session — the prompts above are already fixed for exactly this reason.
- Judging "did it help" from the agent's summary rather than from the diff.
