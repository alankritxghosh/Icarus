# Icarus — UI/UX Brief (for the Figma draft)

This is the design groundwork for redoing the product's screen. It describes
**what the face must show, the states it has, and the real data behind each** —
so the Figma design matches what the brain can actually deliver, and leaves room
for the next bricks. The current `demo/index.html` is a throwaway; this is the
real thing.

## What this screen is
The **face** of a privacy-first engineering brain. A person asks a "why / what /
how" question about a codebase and gets **either a cited answer or an honest "no
one wrote this down."** The honesty — citations on every answer, and a confident
refusal when nothing was recorded — **is the product.** The design's #1 job is to
make that trustworthiness *visible*, not to look like a generic chatbot.

Design north stars (from the product vision):
- **The honest "I don't know" is the hero**, not an error or a dead end.
- **Every answer carries its receipts** (clickable citations to the real source).
- **Calm, trustworthy, engineer-grade** — not playful, not salesy.

## The real data the UI has to work with (per request)
The backend returns exactly this for each question (`build_payload`):
- `verdict`: `"answer"` or `"unknown"`
- `answer`: the prose (empty when unknown)
- `citations`: list of `{ ref, url }` — e.g. `{ "ref": "pr:1482", "url": "https://github.com/…/pull/1482" }`. `ref` is typed: `pr:` / `issue:` / `code:`.
- `searched`: the list of source refs it actually looked at (even when it abstains)

Design only against these fields — anything else would be invented.

## States to design (all of them)
1. **First run / empty** — the ask box, a one-line promise of what Icarus does, maybe 2–3 example questions to click.
2. **Asking / loading** — a calm "thinking" state (the writer takes a few seconds). Not a spinner-as-afterthought; it's most of the wait.
3. **Answer** — the prose answer + a **Citations** group. Each citation: its typed icon (PR / issue / code), the `ref`, links out to GitHub. This is "trust me, and here's proof."
4. **Honest unknown — THE HERO** — a calm, confident card: *"No one wrote this down."* with a short reassurance ("the evidence doesn't record a reason, so Icarus won't invent one") and a **transparent "Searched: …"** disclosure showing it *did* look (the `searched` refs). Must read as a *feature*, never as a failure or error.
5. **Error / backend down** — clearly distinct from #4 (an unknown is honesty; an error is a problem). e.g. "Couldn't reach the brain."

## Citation design (the differentiator — get this right)
- Three source types, each visually distinct: **PR** (the "why"), **issue** (context), **code** (the "what"). Different icon/color.
- Citations are **clickable and land on the exact source** at the pinned commit.
- Consider a subtle "grounded in N sources" affordance; the `searched` list can be a collapsed "what I looked at" disclosure for transparency without clutter.

## Leave room for the next bricks (so the design doesn't get redone)
The roadmap will add these — the layout should anticipate them even if v1 hides them:
- **Repo context / picker** (Bricks 7, 11): a place to show "answering about: `owner/repo`" and later switch/select among multiple repos.
- **Public vs private + "safe model" indicator** (Bricks 8–9): a small trust badge — e.g. "private · zero-retention model" vs "public" — so the user knows their code is handled safely.
- **Source-type filters** (multi-language, Brick 10): room for more than PR/issue/code.
- **Freshness** (live sync, Brick 12): a subtle "indexed as of <commit/date>".

## Explicit non-goals (do NOT design these now)
- The macOS hotkey / mic / **translucent overlay** — that's the Mac app (Phase 3), not this web face.
- Accounts, billing, settings, admin, multi-tenant dashboards — not yet.
- A chat thread / conversation history — v1 is single question → single grounded result. (Note if you *want* threads; it's a brain change, flag it.)

## Constraints / facts for the designer
- It's a local web page today (stdlib server). Keep it a **single screen**, responsive, fast.
- Latency is real (seconds per answer) — the loading state matters.
- Tone: an engineer's trusted colleague. Citations and the honest refusal are the brand.

---
*When the Figma draft exists, hand it back and we'll map it to the build (the
payload fields above are the contract). The brain doesn't change for the redesign
— this is purely the face.*
