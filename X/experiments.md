# Experiments — the log

Discipline borrowed from `docs/experiments/PROTOCOL.md`, which exists because
each of its rules cost a real run. The three that transfer:

1. **Register the prediction before launch.** A prediction written after the
   result is not a prediction.
2. **Read the result from the instrument, never from self-report.** On X the
   instrument is the analytics panel at ~48h, not how the post felt.
3. **An inconvenient result goes in the result, not in a footnote.**

One post is not an experiment. An experiment is a *comparison* with a registered
prediction and a stated disproof condition.

## Template

```markdown
### E<n> — <name>  ·  status: registered / running / concluded
**Hypothesis:** (id from hypotheses.md)
**Prediction (registered <date>, before launch):**
**Design:** what varies, what is held constant, n, over what period
**Confound known in advance:**
**Invalid if:**
**Result:**
**Verdict:** supported / refuted / inconclusive — and which hypothesis it moves
**Lesson:** (route durable ones to the vault; one home per item)
```

---

## E0 — Instrument the funnel · status: **partially concluded 2026-08-22**
**Hypothesis:** none. This is a prerequisite, not a test.
**Why first:** four of five Tier-1 metrics in `analytics.md` are currently
unavailable, so E1–E3 would produce numbers we cannot interpret. Six posts from
Aug 17–18 are sitting at "metrics pending" past their capture date.
**Design:**
1. Back-capture views/likes/replies for all 6 pending posts → vault § Posted.
2. Establish whether post-level profile visits, link clicks, and bookmarks are
   visible on this account. Record the answer in `OPEN_QUESTIONS.md` either way.
3. Record follower count and audit ~50 followers against the primary segment (H8).
**Invalid if:** metrics are captured >72h late and X has already aggregated them
away — in which case record that as the finding and change the capture cadence.

**Result (step 1 done, 2026-08-22):** all ten Aug 17–18 posts captured, 4–5 days
settled. **5–11 views each. Zero likes, replies, reposts, bookmarks across all
ten.** Reach fell monotonically as cadence rose: Feb ~139 median → Aug 13–16 ~28
→ Aug 17–18 ~8.5. Post count now 69 lifetime (was 54).

**Verdict:** the daily-six regime, as run, produced the account's worst reach on
record. That is a real result and it is inconvenient, so it goes here and not in
a footnote (PROTOCOL §3).

**What it does NOT establish:** that volume *caused* the fall. Three live
explanations, untested and not mutually exclusive:
 (a) the graph is inactive/wrong-segment and Feb's numbers came from a peer
     graph that has since gone quiet — the fall predates the cadence change;
 (b) posting 6/day into a graph that never engages trains distribution down
     (X weights recent engagement rate; ten consecutive zero-engagement posts is
     the strongest negative signal an account can send);
 (c) topic shift — Feb posts were personal/career, Aug posts are technical, and
     the audience that engaged with (a) may simply not exist for (b).
**Do not pick one and act as if it is settled.** (b) and (c) are separable; see
E5.

**Steps 2–3 still open:** per-post profile visits / link clicks (not on the post
row — needs the analytics view), follower count, follower audit. Q1, Q2 remain.

## E1 — Replies as distribution · status: **registered, not started**
**Hypothesis:** H1
**Prediction (register the number before starting, per PROTOCOL §3):** to be
written by Alankrit before the first reply. Do not start without it.
**Design:** 5 substantive replies/day for 20 days = 100 replies, into accounts
the primary segment reads. Every reply logged with: parent account, parent post
topic, reply text, and any resulting profile visit / follow / reply-to-reply.
Original-post cadence held constant so the two are not confounded.
**Confound known in advance:** the daily six runs concurrently, so follows cannot
be cleanly attributed to replies unless X exposes per-post profile visits. If E0
finds it does not, downgrade E1's endpoint to replies-received and follows-total,
and say so.
**Invalid if:** replies drift into "great post" acknowledgements — that is a
different intervention and must be relabelled, not quietly counted.

**Log:**

| # | Date | Parent | Parent reach at send | Payload | Notes |
|---|---|---|---|---|---|
| 1 | 2026-08-22 | @fmontes AGENTS.md | 6.7K views, 78 likes, 54 bookmarks | B1 AGENTS.md paper | Line breaks stripped on paste; shipped as one block, missing space at "20%.Repository". |
| 2 | 2026-08-22 | @dillon_mulroy 70%-of-context | 9.1K views, 227 likes | B1 closed-PR extension | Sent. Reach not yet captured. |
| 3 | 2026-08-22 | @gippp69 agent memory | large account | B1 arXiv:2602.02007 | Sent. |
| 4 | 2026-08-22 | @HarrisDecodes context bottleneck | 1.2K views | B1 60-PR read | Sent. |
| 5 | 2026-08-22 | @xlr8harder "vibefish" | 866 views, 44 likes | B2-4 fluency-with-no-boundary | 3 views on the reply. |
| 6 | 2026-08-22 | @matthias_mrc builder/marketer | 3.7K views, 79 likes, 56 replies | B2-3 compile step | 1 view. **Shipped the pre-lint version** carrying the rule-of-three ("slow, noisy and mostly absent"). Minor. |
| 7 | 2026-08-22 | @JaredKubin seam-filling | 11K views, 50 likes | B2-2 fabrication assembly | 8 views, 1 like. **First like on any reply.** Line breaks stripped again: "4 tasks.The model" and "flagged it.The pieces". |
| 8 | 2026-08-22 | @omarsar0 context acquisition | 3.2K views | B2-1 58/17/14 citation split | Sent. |
| 9 | 2026-08-22 | @wilczyn "smallest change that made a real difference" | 49 views, 2 replies | Agent Mode, zero-awareness version | 1 view. **ERROR SHIPPED: reads "0 calls in 11 tasks, then 40 of 40". The measured result AT THE TIME was 4 of 4, itself later retired to 1 of 4 (2026-08-25).** See below. |

**Result:** —

## E5 — Build a graph that exists · status: **registered, not started** · NEXT
**Hypothesis:** H1 primary; H9 secondary
**Rewritten 2026-08-22** after the follower audit. The original framing tested
whether cadence suppressed reach. With ~13 followers there was never enough
on-graph distribution for that to be the main question. **The endpoint is now
followers gained from the primary segment, not views.**
**Prediction (register before starting):** to be written by Alankrit.
**Design:** 14 days. Cut original posts to **1/day**, drawn only from the
strongest items in `content-pillars.md`. Run E1 (5 replies/day) concurrently.
**What varies:** volume down, borrowed-audience up. **Held constant:** voice,
pillars, verification standard.
**Primary endpoint:** **primary-segment followers gained** (agent/devtool
builders — judged against `audience.md`, recorded by handle, not by count alone).
Baseline: **0**.
**Secondary endpoints:** any non-zero engagement (baseline 0); median views over
the final 7 days vs the 5–11 baseline.
**Explicitly not an endpoint:** total follower count. A build-in-public
follow-back moves that number and moves nothing else — the audit shows ~6 of the
existing 13 are exactly that.
**Confound stated in advance:** two variables move at once. This is deliberate —
separating them costs a month at 8 views/post, and the cost of another dead
fortnight is higher than the cost of an ambiguous attribution. If reach
recovers, split them afterwards.
**Invalid if:** cadence is not actually cut, or replies drift into acknowledgements.
**Result so far (9 replies, 2026-08-22):** 13 -> 14 followers. 1 like on reply
7, the first engagement any reply has drawn. Reply views 1-8, so reply reach is
NOT tracking parent reach the way the 85-view reply in February did. Too early
to read.

### Incident: a wrong number shipped, reply 9

The sent text says **"0 calls in 11 tasks, then 40 of 40"**. The measured C2
result AT THE TIME was **4 of 4**
(`docs/experiments/2026-08-11-agent-mode-exp-c2-results.md`); that number was
itself retired 2026-08-25 (C2's four tasks ran in one shared session, not four
independent ones — re-run measured **1 of 4**, see `docs/experiments/2026-08-25-agent-mode-c2-rerun-fresh-sessions.md`).
The draft supplied on 08-22 was correct FOR ITS TIME; the error that shipped
entered at the keyboard, and is a separate mistake from the later retirement of
the underlying number itself.

It overstates the measurement by 10x on an account whose entire position is that
it does not overclaim, and it is arithmetically impossible on its face: the
experiment had 4 tasks, so 40 calls out of 40 cannot exist beside "11 tasks".

**X has no edit without Premium. The fix is delete and repost.** At 1 view the
cost of deleting is nothing and the cost of leaving it is the one thing this
account sells.

**Process change:** `lint.py` checks the draft, not the paste. Numbers are the
one thing it cannot verify, because it does not know the true value. Read the
digits back against the source before sending, every time.

## E2 — Video vs text · status: **BLOCKED on reach recovery**
**Hypothesis:** H5
**Design:** post `site/shots/demo_icarus.mov` (60.06s — shows both a cited answer
and an honest unknown) in the observation-first voice, no link in body. Compare
to the account's text median over the same fortnight.
**Note:** do NOT use `icarus_product_demo_2026-07-24.mov` — 6.56s, never shows
the answer or the refusal (vault).
**Result:** —

## E3 — The Icarus structure ladder · status: **BLOCKED on reach recovery**
**Hypothesis:** H3
**Design:** four Icarus posts in one week, one per structure (insight / story /
capability / limitation), drawn from `content-pillars.md` items of comparable
strength. Same week, so the 6-month-gap confound does not apply.
**Confound known in advance:** post strength is not controllable across four
different ideas. Treat a spread inside normal variance as inconclusive, not as
a ranking.
**Result:** —

## E4 — CTA cost · status: **BLOCKED on reach recovery**
**Hypothesis:** H7
**Design:** paired posts, same idea, one with a link/ask, one without, spaced so
they do not compete.
**Result:** —

---

> **Blocked means blocked.** At ~8 views the within-window spread is smaller
> than the noise floor; a structure or format comparison run now returns a
> number that looks like a result and is not. See `analytics.md` § The
> measurement floor.

## Concluded

- **E0 (step 1), 2026-08-22.** Ten posts captured. 5–11 views, zero engagement.
  Reach fell as cadence rose. Supports H2 strongly; opens H9; makes H3
  unmeasurable at current reach.

## Pre-registered predictions that were wrong

*(none logged yet on X. Keep this section — on the engineering side it is the
most valuable one in `docs/experiments/`, and an empty section is a prompt.)*
