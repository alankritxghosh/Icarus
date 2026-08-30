---
status: DRAFT — not published
source: docs/experiments/PROTOCOL.md
        docs/experiments/2026-08-10-agent-mode-exp-c.md
        docs/experiments/2026-08-11-agent-mode-exp-c2-results.md
        docs/experiments/2026-08-10-agent-mode-exp-d-directed.md
target: ~1,300 words
checked: every number below read out of the experiment records, 2026-08-23
---

# Why the rules you write down are the ones you break

And I broke the most important one again, one day after writing it down.

---

I have been running measured experiments on whether coding agents consult an
external source of repository history before they write code. Not opinions about
it. Runs, with pinned commits and registered predictions.

The experiments produced a protocol. It has six rules and it opens with a
sentence I had to earn:

> Every rule here exists because it was broken once and cost a real run. Nothing
> is here on general principle.

That constraint is the only reason the document is worth anything. A checklist
assembled from good intentions is a wish list. This one is a scar map, and each
rule names the run it cost.

Here are the three that generalise past my project, and then the part where the
protocol failed to save me from itself.

## Rule 1: an agent's account of its own tool use is not evidence

The first thing I wanted to measure was simple. When an agent is working on a
task, does it call the tool?

The obvious way to find out is to look at what the agent did, and the convenient
way is to ask it. I asked it.

On 2026-08-10 one arm reported `TOOL_CALLS: 6`. The harness metadata for that
same run showed **14**. Not a rounding difference, not a definitional
disagreement about what counts. The agent's summary of its own behaviour, minutes
old, was wrong by more than a factor of two, and it was wrong in the direction
that made its narrative tidier.

An earlier task's "did you use it" answer had been taken at face value until
someone pushed back.

So rule 1 is that tool use is read from the transcript, never from self-report.
There is a script now. It counts real tool-use blocks in the persisted session
files. If a claim about tool use is not backed by that output, it does not go in
the write-up.

The uncomfortable generalisation: an agent asked to describe its own process
produces a plausible account of a process. That account is generated the same
way everything else it says is generated. It is not a log. It is prose about a
log, and nothing checked it against the log.

## Rule 2: the bug has to exist at the commit you are testing

This is the one that cost the most, and it failed in two different ways in a
single experiment.

The setup: give an agent a real bug in a real repository, pinned to a specific
commit, and see whether it reaches the right conclusion with and without help.

**First failure.** One task was validated against the project's live issue
tracker. The issue was open, the discussion was substantive, everything looked
right. But the bug had already been fixed by unrelated work. The live tracker
describes today's HEAD; the experiment runs against a pinned commit. For this
purpose those are two different repositories, and I had checked the wrong one.
The task tested nothing.

**Second failure, same experiment.** Another task was chosen to mirror the
pattern I care about most: work that was attempted and refused, which leaves no
trace in the working tree. Except this one had been reverted and then
recommitted, which is fully visible to `git log`. An unaided agent could reach it
by ordinary means, so the task could not demonstrate the asymmetry it was
selected to demonstrate.

Two of five tasks, wrong in two different ways, both catchable by commands that
take seconds. Rule 2 now names both commands.

## Rule 3: register the prediction before you launch

This one sounds like ceremony until it pays.

I ran a paired comparison where one agent could consult the history tool and one
could not, and I wrote down what I expected first. I expected the consulting arm
to win.

It did not, exactly. The control arm did **better first-principles code reading**
than the arm with the tool. That is the inconvenient half and it is in the
result, not a footnote.

The other half is that the control would still have shipped the eighth duplicate
of a change seven people had already attempted. One directed call surfaced all
seven and flipped the recommendation to *do not write this*.

Both facts are true. I only know the first one is interesting because the
prediction was on paper before the run. A prediction recovered afterwards is a
rationalisation, and it always agrees with the result.

## The part where the protocol did not save me

I wrote all of that down on 2026-08-10.

On 2026-08-11 I ran the next experiment. One of its four tasks turned on a
version-dependent bug in SQLite. In the plan, in writing, I wrote: *local sqlite
is 3.53.3, so the version-dependent bug is reachable here.*

That is backwards. The defect was fixed upstream in **3.51.2**. Version 3.53.3 is
precisely a version where it cannot reproduce.

I had inferred reachability from a version string instead of executing anything.
That is the exact failure class as the first task-selection miss, in the protocol
written one day earlier to prevent it, and I walked into it while holding the
document.

The agent found it. It ran both query forms against 3.51.0 and 3.53.3, got
identical correct rows from all four combinations, and applied the fix anyway.
The change is a no-op against a bug that is not present. The task is invalid and
its outcome is not usable data.

I marked it invalid in the results and left it in the table, because a run with
three usable tasks and one honestly voided is worth more than a run with four
that quietly includes a broken one.

## What I actually think this means

**A protocol is not a defence, it is a diagnosis.** Writing the rule down does
not install it. I had the document open and still reached for the convenient
signal, because the convenient signal answers in one second and the authoritative
one takes a minute. Rules do not compete with laziness on equal terms.

**Every one of these failures has the same shape.** Accepting a convenient source
instead of the authoritative one. The agent's word instead of its transcript. An
issue thread instead of the code at the pinned commit. A version string instead
of an execution. That single sentence now opens the protocol, because six
specific rules are harder to carry into a new situation than one pattern.

**Publish the invalid task.** The strongest thing in these records is not the
headline result — the tool went from zero unprompted calls in eleven sessions to
one out of four independent sessions after I rewrote its description to name
observable events rather than describe its contents. (A same-day re-run once
found four sessions in a row had shared one session rather than run independently
— retired that number and kept the honest one.) That number is smaller than I'd
like, and a reader has no way to know whether I am telling them about the runs
that worked.

They can tell, because the write-ups also contain the run where I contradicted my
own protocol one day after publishing it. The invalid task is what makes the
valid ones legible. A results document with no inconvenient entries is not a
clean record. It is an unfinished one.
