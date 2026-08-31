# Veo prompts — Icarus launch video

**Model:** Veo 3.1 (or 3.1 Fast for cheaper drafts). **Per clip:** 8s, 1080p, 16:9.
**Rule:** one camera move per clip. Generate 2–3 takes per prompt, keep the best.
**Audio:** Veo adds its own — keep the `Ambient noise:` line minimal and plan to
replace/mute all Veo audio in DaVinci with your own music + SFX.

Access: Google Flow (flow.google) — free tier ~50 credits/day. "Fast" = 20
credits, "Quality" = 100. Budget: the 3 image-to-video shots + opener + end card
on Fast ≈ 100 credits ≈ 2 days of free credits, or one day on AI Pro.

---

## Reusable NEGATIVE PROMPT (paste into the negative-prompt field every time)

```
morphing text, warping UI, changing interface, garbled letters, flickering text,
distorted typography, text scrambling, elements sliding around, layout shifting,
extra windows, popups, cursor movement, hands, people, reflections on screen,
lens flare, rolling shutter, heavy film grain, watermark, logo distortion,
color banding, oversaturation, fast motion, shaky camera, zoom pump
```

---

## Shot 1 — OPENER (text-to-video, NO image)  · 6s

```
Slow forward dolly through pure black space toward a single faint warm-gold point
of light far in the distance. As the camera approaches, the point resolves into a
few lines of crisp monospaced code, then a soft-edged UI panel materialising out
of the dark. Volumetric haze, deep blacks, a warm amber vignette at the frame
edges. Anamorphic lens, shallow depth of field, the light blooming gently.
Quiet, cinematic, restrained, high-end product film. No people, no logos.
Ambient noise: a low warm sub drone, almost silent.
```

Alt (safer, more abstract) — use if the code text looks bad:

```
Extreme slow push-in through black volumetric fog toward a single warm-gold
particle of light that drifts slowly upward. The light blooms softly and casts
faint amber haze. Deep cinematic blacks, anamorphic bokeh, shallow depth of
field, subtle film texture. Minimal, patient, premium tech-brand mood.
Ambient noise: a faint low drone.
```

---

## Shot 2 — CITED ANSWER (image-to-video)  · 8s
First frame: `app-shots/01-cited-answer.png`

```
Locked cinematic shot of a laptop screen showing a dark software interface. The
screen content is a real photograph and MUST NOT change, warp, animate, or
re-render — every word, panel and green citation chip stays exactly as in the
source image. The ONLY motion is an extremely slow, smooth camera push-in
(about 4 percent over the whole shot) toward the centre answer card, with a
faint parallax as if the screen sits a few centimetres deep. Shallow depth of
field softly blurring the outer edges of the screen, gentle bloom on the bright
text, warm amber vignette. Calm, precise, high-end product film.
Ambient noise: near silence, a soft room tone.
```

## Shot 3 — HONEST UNKNOWN (image-to-video)  · 8s
First frame: `app-shots/03-honest-unknown.png`

```
Locked cinematic shot of the same dark software interface, now showing an amber
"HONEST UNKNOWN — The available evidence was not sufficient for a grounded
answer" panel. The screen content is a real photograph and MUST NOT change,
warp, animate or re-render — the amber panel and every line of text stay exactly
as in the source image. The ONLY motion is a very slow, smooth camera pull-back
(about 5 percent) away from the amber card, revealing slightly more of the
interface, with faint parallax depth. Shallow depth of field, soft bloom on the
amber text, warm vignette at the edges. Still, deliberate, quiet.
Ambient noise: the room goes quiet, a single faint low tone.
```

## Shot 4 — THE RECEIPTS / DECISION HISTORY (image-to-video)  · 6s
First frame: `app-shots/07-decision-history.png` (or `09-cited-vs-unknown.png`)

```
Locked cinematic shot of a dark software interface listing decision records with
green and amber status chips. The screen content is a real photograph and MUST
NOT change, warp or animate — text and chips stay fixed. The ONLY motion is a
slow lateral camera drift (a short tracking move, right to left, staying within
the frame) across the list, with subtle parallax depth between the sidebar and
the main panel. Shallow depth of field, gentle bloom, warm edge vignette.
Measured, editorial, premium.
Ambient noise: soft low drone.
```

---

## Shot 5 — CONNECTIVE TRANSITION (text-to-video, NO image)  · 4s
Use between the cited shot and the unknown shot, or before the end card.

```
Abstract macro shot: a single horizontal beam of warm-gold light sweeps slowly
left to right across pure black, trailing soft haze and fine particles. Deep
blacks, anamorphic streak, shallow focus, cinematic bloom. Smooth, unhurried,
premium. No text, no objects.
Ambient noise: a soft airy whoosh, low and rounded.
```

Cooler variant (for the cut INTO the honest-unknown beat):

```
Abstract shot: the warm-gold light drains out of frame to the left and the
screen settles into near-total black with one faint amber ember still glowing
low. Volumetric haze clearing, deep cinematic blacks, very slow settle.
Ambient noise: sound falling away to a low hum.
```

---

## Shot 6 — END CARD (text-to-video, NO image)  · 5s

```
Centered on pure black: a minimal line-drawn mark of spread wings rising from a
downward V, in warm gold, drawing itself on with a single clean stroke over the
first second, then holding perfectly still. A faint bloom around the mark, deep
cinematic blacks, subtle grain. The camera does not move. Premium, quiet,
confident. No other elements.
Ambient noise: a single soft low tone, then silence.
```

> Note: Veo will not render your exact wordmark/typography reliably. Generate
> only the wing-mark + glow here, then add the text "Icarus. It won't bluff." and
> "alpha — live today" as clean title layers in DaVinci over this clip.

---

## Assembly order in DaVinci (≈24s)

| # | Clip | Length | Notes |
|---|------|--------|-------|
| 1 | Shot 1 opener | 5s (trim from 6) | fade up from black |
| 2 | Shot 5 transition | 1s (trim from 4) | quick light sweep |
| 3 | Shot 2 cited answer | 6s (trim from 8) | add title: "Every answer carries its receipts." |
| 4 | Shot 5b cool transition | 1s | light drains |
| 5 | Shot 3 honest unknown | 6s (trim from 8) | add title: "When no one wrote it down, it says so." |
| 6 | Shot 4 receipts drift | 3s (trim from 6) | optional |
| 7 | Shot 6 end card | 5s | add titles: "Icarus. It won't bluff." + "alpha — live today" |

Then in DaVinci: one music bed (lower to ~-18 dB), a soft whoosh on cuts 2 and 4,
a low boom under the end-card mark. Mute every Veo-generated audio track.

## If the UI warps anyway (likely on some takes)

- Regenerate with **shorter duration (4s)** — less time to drift.
- Add to the prompt: `the screen is a still printed photograph mounted on a wall, only the camera moves`.
- Lower the push/drift amount wording ("2 percent", "barely perceptible").
- Worst case: use the screenshot as a still in DaVinci with a slow Ken Burns
  pan/zoom keyframe — no AI, zero warp, and it cuts fine against the Veo opener
  and end card.
