# Icarus — Evaluation

How we prove Icarus isn't bluffing. The product's entire value is that it knows
the difference between what it can prove and what it's guessing — so the
evaluation harness is not a nice-to-have, it **is** the product's conscience. We
build it in Phase 1, before the brain is "done."

---

## The core principle

> **Prove the gap with a failing eval before you change the brain.**

Every capability is judged by the harness, never by vibes. A feature is "done"
when a previously-failing evaluation turns green — not when a demo looks good. A
demo can be cherry-picked; an eval set cannot.

## What we are actually testing

Icarus can fail in two opposite, equally fatal ways:

1. **Bluffing (over-confidence):** it answers when it shouldn't — states a "fact"
   that the retrieved evidence does not support. This is the catastrophic failure.
   Target: **zero ungrounded claims.**
2. **Under-finding (under-retrieval):** the answer *was* written down, but Icarus
   couldn't find it and said "I don't know." This is a quality gap, not a lie —
   but too much of it makes the product useless.

The whole game is pushing under-finding down **without ever allowing bluffing**.

## The eval set

A growing benchmark of real questions against real repositories, each labelled:

- **Answerable-with-evidence** — the reason is documented somewhere (a PR
  description, a review comment, an ADR). We record *where*, so we can check
  Icarus cites the right place.
- **Unanswerable** — the reason was genuinely never written down. The only correct
  behavior is an honest "I don't know."

Start with public repos in Phase 1 (so the set is shareable and reproducible),
then add customer-private eval sets per deployment later.

## The metrics the harness reports

| Metric | Question it answers | Target |
|--------|---------------------|--------|
| **Groundedness** | Does every spoken claim trace to a retrieved citation? | 100% — no ungrounded claims |
| **Abstention precision** | When it says "I don't know," was the answer really unrecorded? | high |
| **Abstention recall** | When the answer was unrecorded, did it correctly abstain (not bluff)? | 100% (never bluff) |
| **Retrieval recall@k** | Is the right evidence in the top *k* retrieved pieces? | rising over time |
| **Citation correctness** | Does it cite the *actual* source of the reason, not a lookalike? | high |
| **Answer correctness** | For answerable questions, is the answer right? | rising over time |

The non-negotiable column is **abstention recall** and **groundedness**: those
must hold at 100%. Everything else is a quality dial we turn up over time. We
**never** improve a quality metric by weakening the honesty guarantee, and we
never "fix" a failing case by deleting it from the eval set.

## The development loop

1. Add a real question to the eval set with its correct label.
2. Run the harness. A new gap shows up **red**.
3. Make the smallest change to the brain that turns it **green** — without
   regressing any other case.
4. Repeat.

This is exactly how a documented bug should be proven before it is fixed: red
first (proving the gap is real), then green (proving the fix works).

## Two specific traps to watch for

- **README-only citations.** Answering from a generic README when the real
  rationale lives in a PR is a shallow win that looks right and isn't. The grader
  checks that an answer doesn't rest *solely* on a weak source.
- **Self-contradiction.** Never emit a high-confidence rationale claim next to an
  honest-unknown verdict. If the rationale is unknown, the confidence is low,
  everywhere in the output.

## What the harness is NOT (yet)

- Not a measure of voice quality or latency — those are
  [METRICS.md](METRICS.md) experience metrics, measured separately once Phase 3
  exists.
- Not a replacement for human spot-checks early on, but the goal is that the
  harness becomes the trusted gate that lets us ship without manual review.
