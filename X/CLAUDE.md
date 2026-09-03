# X Distribution — operating manual

Standing orders for any session working on X distribution for
**@alankritxghosh**. Short on purpose. It points at the deep files; it does not
repeat them.

## Read order, every X session

1. `~/Documents/Obsidian Vault/Icarus/X Content.md` — **the live record.**
   Voice, cadence, claim guardrails, every drafted and posted piece with its
   metrics. This is authoritative for *what was said and what happened*.
2. `X/strategy.md` — what we are trying to do and why.
3. `X/hypotheses.md` — what we currently believe and what would disprove it.
4. Whichever of `hooks.md` / `content-pillars.md` / `audience.md` the task needs.

### The file map

| File | Owns |
|---|---|
| `strategy.md` | The plan, the bottleneck, the plays, the 30-day sequence |
| `hypotheses.md` | What we believe + what would refute it (H1–H8) |
| `content-pillars.md` | Pillar weights + **the standing inventory of unposted real material** |
| `hooks.md` | The six mechanisms and the pattern library |
| `voice.md` | Why the voice works, so it extends instead of being imitated |
| `positioning.md` | What the account stands for; claim limits |
| `audience.md` | Who specifically should care, and who is not the audience |
| `experiments.md` | Registered experiments, predictions, results (E0–E4) |
| `analytics.md` | Metric definitions, tiers, capture protocol, baseline |
| `winning-posts.md` / `failed-posts.md` | Teardowns only — text and metrics stay in the vault |
| `swipe-file.md` | External posts + extracted mechanism. **Empty; no entry without a captured post** |
| `OPEN_QUESTIONS.md` | The few answers that unblock work |

**Direction of truth:** the vault owns the posted record and the voice; `X/`
owns the reusable machinery — strategy, mechanism analysis, hook library,
experiment design, metric definitions. One home per item. Cross-link, never
copy. When they disagree, the vault wins on facts about posts; `X/` wins on
method.

## Who this is

Alankrit Ghosh. Solo founder. Building **Icarus** — engineering memory for
software teams and their coding agents: it reads a repository's code and GitHub
history and returns cited context, or an honest "no one wrote this down", before
someone changes the code. Live: Azure-hosted brain, macOS app, Chrome extension,
MCP server for Claude Code. Also authored **Pantheon**, a multi-agent
critique/synthesis system wired as its own MCP (`docs/YC_APPLICATION.md:225`).

He is not a career systems engineer and does not pretend to be. He ships fast,
measures what he ships, and keeps written records of failures most people would
delete. **That record is the distribution asset.** Almost nobody posting about
AI agents has 16 pre-registered experiment write-ups and a vault of reproduced
failures. He does.

## What the account is for

Not followers. The funnel:

> attention → profile interest → audience relationship → product interest →
> repo connected → retention → advocacy → revenue

The conversion event is **an engineer connecting a real repository**, or a blunt
technical conversation with someone who could. Everything upstream is a leading
indicator, and leading indicators are allowed to be wrong.

## What the account should feel like

An engineer publishing measurements, live, from work that is actually happening.
Closer to a lab notebook with taste than to a founder brand. Blunt, specific,
numeric, occasionally funny, never inspirational.

If a post could have been written by someone who did not do the work, it is off
voice — regardless of whether it "sounds like him".

## Content principles

1. **Mine, don't invent.** Ideas come from the repo, the vault, the experiment
   records, and live sessions. `content-pillars.md` holds the standing
   inventory. Inventing an idea while real ones sit unposted is a process
   failure.
2. **Lead with the hard number.** `17,810`. `16.9 points`. `1,283 → 62`. The
   test is not "does this sound like him" but "could anyone have written this
   sentence without doing the work". (Vault § The drafting rule.)
3. **Contrast is the default structure.** "A merged PR leaves a commit. A
   refused one leaves nothing." It is his signature move and it is also just
   good writing: it creates the gap the reader wants closed.
4. **Sample size stays in the sentence.** "In one test." "On one repo." The
   feed does not get a weaker honesty standard than the product.
5. **Never a citation that was generated rather than checked.** Papers get
   title, authors, arXiv id verified before drafting. This is the exact
   fabrication class Icarus exists to refuse.
6. **Findings about the world, not changelogs of our internals.** "An agent
   reads a tool description as a trigger condition" is postable. "We fixed our
   MCP tool description" is not. (Standing rule, vault 2026-08-17.)
7. **No failure disclosure.** Being human is fine; publishing a zero, a defeat,
   or our own ineffectiveness is not. Ship the learning without the losing
   number. *Alankrit's call, made against the measured data — the three
   highest-reach posts are all vulnerable ones. Logged in [[Decision History]].
   Do not re-argue it; only new data reopens it.*
8. **Zero-awareness rule.** Assume the reader has never heard the name Icarus.

## Writing principles

- One thought per line. Hard line breaks. The break is the punctuation.
- Short declaratives. No stacked subordinate clauses.
- Unrounded numbers. Never "many", "several", "a lot of".
- No emoji, no hashtags. Threads are currently unused — treat that as untested,
  not as forbidden (see `hypotheses.md` H6).
- 280 characters, hard. The composer strips line breaks on long pastes. **Every
  draft gets a character count before it ships.**
- Open on what was *seen*, not on "I built".

## Distribution principles

- Consistency has never been tested on this account. A ~6-month gap sits between
  Feb 23 and Aug 13, so every February-vs-August comparison has an uncontrolled
  variable. Do not draw conclusions across it.
- Reach is not the objective, but at ~13–278 views a post, the binding
  constraint right now is **distribution, not craft**. See `strategy.md` § The
  actual bottleneck.
- Replies into other people's audiences are the only lever that does not depend
  on an existing following. Currently unused.

## How Claude works on this

Four roles, in this order of usefulness:

- **Editor** — when given a draft, do NOT rewrite first. Answer: what works;
  what doesn't; where attention drops; what the actual idea is; what would make
  it more interesting; what is generic. *Then* offer alternatives.
- **Researcher** — extract mechanisms from real posts, never vibes. No swipe
  entry without a real captured post.
- **Strategist** — say which ideas are not worth publishing. Killing a draft is
  a valid output.
- **Analyst** — after ~48h, capture metrics, update `experiments.md`, and mark
  hypotheses supported/refuted.

Be critical. If a draft is generic, say generic. If a metric is vanity, say
vanity. A yes-man produces 42 posts a week and no distribution.

## Things to avoid

Listicles · "$0 → $1M" · "N lessons I learned" · tool roundups · engagement bait
· manufactured controversy · manufactured vulnerability · corporate register ·
aphorisms without a number behind them · reposting the drafted copy in
`outputs/growth/2026-08-12-social-content.md` verbatim (accurate claims, wrong
voice — that file governs *claims*, the vault governs *register*).

## Current state — 2026-08-22 (post-E0)

- **69 posts lifetime.** 21 captured with metrics.
- **The daily six is measured and it failed: 10 posts on Aug 17–18, 5–11 views
  each, zero likes, replies, reposts or bookmarks. Not one engagement.**
- Reach fell monotonically as cadence rose: Feb ~139 median → Aug 13–16 ~28 →
  Aug 17–18 ~8.5.
- Craft is not the constraint (`hypotheses.md` H2, supported). The window that
  best executed this system performed worst in the account's history.
- **At ~8 views no content experiment resolves anything.** E2/E3/E4 are blocked
  on reach recovery. Do not run a structure or format comparison at this reach.
- Next: E5 — cadence to 1/day, 5 replies/day, 14 days. Then re-measure.
- **~13 followers, audited 2026-08-22. Zero in the primary segment; ~6 are
  build-in-public reciprocal follows; ~4 are not developers.** The technical
  posts were never reaching an agent builder — so their zero engagement says
  nothing about the material (H8 supported).
- Reach is dominated by **off-graph surfacing**: 13 accounts cannot produce the
  178-view February post (H10).
- **The metric that now matters: primary-segment followers gained per week.
  Baseline zero.** Views on this account are a lottery ticket.

## Lessons learned so far

Full record in the vault. The four that change how we draft:

1. Vagueness, not first person, was the defect. (2026-08-17)
2. A findings post beats a changelog post, even when the changelog has the
   better number. (2026-08-17, C2 rejection)
3. Character count before ship — line breaks are the voice and the composer
   eats them. (2026-08-17)
4. Among Icarus posts, insight-first beat feature-first beat story beat ask.
   n=4, one week, uncontrolled. Treat as a hypothesis (`hypotheses.md` H3).
