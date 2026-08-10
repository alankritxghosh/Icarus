# Experiment A, run 3 — the abstention test that tested the wrong thing

Date: 2026-08-10
Repo: `astral-sh/uv` @ `6253839` — Icarus corpus at `1881d307`
Task: [issue #20981](https://github.com/astral-sh/uv/issues/20981) — `uv tool
run` ignores the installed version if a newer one exists. Labels: `bug`,
**`needs-decision`**.

Chosen to test **abstention**: `needs-decision` should mean no recorded
decision, which is run 1's exact failure condition (no single source answers →
writer composes). Design included a control question that should answer, so an
abstention could not be dismissed as "nothing indexed on this topic".

## The premise was wrong

Icarus did not abstain. It answered, and **the answer was correct** — every
clause traceable to a maintainer comment I had not read:

| Icarus | zanieb (MEMBER), in comments |
|---|---|
| settings recorded in receipt; later runs compare and consider incompatible | "we record that in the install, subsequent `uv tool run` invocations compare the current resolver settings (without `exclude-newer`) and consider the requests incompatible" |
| "difficult to make the alternative intuitive" | "I'm not sure we'll change this as it seems hard to make intuitive" |
| intended pattern is `uv tool install` for persistent installs | "That's the intended pattern. `uv tool run` is mostly intended to run tools _without_ a persistent installation" |

**`needs-decision` labels an unresolved *decision*, not absent *rationale*.** A
maintainer had stated the reasoning plainly; what remains open is only whether
to change it. Icarus drew that distinction correctly and I did not.

**So the abstention property is still untested.** Testing it needs a question
whose answer is genuinely unrecorded — which is what the frozen eval board's
four unanswerable `simonw/llm` questions already provide, and which this run
did not.

The control question also answered correctly (the documented behaviour, quoted
from the issue body). Both run-3 answers were quotations.

## The result that matters more than abstention

My cold read diagnosed the mechanism correctly (strict `ToolOptions` equality
against the tool receipt, `tool/run.rs:1002-1022`) and Icarus independently
confirmed it. If I had stopped there — as an unaided coding agent would — I
would have written a fix.

**Icarus's answer says not to.** The maintainer considers the behaviour
intended, is disinclined to change it, and regards the reporter's workflow as a
misuse of the command. The correct action on this task is *not to write code*.

That is a stronger outcome than "better context": Icarus **prevented work**
rather than informing it. It is also the outcome an agent is least able to
reach alone, because nothing in the code says "we discussed this and declined".

## Running score across three runs

7 substantive claims, **6 accurate, 1 fabricated**.

The quotation/composition split from run 2 holds perfectly:

- All 6 accurate answers were **quotations** — a PR title, a doc comment, an
  issue comment, a PR body, a maintainer comment, a docs excerpt.
- The 1 failure (run 1, the "`..` escapes the root" rule) was the only
  **composition** — no single source stated it.

Three runs, one consistent predictor. That is now worth building on rather than
just noting: the writer knows whether it is paraphrasing one chunk or merging
several, and surfacing that distinction would let a caller verify selectively
instead of verifying everything.

## The repeated result across all three runs

On every run, the decisive question was *"is the current behaviour intended?"*
— and on every run my code-only read got it wrong while Icarus got it right:

| run | my cold read | truth |
|---|---|---|
| 1 (#20477) | looked deliberate | regression inside a fix |
| 2 (#20917) | leaned deliberate | regression the maintainer admitted |
| 3 (#20981) | no opinion; would have fixed it | intended, won't change |

Three for three, in the same direction: **code shows what, never why, so an
agent reading only code systematically mis-reads intent.** Twice I would have
"fixed" deliberate behaviour or mis-scoped a regression; once I would have
written an unwanted patch outright.

This is the Agent Mode hypothesis surviving its first real contact, on the
question that actually decides whether code gets written.
