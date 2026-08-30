# Failed posts and killed drafts — the postmortems

Same one-home rule as `winning-posts.md`: post text and metrics live in the
vault. This file holds the diagnosis.

**A killed draft belongs here too.** Two rejections on 2026-08-17 produced
standing rules that now govern every draft — those rules are the durable output
of that day, not the posts that shipped.

---

## The whole Aug 17–18 window — 10 posts, **12–38 views** (revised), zero replies

> [!warning] Corrected 2026-08-26. The "5–11 views" this section was built on was
> a stale capture; the real range is 12–38, median ~16.5, and one post has a like.
> The diagnosis below is **weakened but not overturned**: the window is still the
> weakest of 2026 and still drew zero replies, reposts and bookmarks. But it is no
> longer a zero-engagement window, and "served to almost nobody" was overstated by
> a factor of two. See `analytics.md` § Settling curve.

### Original diagnosis, left as written

## The whole Aug 17–18 window — 10 posts, 5–11 views, zero engagement

**This is the largest failure in the record and it is not a writing failure.**
Every one of the ten met the standard: papers verified to author and arXiv id,
contrast openers, character counts taken, sample sizes in the sentence, no
changelog posts, no fabricated citation. The window that best executed this
system performed worst.

**Failure point: distribution, not craft** (`hypotheses.md` H2, now supported).
Ten posts to a graph that produced zero engagements means the posts were served
to almost nobody, and the handful reached contained nobody who cared.

**What must NOT be concluded:** "technical content doesn't work." That
conclusion is unavailable at 8 views — the sample cannot distinguish a bad post
from an unseen one. Also unavailable: "the daily six caused it." Three live
explanations, none excluded (E0 result).

**What changes:** cadence to 1/day, replies to 5/day, reach measured before any
further content experiment (E5). Craft work is currently the lowest-yield
activity available.

---

## Published, underperformed

### 2026-08-16 · "Looking for 10-20 engineers" — ~~13 views, lowest in the record~~ 27 views, mid-pack
**Corrected 2026-08-26.** It was never the lowest — it was the *earliest measured*.
At 27 views it sits above every Aug 17 post. **The unearned-ask diagnosis below
lost its supporting number** and is now an untested hypothesis, not a finding.
**Failure point:** the ask arrived before any reason to care. The post explains
what Icarus does *after* asking for a commitment.
**What was actually good:** "break it, not just give me polite feedback" is a
strong, specific line worth keeping.
**Hypothesis:** a direct ask is not the problem; an *unearned* ask is. Confounded
with H7 (does any CTA suppress reach?) — E4 separates them.
**Change:** ask in beat three, never beat one. Or ask in a reply to a post that
earned it.

### 2026-08-14 · Agent Mode ships — ~~33~~ 43 views (corrected 2026-08-26)
**Failure point:** feature-first. "Icarus now works inside Claude Code as…"
announces a topic; it does not open a gap.
**Change:** the same material with a scene opener is item 2–3 in
`content-pillars.md` and is unposted. Rewrite, don't repeat.

### 2026-08-17 · Claude Code auto mode — captured at 2 views
**Not a failure — a measurement error.** Captured 19 minutes after posting.
**Change:** capture at ~48h, always (`analytics.md`). This entry exists so the
number is never quoted as a result.

---

## Killed in review — the valuable ones

### The five-second test (posted, then diagnosed) — 2026-08-17
**What happened:** the no-failure-disclosure rule was applied by stripping the
specifics along with the losing number. What survived was an aphorism.
**Diagnosis, in Alankrit's words:** *too generalised.*
**Standing rule produced:** the defect was never first person — it was
**vagueness**. Lead with the hard number, keep the specifics, make them about
work done. (Vault § The drafting rule.)
**Why it matters:** this is the failure mode that will recur most often, because
the no-failure rule and the specificity rule pull against each other on every
personal draft.

### The C2 changelog draft — killed 2026-08-17
**Draft:** our MCP tool description rewrite, 0/11 unprompted calls → 4/4.
**Why killed:** a before/after about *our own tooling*. The reader learns nothing
they can use; the number is only interesting if you already care about our MCP
surface.
**Standing rule produced:** post findings about how repositories and agents
behave, never a changelog of our internals.
**The reframe that survived:** *"An agent reads a tool's description as a trigger
condition, not as a description."* Same numbers, general lesson, sample size in
the sentence. Drafted at 250 chars; still unposted.

### The 316-character first draft — 2026-08-17
**What happened:** the composer stripped the line breaks on paste. The line
breaks are the voice.
**Standing rule:** character count before every ship. 280 hard.

---

## The recurring failure modes, ranked by how often they will happen

1. **Specifics stripped in the name of some other rule.** → the anyone test.
2. **Feature/product in beat one.** → move it to beat three.
3. **A conclusion supplied for the reader.** → delete the last sentence.
4. **Measuring too early and quoting the number.** → 48h.
5. **A number quoted without its sample size.** → "in one test", "on one repo".
