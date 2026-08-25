# Experiment 7b — does the C2 result hold on a repository Icarus has never seen?

Registered **before any task is run**, per `docs/experiments/PROTOCOL.md` §3.
Nothing below may be edited after the first task starts.

## What is being tested

C2 (2026-08-11) measured **4 unprompted Icarus calls out of 4 tasks**, against a
0/11 baseline, after `get_change_context`'s description was rewritten to trigger
on observable events. That number is load-bearing: it appears on the site, in X
replies, and in the shipped MCP tool description.

**Its measured window is narrow.** Four tasks, one session, one repository
(`simonw/llm`) — the same repository the Icarus corpus is pinned to and the same
one used in Experiment C. [[Unknowns]] already asks whether unprompted calls are
durable outside it. 7b is that question.

**One variable changed from C2: the repository is one Icarus has never indexed.**
Tool description as shipped today. No `CLAUDE.md` nudge, same as C2.

## Setup

- Repo: **`Textualize/rich`** @ `9d8f9a372cc5916fd4781fec207ced7ddac2f08f`.
  Never indexed by Icarus — not in the onboarding probe's ten
  (`sqlite-utils`, `click`, `requests`, `cobra`, `glow`, `execa`, `shellcheck`,
  `lazygit`), and not `llm`, `uv`, `meilisearch-swift`, `media-chrome`,
  `sqlite-utils` or `firecrawl` from prior runs.
- Clone: `/Users/alankritghosh/JARVIS /experiment-7b-rich`. **No `CLAUDE.md`.**
- Brain: local `demo.server`, connected to `Textualize/rich`. The MCP adapter
  reaches it through the documented `ICARUS_BRAIN_URL` development override
  (`demo/mcp_server.py:290`), not the Mac app.
- Agent: real headless `claude -p` runs in the clone, so the transcript lands in
  `~/.claude/projects/<slug>/*.jsonl` where `scripts/agent_call_audit.py` reads
  it. A subagent spawned inside the Icarus session would inherit that session's
  MCP config and point at the wrong repository.
- Counting: **transcripts only.** No self-report, per PROTOCOL §1.

## Tasks — both validated per §2 BEFORE selection

### Task 1 — CRLF handling in `Text.from_ansi()`
- **§2a, executed not inferred:** at the pinned commit,
  `Text.from_ansi('line one\r\nline two\r\n').plain` returns `'\n\n'`. The text
  is not merely mis-split, it is **gone**. Behaviour confirmed present.
- **§2b:** **six** genuine closed-unmerged pull requests on this exact
  behaviour — #4159, #4145, #4138, #4113, #4103, #4099 — every one
  `state=CLOSED, mergedAt=null`, all human-authored. None is a
  reverted-then-recommitted change.
- Why it is a fair test: an agent fixing this is writing the **seventh**
  attempt, and `git log` shows none of the previous six.

### Task 2 — `ReprHighlighter` merges adjacent markup tags
- **§2a, executed:** at the pinned commit, highlighting `<tag1> <tag2>` yields
  spans `[(0,1,tag_start), (1,5,tag_name), (5,12,tag_contents), (12,13,tag_end)]`.
  The `tag_contents` span runs 5..12, swallowing the second tag's opening — two
  adjacent tags read as one. Confirmed present.
- **§2b:** #4142, `state=CLOSED, mergedAt=null`, human-authored.

### Rejected during validation, and this is the point of §2
- **`FileProxy.isatty()` (#4074)** — rejected. `FileProxy` already defines
  `isatty` and it already delegates to the proxied file at the pinned commit.
  The bug is NOT present, so the task would have tested nothing. This is the
  same failure class as C's task 3 and C2's own task 2, caught here by
  executing the check instead of reading the PR title.
- **`Segment._split_cells` (#4146, #4066)** — rejected. Could not reproduce the
  claimed infinite loop; wide-character splitting behaved as documented.
  Unreproduced means unvalidated, and unvalidated means unused.
- **`__notes__` chaining (#4067)** — rejected, needs `pygments`, and adding a
  dependency to make an experiment run is not a neutral act.

## REGISTERED PREDICTION

1. **I expect 1 or 2 calls out of 2 tasks, and I expect this to be WEAKER than
   C2's 4/4.** Confidence: medium.
2. **Reasoning for the drop:** C2 ran on `simonw/llm`, which is the corpus the
   tool was tuned against and the repo used in Experiment C. On an unseen
   repository the tool has no advantage it did not earn from the description
   alone. If 4/4 was partly an artefact of that familiarity, 7b is where it
   shows.
3. **If it fires, I expect Task 1 over Task 2.** Six prior attempts is the exact
   shape the rewritten description names, and CRLF handling looks ambiguous
   enough from the code alone to prompt a check. Task 2's regex bug looks
   solvable by reading one pattern.
4. **A 0/2 is a real finding and gets reported as plainly as a 2/2.** It would
   mean the 4/4 does not generalise and every public statement resting on it
   needs softening in the same pass, per Work Queue §7b.
5. **Two tasks cannot confirm 4/4.** The most this run can do is fail to refute
   it, or refute it. Stated now so the write-up cannot quietly overclaim.

## Result — 0 of 2, and the run is weaker evidence than it looks

    81869950    0 calls  unprompted -
    f523902e    0 calls  unprompted -
    2 sessions, 2 undirected; 0 of those called Icarus (0 calls total)

Transcript-verified via `scripts/agent_call_audit.py --project experiment-7b-rich`.
Both sessions flagged undirected, so neither prompt leaked the tool's name.

**Both agents did competent work.** Task 1 traced the cause to
`AnsiDecoder.decode_line` (`rich/ansi.py:150`), correctly identified that
`line.rsplit("\r", 1)[-1]` discards everything before the last carriage return,
reasoned that a trailing CR carries no overwrite semantics, fixed it, checked
mid-line CRs still overwrite, checked SGR handling, added a test, ran 138 tests.
Task 2 rewrote the tag regex, checked the alternation was anchored against
catastrophic backtracking, added a regression row, and — the detail worth
noting — ran the full suite and correctly separated 9 pre-existing environment
failures from its own change.

Task 1's fix is, as far as `git log` can show, novel work. It is the **seventh**
attempt. Six closed-unmerged pull requests sat in Icarus one tool call away.
This is directed-D's finding again: better first-principles reading, and it
would still have shipped the duplicate.

### Prediction versus outcome

| # | Registered | Outcome |
|---|---|---|
| 1 | 1 or 2 calls of 2, weaker than C2's 4/4 | **WRONG on the number: 0 of 2** |
| 3 | If it fires, Task 1 over Task 2 | untestable, nothing fired |
| 4 | A 0/2 is a real finding, report it plainly | doing that here |
| 5 | Two tasks cannot confirm 4/4 | held |

### The design flaw, stated before any interpretation

**I set out to change one variable and changed at least three.** C2's own plan
says "C2 is C with one variable changed", and this run does not meet that bar.

1. **Repository** — intended. `Textualize/rich`, never indexed.
2. **Prompt richness — NOT intended, and it is the serious one.** C2's prompts
   were bare one-liners: *"In this repo, schema_dsl() crashes with an IndexError
   when a field has no name before the colon. Fix it."* No reproduction, no
   mechanism. Mine handed over a runnable reproduction, the exact wrong output,
   and for Task 2 the literal span offsets. **C2's registered prediction said
   calls would fire on tasks "where the code alone looks ambiguous" — and I
   removed the ambiguity before the agent started.** An agent given a
   reproduction has no open question to take to a tool.
3. **Harness** — C2 used fresh interactive sessions; this used headless
   `claude -p`. Tool-exploration behaviour under `-p` is not measured anywhere.

Also unmeasured: the model version differs (CLI 2.1.238, 2026-08-24) from
C2's 2026-08-11 run.

**So this run does NOT refute 4/4.** It cannot: [[Learning]] § An uncontrolled
variable makes a comparison worthless applies directly, and I wrote the
uncontrolled variable into the prompts myself.

### What it DOES establish

One thing, and it is worth having: **on a repository Icarus has never seen,
with a well-specified task and no nudge, two capable agents each solved a bug
from first principles and neither consulted recorded history — including on a
bug six people had already tried to fix.** That is a real observation about
when the tool is NOT reached for, and the shape is consistent with C's 0/4
rather than C2's 4/4.

The live hypothesis it suggests, untested: **the rewritten description fires on
ambiguity, not on the observable events it names.** C2's agents had to
investigate before they could act; mine were handed the investigation. If that
is right, the tool is reached for when an agent does not know what to do, and
the "about to edit a file" trigger is doing less work than the 4/4 implied.

### What a clean re-run needs

- C2-style bare prompts. `"In this repo, Text.from_ansi() mishandles CRLF line
  endings. Fix it."` and nothing more.
- Same harness as C2 (interactive sessions), or headless for BOTH arms.
- Four tasks, so a single agent's habits do not dominate.
- Both repos, so repo-familiarity separates from prompt-richness.

Until that runs, **the honest public position is unchanged from what
`Work Queue` §7b already required: the 4/4 rests on four tasks, one session,
one repository.** Nothing here licenses softening it and nothing here licenses
repeating it more confidently.

---

## WITHDRAWN 2026-08-25 — the agents never had the tool

Appended, not edited, per the append-only rule.

Both sessions in this run (`81869950`, `f523902e`) show **zero** occurrences of
`mcp__icarus__` anywhere in their transcripts, including the tool catalogue
Claude Code records. Headless `claude -p` did not load the project's MCP server.
The same defect silently invalidated 7c and 7d; the evidence, four independent
confirmations and a validated positive control are in
`2026-08-25-agent-mode-7d-repo-vs-harness.md`.

**So the 0 of 2 above is not a measurement**, and neither is the design-flaw
analysis built on it. This run's own verdict — "it does NOT refute 4/4" — was
right for a reason it did not know: there was nothing in it to refute anything
with.

The live hypothesis it proposed ("the description fires on ambiguity, not on the
observable events it names") remains **completely untested**. 7c set out to test
it and failed the same way.

What still stands: both tasks were genuinely §2-validated, both agents did
competent first-principles work, and Task 1's fix was the seventh attempt at a
bug six people had already had closed — none of which depends on which tools the
sessions held.
