# Experiment 7c — was 7b's 0 of 2 the repository, or the prompt?

Registered **before any task is run**, per `docs/experiments/PROTOCOL.md` §3.
Nothing above the Result section may be edited after the first task starts.

## Why this run exists

`docs/experiments/2026-08-24-agent-mode-7b-plan.md` set out to change one
variable against C2 and changed at least three: repository (intended), **prompt
richness (not intended)**, and harness. Its own write-up says so, and refuses to
read its 0/2 as a refutation of C2's 4/4.

It left one hypothesis live and untested:

> the rewritten description fires on ambiguity, not on the observable events it
> names. C2's agents had to investigate before they could act; mine were handed
> the investigation.

7c tests exactly that, and nothing else.

## The one variable

**Prompt richness.** Everything else is held at 7b's settings — same repository,
same pinned commit, same two tasks, same headless harness, same CLI build, same
brain, same tool description.

| | 7b (already run) | 7c (this run) |
|---|---|---|
| Repo | `Textualize/rich` @ `9d8f9a3` | same |
| Tasks | T1 CRLF, T2 tag merge | same two |
| Harness | headless `claude -p` | same |
| Claude CLI | 2.1.238 | 2.1.238 — checked, not assumed |
| Prompt | reproduction + exact wrong output + span offsets | **bare C2-style one-liner** |
| Result | 0 of 2 | — |

This is a true one-variable comparison against an arm that already exists, which
is why it is two tasks and not four: the contrast is with 7b, not with C2.

## Setup

- Clone: `/Users/alankritghosh/JARVIS /experiment-7b-rich`, working tree reset to
  the pinned commit before each task (7b left task-2 edits in it). **No
  `CLAUDE.md`.**
- Brain: local `demo.server`, connected to `Textualize/rich`, reached through the
  documented `ICARUS_BRAIN_URL` development override. The 7b corpus cache is
  gone, so the repository is re-ingested for this run — same repository, freshly
  indexed.
- Counting: **transcripts only**, `scripts/agent_call_audit.py`, per §1.

## The prompts, fixed here before launch

Verbatim, and this is the whole intervention:

- **T1** — `In this repo, Text.from_ansi() mishandles CRLF line endings. Fix it.`
- **T2** — `In this repo, ReprHighlighter merges adjacent markup tags. Fix it.`

Nothing else is said. No reproduction, no expected output, no file named.

## Task validation — re-executed today, not carried over

§2 says mechanical and says run it before the task is used. Both re-run at the
pinned commit on 2026-08-25 rather than trusting 7b's record:

- **T1 §2a:** `Text.from_ansi('line one\r\nline two\r\n').plain` → `'\n\n'`.
  The text is gone, not merely mis-split. Present.
- **T2 §2a:** highlighting `<tag1> <tag2>` yields
  `[(0,1,tag_start), (1,5,tag_name), (5,12,tag_contents), (12,13,tag_end)]` —
  `tag_contents` runs 5..12 and swallows the second tag's opening. Present.
- **§2b:** #4159, #4145, #4138, #4113, #4103, #4099 (T1) and #4142 (T2) all
  re-checked via `gh pr view`: every one `CLOSED`, `mergedAt=null`. Still genuine
  refused attempts, none merged since 7b.

## REGISTERED PREDICTION

1. **I expect 1 of 2 calls.** Confidence: low-to-medium. This is a genuine
   coin-flip between two explanations that 7b could not separate, and stating a
   number I half-believe is the point of writing it first.
2. **Reasoning:** if the live hypothesis is right, removing the reproduction
   restores the ambiguity C2's prompts had, and the tool gets reached for. If
   the hypothesis is wrong, prompt richness was never the variable and 7c
   reproduces 0 of 2 on an unseen repository — which would make repository
   familiarity, not description wording, the thing C2 measured.
3. **If it fires, I expect T1 over T2**, unchanged from 7b's reasoning: six
   prior refused attempts is the shape the description names, and CRLF handling
   stays ambiguous from the code alone. T2's regex is solvable by reading one
   pattern whether or not the offsets are handed over.
4. **A second 0 of 2 is the more consequential result and gets reported as
   plainly as a 2 of 2.** Two runs, one repository, two prompt styles, nothing
   fired — that would put the burden on 4/4 rather than on this run, and every
   public statement resting on it gets softened in the same pass.
5. **This run cannot confirm 4/4 and cannot refute it.** Two tasks, one
   repository. What it can do is tell prompt richness apart from repository
   familiarity, which is one confounder removed from a three-confounder run.
   Stated now so the write-up cannot quietly promote it.
6. **What still will not be settled afterwards**, listed so it cannot be
   forgotten: four tasks (a single agent's habits can dominate two), the
   `simonw/llm` arm (repository familiarity stays untested until bare prompts
   run there too), and interactive-vs-headless (both 7b and 7c are headless, so
   the harness difference from C2 remains uncontrolled in both).

## Result

*(written after the run — nothing above this line changes)*

**0 of 2. The prediction was wrong, and this is the consequential branch.**

    297d464a    0 calls  unprompted -      <- 7c T2 (bare prompt)
    2cae0553    0 calls  unprompted -      <- 7c T1 (bare prompt)
    81869950    0 calls  unprompted -      <- 7b T1 (rich prompt)
    f523902e    0 calls  unprompted -      <- 7b T2 (rich prompt)
    4 sessions, 4 undirected; 0 of those called Icarus (0 calls total)

Transcript-verified, `scripts/agent_call_audit.py --project experiment-7b-rich`.
All four sessions flagged undirected, so no prompt leaked the tool's name.

### The one variable moved and the outcome did not

| | prompt | result |
|---|---|---|
| 7b | reproduction, exact wrong output, span offsets | 0 of 2 |
| 7c | bare one-liner, nothing else | **0 of 2** |

**7b's live hypothesis is not supported.** Removing the reproduction restored
exactly the ambiguity C2's prompts had, and nothing fired. Prompt richness was
not the explanation for 7b's zero, which means 7b's own most generous reading of
itself was wrong.

Not *refuted* — two tasks cannot refute anything, as §5 of the prediction says.
But the hypothesis was the reason 7b's 0/2 could be set aside, and it no longer
does that work.

### What the agents did, both competent, neither aided

- **T1** traced the fault to `AnsiDecoder.decode` stripping only `"\n"`, leaving
  a trailing `"\r"` that `decode_line`'s `rsplit("\r", 1)[-1]` then treats as an
  overwrite and discards the line. Fixed it, checked mid-line CR still
  overwrites, added `test_decode_crlf`, ran the suite and correctly separated 9
  pre-existing Pygments-drift failures from its own change. **It is the seventh
  attempt.** Six closed-unmerged pull requests sat one tool call away.
- **T2** identified the greedy `[\w\W]*` in `tag_contents` crossing its own `>`,
  found via `git log` that the greediness was deliberate (`ce55112`, to keep
  `<foo: <bar: 23>>` balanced), and replaced it with a nesting-aware pattern
  rather than a plain revert. It also disclosed a real remaining limit (depth > 1
  still unbalanced).

  **T2 independently reproduced the exact diagnosis of #4142** — same greedy
  group, same merge mechanism — which a human submitted and had closed unmerged
  on 2026-05-23. The agent reached commit history through `git log` and never
  reached the refused attempt, because `git log` structurally cannot show it.

### The check 7b never ran: the arm was capable of firing

Before either task launched, the connected brain was asked directly:

    "Has anyone tried to fix CRLF line ending handling in Text.from_ansi before?"
    verdict: answer
    citations: pr:4099, pr:4145, pr:4138, pr:4091, pr:4159, pr:4103

Five of the six §2b refused pull requests, cited, plus a sixth (#4091) the task
validation had not listed. **So 0 of 2 is a statement about the agent not
reaching for the tool, not about the brain having nothing to give it.** 7b left
that ambiguous; it is closed now.

### What this leaves, stated as a burden rather than a conclusion

With the description as shipped, the measurements now stand at:

| run | repo | harness | prompts | nudge | calls |
|---|---|---|---|---|---|
| C | `simonw/llm` | interactive | bare | strong `CLAUDE.md` | 0 of 4 (old description) |
| C2 | `simonw/llm` | interactive | bare | none | **4 of 4** |
| 7b | `Textualize/rich` | headless | rich | none | 0 of 2 |
| 7c | `Textualize/rich` | headless | bare | none | 0 of 2 |

**Two candidate explanations survive, and 7c cannot separate them:**

1. **Repository familiarity** — C2 ran on the repository the description was
   tuned against and that Experiment C used. Every zero is on a repository
   Icarus had never indexed.
2. **Harness** — C2 used fresh interactive sessions; both zeros are headless
   `claude -p`. Tool-exploration behaviour under `-p` is measured nowhere.

**The public position does not change and does not get repeated more
confidently.** 4/4 stands as what it always was: four tasks, one session, one
repository. What 7c adds is that four undirected sessions on an unseen
repository, across both prompt styles, produced zero — with the tool provably
able to answer. That is pressure on how far 4/4 generalises, and it is not a
refutation.

### The next run, and it is cheap

Bare prompts, **headless**, on **`simonw/llm`** — C2's own repository and C2's
own tasks. One variable against C2 (harness) and one against 7c (repository), so
whichever way it lands it removes one of the two survivors:

- fires → repository familiarity is the variable, and the description does less
  work on unseen code than 4/4 implies.
- zero → the harness is the prime suspect, and C2's 4/4 may be a property of
  interactive sessions rather than of the description.

The corpus is already built (it is the committed board), so this costs an agent
run, not an ingest.

### Disclosed, so it is not discovered later

- Both 7c agents hit a broken sandbox Python: T1 reported 9 pre-existing test
  failures from Pygments drift, T2 could not install pytest at all and ran the
  highlighter test table directly. Neither affects a call count, which is read
  from transcripts, but it means "ran the suite" is weaker here than it sounds.
- 7b and 7c share a corpus that was **re-ingested today**, not the one 7b ran
  against (that cache was gone). Same repository, same pinned commit, freshly
  indexed: 8,262 chunks (1,503 pr · 1,528 issue · 4,460 commit · 431 code ·
  326 doc · 14 config), semantic index built before either task launched.
- Ingest attached full discussion to the 50 most recent pull requests of 1,503
  and the 400 most recent issues of 1,528; older ones are indexed by description
  and fetch their thread on demand. The refused pull requests here are recent and
  were reachable, as the capability check shows.

### Correction, found while setting up the follow-up: "bare C2-style" was wrong

7b's write-up describes C2's prompts as bare one-liners. Reading them again in
`2026-08-11-agent-mode-exp-c2-plan.md`, they are not quite:

    In this repo, schema_dsl() crashes with an IndexError when a field has no
    name before the colon, e.g. "name, : int". Fix it.

C2 gave the symptom **and one example input**. 7c gave the symptom and nothing
else. **So 7c's prompts are leaner than C2's, not equal to them** — the label
"C2-style" above is inaccurate and stays as written, because the prediction was
registered with it.

The direction matters and it favours the conclusion, which is why it is stated
rather than left out: 7c gave its agents *less* to go on than C2 did, so *more*
ambiguity, and the tool was still never reached for. The tidier reading — that
7c under-tested the hypothesis by handing over too much — is not available.

What this does cost is the clean prompt-parity claim against C2. The gap between
7c and C2 is now repository, harness, **and** a small prompt difference in the
direction of less information. The follow-up on `simonw/llm` will use C2's four
prompts verbatim, which removes the third.

---

## WITHDRAWN 2026-08-25, same day, by the run that followed it

**The two agents in this run never had the Icarus tools.** `mcp__icarus__`
appears nowhere in either transcript — not as a call, not in the tool catalogue
Claude Code writes into the session. Headless `claude -p` did not load the
project's MCP server, and four separate outside-the-session checks all said it
was working.

Full evidence and the four confirmations are in
`2026-08-25-agent-mode-7d-repo-vs-harness.md`.

**Everything in the Result section above that depends on an agent's choice is
withdrawn**: the 0 of 2, the finding that 7b's ambiguity hypothesis "is not
supported", and the table putting a burden on C2's 4/4. The hypothesis was never
tested. A zero from an agent that was never offered the tool is not a zero.

What stands, because it never depended on the agents:

- the capability check — the brain does surface the six refused CRLF pull
  requests, cited, on a direct ask;
- T2 independently reproducing #4142's exact diagnosis and shipping it, having
  reached commit history through `git log` and never the refused attempt;
- the correction to the "C2-style bare prompt" label.

`scripts/agent_call_audit.py` now refuses to score a session that never held the
tool, so this specific mistake cannot be made silently again.
