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

## Task 2 — #1511 fragment filter on newer SQLite

**Call behaviour: a second unprompted `get_change_context` call**, transcript-
verified (`2 calls  unprompted`, one session). No nudge present. So on call
behaviour the score is 2 for 2.

**Task validity: INVALID, and the error is mine.** PROTOCOL §2a requires the
bug to be proven present at the commit under test. I wrote, in the plan: "local
sqlite is 3.53.3, so the version-dependent bug is reachable here." That is
backwards. The SQLite defect was fixed upstream in **3.51.2**, so 3.53.3 is
precisely a version where it CANNOT reproduce. I inferred reachability from a
version string instead of executing anything — the same failure class as
Experiment C's task 3, in the protocol written to prevent it, one day later.

The agent found this itself: running both the `EXISTS(A UNION B)` form and the
`OR` rewrite against sqlite 3.51.0 and 3.53.3, all four combinations returned
identical, correct rows. It applied the rewrite anyway. The change is a no-op
against a bug that is not present, and its outcome is not usable data.

Call behaviour and task validity are independent, and only the first survives
from this task.

## Finding — Icarus called a refused pull request's approach "the accepted fix"

Icarus's answer: *"The **accepted** fix in llm/cli.py is to replace the single
EXISTS clause containing a UNION with two separate EXISTS clauses joined by an
OR operator"*, citing `issue:1511` and `pr:1549`.

`pr:1549` is listed as a rejected attempt **in the same payload**. Nothing in
either cited chunk says any fix was accepted — "accepted" is the writer's
inference, and the honesty gate cannot catch it, because both citations resolve
and the claim is about what the evidence MEANS.

It is also, as it happens, TRUE — see the next section. Icarus could not have
known that from what it cited. A right answer for unsupported reasons is still
the failure mode this project exists to prevent, and it is worth more as a
recorded example than a hundred correct citations.

**This is exactly the false negative in `rests_on_rejected` (`a2c5712`).** That
flag marks a claim only when EVERY citation is a closed-unmerged PR, which was
called conservative when it shipped that morning. Here the claim cites one
refused PR plus one issue, so the flag stayed silent on a sentence describing a
refused pull request's approach as accepted. The conservatism has a concrete
cost, and this is what it looks like.

## Finding, stronger — the closure comments say the approach WON

Task 1's finding repeated, with explicit evidence this time
(`gh pr view --json comments,reviews`):

- **#1512** — simonw: *"I'm going to use the fix from: #1571"*
- **#1549** — simonw: *"I'm going to use the fix from: #1571"*
- **#1571** — also closed unmerged: *"Landed a version of this that resolved
  the conflicts here: `9efdfa6`"*
- **#1511** closed with: *"Turns out this was a SQLite bug that was fixed in
  3.51.2"*

So all three "refused attempts" were the approach that was adopted. Two were
closed as duplicates OF the third, and the third was closed because it had
already been landed by hand.

Across tasks 1 and 2, **seven pull requests that `rejected_attempts` reports as
closed-unmerged, and not one was refused on its merits.** Four were swept when
the maintainer fixed the issue himself; three were the winning approach.
`closed_unmerged` is a real, honest, checkable fact — and as a proxy for
"someone tried this and it was rejected", the measured hit rate in this sample
is zero.

That does not make the feature worthless: in directed-D it demonstrably stopped
an 8th duplicate submission, and "someone already did this, do not send it
again" is genuinely actionable — it just is not the same claim as "this
approach was rejected". The description says it reports only THAT a PR was
closed, which stays true. The gap is between that literal statement and what
any reader concludes.

## Tasks 3 and 4 — re-validated BY EXECUTION after the task-2 error

Both were originally validated by reading code, which is what failed on task 2.
Re-done by executing the pinned source (`git show 94769b8:llm/cli.py`), with the
tasks-1/2 edits confirmed not to touch either path.

**Task 3 (#1583) — VALID, reproduced.** Executing the pinned template-resolution
block with `--schema from_cli` already set and a template defining
`from_template`:

    schema in effect after template resolution: ['from_template']

The CLI argument is silently discarded. Note the two lines immediately above it
COMBINE template and CLI fragments, so the override is inconsistent with its own
neighbours.

**Task 4 (#1580) — VALID, reproduced.** Executing the pinned toolbox-listing
loop with a toolbox exposing no tools renders exactly `'Dynamic:\n'` — a bare
header with nothing under it. Confirmed faithful to the real report, which shows
`MCP:` printed empty because that toolbox only yields tools when constructed
with a URL.

Honest limit: this proves the RENDERING defect from pinned source. Reproducing
it through the real CLI in this clone would need the `llm-mcp-client` plugin
installed, which was not done.

## Running score

| | task 1 (#1466) | task 2 (#1511) | task 3 (#1583) | task 4 (#1580) |
|---|---|---|---|---|
| unprompted call | yes | yes | not run | not run |
| task valid | yes | **no (my error)** | yes (executed) | yes (executed) |

2 of 2 sessions called Icarus unprompted with no nudge, against a 0/11 baseline
and Experiment C's 0-of-4 WITH a nudge. The registered prediction (0–1 of 4,
expected to fail) is under water on call behaviour. It is not yet decided —
n=2, and neither task's fix outcome has been shown to be better BECAUSE of the
call.
