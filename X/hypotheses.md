# Hypotheses — what we currently believe, and what would kill it

Every entry: the claim, why we believe it, what would refute it, and status.
A hypothesis with no disproof condition is an opinion — do not add one.

Status values: `untested` · `supported` · `refuted` · `retired`

---

## H1 — Replies into other audiences are the highest-leverage unused lever
**Claim:** On an account with ~0 following, a substantive reply under a large
relevant account reaches more of the primary segment than an original post.
**Basis:** Original-post reach is capped by the follower graph; the record shows
13–178 views with 8× craft variance and no correlation to quality. Replies are
served to the parent account's audience. Zero attempted, so zero evidence
against.
**Test:** 100 substantive replies over 20 days, logged.
**Refuted if:** <10 attributable profile visits, or 0 follows, across 100 replies.
**Status:** untested. Blocked on E0 (we cannot currently see profile visits).

## H2 — Distribution, not craft, is the binding constraint right now
**Claim:** Marginal effort on reach beats marginal effort on writing quality.
**Basis:** Best-written post = 22 views. Least-crafted post = 178 views.
**Refuted if:** any post exceeds ~1,000 views with no borrowed audience, no
video, and no external link-in.
**Status:** **supported, 2026-08-22.** Ten posts written to the full standard of
this system — verified papers, contrast openers, character-counted, sample sizes
intact — landed 5–11 views with zero engagement. The best-executed window in the
account's history is also its worst-performing. Craft is not the constraint. Do not treat as licence to write
badly — craft is what converts borrowed attention once it arrives.

## H3 — Among Icarus posts, insight-first > capability > story > ask
**Claim:** Opening on the mechanism outperforms opening on the feature.
**Basis:** 59 (insight) > 33 (capability) > 22 (story) > 13 (ask). n=4, one week,
uncontrolled, and the "story" post was the best-written of the four — which is
itself evidence for H2.
**Refuted if:** a controlled same-week run of all four structures reverses the
order, or the spread falls inside normal post-to-post variance.
**Status:** **unmeasurable at current reach.** Aug 17–18 put insight (5), and
limitation (9) inside a 5–11 band shared by every other pillar. At ~8 views the
spread is smaller than the noise floor. Parked until reach recovers — see
`analytics.md` § The measurement floor.

## H4 — Personal posts sourced from work done retain the reach of vulnerable ones
**Claim:** The no-failure-disclosure rule (Decision History, 2026-08-17) does not
cost the reach advantage personal posts showed, provided the specifics survive.
**Basis:** The reach advantage is real (178/154/123 vs 13–59) and the standing
rule forbids reproducing what caused it. The vault's own diagnosis is that the
active ingredient was *specificity*, not *defeat* — the Aug 17 five-second-test
post was rejected precisely because stripping the failure also stripped the
specifics.
**Refuted if:** 10 work-sourced personal posts median below the account's overall
median.
**Status:** untested. **This is the most consequential open hypothesis in the
file** — if refuted, the standing rule has a measurable price and Alankrit
should be told the number, not argued with.

## H5 — Video outperforms text on this account
**Claim:** A 60s product demo reaches further than the text median.
**Basis:** Zero video posted, ever. X's distribution of native video differs
mechanically from text. Pure bet.
**Refuted if:** two video posts land below the ~33-view text median.
**Status:** untested. Asset already exists (`site/shots/demo_icarus.mov`).

## H6 — Threads are not worth running below ~200 views/post
**Claim:** A thread spends one idea across N posts; on a small graph it reaches
the same small group N times and adds no new audience.
**Basis:** Mechanism argument, no data. The account has never posted a thread.
**Refuted if:** a single thread outperforms the sum of the same material posted
as separate standalone posts.
**Status:** untested. Low priority — deliberately parked, not forbidden.

## H7 — A CTA in the body suppresses reach on this account
**Claim:** Posts with a link/ask reach fewer people than the same idea without.
**Basis:** The three link-card posts sit at 59/33/22; the direct-ask post is the
lowest in the entire sample (13); the top three have no link and no ask. Confounded
— those are also the personal ones.
**Refuted if:** paired posts (same idea, one with CTA, one without) show no gap.
**Status:** untested. Design the pair before believing either direction.

## H11 — Unverified replies are handicapped in thread ranking
**Claim:** Play A runs at a disadvantage without X Premium, whose advertised
features include boosted replies.
**Basis:** X's own marketing, surfaced on the profile 2026-08-22. **Not measured
by us**, and the effect size is unknown.
**Refuted if:** E1 produces primary-segment follows at an acceptable rate
unverified.
**Test:** run E1 unverified two weeks, then buy Premium and compare the same
payload types. **Status:** untested. Do not treat X's marketing as a finding.

## H10 — Off-graph surfacing, not the follower graph, sets reach here
**Claim:** On this account, views come overwhelmingly from non-followers.
**Basis:** ~13 followers against a 5–178 view range. 178 views cannot come from
13 accounts. The graph is arithmetically incapable of explaining the variance.
**Why it matters:** it means reach is *winnable without followers first* — but
also that the thing being optimised is whatever X uses to decide off-graph
surfacing, which we have never measured and cannot see.
**Refuted if:** per-post analytics show follower impressions dominating.
**Test:** the per-post analytics view (Q1). **Status:** strongly indicated,
one screen away from confirmation.

## H9 — The daily six suppressed reach rather than building it
**Claim:** Posting 6/day into a graph that never engages trains distribution
down; X weights recent engagement rate, and ten consecutive zero-engagement
posts is the strongest negative signal an account can send.
**Basis:** Reach fell monotonically as cadence rose — Feb ~139 median → Aug
13–16 ~28 → Aug 17–18 ~8.5, the last window being ten posts in two days.
**The honest competing explanations** (E0 result, none excluded):
 (a) the graph was already inactive and the fall predates the cadence change;
 (c) topic shift from personal/career to technical, and the audience that
     engaged with the first does not exist for the second.
**Refuted if:** cutting to 1/day for 14 days leaves the median at 5–11.
**Status:** **largely defused by the follower audit, 2026-08-22.** With ~13
followers there was never much on-graph distribution to suppress, and 5–11
views is a plausible off-graph floor rather than a penalty. Suppression may
still be real at the margin, but it is no longer the leading explanation and
must not be treated as one. **The leading explanation is now simply: there is
almost no audience, and off-graph surfacing is doing all the work.**
**Retained as:** a secondary reading of E5, not its purpose.

## H8 — The primary segment is not currently in the follower graph
**Claim:** The 178-view post reached a friend/peer graph, not agent builders.
**Basis:** Inference only. Both replies ever received came from personal posts;
no Icarus post has drawn a reply.
**Why it matters more than the view counts:** if true, every reach number in the
record measures the wrong audience, and Play A is not just the best lever — it is
the *only* one that changes who is reading.
**Refuted if:** a manual audit of followers finds a meaningful share shipping with
coding agents.
**Status:** **SUPPORTED, 2026-08-22, by direct audit.** ~13 followers, list
enumerated end to end. Zero clear primary-segment members. ~6 are
build-in-public reciprocal follows — the cohort `audience.md` names as *not the
audience*. ~4 are not developers at all. The technical posts were never reaching
an agent builder, so their zero engagement says nothing about the material.
**This closes the question the ten-post zero could not answer.** Listed in `OPEN_QUESTIONS.md`.

---

## Retired / decided (do not re-argue)

- **"Post more Icarus content."** Rejected on data: Icarus posts measured
  13–59 views, personal 123–178. Icarus stays 1 of 6. (Vault § Why Icarus is 1
  of 6.) Reopen only with new reach data.
- **"Disclose the zeros publicly."** Decided against by Alankrit 2026-08-17
  against the measured data. Logged in vault [[Decision History]]. H4 measures
  the price; it does not reopen the decision.
