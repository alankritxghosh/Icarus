# Launch film — shot list, v0.1

**Status: OPEN. Not agreed.** Direction set 2026-08-26 (cinematic, Apple-grade,
Linear pole rather than Arc pole). This is a first pass to argue with, not a
lock. Open questions at the bottom are real, not rhetorical.

Companion to `outputs/growth/2026-08-23-capture-spec.md`, which owns the
SHOOTING rules. This file owns the EDIT. Where they disagree, the capture spec
wins on anything to do with what is real on screen.

---

## The two deliverables, which are not the same asset

**A. Working capture (owed to Harshitha, same day as the shoot).** Three takes,
unedited, sent as-is. Its job is to show a person what the product does. No
grade, no type, no sound design. Do not hold this back for the film.

**B. The launch film (this document).** Built from a second, more careful pass
over the same three takes. Weeks, not a day.

Folding B into A delays A by weeks and produces a worse B, because a film shot
to be sent tonight is shot in a hurry.

---

## The rule that governs every shot

**Nothing on screen may imply more than Icarus does.** Apple's grammar is
aspirational and this product's identity is refusing to overclaim. A cinematic
edit that suggests a capability we do not have is the 25% claim again, in a
format that is harder to retract. Each shot below carries a claim check.

Corollary: no manufactured UI, no motion-graphic "AI thinking" abstraction, no
invented latency. If retrieval takes four seconds, the cut may compress it, but
it may not depict it as instant.

---

## Structure — one turn, ~55s

The film has exactly one narrative turn: **it answers, and then it refuses.**
Everything before the turn earns the turn. Everything after is one line of type.

| # | Dur | Source | On screen | Type | Sound | Claim check |
|---|---|---|---|---|---|---|
| 1 | 4s | none | Black | `Your codebase does not explain itself.` | Room tone only | Not a product claim |
| 2 | 6s | new capture | A real source file scrolling slowly, dark, no chrome, no cursor | none | Low bed enters | Real file, real repo |
| 3 | 3s | new capture | Scroll stops. Hold on ordinary code | `The reason is not in here.` | Bed holds | True by construction |
| 4 | 5s | Take 1 | Repo typed into the sidebar, connect pressed, index begins | none | One UI tick | Real connect. Compress the wait, never depict it as instant |
| 5 | 6s | Take 2 | The overlay opens (⌘⇧I). Question typed, verified against production | none | Key ticks, then silence | Question must be one of the three verified in the capture spec |
| 6 | 5s | Take 2 | Citation chips resolve one at a time. Hold two full seconds after the last | none | A tick per chip | The chips are the product. Do not clip them |
| 7 | 4s | Take 2 | The cited answer, held, readable | none | Bed | Real answer, unedited text |
| 8 | 2s | none | Cut to black | none | **Silence** | The turn |
| 9 | 5s | Take 3 | A second question typed. Something the repo genuinely never recorded | none | Key ticks only, no bed | Must genuinely abstain in production |
| 10 | 6s | Take 3 | **"No one wrote this down."** Hold three seconds past comfortable | none | **Total silence** | The climax. The one frame no competitor can screenshot |
| 11 | 4s | none | Black | `It will not guess.` | Bed returns, single note | True: cite-or-abstain is enforced |
| 12 | 5s | none | Mark, then wordmark | `Icarus` | Resolve | — |

**Total ~55s.** Shot 10 is the film. If runtime has to come out, it comes out of
2, 4 and 7, never 10.

---

## Craft rules for the edit

- **Void, not desktop.** Crop to the app window. No menu bar, no dock, no
  wallpaper, no second window, ever.
- **Nothing snaps.** Ease everything. No whip pans, no speed ramps, no zoom
  punches. If a move draws attention to itself, cut it.
- **Type held long enough to read twice.** Set in the app's own display face
  (`Theme.swift` § display), not a stock geometric sans.
- **One idea per shot.** If a shot carries two claims, it is two shots.
- **Silence is a shot.** Shots 8 and 10 are the only places the bed drops out,
  which is what makes them land.
- **Native resolution, scaled down.** Capture spec already requires ~1280 wide
  minimum against a 778px transcode target.
- **No voiceover in v1.** The Linear pole. Revisit only if the film tests as
  cold rather than restrained.

---

## Reference set to watch before cutting

- **Linear** — the target. Restraint, type, dark, no VO.
- **Vercel, Raycast** — dark technical product film, real capture, dev audience.
- **Browser Company (Arc)** — the opposite pole: narrative, warmth, personality.
  Watch to confirm we are NOT making this.
- **Apple software feature films** — the grammar the others are all derived
  from. Study the software spots, not the hardware films: the hardware work
  needs a stage and motion control and is not reproducible by one person.

---

## Open — genuinely undecided

1. **Which repo.** The capture spec says not `simonw/llm` (the site already
   demos it) and suggests `psf/requests`. But the two verified-abstaining
   questions are `simonw/llm` questions. **A fresh repo needs a fresh verified
   abstention, confirmed against production, before the shoot.** This is the
   single biggest scheduling risk in the film.
2. **Whether voice appears at all.** Hold-Right-Option is real and shipped and
   nobody else has it, but it adds a second idea to a film built on one turn.
   Currently cut. Arguable.
3. **Where this film is allowed to run.** Product Hunt, the website hero and a
   Show HN want different opening surfaces — a PH visitor will not install an
   unnotarized DMG, so a film that opens in the Mac app may sell a thing they
   cannot try that day. Work Queue § 4 already flags this and does not resolve it.
4. **Whether 55s is right.** A website hero loop wants 15s and no type.
5. **Who cuts it.** Remotion plus DaVinci is the stated stack, and this shot
   list is more DaVinci than Remotion.
