# Experiment C2 — results (COMPLETE: 4 of 4)

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

## Task 3 — #1583 template `schema_object` overrides `--schema`

**Third unprompted call** (`3 calls  unprompted`, transcript-verified). Task
valid, reproduced by execution before the run.

The fix the agent shipped is the right one — `if template_obj.schema_object and
not schema:` — and it justified the shape correctly: every other setting in that
same block already defers to what the user typed (`extract`, `if template_system
and not system`, `-o` options), and `--schema-multi` is folded into `schema`
before this point so one guard covers both flags. It also added a red→green pair
(the new tests fail on unpatched code) plus a test that the template schema still
applies when no flag is passed, so the fix is not just disabling the feature.

**This is the best result of the run, and the reason is what Icarus returned.**
The answer cited three refs — `issue:1583`, `pr:1584` (closed unmerged) and
**`pr:1588` (MERGED)**. Verified independently: #1588 is real, merged
2026-08-03, "Fix llm openai endpoint ignoring --schema when template also
defines schema_object". #1584's own closure comment reads *"This looks to be a
duplicate of: #1588"*.

So Icarus supplied the merged precedent, not just the refusal — the agent did
not find #1588 by searching. That gave it what neither `git log` nor
`rejected_attempts` alone could: the approach is ESTABLISHED in this codebase,
and the closed PR was a duplicate of the one that landed. Its own summary drew
exactly the right line: the approach is established, "I don't know why #1584
specifically was closed."

**A wrinkle worth recording.** The second claim reads "This behavior **has been
corrected** to ensure consistency with other template settings". At the pinned
commit it has NOT been — #1588 corrected the `llm openai endpoint` path, not
`cli.py:742`. A reader could take that sentence as "already fixed here" and skip
the change. It is labelled `composed` (citing `pr:1584` + `pr:1588`), which is
the label the tool description tells an agent to verify, and this agent did
verify it. The label did its job; the sentence is still loose.

Note also that `rests_on_rejected` correctly did NOT fire on either claim here —
both cite a merged PR alongside the closed one. That is the rule working as
intended, and is the same mechanism that produced the task-2 false negative:
identical logic, opposite verdicts, because the evidence differed.

## Task 4 — #1580 `llm tools` shows dynamic toolboxes as a bare header

**Fourth unprompted call.** Task valid, reproduced by execution beforehand.

The agent kept the toolbox listed and explained the emptiness, and separately
made toolbox INSTANCES list their real tools (`.tools()` for an instance,
`method_tools()` for a class) — noticing that `llm tools 'MCP("...")'`, the
obvious next command, also printed a bare header because `method_tools()` is a
classmethod that never sees the instance's registered tools.

**It knew #1581 had been closed, and deliberately went the other way**, on the
stated reasoning that dropping empty toolboxes from the listing destroys the
discoverability the command exists for.

**Independently verified: upstream agrees with the agent, not with #1581.** The
real fix (`1b99533`, "llm tools now displays dynamic toolboxes usefully, closes
#1580") rewrites `introspect_tools` to dispatch on instance-vs-class exactly as
the agent did — same structure, same reason. #1581's approach (skip empty
toolboxes) is not what landed, and the #1580 thread shows the maintainer working
toward instantiating toolboxes and listing their tools.

**So this is the case where `rejected_attempts` had genuine predictive value.**
Unlike tasks 1–3, here "closed unmerged" really did mean "this approach was not
adopted", and knowing it steered the agent to the solution upstream chose.

## The closed-unmerged tally across the whole run

Nine pull requests surfaced as `rejected_attempts` across four tasks. What each
closure actually meant, from the closure comments and commits:

| task | PRs | what "closed unmerged" meant |
|---|---|---|
| 1 | #1467 #1469 #1487 #1544 | maintainer fixed it himself, **same approach**; four swept in 29s with no comment |
| 2 | #1512 #1549 #1571 | **the winning approach** — two closed as duplicates of the third, the third landed by hand |
| 3 | #1584 | duplicate of **merged** #1588, same approach |
| 4 | #1581 | **genuinely not adopted** — "I fixed this another way" |

**One in nine corresponded to an approach that was actually not taken.** The
other eight were the right approach arriving by another route. The signal is
honest and it is useful — in task 4 it steered correctly, and in directed-D it
stopped an 8th duplicate — but "closed unmerged" answers *"do not send this
again"* far more often than *"this idea was wrong"*, and those recommend
different next actions.

## Conclusion

**My registered prediction was wrong.** I predicted 0–1 of 4 unprompted calls
and argued the interface was never the bottleneck. The result is **4 of 4**,
with no `CLAUDE.md` nudge, against a 0/11 baseline and Experiment C's 0-of-4
*with* a strong nudge. Alankrit's read — that C's nudge was badly written rather
than the approach being structurally doomed — is the one the evidence supports.

What changed was not the interface but what the description SAYS: leading with
the capability the agent cannot otherwise reach, and triggering on observable
events ("you are about to edit") instead of on the agent's own estimate of
whether a task is important enough. The prior wording asked a coding agent to
judge its task "meaningful", and it reliably judged it wasn't.

Outcome influence, on the three valid tasks: task 3 (supplied merged precedent
#1588, unreachable by search) and task 4 (steered away from the approach that
was not adopted) both changed the work. Task 1's contribution was a correct
warning about PRs that turned out not to be refusals. So 2 of 3 clearly, 3 of 3
if you count a warning that was right in form.

**This does not retire the deterministic-trigger option.** 4 of 4 in one
repository, one agent, one session's worth of tasks, all bug-fix shaped and all
in a repo whose history is unusually rich in duplicate attempts. A description
persuades; a hook guarantees. What this run establishes is that persuasion was
not exhausted, which is what Alankrit said and I doubted.

## Queued, deliberately not done during the run

1. Disclose in the tool description that a closed pull request may mean the
   change was made another way rather than refused — now backed by 8 of 9.
2. `rests_on_rejected`'s every-citation rule produced a real false negative in
   task 2 ("the accepted fix", citing one refused PR plus an issue). Decide
   whether to relax it to any-citation or to leave it and rely on `composed`.
3. The `llm` fixes themselves are uncommitted in the clone. Four of them target
   issues whose PRs were closed; per the tally above, read the closure threads
   before submitting anything upstream.

## Running score

| | task 1 (#1466) | task 2 (#1511) | task 3 (#1583) | task 4 (#1580) |
|---|---|---|---|---|
| unprompted call | yes | yes | yes | yes |
| task valid | yes | **no (my error)** | yes (executed) | yes (executed) |
| changed the outcome | warned of 4 prior attempts | no (invalid task) | **yes — supplied merged precedent #1588** | **yes — steered AWAY from the refused approach** |

**3 of 3 undirected sessions called Icarus with no nudge**, against a 0/11
baseline and Experiment C's 0-of-4 WITH a strong nudge. My registered
prediction (0–1 of 4, expected to fail) is refuted on call behaviour; I was
wrong, and the direction Alankrit chose is doing better than I argued it would.

What is NOT yet established is that the calls improve outcomes. Task 1's
influence was advisory (a warning, correct but about PRs that turned out not to
be refusals), task 2 is invalid, and only task 3 shows the tool supplying a
fact — merged precedent #1588 — that measurably shaped the work and that the
agent would not otherwise have had.
