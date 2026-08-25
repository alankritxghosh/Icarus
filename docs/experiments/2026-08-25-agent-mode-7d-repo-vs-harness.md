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

**INVALID. The agents never had the tool, so there was nothing to measure.**

The run produced 0 of 3, which is exactly what the prediction said. It is not
evidence for the prediction, because the check that PROTOCOL §5 demands — read
the state that produced the result — showed the arm was never armed.

    4226df10    TOOL NOT AVAILABLE — not a measurement
    975918bb    TOOL NOT AVAILABLE — not a measurement
    e80b33ed    TOOL NOT AVAILABLE — not a measurement

### How it was found, and why it nearly was not

The result agreed with the prediction, which is the most dangerous place for a
run to be: nothing about a confirmed expectation invites another look. The check
happened only because §5 says to read the state behind a result, not just the
result.

`mcp__icarus__` appears **nowhere** in any of the three transcripts. Not in a
`tool_use` block, and not in the `deferred_tools_delta` attachment where Claude
Code writes the tool catalogue it was handed. Four confirmations, in order:

1. **Transcript catalogue** — the three sessions list `mcp__ares__`,
   `mcp__pantheon__` and thirteen `mcp__claude_ai_*` servers. No `icarus`.
2. **Positive control** — an interactive session in this repository on the same
   day, with the tool available and never called, shows **14** mentions and 0
   calls. Available-and-unused looks nothing like this.
3. **Asked an agent directly** — a scratch directory with a byte-identical
   `.mcp.json` and `settings.local.json`, `claude -p "do you have any tool whose
   name starts with mcp__icarus__?"` → *"No."*, listing only `ares` and
   `pantheon`.
4. **Forced it** — `--mcp-config .mcp.json` and then
   `--mcp-config .mcp.json --strict-mcp-config` both still produced *"No."*,
   the second reporting **no MCP servers at all**.

Meanwhile `claude mcp list` from an interactive shell in that same directory
prints `icarus: /Applications/Icarus.app/Contents/MacOS/Icarus --mcp - ✔
Connected`, and the project server runs correctly standalone — piping an
`initialize` + `tools/list` handshake into
`.venv/bin/python3 -m demo.mcp_server` returns the real server info and
instructions. **Every check available from outside the session said the tool was
working.** Only the transcript said otherwise, and the transcript is the
authoritative source, which is PROTOCOL §1's rule arriving one layer down.

### It invalidates 7b and 7c as well

Same harness, same project config, same absence. The four sessions in
`experiment-7b-rich` — 7b's two from 2026-08-24 and 7c's two from today — show
zero mentions of `mcp__icarus__` each.

| run | reported | actually |
|---|---|---|
| 7b | 0 of 2 on an unseen repo | **no measurement** |
| 7c | 0 of 2 with leaner prompts | **no measurement** |
| 7d | 0 of 3 on C2's own repo | **no measurement** |

**Nine agent sessions across two repositories produced no evidence about
anything.** 7c's conclusion that "7b's live hypothesis is not supported" is
withdrawn: the hypothesis was never tested. So is 7c's framing of a burden
falling on 4/4 — nothing here puts any burden anywhere.

What survives from those runs is only what did not depend on an agent's choice:
both capability checks (the brain does surface the refused pull requests, cited,
on both repositories), and the observation that agents fixing these bugs from
first principles write duplicates of work already refused — which is visible in
their diffs regardless of what tools they held.

### What the tooling now does about it

`scripts/agent_call_audit.py` could not tell "had the tool, did not use it" from
"never had the tool". Both printed `0 calls  unprompted -`. It now reads the
transcript for the catalogue and prints `TOOL NOT AVAILABLE — not a measurement`,
excludes those sessions from the denominator entirely, and warns:

    9 session(s) never had the Icarus tools at all and are excluded.
    They are not zeros — they are nothing.

Its `--selftest` grew two cases pinning the distinction. Validated against the
positive control described above before being trusted.

### The one thing this run did establish, and it is about C2

Running the audit over the existing projects with the availability check:

- **Experiment C** — both sessions HELD the tool. That baseline stands.
- **C2** — held the tool, 4 calls, unprompted. **The 4/4 is real.**

But the same pass found something C2's own plan calls invalidating. C2 lists
under *What would make this run invalid*: *"Reusing a session across tasks (each
task gets a fresh session, or the first task's tool use contaminates the rest)."*
There is **one** transcript file for C2, and all four task prompts are in it,
with one Icarus call under each:

    icarus calls per task-position: {1: 1, 2: 1, 3: 1, 4: 1}

Every other run in this data writes one file per `claude -p` invocation, so one
file is one session.

**The calls happened — that is not in question.** What is in question is
independence. Tasks 2, 3 and 4 were performed by an agent that had already
called the tool and seen it return something useful. Only task 1 is an
observation of a cold agent reaching for it unprompted.

**Honest restatement, and it should replace "4 of 4" wherever that appears:**
*in one continuous session, an agent called Icarus on each of four consecutive
tasks; the first of those was unprimed and the other three followed a call that
had just paid off.* That is still a real result and still the best evidence there
is. It is a weaker claim than the one currently in circulation, and it was found
by looking at the transcript rather than the write-up.

### What has to happen before any of this is a measurement again

1. **Get the tool into a headless session, or stop using headless.** Four
   attempts failed today. Until one works, `claude -p` cannot run this
   experiment at all, and that is an operational finding worth more than the
   run: it means every future Agent Mode experiment is manual-interactive work.
2. **Re-run 7c and 7d with availability verified in-session before the task
   prompt is sent**, not after the result disappoints.
3. **Re-run C2 properly** — four genuinely fresh sessions, one task each — since
   the number in public rests on a session structure C2 itself ruled out.

Nothing about the public position changes in the direction of confidence. It
changes in the other direction, and §7b of the Work Queue already said that when
a claim does not survive, it gets softened everywhere it appears.
