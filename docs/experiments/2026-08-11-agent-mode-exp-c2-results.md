# Experiment C2 — results (IN PROGRESS: task 1 of 4)

Plan and registered prediction: `2026-08-11-agent-mode-exp-c2-plan.md` (`1853e6f`),
committed before this run started. Protocol: `PROTOCOL.md`.

## Task 1 — #1466 `schema_dsl()` IndexError

Prompt given verbatim, naming no tool and no history:

> In this repo, schema_dsl() crashes with an IndexError when a field has no
> name before the colon, e.g. "name, : int". Fix it.

**Result: one UNPROMPTED `get_change_context` call**, verified from the
transcript, not from the agent's account of itself (PROTOCOL §1):

    $ python3 scripts/agent_call_audit.py --project experiment-c2
    8ddbaf3a    1 calls  unprompted get_change_context
    1 sessions, 1 undirected; 1 of those called Icarus (1 calls total)

Against a baseline of **0/11** undirected sessions under the previous
descriptions, and against Experiment C's 0-of-4 *with* a strong `CLAUDE.md`
nudge. There is no nudge in this clone.

The call changed the output. Unasked, the agent closed with: this bug is
#1466, four PRs fixing it have been closed without merging, "I don't have the
maintainer's stated reason for the closures, so I can't tell you whether the
objection was to the approach or something else — but a fifth identical PR
seems unlikely to land without checking the closure comments first."

That is the intended behaviour exactly: it reported WHAT was refused, declined
to invent WHY, and pointed at where the reason lives.

Also observed live: `rests_on_rejected: true` on a `composed` claim — the flag
shipped that morning (`a2c5712`), doing its job in a real session.

**Honest limits on this data point.** n=1 of 4. It is the task whose bug I
proved by execution, i.e. the most clear-cut one. And one run cannot separate
"the description works" from "this particular task invited a history question."
Tasks 2–4 decide it; the registered prediction (0–1 of 4, expected to fail) is
not yet refuted, but it is under pressure.

## Finding — "refused" and "already done" are the same signal, and they mean
opposite things

Following up on those four closures (`gh pr view --json comments,reviews`, then
the issue timeline) produced a result worth more than the task:

- **None of the four PRs has a single comment or review.** #1544, #1467, #1469
  and #1487 were closed at 22:33:20, :41, :45 and :49 on 2026-07-30 — all four
  inside 29 seconds, with issue #1466 closed 14 seconds earlier. A bulk sweep,
  not four review decisions.
- The maintainer had commented on the issue: *"This is an invalid schema
  string... I'm going to have it raise a `ValueError` with a better error
  message"*, then fixed it himself in commit `8dfd6b4` and swept the community
  PRs closed behind it.
- **`llm/utils.py` at HEAD today carries essentially the same fix the agent
  wrote** — `if not field_parts: raise ValueError(...)`.

So the approach was never rejected. It was right, and the maintainer shipped it
himself.

**Why this matters for `evals/attempts.py`.** The signal is honest — those pull
requests really were closed without merging, and the code says only that. But
the inference a reader draws from it is *this approach was refused*, and here
the truth was *this was already done by someone else*. Same evidence, opposite
implication for what to do next, and nothing distinguishes them without reading
the closure timeline that Icarus deliberately does not interpret.

This is a distinct failure mode from the disclosed one — the tool description
already warns that a closed PR can be irrelevant (measured up to one in three).
This one is worse, because the PR is perfectly *relevant*: it is about exactly
your change, and still means the opposite of what it looks like.

The agent's own wording survived this correctly ("I can't tell you whether the
objection was to the approach"), which is evidence the honesty discipline holds
where the raw signal misleads. A reader skimming `rejected_attempts` alone would
not have been so lucky.

### Deliberately NOT fixed yet

The obvious response is to disclose this in `get_change_context`'s description.
**Doing that now would invalidate tasks 2–4**: the description is the single
variable under test, and changing it mid-run makes the remaining tasks
uninterpretable. Queued for after the run:

1. Disclose in the tool description that a closed pull request may mean the
   change was made another way, not that the approach was refused.
2. Consider whether it is cheaply detectable — a closed PR whose linked issue
   was closed COMPLETED within seconds of it is a strong signature of exactly
   this sweep, and both facts are already fetchable. Do not guess a reason;
   report the shape and let the reader look.

## Tasks 2–4

Not yet run. Prompts are fixed in the plan; run each in a fresh session in
`/Users/alankritghosh/JARVIS /experiment-c2-llm`, then re-run the audit.
