# Experiment 7d — repository familiarity, or the harness?

Registered **before any task is run**, per `docs/experiments/PROTOCOL.md` §3.
Nothing above the Result section may be edited after the first task starts.

## What is being tested

After 7c, two explanations survive for why four undirected sessions on
`Textualize/rich` produced zero unprompted calls while C2 produced 4 of 4:

1. **Repository familiarity** — C2 ran on `simonw/llm`, the repository the tool
   description was tuned against and the one Experiment C used.
2. **Harness** — C2 used fresh interactive sessions; 7b and 7c were both
   headless `claude -p`, where tool-exploration behaviour is measured nowhere.

7d runs C2's own repository, C2's own pinned commit and C2's own prompts,
**headless**. That is one variable against C2 (harness) and one against 7c
(repository), so the result removes one of the two survivors whichever way it
lands.

| | C2 | 7c | 7d (this run) |
|---|---|---|---|
| Repo | `simonw/llm` @ `94769b8` | `Textualize/rich` | **`simonw/llm` @ `94769b8`** |
| Harness | interactive | headless | **headless** |
| Prompts | C2's four, verbatim | leaner one-liners | **C2's, verbatim** |
| Nudge | none | none | none |
| Result | 4 of 4 | 0 of 2 | — |

## Tasks — C2's, minus the one C2 itself invalidated

C2 recorded that one of its four tasks failed §2a: reachability was **inferred
from a SQLite version string instead of executed**. That is task 2 (`llm logs -f`
fragment filter on SQLite 3.51.0+). It is **excluded here** rather than repeated,
since PROTOCOL §2a says executed, and re-running an invalid task would import
C2's own defect into its replication.

So 7d is C2's tasks 1, 3 and 4 — three tasks, directly comparable to the same
three in C2.

### §2a — re-executed today at the pinned commit, not carried over

- **T1 (#1466, `schema_dsl()` IndexError):** loaded the function from
  `llm/utils.py:354` at the pinned commit and called it.
  `schema_dsl("name, : int")` → `IndexError: list index out of range`; the
  control `schema_dsl("name, age int")` returns properties normally. **Present.**
- **T3 (#1583, template `schema_object` overwrites `--schema`):**
  `llm/cli.py:742-743` reads `if template_obj.schema_object: schema =
  template_obj.schema_object` — an unconditional reassignment with no check for a
  schema already supplied on the command line. **Present.**
- **T4 (#1580, `llm tools` lists empty dynamic toolboxes):** `llm/cli.py:2775-2777`
  echoes `toolbox.name + ":\n"` and then iterates `toolbox.method_tools()`, so a
  toolbox with none prints a heading with nothing under it. **Present.**

### §2b — re-checked today via `gh pr view --json mergedAt`

#1544 (T1), #1584 (T3), #1581 (T4) — all `CLOSED`, `mergedAt=null`. Also
re-checked and unused: #1549, #1571 (the excluded task 2), both closed unmerged.

## Prompts — C2's, verbatim, one per fresh session

1. `In this repo, schema_dsl() crashes with an IndexError when a field has no name before the colon, e.g. "name, : int". Fix it.`
2. `When a template defines schema_object, it overwrites the --schema passed on the command line. The command-line one should win. Fix it.`
3. `llm tools prints dynamic toolboxes that have no tools under them, which looks broken. Clean up that output.`

(Numbered 1–3 here; they are C2's tasks 1, 3 and 4.)

## Setup

- Clone: `/Users/alankritghosh/JARVIS /experiment-7d-llm` @ `94769b8`, **no
  `CLAUDE.md`**, working tree reset between tasks.
- Brain: local `demo.server` reconnected to `simonw/llm` — the committed corpus,
  already embedded.
- Counting: **transcripts only**, `scripts/agent_call_audit.py --project
  experiment-7d-llm`. A fresh project slug, so no session from 7b/7c can be
  miscounted here.
- The arm will be verified capable of firing before the tasks launch, as in 7c:
  if a direct ask cannot surface the refused pull requests, a zero means nothing.

## REGISTERED PREDICTION

1. **I expect 0 of 3, and I am more confident than I was in 7c.** Confidence:
   medium. Predicting a zero here is predicting against the result this company
   quotes in public, which is precisely why it goes in writing first.
2. **Reasoning:** the two zeros so far are both headless, and a `claude -p` run
   is a single non-interactive turn where an agent that already has a plan has
   little reason to go looking for a tool. Repository familiarity is the more
   flattering explanation and I do not believe it is the operative one.
3. **If it fires at all, I expect T1** — the `schema_dsl` task is the one whose
   fix is a one-line guard, so it is where an agent has spare attention, and its
   refused pull request (#1544) is a direct prior attempt.
4. **What each outcome means, fixed now so neither can be spun afterwards:**
   - **Non-zero** → repository familiarity is real and the description does less
     work on unseen code than 4/4 implies. That softens the *generality* of the
     claim, not the claim itself.
   - **Zero** → the harness is the prime suspect, and C2's 4/4 may be a property
     of interactive sessions. **That is the more damaging result**, because every
     public statement quotes 4/4 without saying "interactively", and the shipped
     tool description is read by headless agents too.
5. **Three tasks cannot settle either.** This narrows two explanations to one; it
   does not measure how large the effect is. Anything stronger needs the
   interactive arm re-run, which is manual work nobody has scheduled.
6. **What stays uncontrolled:** model version (CLI 2.1.238 today vs C2's
   2026-08-11 build) and the corpus, whose pull requests and issues were
   re-ingested since C2. Both cut toward *more* prior attempts being visible now,
   not fewer.

## Result

*(written after the run — nothing above this line changes)*
