# Experiment A, run 2 — Icarus → Claude Code

Date: 2026-08-10
Repo: `astral-sh/uv` @ `6253839` — Icarus corpus at `1881d307`
Task: [issue #20917](https://github.com/astral-sh/uv/issues/20917) — workspace
dependency groups no longer additive for members, since 0.12.1.

Chosen to test whether run 1's fabrication (Result 3) recurs. Two deliberate
differences from run 1: the issue body names **no PR** (run 1's body handed me
the culprit), and the issue is labelled `enhancement, configuration` rather
than `bug`, so "yes, deliberate" was a live answer.

Protocol identical: issue title+body only, 4 greps (~6 min), **priors frozen in
writing**, then 2 Icarus questions deliberately mirroring run 1's two shapes —
Q1 intent (reliable in run 1), Q2 code-rule (fabricated in run 1) — then every
claim verified against GitHub and the clone.

## Q1 (intent) — accurate, and corrected my prior

Icarus: the change was **not deliberate**; the maintainer called the previous
additive behaviour incidental and a bug.

Verified in the issue comments — which are *not* in the body I read:
- zanieb (MEMBER): "If we were merging those groups, that sounds like a bug?"
- zanieb: "I was not aware of any group merging happening between the workspace
  root and its members, which would explain how I regressed it :)"

My frozen prior leaned **deliberate** (two code comments state the rule as
intent; 0.12 is a major version). Wrong. Icarus corrected me — as in run 1,
and again on the question that actually determines how you approach the fix.

Bonus: zanieb also wrote "this only worked if your workspace root didn't have a
`[project]` table" — independently confirming the mechanism half of my prior.

## Q2 (code-rule) — accurate. The run-1 failure did NOT recur.

Icarus: root groups are inherited by members but only included when explicitly
requested (to avoid activating unrelated default groups); when requested, a
member's own definition takes precedence over a same-named root group.

Verified verbatim in the cited PRs:
- PR #20840 (MERGED): "Make root groups available to a selected single workspace
  member … **A member definition takes precedence over a same-named root group,
  including an explicitly empty group**."
- PR #20930 (MERGED): "**Inherit root groups only when explicitly requested,
  while preserving the selected member's own default groups.**"

Every clause maps to a sentence someone actually wrote. No synthesis gap.

**And here my cold read was the wrong one.** I concluded from
`Workspace::workspace_dependency_groups()` that root groups apply only when the
root is non-project. That describes an older rule; I had read the *validation*
site (`install_target.rs:560`) and missed the inclusion path PR #20840 added on
2026-07-30 — nine days before the commit I had checked out. Icarus surfaced a
whole cluster of recent related work (#20840, #20930, #20836, #20920) that I
had no idea existed.

## What the two runs together say

4 substantive claims across 2 runs: **3 accurate, 1 fabricated.**

The differentiator is not question shape — it is whether **one source states
the claim**:

| | claim stated verbatim in a cited source? | outcome |
|---|---|---|
| run 1, PR #18176 intent | yes (PR title + label) | accurate |
| run 1, `${PROJECT_ROOT}` | yes (doc comment) | accurate |
| run 1, "`..` escapes root → absolute" | **no** — synthesised across two real sources | **fabricated** |
| run 2, maintainer intent | yes (issue comment) | accurate |
| run 2, root-group precedence | yes (PR body) | accurate |

So run 1's Result 3 was not a systematic failure of the "code-rule" question
type. It was a synthesis failure: when no single indexed chunk answers the
question, the writer composes a plausible rule from adjacent ones, and the
honesty gate passes it because every citation genuinely resolves.

**Revised working rule** (replaces run 1's): don't sort claims by topic. Ask
whether the answer is a *quotation* or a *composition*. Compositions need
verification; quotations mostly don't. Usefully, the interface could expose
this — the writer knows whether it is paraphrasing one chunk or merging several.

## Score on the real question

On both runs, on the decisive question — *was this deliberate?* — Icarus was
right and my cold read was wrong, in opposite directions (run 1: I said
deliberate, it was a regression; run 2: I said deliberate, it was a regression
the maintainer admitted). That is a genuinely repeated result and the strongest
signal so far for the Agent Mode hypothesis: an agent reading only code
systematically over-attributes intent to whatever it finds, because code shows
*what* and never *why*.

Run 2 also cost less: 2 queries, ~6 min cold read, and the verification was
cheap because the claims were quotations.

## Still not done

- Neither run has reached Step 4 (implement) or 5 (full evaluation).
- Interface finding from run 1 stands and got worse: run 2 returned 20 refs per
  answer, all but 2-3 with empty excerpts.
