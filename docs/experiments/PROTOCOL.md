# Agent Mode experiment protocol — the checks that are not optional

Every rule here exists because it was broken once and cost a real run. Nothing
is here on general principle. Follow it for any with/without-Icarus or
does-the-agent-call-it experiment.

The single failure shape behind all of these: **accepting a convenient source
instead of the authoritative one.** The agent's word instead of its transcript,
a handoff doc instead of `git remote -v`, an error string instead of the state
that produced it. Each was cheap to check.

## 1. Tool use is read from transcripts, never from self-report

An agent's account of its own tool calls is not evidence. Measured twice on
2026-08-10: one arm self-reported `TOOL_CALLS: 6` where the harness metadata
for that same run showed `14`, and an earlier task's "did you use Icarus"
answer was accepted at face value until challenged.

    python3 scripts/agent_call_audit.py --project <slug>

Counts real `mcp__icarus__*` `tool_use` blocks in
`~/.claude/projects/<slug>/*.jsonl`. If a claim about tool use is not backed by
that output, it does not go in the write-up.

## 2. A task is only valid if BOTH checks pass at the PINNED commit

Two of five Experiment C tasks were selected wrongly, in two different ways.
Both checks are mechanical; run them before the task is used, not after it
disappoints.

**2a. The bug must actually exist at the commit under test.** Task 3 was
checked against GitHub's LIVE issue tracker; the bug had been fixed by
unrelated work, so the task tested nothing. The live tracker describes today's
HEAD, and the experiment runs against a pinned commit — they are different
repositories for this purpose.

    git -C <clone> log --oneline -1          # confirm the pinned commit
    # then read the actual code path at that commit, not the issue thread

**2b. The mechanism must be the one being tested.** Task 2 was chosen to mirror
the closed-unmerged-PR pattern but was a reverted-then-recommitted change —
fully visible to `git log`, so an unaided agent could reach it and the task
could not demonstrate the asymmetry.

    gh pr list --repo <repo> --state closed --search "<topic>" \
      --json number,title,mergedAt,closedAt
    # a valid rejected attempt has mergedAt: null and closedAt set.
    # If it was merged, or reverted-then-recommitted, pick another task.

## 3. Register the prediction in writing before launching

Not for ceremony: the 2026-08-10 directed-D prediction was wrong, and it was
only interesting BECAUSE it was written down first. A prediction recovered
afterwards is a rationalisation. Record what you expect and why, then record
the result against it whether or not it agrees.

## 4. Report the direction of every result, including the inconvenient ones

Efficiency has gone both ways across runs (slower, slower, faster). Never
represent it as a consistent win. Where a control arm did BETTER work than the
experiment arm — as it did on pure code reading in directed-D — say so in the
result, not in a footnote.

## 5. Before asserting anything about repo state, check the state

`git remote -v` before any claim about CI, remotes, or deployment. A doc
describing what was true at some past session is not the current state; the
handoff explicitly said the deploy sync was "not built" long after
`.gitlab-ci.yml` was built. When a tool returns a puzzling error, read the
state that produced it (mint a session, query `/status`) rather than retrying
and inferring.

## 6. Say which arm is directed

"Unprompted" means the prompt never named Icarus or a tool. If the run was
directed, the write-up says directed. `agent_call_audit.py` flags a session as
directed when a user message mentions Icarus by name — coarse, and deliberately
biased toward calling a session directed, so the unprompted number under-claims
rather than over-claims.

## 7. Prove the agent HELD the tool before scoring it as not using one

Nine sessions across three runs (7b, 7c, 7d, 2026-08-24 and 2026-08-25) were
reported as zero unprompted calls. In every one of them the agent had never been
offered the Icarus tools at all: headless `claude -p` did not load the project's
MCP server. Three write-ups, two of them reasoning at length about why agents do
not reach for the tool, rested on agents that could not have.

    python3 scripts/agent_call_audit.py --project <slug>
    # a session that never held the tool now prints
    #   TOOL NOT AVAILABLE — not a measurement
    # and is excluded from the denominator

**Every check from outside the session said it was fine** — `claude mcp list`
printed `icarus: ✔ Connected`, and the server answered a hand-piped
`initialize`/`tools/list` handshake correctly. Only the transcript was right.
That is rule §1 one layer down: the authoritative record of what an agent held
is the same file as the record of what it did.

A zero and a blank look identical in a results table and mean opposite things.
If the transcript never names the tool, the run measured nothing — say that, and
do not interpret it.

## 8. A result that matches the prediction gets the same scrutiny as one that does not

7d predicted 0 of 3 and returned 0 of 3. The agreement is exactly why nobody
would have looked again, and the run was invalid. Confirmation is not
verification: run §5's read-the-state check on a result you expected, not only on
one that disappoints.

## 9. One task per session, and verify the tree is clean between them

C2 reported 4 of 4 and its own plan listed session reuse as invalidating; all
four tasks had in fact run in one session. Re-run with four fresh sessions
(2026-08-25) it measured **1 of 4**. Session reuse was worth three calls.

    ls ~/.claude/projects/<slug>/*.jsonl   # one file per task, or it was one session

Resetting the working tree between tasks is not enough on its own. In the re-run,
task 1 verified its fix by stashing it and never restored it; task 2's agent
found the stash, popped it, and worked with another agent's edit in its tree —
and task 2 was the one session that called the tool. Check `git stash list` as
well as `git status`, and record the tree state per task.
