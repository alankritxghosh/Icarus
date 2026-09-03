# X Distribution Strategy v0.1 — 2026-08-22

Status: **v0.1, mostly untested.** Everything below is either a fact from the
record (marked with its source) or a bet (marked as a bet, with the hypothesis
id that tests it). Nothing here is advice; it is a plan with disproof conditions.

---

> **REVISED 2026-08-22 after E0 + the follower audit.** §1 below was written
> before either. It called the bottleneck correctly — distribution, not craft —
> but for the wrong reason. The real number: **~13 followers**, ten posts at
> 5–11 views, zero engagements. See §1a. Everything downstream of §1a supersedes
> the original plan where they conflict.

## 1a. The actual bottleneck, measured

**There is no audience. That is the entire problem, and it is not a metaphor.**

- ~13 followers, list enumerated end to end (`audience.md`).
- Zero of them are clearly in the primary segment; ~6 are build-in-public
  reciprocal follows the audience file already excludes; ~4 are not developers.
- Ten posts on Aug 17–18: 5–11 views, **zero** engagements of any kind.

**What this rules out:** craft (H2, supported), content quality, pillar mix,
hook strength, posting time. None of those can be the constraint when the
material never reaches a relevant human.

**What the 178-view February post proves:** reach here is dominated by
**off-graph surfacing**, because 13 accounts cannot generate 178 views (H10).
So reach is winnable without a following — but the lever is whatever X uses to
decide off-graph distribution, which is unmeasured and largely outside our
control.

**The two levers that remain, in order:**

1. **Put the work in front of people directly** — replies into other people's
   audiences (Play A). This bypasses both the empty graph and the off-graph
   lottery. It is still at zero attempts.
2. **Convert the reach that already happens into followers.** At 13, each new
   follower is ~8% of the graph. The profile is the conversion surface and has
   never been reviewed (Q4).

**The metric that now matters most: followers gained per week from the primary
segment.** Not views. Views on this account are a lottery ticket; a
primary-segment follower is a permanent, compounding asset — and there are
currently zero.

**What is no longer worth doing:** anything whose value depends on comparing
posts to each other. At 5–11 views the sample cannot tell a good post from an
unseen one.

## 1b. The original §1 — the actual bottleneck (pre-audit, kept for the record)

**It is not writing quality. It is distribution.**

The evidence: the best-written post in the entire record — the Aug 15 rejected-patch
post, three beats, observation → mechanism → product — got **22 views**. The
highest-reach post ever is two lines written in January with no product, no
link, and no craft investment: **178 views**. Craft varies by 8× between those
two posts. Reach varies in the *opposite* direction.

That is the signature of a system where the ceiling is the follower graph, not
the writing. On an account with no meaningful following, organic reach is
approximately: (followers who see it) × (their engagement) → algorithmic
amplification that never triggers because the first number is too small.

**Consequence:** for the next 30 days, effort spent making a post 20% better is
worth less than effort spent putting an existing good post in front of someone
else's audience. Both matter. Only one is currently at zero.

**The counter-evidence to watch for:** a post that breaks 1,000 views without
any borrowed audience would refute this and mean craft was the constraint all
along. Nothing in the record has come close (max 178).

## 2. The funnel, and where it currently breaks

```
attention → profile interest → audience relationship → product interest
         → repo connected → retention → advocacy → revenue
```

| Stage | Current state | Measured? |
|---|---|---|
| attention | 13–178 views/post | yes, 11 posts |
| profile interest | unknown — no profile-visit data | **no** |
| audience relationship | 2 replies ever, both on personal posts | yes |
| product interest | unknown — no link-click data | **no** |
| repo connected | unknown — PostHog exists but is not joined to X | **no** |
| everything downstream | zero observed | — |

**The break is at stage 1 → 2, and we cannot even see stage 2.** Fixing the
measurement gap is cheap and is Experiment E0 (`experiments.md`). Do it before
running any content experiment whose result depends on it.

## 3. The three plays, ranked by expected value

### Play A — replies into other people's audiences (UNUSED, highest EV)

The only mechanism on X that does not require an existing following. A reply
under a large account's post is served to that account's audience, not yours.
It is the single largest untried lever in this system.

- **Target:** 5 substantive replies/day, under posts by agent-tooling, retrieval,
  and devtool accounts (the primary segment in `audience.md`).
- **What counts as substantive:** a reply that carries a number or a mechanism
  the original post lacked. "Great post 🔥" is noise and actively harms
  positioning. A reply that says *"we measured this: 0 calls across 11 tasks
  when the tool description described the tool, 1 of 4 independent sessions
  when it named the trigger moments"* is a post that borrowed someone's
  audience. (The example number here was 4/4 before 2026-08-25 — that figure
  is retired, see [[Agent Mode]] in the vault; the mechanism it illustrates,
  wording as trigger, still holds.)
- **Constraint:** every content rule in `CLAUDE.md` applies inside a reply.
  Sample size stays in the sentence. No citation that was generated, not checked.
- **Hypothesis:** H1. **Disproof:** 100 substantive replies over 20 days produce
  fewer than 10 profile visits attributable to replies, or zero follows.

### Play B — the daily six (RUNNING, unmeasured)

Set 2026-08-17: 2 personal / 2 papers / 1 agentic / 1 Icarus. Achieved 6/6 once,
3/6 once, then nothing captured. This is currently *running blind* — four days
of posts exist with no metrics.

- **The real risk is not writing time, it is source material honesty.** The
  vault already flags this. See `content-pillars.md`: the standing inventory
  proves the material exists for roughly 6–8 weeks at this cadence. Beyond that
  the mix must be refilled from new work, not from invention.
- **The failure mode to watch:** a day where the paper slot gets filled by a
  paper that was not read. That single event costs more than a month of missed
  slots, because the product's entire claim is that it does not do that.

### Play C — the asset posts (demo video, screenshots) (UNUSED)

`site/demo.mp4` and `site/shots/demo_icarus.mov` (60.06s, shows both a cited
answer and an honest unknown) exist and have never been posted. Video is the
one format on X with materially different distribution mechanics from text, and
this account has published exactly zero.

- **Hypothesis:** H5. **Disproof:** a video post underperforms the account's
  text median (~33 views) twice.

### Explicitly deprioritised

- **Threads.** Never used on this account. Untested, not forbidden (H6). Do not
  start threads until single posts are consistently over ~200 views; a thread
  spends the same idea across N posts, and on a small graph N posts of one idea
  reach the same small group N times.
- **Growing followers as a goal.** Followers are the *mechanism* by which reach
  compounds, so they matter — but a follower who is not in the primary segment
  makes the reach numbers prettier and the funnel worse. See `analytics.md`
  § Vanity.

## 4. The 30-day plan

**Week 1 (Aug 22–28) — instrument, then borrow.**
1. E0: capture profile-visit, link-click, and follower data; fill `OPEN_QUESTIONS.md`.
2. Back-capture metrics for the 6 posts sitting at "pending" in the vault.
3. Start Play A at 5 replies/day. Log every one in `experiments.md`.
4. Keep the daily six, but drop to 4/day if source material is thin. A missed
   slot costs nothing.

**Week 2 (Aug 29–Sep 4) — the video test.**
5. Ship the demo post (Play C), written in the observation-first voice, not the
   `outputs/growth/` register. No link in the body; install path in the reply.
6. First analyst pass: which pillar actually reaches whom, now that we can see
   profile visits.

**Week 3 (Sep 5–11) — double down on whatever moved.**
7. Kill or scale Play A on data, not feel.
8. Run H3 properly: 4 Icarus posts, one per structure (insight / story /
   capability / limitation), same week, so the comparison is not confounded by
   the 6-month gap.

**Week 4 (Sep 12–18) — conversion.**
9. First deliberate conversion test: one post with a CTA, one identical-idea
   post without, measure profile visits on both. (H7)
10. Write v0.2 of this file from the data. Delete every bet that got refuted.

## 5. What would make this strategy wrong

Stated in advance, per `docs/experiments/PROTOCOL.md` §3 discipline:

- If replies produce nothing over 100 attempts, the bottleneck is not the
  follower graph — it is that the content does not interest the primary segment,
  and positioning is the problem, not distribution.
- If reach rises with cadence alone, consistency was the whole answer and every
  pre-Aug-17 number is worthless as a baseline.
- If profile visits are high but zero repos get connected, the funnel breaks at
  the product/landing page, not on X, and this entire workstream is optimising
  the wrong stage.
