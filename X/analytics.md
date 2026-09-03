# Analytics — what we count, what we ignore, and how we capture it

## The one rule

**A metric earns its place by changing a decision.** If no plausible value of it
would change what we do next, it is a vanity metric and it does not go in the
table.

## Metric tiers

### Tier 1 — decision-grade (capture always)
| Metric | Why it changes a decision | Available? |
|---|---|---|
| Profile visits per post | The only direct measure of stage 1→2 of the funnel | **unknown** (E0) |
| Follows per post | Whether a post recruited or merely entertained | **unknown** (E0) |
| Replies received | The only signal that a specific human engaged | yes, manual |
| Link clicks | Stage: product interest | **unknown** (E0) |
| Repos connected, attributable | The actual conversion event | PostHog exists, not joined to X |

### Tier 2 — diagnostic (capture, never optimise directly)
| Metric | Reads as |
|---|---|
| Views | Distribution reach. Confounded by cadence and by the 6-month gap. |
| Bookmarks | Strongest quality proxy X gives — a bookmark is "I will need this". For a technical account this is worth more than likes and is currently uncaptured. |
| Reposts | Borrowed distribution, unrequested |

### Tier 3 — vanity (record, do not reason from)
Likes. Follower count as a headline number. Impressions on replies.

**Likes specifically:** the record shows 0–1 likes on every post from 13 to 178
views. A metric with no variance carries no information.

**Follower count specifically:** a follower outside the primary segment makes
Tier 2 prettier and the funnel worse. Growth in the wrong segment is negative
progress that looks like progress. See `hypotheses.md` H8.

## Capture protocol

1. **Capture at ~48h, never at 10 minutes.** The Aug 17 Claude Code post is in
   the record at "2 views" because it was captured 19 minutes after posting.
   That number is noise and is labelled as such.
2. **Record zeros.** A post that landed nothing is data. (Vault § Recording
   results; [[Learning]] — the email batches' zeros were the useful part.)
   *Internal record only — the no-failure-disclosure rule governs publication,
   not measurement.*
3. **One home:** per-post metrics live in the vault's `X Content.md` § Posted,
   alongside the post text. This file owns definitions and the aggregate view
   only. Never copy a post's metrics here.
4. **Sample size travels with every number** in any analysis written from this.

## Settling curve — the finding that invalidates the capture protocol

**Measured 2026-08-26 by walking the profile timeline post by post** (Aug 13 →
Feb 23, so the whole 2026 window; nothing between Aug 13 and Aug 26 is missing
from the vault except the Aug 23 post, now logged).

| Post | At 08-22 capture | At 08-26 | Factor |
|---|---|---|---|
| 08-18 index drift | 5 | **38** (+1 like) | 7.6x |
| 08-18 ContextBench | 5 | **31** | 6.2x |
| 08-18 AGENTS.md | 8 | **26** | 3.3x |
| 08-17 refused vs abandoned | 11 | **18** | 1.6x |
| 08-17 agent memory / RAG | 10 | **17** | 1.7x |
| 08-17 SkillRet | 7 | **16** | 2.3x |
| 08-17 honest limitation | 9 | **15** | 1.7x |
| 08-17 Claude Code auto mode | 11 | **15** | 1.4x |
| 08-17 vault loop | 8 | **13** | 1.6x |
| 08-17 five-second test | 8 | **12** | 1.5x |
| 08-16 testers ask | 13 | **27** | 2.1x |
| 08-14 abundance | 24 | **37** | 1.5x |
| 08-14 Agent Mode | 33 | **43** | 1.3x |
| 08-13 code shows what exists | 59 | **69** | 1.2x |

**The rule "capture at ~48h" is wrong for this account, and the Aug 17 auto-mode
post proves it three ways: 2 views at 19 minutes, 11 at four days, 15 at nine
days.** On a low-velocity account a post is still accruing a week later, because
the few impressions it gets arrive from search and profile visits rather than
from a timeline burst. 48h is a burst-account heuristic imported without
checking whether this account bursts. It does not.

**Revised protocol:** capture at ~48h as a provisional read, then **re-capture
the whole window at 7+ days before any number is used in an analysis**. Label
every figure with its capture age. A figure without one is not usable.

**The newer the post, the more understated it is** — which means the 08-22
snapshot did not just shift every number down, it shifted the *recent* ones down
hardest, manufacturing a decline. Any trend line drawn across posts of different
ages on this account is measuring capture lag, not reach.

**Posts and replies settle differently, and only posts needed the fix.** Measured
in the same 08-26 pass: replies gained ~40–50% over three days (freeCodeCamp
114→157, debasishg 22→33, fmontes 38→51), posts gained 200–600%. A reply's reach
is set in its first hours by the parent's live traffic; a post's accrues for a
week from search and profile visits. **Capture replies at 48h — that rule was
always right for them. Capture posts at 7+ days.** One protocol was being applied
to two distributions.

**Reply reach is now measured 2 to 908 views** — the 908 into @arpit_bhayani's
47K-view parent on 08-25, an all-time record by 2.3x, and it produced no like,
bookmark, reply or follow. **Reach and engagement are separable on this account
at every scale measured**, which is the single most useful thing the two
reconciliations produced: it means the Aug 17–18 zero-engagement window was not
diagnostic of the writing, and it means chasing bigger parents may not convert
either.

**Pinned posts are not comparable.** 08-15 rejected patch reads 81 views, the
highest of any 2026 post, because it is pinned and collects a view per profile
visit. It is a profile-visit proxy. Exclude it from reach comparisons — and note
it is the closest thing to the profile-visit metric Tier 1 says is unavailable.

## Current baseline — 2026-08-22 (SUPERSEDED, kept for the audit trail)

> [!caution] Every figure in the table below is low by 2–7x.
> Superseded by § Settling curve above. The revised Aug 17–18 window is
> **12–38 views, median ~16.5**, not 5–11 / median 8.5. Do not quote this table.
> The measurement-floor argument beneath it is left standing because its
> *conclusion* survives the correction — see the note after it.

## Current baseline — 2026-08-22 (revised after E0 capture)

**All ten daily-six posts from Aug 17–18 are captured.** Per-post text and
metrics: vault § Posted.

| Window | Posts | Views range | Median | Engagements |
|---|---|---|---|---|
| Feb 2026 | 4 | 71 – 178 | ~139 | 3 likes, 2 replies |
| Aug 13–16 | 4 | 13 – 59 | ~28 | 2 likes |
| **Aug 17–18 (daily six)** | **10** | **5 – 11** | **~8.5** | **0 — of any kind** |

**Reach fell monotonically as cadence rose.** Not one like, reply, repost or
bookmark across ten posts.

### The measurement floor — read this before designing any content experiment

At ~8 views/post, **no content experiment can resolve anything.** The
within-window spread (5–11) is smaller than the noise floor of a sample that
size, and one impression is a ~12% swing. Pillar, structure, hook and CTA
comparisons are all unrunnable at this reach.

Consequence: E2 (video), E3 (structure ladder) and E4 (CTA cost) are **blocked
on reach recovery**, not on writing time.

> [!note] Re-read 2026-08-26 against the corrected numbers.
> At a median of ~16.5 rather than 8.5 the floor argument still holds — the
> within-window spread (12–38) is still dominated by post age rather than by
> anything about the writing, and the three highest are all the *newest* three,
> which is the settling curve and not a content effect. **E2–E4 stay blocked.**
> The reason changes: not "reach is too low to resolve anything" but "reach is
> confounded with capture age, and until every post is measured at the same age
> the comparison is meaningless." Same block, better reason. Running them now produces numbers that
look like results and are not.

### The one thing the zeros do tell us

Ten posts, zero engagements, is not a craft signal — it is an **audience-presence
signal**. Views this low mean the posts were served to almost nobody, and the
handful reached did not include one person who cared. Either the follower graph
is inactive, or it is not the primary segment (`hypotheses.md` H8), or both.

## Known measurement debt

- ~~Six posts from Aug 17–18 have no metrics.~~ **Resolved 2026-08-22** — all
  ten captured. See baseline above.
- Bookmarks are visible per post (all zero). Profile visits and link clicks are
  **not** on the post row — they require the per-post analytics view. Still
  uncaptured (`OPEN_QUESTIONS.md` Q1).
- Follower count still uncaptured. At this reach it is now a priority, not a
  curiosity: it is the most likely direct explanation of the numbers above.
- PostHog product analytics are not joined to X traffic, so the bottom half of
  the funnel is invisible.
- **Posts are reaching the record only if someone remembers to log them.** The
  2026-08-23 post (44 views, 2 likes — best since February) was absent from
  `X Content.md` § Posted until Alankrit found it on the post page on 08-26.
  Every aggregate written between those dates, including the reach-collapse
  baseline above, was computed over an incomplete set. **Reconciled by a full
  timeline walk 2026-08-26** — see § Settling curve. No other post was missing;
  the far larger problem was that every number on file was stale-low.
- **Likes are no longer a no-variance metric.** The Tier 3 classification rests
  on "0–1 likes on every post from 13 to 178 views". The 08-23 post drew 2.
  Re-read that tier at the next capture.
- The Feb/Aug gap makes every cross-period comparison uncontrolled. Do not run
  one and call it a result.
