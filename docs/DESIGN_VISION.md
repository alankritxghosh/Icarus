# Icarus — Design Vision (art direction)

The aesthetic companion to [UI_UX_BRIEF.md](UI_UX_BRIEF.md) (which covers states &
data). This doc is opinionated on purpose — it's the *look and feel* I'd build
toward. Target the space you named: **between clean modern (Figma) and
neo-brutalist.**

## The one-line direction: **Honest Brutalism**
A calm, modern, generously-spaced base (the Figma side) with **brutalist honesty**
in the structure: visible edges, hard shadows, monospace evidence, blunt language,
nothing hidden or glossed. The design should *embody the product's promise* —
Icarus shows its receipts and refuses to bluff, so the UI should look like it has
nothing to hide: raw structure, plain words, evidence in mono, the refusal owned
loudly. Polish where it aids reading; brutalism where it signals honesty.

**Why this synthesis fits Icarus (not just taste):**
- **Brutalism = honesty made visual.** Exposed structure, hard edges, no
  decorative gloss → mirrors "cite-or-unknown, no bluffing." A glossy, rounded,
  gradient SaaS look would *undersell* the one thing that makes Icarus special.
- **Figma-calm = trust + readability.** Engineers read carefully; the base needs
  restraint, whitespace, a real type scale. Pure brutalism alone is fatiguing and
  reads as a gimmick.
- The fusion says: *serious, blunt, engineer-built, trustworthy.*

## Principles
1. **Evidence is monospace.** Anything from the codebase — citations, refs, the
   "searched" list — is mono. It reads as "machine truth," and visually separates
   *the model's prose* from *the repo's receipts*.
2. **Structure is visible.** Real 1.5–2px solid borders, hard **offset shadows
   (no blur)** as the signature motif. Cards are flat blocks — *in the windowed
   app*. The floating ask overlay is the deliberate exception; see "The overlay
   exception" below.
3. **Calm base, loud truth-moments.** Quiet layout; the two hero states (cited
   answer, honest unknown) are where boldness is spent.
4. **Blunt language, big.** Confident headings, plain words. "No one wrote this
   down." is a *headline*, not a toast.
5. **Restraint in color.** Near-monochrome paper + ink, one signal accent, two
   semantic tones. High contrast (brutalist) without circus.
6. **No fake confidence.** No glossy gradients, AI-sparkle clichés, or effects
   standing in for substance. The credibility comes from structure, not polish.
   This principle is untouched by the overlay exception below: translucency
   there is a *spatial* device, not a confidence device.

## The overlay exception (decided 2026-07-22, Alankrit)

**The floating ask overlay is translucent. The windowed app is not.** This
reverses an earlier blanket ban on glass, deliberately and with a reason —
recorded here so it is not re-litigated, and not quietly re-drifted either way.

Why the exception is principled rather than a taste climb-down:

- The overlay **sits on top of your actual work** and must be dismissable from
  attention without being dismissed from the screen. Translucency is how a
  surface says "I am temporary and I am over your editor" — it is spatial
  information, not decoration. The windowed app makes no such claim, so it keeps
  the flat blocks and hard offset shadows.
- The **honesty principles are unaffected.** Evidence stays monospace, the
  refusal stays a headline, the palette stays restrained. What was banned was
  gloss substituting for substance; a blur that communicates layering is not
  that. If translucency ever starts hiding structure — softening a border,
  blurring the receipts — it has crossed back into the ban.

Constraints the overlay carries (from live use, 2026-07-22):

- **Small.** It must not occupy much of the screen. Direction 03 ("Receipt") is
  ~430pt wide.
- **The written proof is on screen**, quoted from the source — not a pointer you
  must click to verify. An overlay that shows only refs makes the user leave it
  to check anything, which is the wrong default for a product whose whole claim
  is that it never asks to be taken on faith.
- **Speech is a summary; the screen is the record.** Icarus speaks the first
  sentence of the grounded answer, never the whole thing and never a separately
  generated précis (a second generation is a second thing that can drift from
  the citations).

**Known open:** transition smoothness on the overlay is unresolved as of
2026-07-22. Profiling showed the app's main thread is essentially idle during
transitions, so the cause is NOT in-process CPU; do not "fix" it by reaching for
more animation tuning without measuring first.

## Tokens (a starting palette — tune in Figma)
Lean "paper & ink" so citations and code feel native; works light or dark.

- **Surface:** off-white paper `#F7F6F2` (light) / ink `#0E0F12` (dark). Avoid pure
  #FFF/#000 — slightly warm/desaturated reads as crafted, not default.
- **Ink/text:** `#16181D` on light; `#ECECE7` on dark. One muted gray for
  secondary (`#6B7280`-ish).
- **Signal accent (actions, links):** one confident, slightly-electric hue — e.g.
  a strong blue `#2F6BFF` or an acid lime `#C7F000` if you want more brutalist
  edge. Pick ONE and use it sparingly (button, citation link, focus ring).
- **Two semantic tones (the heroes):**
  - *Grounded answer* — a steady, credible green/teal accent on the citations block.
  - *Honest unknown* — NOT red, NOT an error. A calm, confident neutral/amber block
    that reads as a deliberate stance. (Error states get their own clearly-different
    treatment so "I don't know" never looks like a failure.)
- **Borders:** `#16181D` at 1.5–2px (light) — black-ish, brutalist.
- **Signature shadow:** hard offset, e.g. `4px 4px 0 #16181D`, **0 blur**. This one
  motif carries the whole brutalist feel.
- **Radius:** small and consistent — `0–4px`. Brutalist leans 0; allow up to 4 to
  soften toward the Figma side. Never pill-rounded cards.

## Type
- **UI / prose:** a clean grotesque — Inter, Geist, or Söhne-like. Real scale:
  big confident H1 (28–36px), comfortable body (16–17px), tight labels (12px,
  uppercase, letter-spaced — a brutalist tell).
- **Evidence / code / refs:** a monospace — Berkeley Mono / JetBrains Mono / IBM
  Plex Mono. Used for `pr:1482`, code paths, the searched list.
- Pairing a grotesque + a mono *is* the Figma↔brutalist bridge in one move.

## The hero moments (where the look earns its keep)
- **Cited answer:** calm prose in the grotesque, then a bordered **"Evidence"
  block** — mono citation chips, each a signal-accent link to the real source
  (PR / issue / code, visually typed). The receipts look like receipts.
- **Honest unknown (THE shot):** the most brutalist screen. A full-width bordered
  block, hard shadow, a big plain headline **"No one wrote this down."**, one calm
  line of reassurance, and a muted mono *"Searched: …"* so the honesty is
  transparent. It should feel *intentional and confident*, never apologetic.

## Motion
Minimal and snappy (120–180ms, ease-out). No bounce, no float, no shimmer. Honest
software moves directly. The "thinking" state is a calm, structural placeholder
(skeleton block / blinking caret in mono), not a spinner.

## Anti-patterns (do not)
Decorative gradients · blurred drop shadows · everything-rounded · emoji-as-UI ·
gradient "AI" buttons · a chat-bubble thread look · centered hero marketing
fluff. None of it matches a tool whose pitch is *it won't lie to you.*

**Glassmorphism was on this list until 2026-07-22** and is now permitted on the
floating overlay ONLY, for the spatial reason given in "The overlay exception".
It remains an anti-pattern everywhere else — the windowed app, the web demo, any
marketing surface.

## Carrying forward
The macOS app (Phase 3) adds a translucent overlay — Honest Brutalism still holds:
the overlay is the *frame*, but the content keeps mono evidence, hard borders, and
the blunt honest-unknown block. Web and app share the same visual language.

---
*Net: think "a beautifully typeset engineering notebook with hard edges," not "a
friendly AI chatbot." Clean enough to trust, raw enough to believe it isn't
bluffing.*
