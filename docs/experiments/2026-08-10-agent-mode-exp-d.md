# Experiment D — control vs. Icarus, on two fresh tasks

Date: 2026-08-10
Repo: `astral-sh/uv` @ `a50af60f` (the freshly re-ingested corpus)

## Design, and what it cannot measure

Paired **within-task**: control arm (code only, cold, searches counted) run
first and **frozen in writing**, then the Icarus arm on the same task, then
every claim from both arms verified against GitHub.

Control-first is the honest ordering — the control cannot benefit from Icarus.
But the Icarus arm IS contaminated by having just read the code, so:

- **Measurable here:** incorrect assumptions, changed conclusions, prevented
  wrong approaches, the control's real search cost.
- **NOT measurable here:** time-to-implementation or search savings in the
  Icarus arm. Those need two uncontaminated agents (subagents or two
  sessions), which this run deliberately did not use.

Two tasks were chosen to *disconfirm*, not confirm, with predictions
registered before asking:

- **Task A #20744** (backslash continuation before a version specifier) — a
  mechanical parser bug with no intent question. **Predicted: Icarus adds
  LITTLE.** This was the negative control.
- **Task B #20818** (prerelease constraint ignored in `explicit` mode) — a
  regression tied to a named PR. **Predicted: Icarus adds A LOT.**

## Task A — the prediction was WRONG, and that is the finding

Control (4 searches, ~5 min): root cause is
`parse_requirement_and_hashes` handing PEP 508 a raw
`&content[start..end]` slice that still contains the `\`, even though the
scanner skips escaped newlines. Fix: strip escaped newlines before parsing.
**"Would I write code? YES, immediately."**

Icarus surfaced what no amount of code reading could:

- **PR #20787 "Support continued version specifiers in requirements files" —
  CLOSED.** Its stated fix is verbatim mine: "remove escaped physical line
  breaks before PEP 508 parsing".
- Closed by a MEMBER with: *"This is the same as #20751. We need to understand
  the actual supported behavior of pip before we can make any changes here."*
- So **#20751 was a prior attempt too** — mine would have been the third.
- Both carry the repo's AI-policy bot comment.

**The correct action is not to write the fix.** Maintainers have explicitly
blocked this change pending research into pip's real behaviour. The control
arm would have produced a third rejected PR.

This kills the negative control, and reveals a category runs 1-3 never
touched: the decisive history was not *intent* but **prior attempts**. A
"purely mechanical" bug with an obvious fix is exactly where an agent is most
confident and most likely to duplicate rejected work — because the code cannot
say "two people already tried this and were told no."

One discrepancy worth recording: Icarus's mechanism sentence paraphrases
#20787's own root-cause text ("the following version specifier was omitted"),
which differs subtly from my cold diagnosis (the backslash is retained). The
reported error is `found '\'`, which only happens if the backslash reaches PEP
508 — so **my diagnosis appears more consistent with the symptom than the
quoted PR's**. Icarus faithfully quoted a source that may itself be imprecise.
Quotation guarantees provenance, not correctness.

## Task B — right verdict, fabricated reason, missed the resolution

Control (8 searches, ~9 min): `explicit_packages` is fed by
`manifest.candidate_selection_requirements`, which chains requirements +
overrides + scoped overrides and **never constraints**. Fix: include
constraints. **"Would I write code? YES."**

Icarus: the exclusion **is intentional** — correct, and it is the maintainer's
own word (charliermarsh: *"I think the behavior here _is_ intentional"*). That
verdict alone stops the control's wrong fix.

But grading the whole answer:

| Icarus said | truth |
|---|---|
| exclusion is intentional | ✅ maintainer's word |
| because "the resolution strategy is built from the manifest before resolution begins, and constraints are treated differently in that process" | ❌ **nobody said this.** The real reason: `explicit` *enables* prereleases for marked dependencies but does not *prefer* them over stable |
| — | ❌ **missed PR #20837**, which maintainers named as the actual fix, and missed that the reporter is inclined to close the ticket |

So the second half of the answer is another **composition** — a plausible
rationale assembled from code structure that no source states. Same failure
mode as run 1's `..` rule, now at 2 occurrences in 9 substantive answers.

Had I acted on the stated reason, I would have "fixed" the manifest plumbing —
still the wrong change, just for a different wrong reason. The verdict saved
me; the rationale would have re-misled me.

## Result

**2 of 2 tasks: the control arm would have written code, and both times that
was the wrong action.** Icarus prevented both.

Combined with runs 1-3, that is **5 of 5 tasks where a code-only reading
produced the wrong action** — twice mis-scoping a regression, once patching
declined behaviour, once duplicating rejected work, once fixing the wrong
layer.

Against that, Icarus's own error rate is now **2 fabricated rationales and 1
scope inflation in 9 substantive answers**, all of the same species: a
composed rule or reason no single source states, passing the honesty gate
because every citation is real.

The honest summary for a design partner: **Icarus is reliable about *whether*
to act and unreliable about *why*.** The verdict ("this was intentional",
"someone already tried this") is quotation and held every time. The
explanation attached to it is sometimes composed and needs checking. Both runs
here reproduce that split exactly.

## What this does NOT establish

- No efficiency numbers. The design cannot produce them (see above).
- n=2 here, n=5 overall. Directionally consistent, not statistically anything.
- Both tasks come from one repository whose index is truncated at 5,000
  PRs/issues; a repo whose relevant history falls outside that window would
  behave worse, and nothing here tests that.

## Next

The efficiency half needs the uncontaminated design: same task, two agents,
one with Icarus and one without, neither having seen the other's work. That is
the run that produces a number worth quoting.
