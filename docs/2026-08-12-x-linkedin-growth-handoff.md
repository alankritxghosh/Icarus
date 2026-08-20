# X + LinkedIn growth — handoff

Scoped handoff for one specific thread of work: X content, finding leads on
X/LinkedIn, and distribution strategy on both. Written 2026-08-12, pulled
from the outreach/growth work done that session — not an engineering plan,
so it doesn't follow `docs/plans/` conventions.

**Scope note:** `CODEX.md` defines Codex's mandate here as quality
enforcement and production-readiness, explicitly *not* feature/content work.
This document is marketing/distribution strategy, outside that mandate as
written. Whoever picks this up should either be a session not bound by that
file, or `CODEX.md` should be updated first — don't silently stretch scope.

## 1. X content

Priority 5 in `docs/HANDOFF.md` (search "PRIORITY 5 — Icarus X Content")
specifies two posts, not yet written:

- **Post 1 — Demo.** Accompanies a demo video showing Icarus against real
  repos. Must communicate: what Icarus does, why engineering memory/context
  matters, what the demo actually shows, why this differs from generic code
  search/RAG. Don't oversell — let the demo carry the argument.
- **Post 2 — Agent Mode.** Introduces the Agent Mode direction: coding
  agents are good at writing code, bad at knowing *why* the codebase is the
  way it is. Icarus supplies that. Position as `Coding Agent + Icarus
  Engineering Context = Better-informed implementation` — not a competitor
  to coding agents, the context layer under them.

**Raw material already on hand, don't re-derive:**
- Two recorded product demos sit uncommitted at `site/shots/demo_icarus.mov`
  and `site/shots/icarus_product_demo_2026-07-24.mov` — check before
  recording a third.
- The real cited-answer examples on the live site (`psf/requests` HTTP/2
  question + the honest-unknown redirect-limit question) are proven,
  screenshot-able receipts — reuse rather than inventing a new example.
- `docs/decisions/2026-06-30-organizational-memory-positioning.md` has the
  positioning language ("organizational memory," explanation as the wedge)
  that Post 2's Agent Mode framing should stay consistent with.

**Tone lesson to carry over from email (see §3):** two full-scale cold
email batches failed — one generic, one heavily personalized with landing
pages. Alankrit's read: information volume was the failure mode, not
personalization depth. The standing outreach template since is short,
direct, one ask, no em-dashes, reads like a person typed it. Apply the same
instinct to X copy — a post that tries to pre-empt every objection in one
go will likely underperform a short, confident claim + the demo doing the
proving.

## 2. Finding leads on X and LinkedIn

**X: 50/50 done.** `outputs/leads/x_accounts.md` — every row is a real,
found post or profile with a working link, not a guess. Sourced by
searching for people who: build software, use coding agents, discuss
Claude Code/Codex/Cursor, build developer tools, run engineering teams,
work on AI infra, or openly discuss engineering workflow — per Priority 4's
brief in `docs/HANDOFF.md`. Read that file's "What's NOT here, and why"
section before extending it — it names exactly which rows are weak
(single-post evidence, reach-not-fit accounts) and which searches were
tried and came up empty.

**Method that worked, reusable for the next batch:**
- Search X directly (`site:x.com "<phrase>" <topic> 2026`), not general web
  search — general search surfaces blog posts *about* X activity, not the
  posts themselves, and a citation needs to resolve to the real post.
- Require a real, dated, linkable post or profile per person. No
  "referenced in a search cluster" entries without individually verifying
  — one such row (`Peter Pang`) is flagged lower-confidence in the file for
  exactly this reason; don't repeat it uncorrected.
- Drop aggregator/no-personal-opinion accounts (two were found and cut:
  `@ArchiveExplorer`, `@vasuman`) and thin-evidence accounts unless flagged
  explicitly as such.
- Org/community accounts (`@duckdb`, `@claude_code`) need a different pitch
  than individuals — partnership framing, not a personal DM — and unclear
  ownership accounts need affiliation confirmed before any outreach.

**LinkedIn was not started when this handoff was written; the independent
batch is completed in the session update below.** The original Priority 4
brief asked for a LinkedIn cross-reference on every X lead and it was
explicitly skipped under a time ceiling — see `x_accounts.md`'s "No LinkedIn
cross-reference done." The session chose option 2 below deliberately:
1. **Cross-reference the existing 50** — find each X account's LinkedIn
   profile (same identity-verification bar: real name match, real role
   confirmation, no guessing a profile is the same person off a name
   alone).
2. **Source LinkedIn independently** — different platform, different
   population skew (more enterprise eng leaders/managers, less
   independent-builder voice than X). A fresh search rather than a mirror
   of the X list may find a genuinely different audience segment worth
   having separately.

LinkedIn's own search is far more locked down for non-logged-in/API access
than X — expect this to need either manual browsing (`claude-in-chrome` /
`computer-use` against a real logged-in LinkedIn session, not scraping) or
LinkedIn's own Sales Navigator-style search if available, not a generic web
search substitute. Don't fabricate a LinkedIn URL from a guessed
name-slug pattern — verify the profile is real before citing it as a lead.

## 3. Distribution strategies on X and LinkedIn

**What's already been tried and failed, so it isn't repeated:**
- Batch 1 (23 cold emails, generic copy): 0 replies.
- Batch 4 / "repo-proof" (17 cold emails, heavily personalized, each with a
  linked landing page + real per-repo Icarus finding): ~0 useful replies.
- Combined finding (`repo-proof-outreach-also-failed-simple-copy-now-standing`
  memory): two structurally opposite strategies both failed. The working
  hypothesis is information volume in the *first touch*, not targeting or
  personalization depth. Landing pages, install manuals, and repo-specific
  findings now go in the *reply*, not the opener.

**Strategy options for X, roughly ordered by effort:**
1. **Direct DM outreach to the sourced 50** (`outputs/leads/x_dm_drafts.md`
   has drafts already). Apply the email lesson: keep the opener to 2-3
   sentences, one clear ask, no link in the first message unless it reads
   naturally — offer to send it, don't front-load it.
2. **Organic posting** — the two Priority 5 posts, plus a steady low-volume
   cadence (1-2x/week) mixing: a real cited-answer screenshot, a build-log
   update, and occasional replies into bigger threads about coding-agent
   limitations (reply-guy strategy — cheap, and the accounts sourced in
   `x_accounts.md` are exactly the threads to reply into instead of only
   DMing).
3. **Demo-video reuse loop** (see memory `outreach-demo-recording-content-
   loop`): record one demo per newly connected repo, reuse across X,
   Substack, and HN. Open question flagged in that memory and still
   unresolved: is HN better used as a lead source (comments naming real
   pain points → new leads) or pure distribution (submit and hope for
   traffic)? Worth deciding before investing in a cross-post routine.

**Strategy options for LinkedIn:**
- LinkedIn skews toward longer-form, more explicitly professional
  "thought leadership" posts than X's short, punchy format — a straight
  repost of X copy will likely underperform. The Agent Mode post
  especially could work as a slightly longer LinkedIn-native version
  (more context, more explicit "for engineering leaders" framing) rather
  than a copy-paste.
- LinkedIn's audience here likely skews more toward engineering
  managers/directors evaluating tools for a team, versus X's more
  individual-builder skew — if a LinkedIn lead list gets built (see §2),
  distribution copy should speak to team/adoption concerns (the kind of
  case-study angle already used for some X leads like the Uber/Microsoft
  rollout threads), not just personal productivity.
- At handoff time, no LinkedIn posting cadence, account, or content had been
  started. The session update below records the first content and cadence
  drafts; nothing was published or scheduled.

## What this handoff does NOT cover

- Actually sending anything — every draft referenced above is unsent by
  design (per `AGENTS.md`'s explicit-permission rule on sending messages).
- Priority 6 (sharing with an engineer friend) — separate thread, blocked
  on a missing email address, not part of X/LinkedIn.
- Any decision on hiring/cofounder GTM ownership — a live, separate
  conversation (see recent session context on the Manroze thread), not
  scoped into this document.

## Session completion update — 2026-08-12

Alankrit explicitly authorized the scoped growth session described above. No
post, DM, connection request, email, or other external message was sent or
scheduled.

Completed deliverables:

- `outputs/growth/2026-08-12-social-content.md` — the two final X drafts with
  alternate hooks, two LinkedIn-native versions, asset choice, and claim
  guardrails.
- `outputs/growth/2026-08-12-x-outreach-audit.md` — exhaustive segmentation,
  a prioritized eight-account cohort, current-activity checks, corrected
  account ownership, and revised openers.
- `outputs/growth/2026-08-12-linkedin-leads.md` — twelve independently sourced
  engineering leaders with real LinkedIn URLs and live headline evidence.
- `outputs/growth/2026-08-12-distribution-plan.md` — four-week X/LinkedIn
  calendar, engagement bounds, qualified-conversation metrics, decision rule,
  and the HN recommendation.

Evidence corrections made during the work:

- The X list said 50/50 but held only 49 table rows. Lee Robinson was added
  from a real 2026 X post; the list and DM headings now mechanically total 50.
- `@trq212` is confirmed as Thariq working on Claude Code at Anthropic.
- `@claude_code` explicitly describes itself as an independent community
  account, not an official Anthropic voice.
- `site/shots/demo_icarus.mov` is the selected demo: 60.06 seconds and shows
  both the cited answer and honest refusal. The 6.56-second alternative stops
  before the answer, so no third recording was needed.

The next smallest brick, after Alankrit reviews the copy, is to publish only
the demo post and measure qualified responses before releasing the Agent Mode
post or authorizing any direct outreach.

### Zero-awareness correction

Alankrit clarified after reviewing the first batch that Icarus is unknown to
the audience. The copy and distribution plan were revised accordingly. Every
standalone post and first-touch draft now begins by defining Icarus, its user,
its job, and its evidence boundary before using the tagline, showing the demo,
or introducing Agent Mode. The four-week plan now measures whether people can
describe Icarus correctly, not only whether they engaged.

### Full-product correction

Alankrit then clarified that the original growth framing reflected an outdated,
too-narrow product model. A read-only reconstruction of the August 7–12 work
confirmed that Icarus is no longer accurately introduced as only a voice
overlay, code explainer, or question-answering tool. The current category is:

> Icarus is engineering memory for software teams and their coding agents. It
> reads a repository's GitHub record and returns cited context or an honest
> unknown before someone changes the code.

The growth artifacts were revised around the actual current system:

- Human workflows: repository orientation, returning-user briefing,
  multi-step investigation, decision history, and engineering-memory gaps.
- Agent Mode: read-only change, code-range, and structured task context over
  the same brain; Icarus complements agents and never edits code.
- Measured evidence: the four-of-four unprompted-call trigger result and the
  single directed task where seven prior attempts stopped an eighth duplicate,
  always presented with their sample limits.
- Memory capture: an unknown can become a human-authored, GitHub-reviewed
  engineering-memory record, citable only after merge and re-indexing.
- Honesty limits: deterministic citation containment and covered guards are not
  advertised as a mathematical proof of arbitrary semantic entailment.

The remaining public website and canonical-document drift found during that
reconstruction is outside this growth-artifact revision. No website, runtime,
deployment, post, or message was changed or published in this session.
