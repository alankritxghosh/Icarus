# Dogfooding Icarus on two real issues in `meilisearch-swift`

Date: 2026-08-14
Two real, separately-shipped PRs against `meilisearch/meilisearch-swift`
(`repo:` argument used on every call, per the fork's own `CLAUDE.md` policy
requiring it), each gated on Icarus before code was written and again before
commit. Both PRs opened clean and green: [#532](https://github.com/meilisearch/meilisearch-swift/pull/532)
(issue #531, index stats) and [#533](https://github.com/meilisearch/meilisearch-swift/pull/533)
(issue #523, personalized search). This is a report of what Icarus actually
contributed to each, not a synthetic benchmark — every claim below was
independently checked against `gh pr view`/`gh pr diff`/`gh api .../timeline`
or a live Meilisearch instance before being acted on, per the CLAUDE.md rule
this session was built to test.

## Issue #531 — add `indexSize`/`usedIndexSize` to index stats

**`get_task_context` failed outright, twice**, with `MCP error -32603:
Internal error`, no partial output. This is the tool positioned for exactly
this moment ("before starting a non-trivial engineering task"). Fell back to
`get_change_context`.

**`get_change_context` produced one claim that was actively wrong.** It
stated "adding new fields like `indexSize`/`usedIndexSize` has been attempted
before," labeled `"composed"`, citing only `issue:531` itself. That's not
evidence of a prior attempt — it's the issue restating its own existence.
Taking it at face value would have meant reporting false repo history.

**But the same call surfaced the one fact that mattered most**, buried in a
flat citation list with no framing: `pr:522`, an open, reviewer-approved,
unmerged PR that introduces a `SizeValue`/`sizeFormat` mechanism touching the
exact struct (`Stat`) #531 needed to change. Icarus never said why it
mattered or connected it to #531 explicitly — I had to pull the diff myself
(`gh pr diff 522`) to understand the actual shape of the conflict, then
separately verify the upstream engine PR
([meilisearch/meilisearch#6563](https://github.com/meilisearch/meilisearch/pull/6563))
to confirm field names and `sizeFormat` behavior. Implemented narrowly (plain
`Int`, matching what the SDK's public API supports today) rather than
duplicating #522's unmerged design, and flagged the coordination risk in both
the PR description and the fork's `CLAUDE.md`.

**Re-check against the final diff** (`explain_code_context` on the committed
`Stat.swift`) repeated the same failure mode in a new spot: it asserted "the
existing `Stat` model... already uses this `SizeValue` type" — false, I had
just read and compiled that exact file with plain `Int` fields. It had
conflated PR #522's *proposed* diff with the *current* state of `main`.

## Issue #523 — add `personalize` search parameter

**`get_task_context` worked cleanly this time** — no error, correct file list
(`Search.swift`, `SearchParameters.swift`) unprompted. Same tool, same repo,
different call, opposite reliability outcome from #531. No visible reason for
the difference.

**The `risks`/`rejected_attempts` field surfaced something concretely
actionable for the first time this session**: [PR #515](https://github.com/meilisearch/meilisearch-swift/pull/515)
("Add `distinct` search parameter"), structurally the same class of change I
was about to make, labeled as a rejected attempt.

**The label overstated what happened, in a way worth naming precisely** —
this is a distinct failure mode from the false-positive-rate work in
`2026-08-10-rejected-attempt-false-positive-rate.md`, which measures whether
a listed closed PR is *topically relevant*. Every PR the parser named in that
experiment genuinely was closed-and-unmerged and on-topic; the open question
there is precision of retrieval. Here the PR (#515) genuinely was on-topic
and closed-unmerged too — retrieval was correct. The problem is a second,
separate axis: **why it closed.** I pulled the actual timeline
(`gh api repos/.../issues/515/timeline`): no maintainer ever reviewed it, the
author self-closed it three hours after opening with zero substantive
comments, and the issue it claimed to close (#446) is still open today. That
is an abandoned, unreviewed submission, not a maintainer *rejection* — but
"rejected" is the only label the field offers, and it reads as a judgment
call that never occurred.

**Re-checking `explain_code_context` against the final diff was accurate this
time** — "adding a `personalize` field... is consistent with the existing
pattern... as seen with fields like `limit`, `filter`, and `distinct`,"
correctly grounded in the current file, not a proposed one.

**Two facts that mattered for correctness came from live investigation, not
Icarus, and this isn't a knock on it** — this SDK never implemented
GET-based search at all (half the issue's task list didn't apply — found by
grepping `Sources/`), and personalization requires the server to be started
with a real `--experimental-personalization-api-key` (found by standing up a
live Meilisearch v1.53.1 instance and probing `/experimental-features` and
`meilisearch --help` directly). Icarus indexes repo history; it has no way to
know live server behavior or a dependency's runtime requirements, and didn't
pretend to.

## What this establishes

**Two distinct, previously-unmeasured failure shapes, both about
over-stated certainty rather than wrong retrieval:**

1. **Citation-conflation** (#531, both the initial call and the re-check):
   citing "the issue that requests X" as if it were "evidence X was
   attempted," and citing an unmerged PR's diff as if it described the
   current file. Retrieval found the right documents both times; the prose
   layer on top overstated what they proved.
2. **Rejection-conflation** (#523): `rejected_attempts` collapses "a
   maintainer reviewed this and declined it" and "the author abandoned it
   unreviewed" into one undifferentiated label. This is orthogonal to the
   relevance/false-positive axis already being measured in the 2026-08-10
   experiment — a hit can be perfectly on-topic and genuinely closed-unmerged
   (as #515 was) and *still* mislead about maintainer intent.

**One reliability data point**: `get_task_context` failed twice on #531 and
worked cleanly on #523, same repo, same session. N=2 is not enough to
characterize the failure rate, but it rules out "always broken" — this looks
intermittent, which is a different (and probably more tractable) class of bug
than a systemic one.

## Consequences

1. **The rejection-conflation gap is new and not covered by the existing
   false-positive-rate work.** That experiment should be extended, or a
   sibling one opened, to measure how often a `rejected_attempts` entry is a
   genuine maintainer decline vs. an abandoned/unreviewed self-close — a
   `gh api .../timeline` check (reviews present? closed-by-author vs.
   closed-by-maintainer? linked issue still open?) is a cheap, scriptable
   oracle for this, same shape as the relevance labels already used.
2. **The citation-conflation failures (both #531 instances) are exactly what
   the `"composed"`/`"quoted"` labeling exists to catch, and it worked as
   designed** — I caught both because the claims were flagged for scrutiny,
   not because they were self-evidently wrong. That's the system functioning
   correctly, not a gap; the gap is that `rejected_attempts` doesn't carry an
   equivalent hedge, so item 1 needed a manual out-of-band check instead of a
   flag the tool itself raised.
3. **`get_task_context`'s intermittent failure needs reproduction, not just a
   note.** Two calls in one session, one repo, is too little to file as a bug
   with confidence, but "the highest-leverage tool is the one I can't
   currently assume will respond" is a real cost to a workflow that's
   supposed to call it before every non-trivial task.

## Limits

- N=2 issues, one repo (`meilisearch-swift`), one session. Both PRs shipped
  correctly, but that's two data points on tool reliability, not a rate.
- I don't have visibility into why `get_task_context` failed on #531 and not
  #523 — no error detail was returned either time it worked or didn't, so
  this can't be narrowed further from the client side.
- Every finding here required independent verification via `gh` or a live
  server before being trusted — consistent with both experiment sessions
  cited above, this is not something to soften by relaxing that requirement
  on the theory that hit rate has improved.

---

## Follow-up, same day: all three consequences addressed

Appended after the fixes landed, so this record stays the single place the
findings and their outcomes sit together.

1. **Rejection-conflation — fixed with data, not a disclaimer.** GitHub's own
   `reviewDecision` answers it mechanically, and `gh pr list --json` (which
   ingest already calls) carries it, so `evals/ingest.py` now records
   `Review: approved|changes_requested|none` and `evals/attempts.py` reports it
   as `review`. `none` means no review reached a decision — not "nobody
   looked", since a plain COMMENTED review leaves it unset either way. Absent
   when unknown, which is every corpus ingested before today. Measured over 60
   real `meilisearch-swift` PRs: of the 11 closed-unmerged, **6 `none`, 3
   `approved`, 2 `changes_requested`** — so the word "rejected" was defensible
   for 2 of 11, and #515 reports `none` without anyone having to pull the
   timeline by hand. The proposed `gh api .../timeline` oracle was not needed.
2. **Citation-conflation (the unmerged-diff half) — fixed.** `rests_on_rejected`
   could never have caught this: #522 is OPEN, so it was not in
   `rejected_attempts` at all. The predicate the code described ("nothing cited
   shows this LANDED") was implemented against closed-only. It is now
   `rests_on_unlanded`, computed from `attempts.unlanded_prs`, covering open
   and closed-unmerged pull requests and a `diff:N` inheriting its pull
   request's state. Renamed because calling an approved open pull request
   "rejected" is the same overclaiming the flag exists to catch. Verified on
   the same 60 PRs: 22 unlanded vs 11 refused, no MERGED PR marked, no OPEN one
   leaking into `rejected_attempts`.
3. **`get_task_context`'s failure — reproduced and root-caused**, see
   [`2026-08-14-get-task-context-timeout-reproduction.md`](2026-08-14-get-task-context-timeout-reproduction.md).
   A flat 60s timeout, not an internal fault.

4. **Citation-conflation (the issue-as-evidence half) — fixed, and it
   reproduced live first.** `rests_on_unlanded` required at least one unlanded
   pull request among the citations, so a claim resting on issues ALONE was
   the one arrangement nothing checked — which is exactly the arrangement of
   the "has been attempted before" claim citing `issue:531`. While fixing it,
   the same shape reproduced unprompted on the live brain: asked whether index
   size reporting had been added, Icarus answered *"Yes, issue #531 tracks the
   addition of `indexSize` and `usedIndexSize`..."*, citing `issue:531` alone,
   labelled `quoted`. The issue that ASKED for the change, read back as the
   answer to whether it happened.

   The anchor is gone: nothing cited showing a landing is now sufficient,
   whether the citations are unlanded pull requests, issues, or both. The
   principle was already written in the code ("an issue reports a problem; it
   never records an adoption") and simply was not applied uniformly.

   **Measured before widening**, since a flag that fires often stops being
   read: over 10 real questions on this repo, 3 of 8 claims were issue-only.
   All three were true positives — two describing a Core module that is
   proposed and not built, one the `issue:531` case above. Honest limits: n=8
   claims, one repo, and the question set deliberately included "has X been
   done" phrasings, which is where this shape lives, so 38% is an upper bound
   on a biased sample rather than a rate. A claim citing code or a merged pull
   request alongside an issue still does not fire, which is what stops this
   marking ordinary grounded answers.

**Reach:** every fix above depends on `Review:` being in the corpus, so a repo
must be re-ingested before `review` appears; `rests_on_unlanded` needs no
re-ingest, since PR state was always recorded.
