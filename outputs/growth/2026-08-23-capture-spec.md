# Capture spec — the one asset three things are waiting on

Written 2026-08-23. **This is a shooting brief, not a script.** It exists
because Work Queue § 4 is blocked on footage only Alankrit can record, and the
same footage unblocks the Product Hunt gallery and the hole at
`site/index.html:510`.

**Why the existing files cannot be used:** `site/shots/demo_icarus.mov` is
60.06s and covers exactly the right two states, but it was captured 2026-07-23
and the app went dark on 2026-08-10. It shows a light interface the shipped app
does not have. Grading cannot fix it — the greens and ambers MEAN cited and
honest-unknown, so recolouring them misstates the product. See [[Learning]] §
A marketing asset ages out of the product. `icarus_product_demo_2026-07-24.mov`
is 6.56s and never reaches an answer.

---

## Before you press record

- [ ] **Build is the current dark one.** Open it and confirm the sidebar is dark
      before recording, not after.
- [ ] **Signed in, and NOT already connected to the repo you will demo.** The
      connect step is part of the story.
- [ ] **Display at 1512x982 or larger, scaled so the app window is ~1280 wide.**
      The transcode target is 778px wide; anything smaller than 1280 goes soft.
- [ ] **Hide everything else.** No other windows, no notifications, no dock
      badges. Turn on Do Not Disturb.
- [ ] **Clean menu bar.** Personal items in the menu bar end up in a PH gallery.
- [ ] **The brain is warm.** Ask one throwaway question first and discard it — a
      cold first ask includes model load time and reads as slowness.
- [ ] QuickTime screen recording, or ScreenStudio if you have it. No cursor
      effects, no zoom effects. The product is the point.

---

## What to record — three takes, not one

Record these **separately**. A single 60-second take means one fumble costs the
whole thing, and the edit wants to cut between them anyway.

### Take 1 — connect (target 15s)
Type a repo you have not connected before into the sidebar, press connect, let
it index. If indexing takes more than ~20s, keep rolling anyway; the edit will
compress it and honest waiting is better than a cut that implies it was instant.

**Repo choice matters.** Use something recognisable that is not `simonw/llm` —
the website already demos that one, and a PH visitor who sees the same repo in
both places reads it as the only repo that works. `psf/requests` is what the old
capture used and it worked.

### Take 2 — the cited answer (target 20s)
Ask a question you have **already verified answers with citations on the current
production build**. Do not improvise this on camera.

Let the citations render fully and hold for two seconds before stopping. The
citations are the product; a cut that clips them sells the thing everyone else
sells.

### Take 3 — the honest unknown (target 20s)
Ask something the repository genuinely never recorded, and let it refuse.

**This take is the whole video.** Work Queue § 4's definition of done says a
demo showing only the cited answer sells the wrong product, and it is right.
Hold on the refusal longer than feels comfortable — three seconds. It is the
one frame nobody else can screenshot.

---

## Question selection

Three questions are already verified **against production** and are on the site
right now (`site/index.html:468-470`). They are for `simonw/llm`, so they work
as a fallback if a fresh repo misbehaves on the day:

1. "Why was a new hide_reasoning parameter added when there was already a -R/--no-reasoning option?" — answers, cited
2. "What concrete use case drove the PauseChain primitive in llm?" — answers, cited
3. "Why is the maximum conversation-name length set to 32 characters specifically?" — **abstains**

**Verify any new question against production before the shoot, never against a
laptop.** [[Learning]] § A demo verified on a laptop is not verified: a question
that answered locally abstained live, because the deployed index does not
retrieve the same evidence for that phrasing. The gate was right; the example
was wrong. Budget ten minutes for this and it is the highest-value ten minutes
of the whole task.

---

## After the shoot

Drop the raw files at `site/shots/` with the date in the filename. The website
transcode is already known-good and produced 668 KB for 60 seconds:

```
ffmpeg -i <file> -an -vf "scale=778:-2,fps=24" -c:v libx264 -crf 27 -preset slow -movflags +faststart -pix_fmt yuv420p site/demo.mp4
```

The player, poster handling and visibility-gated autoplay were written and
verified on 2026-08-19 and are one commit away in git history — they were
removed with the stale asset, not deleted.

**Keep the raw files.** Product Hunt wants stills as well as video, and a still
pulled from a 778px transcode is unusable. The refusal frame from take 3 is the
single most valuable still in the set.

---

## What this does NOT cover

**The Product Hunt video is probably a different edit from the website video,
and possibly a different product surface.** A PH visitor is not going to
download an unnotarized alpha DMG on the day. The site's public try box needs
no sign-in and no install, so it may be the better opening shot for PH even
though the Mac app is the real product. Flagged, not decided — that call is
Alankrit's and it belongs with the PH sequencing, after HN.
