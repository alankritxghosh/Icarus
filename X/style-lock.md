# Style lock

Written 2026-08-22 after Alankrit called the drafts too polished. The diagnosis
was correct and the evidence is countable: 272 em-dashes across the files in
this directory, all mine, and 4 of the 5 batch-2 drafts contained no number.

## What actually went wrong

Not the dashes. The dashes are a symptom.

The real drift: I started writing sentences about mechanisms instead of
sentences carrying findings. "A guess is shaped like an answer" is a nice line
that anyone could write. "58 of the citations came from commits, 1 from code" is
a line only someone who ran it can write. The second is the account's whole
advantage and I stopped using it.

This is the same failure the vault already recorded on 2026-08-17, when a real
outreach learning was stripped down to "a maintainer decides in about five
seconds" and Alankrit called it generalised. The rule was already written. I
drifted off it inside four days.

## The lock

`lint.py` runs before anything ships. `python3 X/lint.py draft.txt`, or pipe it.
`--selftest` proves the checker can fail before a pass means anything.

Hard fails: em/en dash, ellipsis, smart quotes, emoji, hashtag, over 280 chars,
rounded quantity, and a slop word list (delve, leverage, robust, seamless,
landscape, testament, pivotal, unlock, myriad, holistic, comprehensive, and the
rest).

Warnings, which need a reason to override: no number in the draft, "not just X",
"isn't X it's Y", rule of three, rhetorical question, aphoristic closer starting
"That's the", three -ly adverbs, bold markup.

## The one rule under all of it

**Every draft carries something only someone who did the work could write.**
Usually a count. Sometimes a specific thing that happened. Never a formulation.

If the lint says "no number" and there is a real reason (a joke post, a
philosophical thread where a statistic would be tone-deaf), that is a fine
override. If it says "no number" because the draft is a nice-sounding
generalisation, the draft is broken and rewriting it means going back to the
inventory in `content-pillars.md`, not rephrasing.

## Scope

Applies to every post, reply and bio. Applies to how Claude writes in chat too,
which is where the register leaked in from.

The 272 dashes already in the notes in this directory stay. A blind substitution
would mangle 272 sentences to fix a habit that only matters where text ships.
