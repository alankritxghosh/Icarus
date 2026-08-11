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
