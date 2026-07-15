# Icarus — Read Before You Test

Thanks for trying Icarus. It's an early alpha, so a few things are rough on
purpose. This page tells you what to expect, what's a known limit (not a bug),
and how to report anything that surprises you. Two minutes now saves confusion
later.

## What Icarus is

Ask a question about a public GitHub repo — by typing (**⌘⇧I**) or by holding
the **Right Option** key and speaking — and Icarus answers like a teammate, with
clickable receipts (the exact PRs, issues, and code lines behind the answer). If
the answer was never actually written down anywhere, it says **"No one wrote this
down"** instead of guessing. That honesty is the whole point.

## Opening it the first time (the one awkward step)

Icarus isn't signed by Apple yet, so macOS will say it "cannot be opened because
Apple cannot check it for malicious software." This is expected for an alpha —
it is **not** a warning that anything is wrong. To open it:

1. Drag Icarus into your **Applications** folder.
2. Try to open it. When macOS blocks it, go to **System Settings → Privacy &
   Security**, scroll down, and click **Open Anyway** next to the Icarus message.
3. If no "Open Anyway" button appears, open **Terminal** and run:
   `xattr -dr com.apple.quarantine /Applications/Icarus.app`
   then open Icarus normally.

You only do this **once**. After that it opens like any other app. (A signed,
notarized build that skips this step is planned before any public release.)

## Two known limits — please read these

These are documented limits of how the system works, not bugs. If you hit one,
it's working as designed.

**1. Icarus proves its receipts are real, but it can't fully guarantee the
*wording* of an answer is un-tampered.**
Every citation Icarus shows is genuinely retrieved from the repo — it can never
cite something that isn't there. But a repo you connect could contain text
someone planted specifically to steer an answer (e.g. a PR description written to
say "this code is secure"). Icarus reads that text as evidence. So: trust the
**receipts** (they're real and clickable), and treat the **prose** of an answer
about an unfamiliar or untrusted repo with the same caution you'd treat the repo
itself. For well-known public repos this is a non-issue.

**2. Fake code that's shaped exactly like the real codebase can occasionally be
described as if it were real.**
If you paste in a code snippet that closely imitates the repo's real structure
but doesn't actually exist in it, Icarus may explain it as though it does. It
won't invent citations — but it may over-trust a convincing fake. Genuine
questions about the real repo are unaffected.

## What's normal (not a bug)

- **A brand-new repo takes a few seconds to index the first time.** You'll see a
  progress line ("Reading the repository…", then "Building smart search…"), not a
  frozen spinner. Once someone has connected a repo, it's near-instant for
  everyone else.
- **A repo with GitHub Issues turned off** still works — it just has fewer
  sources to draw on.
- **"Slow down — try again later"** when connecting several repos quickly is a
  real rate limit doing its job, not a failure. Wait a minute.
- **Voice** uses your Mac's speech recognition. A bad transcription stays
  visibly bad — Icarus won't turn a misheard question into a confident wrong
  answer.

## How to report a problem

Please send: **(1)** what you did, **(2)** what you expected, **(3)** what
happened, and **(4)** roughly when (so we can find it in the logs).

> Report to: _<add your Google Form link or email here>_

The more specific the better — "asked X about repo Y at ~3:15pm, got Z" is worth
ten "it didn't work"s. Thank you.
