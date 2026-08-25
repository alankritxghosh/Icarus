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
