# Brag Plan: Icarus

## What is this app?
Icarus is a privacy-first engineering brain: point it at a GitHub repo and ask
*why* the code is the way it is — out loud — and it answers from the repo's own
pull requests, reviews and issues, with the exact evidence on screen. When no
one ever wrote the reason down, it says "no one wrote this down" instead of
guessing. The honesty is enforced in code, not by asking a model nicely.

## The angle
Every other AND-dev tool brags about how much it *generates*. Icarus brags about
what it *refuses to say*. The flex is restraint: a brain that talks beautifully
but can't tell when it's wrong is a liability with a great voice — this is the
opposite. The video shows one real cited answer, then one real refusal, and
lets the refusal be the punchline. Specific to Icarus: the questions and the
`pr:1442` citation are real, pulled from production against `simonw/llm`.

## Hook (first 2-3 seconds)
Black screen. Three mono lines type in fast — `git log`, `git blame`,
`git diff` — then a hard cut to serif: **"Code shows what exists."** beat.
**"Not why."** The three things every coding agent can see, and the one thing
none of them keep.

## Key moments (the middle)
- A real question typing into a card, then the answer, then a green
  `pr:1442` citation chip snapping into place — "every answer carries its receipts."
- A second real question — the conversation-name-length one — a held beat, then
  amber serif: **"No one wrote this down."** Small line under it:
  "It refuses to guess. Enforced in code."
- The agent contrast, split: "A merged PR leaves a commit." / "A refused one
  leaves nothing." → "Your coding agent reads git. Icarus reads the rest."

## Outro / punchline
The Icarus wing mark. One mono line: "macOS · Chrome · MCP — alpha, live today."
Then the site. The last word on screen is the product's whole personality:
it would rather say nothing than say something wrong.

## User flow worth showing
Entry → key action → result, three beats, all real:
1. A question is asked (typed into the ask card).
2. Icarus returns a one-line answer with a resolvable citation (`pr:1442`).
3. A different question returns an honest "no one wrote this down" — the refusal
   is the result, not a failure.
This is the centerpiece. Scenes 3 and 4 ARE this flow.

## Tone
- Preset: polished
- Creative direction: "quiet confidence — the brag is that it won't lie"
- Interpretation: measured pacing, generous holds on the two questions and the
  refusal, serif for the claims, mono for the receipts, one accent color per
  meaning (green = cited, amber = unrecorded, gold = brand). No frantic cuts,
  no confetti. Motion is deliberate; the refusal gets the longest hold.

## Format: landscape — 1920x1080
## Duration: 21 seconds

## Visual identity (from the project)
- Background: #0d0c0b (deep) / #131211 (paper)
- Card: #1c1a17
- Accent (brand/gold): #ffc76b ; cited (green): #6fd3a8 ; unrecorded (amber): #e0a23c
- Text: #f4f1ea (ink) / #a09992 (muted) ; hairline: #2f2b26
- Display font: serif — "Iowan Old Style" / "Palatino" / Georgia fallback
- Body font: system sans ; Evidence/receipts: mono — "SF Mono" / Menlo fallback
- Strongest visual element: the citation chip (green pill, `source:ref` in mono)
  and the amber "No one wrote this down." line — the two states the product is
  built around. Secondary: the wing mark (spread wings rising from a downward V).

## Share copy (draft)
Most dev tools brag about how much code they write. Icarus brags about what it
refuses to say. Ask your codebase *why* — get the receipt, or an honest "no one
wrote this down." Live today.

## Audio direction
- Role: sparse professional accents
- Music: assets/music/happy-beats-business-moves-vol-9-by-ende-dot-app.mp3 —
  low bed, enters on the Scene 2 reveal, ducks hard under Scene 4 (the refusal),
  returns quiet, fades out under the outro mark.
- Music treatment: start ~-20 LUFS posture, 0.4s fade-in on reveal, near-silence
  0.5s before "No one wrote this down.", 1.2s fade-out on the final mark.
- Music cue guidance: read assets/music/cues/happy-beats-business-moves-vol-9-by-ende-dot-app.music-cues.json
  if present; align the Scene 2 mark draw and the Scene 3 citation-chip snap to
  the nearest strongCue; otherwise detect at composition via `hyperframes beats`.
- Audio-reactive treatment: subtle — the gold underline sweep in Scene 1 and the
  mark draw in Scene 2 may track music energy; nothing else responds.
- SFX posture: sparse, motion-matched, professional restraint. A soft key tick
  under typed text (low high-freq risk sound), one clean snap on the citation
  chip, one low sub tone on the refusal beat. Nothing on cuts.
- Audio-coupled moments: typed questions (key ticks), citation chip (snap on
  settle), "No one wrote this down." (music duck + single low tone), final mark.
- Restraint rule: no whoosh on every transition, no riser into the outro, no
  stinger on the logo. The refusal must feel like the room going quiet, not a
  drop.

## Storyboard

### Scene 1 — "Not why" — 3.5s
Deep black (#0d0c0b). Three mono lines type top-left, fast, muted (#a09992):
`git log` / `git blame` / `git diff`. Hard cut. Centered serif, large, ink:
"Code shows what exists." holds 0.8s. Below it, same size: "Not why." A gold
(#ffc76b) underline sweeps left-to-right under "Not why." Cursor blink.
Sequential/interaction: yes — 3 mono lines appear one per ~0.25s, then the two
serif lines land in sequence.
Audio intent: quiet, a little cold; the tool's-eye view of a repo.
Audio-coupled idea: key ticks on the 3 mono lines; underline sweep tracks a
small energy rise.
Music: not yet — silence or a single sub swell into Scene 2.
Transition mood: hard → Scene 2

### Scene 2 — Reveal — 3.0s
Background lifts to #131211. The wing mark draws in center (stroke-on, ~0.7s),
gold. Under it, serif wordmark "ICARUS" (letter-spaced). One mono line, muted:
"Git remembers what changed. Icarus remembers why."
Sequential/interaction: yes — mark draws, wordmark fades up, tagline types.
Audio intent: the bed enters here — warm, low, confident, not triumphant.
Audio-coupled idea: mark draw aligned to first strong music cue.
Music: enters, low.
Transition mood: soft → Scene 3

### Scene 3 — The cited answer — 5.0s
Card (#1c1a17, hairline border) center. Mono label top-left: "ASK". Question
types in ink: "Why was hide_reasoning added when -R already existed?" (holds).
Answer fades in below, 2 lines, muted, condensed real answer: "-R only
suppressed the reasoning text — it didn't turn reasoning off, and wasn't passed
to models. hide_reasoning actually disables it." A green (#6fd3a8) pill snaps in
bottom-right: mono "pr:1442". Small ink line under the card: "Every answer
carries its receipts."
Sequential/interaction: yes — question types, answer arrives, citation chip
snaps last.
Audio intent: steady, matter-of-fact.
Audio-coupled idea: key ticks on the question; one clean snap when the chip
settles.
Music: continues, low.
Transition mood: clean → Scene 4

### Scene 4 — The refusal — 5.0s
Same card style. "ASK" label. Question types: "Why is the maximum
conversation-name length set to 32 characters?" Hold 1.0s — nothing happens,
deliberately. Music ducks to near-silence. Then, centered, serif, amber
(#e0a23c), large: "No one wrote this down." Under it, small mono, muted: "Icarus
found the code and found no recorded reason. It will not invent one." Hold long.
Sequential/interaction: yes — question types, a real pause, then the refusal
line lands alone.
Audio intent: the room goes quiet. One low sub tone on the refusal line. This is
the emotional center.
Audio-coupled idea: hard music duck 0.5s before the line; single sub tone on
settle; no other sound.
Music: ducked, then returns very quiet.
Transition mood: soft → Scene 5

### Scene 5 — For agents — 3.0s
Split composition. Left column, ink: "A merged PR leaves a commit." Right
column, muted: "A refused one leaves nothing." A thin gold divider between them.
Then both fade and one serif line lands: "Your coding agent reads git. Icarus
reads the rest." Small mono under it: `"icarus": { "command": "…Icarus", "args": ["--mcp"] }`
(abbreviated).
Sequential/interaction: yes — two columns arrive, then resolve to one line.
Audio intent: bed lifts back to Scene 3 level, forward motion.
Audio-coupled idea: none beyond the bed.
Music: back to low bed.
Transition mood: clean → Scene 6

### Scene 6 — Outro — 1.5s
Deep black. Wing mark, gold, small, center. One mono line, muted: "macOS · Chrome
· MCP — alpha, live today." Below, smaller: "icarus-website-kappa.vercel.app".
Music fades out over 1.2s. End on the mark, still.
Sequential/interaction: no.
Audio intent: settle and stop. No stinger.
Audio-coupled idea: final mark holds as music fades to zero.
Music: fade out.
Transition mood: — (end)
