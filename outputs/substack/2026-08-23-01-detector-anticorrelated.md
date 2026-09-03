---
status: DRAFT — not published
source: docs/experiments/2026-08-10-quotation-vs-composition-negative-result.md
        docs/experiments/2026-08-11-fabrication-recheck-per-claim.md
        docs/experiments/2026-08-10-agent-mode-exp-a-run1.md
target: ~1,400 words
checked: every number below read out of the experiment records, 2026-08-23
---

# Why you trust a made-up answer more than a true one

Forty minutes of work, one deleted file, and the most useful result I have had
all month.

---

Icarus answers questions about a codebase and cites its evidence. The rule it
cannot break is that it never bluffs: every citation resolves to something
actually retrieved, and when the repository never recorded an answer it says so
instead of guessing.

That guarantee is narrower than it sounds, and the gap is the interesting part.
A deterministic check can prove a citation is **real**. It cannot prove the
answer **follows from** it. Those come apart, and when they do the failure is
invisible, because the citation resolves and every downstream check waves it
through.

I watched it happen. Across four measured runs against `astral-sh/uv`, Icarus
produced seven accurate answers and one fabrication. The fabrication asserted
that absolute paths are preserved "when a relative path would require traversing
outside the project root (e.g. starting with `..`)". That rule does not exist.
It was assembled out of two real sources that individually stated neither half.
Every citation resolved. Nothing flagged it.

## The hypothesis, which felt obvious

Looking at the eight answers together, one thing separated them. The seven
accurate ones each restated a **single** cited chunk. The fabrication **merged
two**.

That is a testable difference, and it looked mechanical rather than semantic. So:
split each answer into sentences, measure how much of each sentence's vocabulary
is covered by each cited chunk, and label it. Covered mostly by one chunk →
`quoted`. Covered only by the union of several → `merged`. Covered by none →
`unsupported`. Advisory only, never touching the verdict — a reader gets told
which sentences to check.

I wrote it, then calibrated it on five real cases with real evidence text: three
pulled from the uv runs, two from a frozen corpus.

## What the numbers said

| Case | Truth | Coverage | Label given |
|---|---|---|---|
| the `..` rule | **fabricated** | **1.00** | `quoted` |
| root-group precedence | accurate | 0.65 / 0.91 | `quoted` |
| `tool_call_id` | accurate | 0.83 | `quoted` |
| maintainer rationale | accurate | 0.53 | `unsupported` |
| plugin "rule" | scope-inflated | 0.33 | `unsupported` |

Two false alarms, which I expected. And the single genuine fabrication scored a
**perfect 1.00** — higher than every accurate answer in the set.

My first thought was that bag-of-words had dissolved word order, and that phrase
matching would fix it. So I tested trigram overlap as a second, independent
mechanism:

```
the fabrication              0.57   <- highest
accurate                     0.26
accurate (paraphrase)        0.04
scope-inflated               0.00
```

Same ranking. Exactly inverted, under both mechanisms.

## Why no threshold saves it

I sat with this for a while, because a detector that is merely bad is a tuning
problem and a detector that is **backwards** is something else.

It is backwards for a structural reason, and once you see it you cannot unsee
it.

A fabrication only survives long enough to be noticed if it is plausible. It is
plausible precisely because it was assembled out of the evidence's own
vocabulary and phrasing. High lexical overlap is therefore not a signal of
faithfulness. It is a property of **good** fabrications.

Meanwhile a faithful paraphrase restates the source in the writer's own words
and scores low. In one accurate case Icarus wrote "difficult to make the
alternative intuitive" where the maintainer had written "hard to make
intuitive". Same meaning, almost no shared vocabulary, labelled `unsupported`.

So in this failure mode lexical similarity is anti-correlated with truth. No
threshold separates a 1.00 fabrication from a 0.53 accurate answer in the right
direction. Tuning only chooses which errors to make.

The deeper problem is that the distinction I was chasing — restating one source
versus merging several — is **semantic, not lexical**. A merge of two sources is
lexically indistinguishable from a quotation of one source that happens to
contain both vocabularies. Telling them apart requires entailment. Entailment
requires a model. And a model is exactly what the deterministic layer is not
allowed to become, because the whole value of that layer is that it cannot be
talked into anything.

The experiment did not find a bug in my implementation. It re-derived a
constraint I had already written down, from the other side, with numbers
attached.

I deleted the file.

## What I built instead, and why it also does not work

The observation survives even though the detector did not. Composition really is
where the failure lives. What fails is trying to **detect** it after the fact.

So I moved the question upstream. Instead of inferring from the outside whether
a sentence merged sources, ask the writer to report it from the inside: emit,
per sentence, which refs that sentence restates. Then check deterministically
that those refs were actually retrieved, dropping any that were not — so a
self-report can only ever move a claim toward "unsupported", never away from it.

This is better by construction. The writer knows whether it is paraphrasing one
chunk or merging three, and today that knowledge is thrown away at the
interface. It shipped.

Then I did the thing I would rather have skipped, and checked whether the
replacement catches the original case.

I reproduced the fabrication against the live system. Same sentence, near
verbatim:

> Additionally, absolute paths are preserved if the relative path would require
> traversing outside the project root (i.e., starting with '..').

Self-report for that sentence: **`quoted`, citing one ref.**

`quoted` is the label readers are told to trust. The tool description
specifically tells a calling agent that `composed` sentences are the ones worth
verifying. The fabrication came back wearing the trusted label.

A self-report is evidence. It is not proof. A writer that merged can still
report one ref, and this one did.

## What I actually take from this

Three things, and the third is the one I did not expect.

**A guarantee is only as wide as its mechanism.** "Never bluffs" was doing more
work in my head than in my code. What is provable is that citations resolve.
That is worth a great deal and it is not the same claim. I now write the narrow
version down, including in the project's own docs, because the wide version was
comfortable and wrong.

**Plausibility and evidence-similarity are the same axis.** Any detector built
on how much an answer resembles its sources is measuring how convincing the
answer is. If you are hunting convincing errors, you have built a
convincing-error finder and pointed it the wrong way.

**Check whether the fix fixes the case that motivated it.** The self-report was
a real improvement, argued from first principles, and shipped the same day. It
took a separate deliberate experiment a day later to find out it does not catch
the sentence that started all of this. Nothing forced that check. Nobody would
have noticed if I had skipped it, which is exactly why it needed doing.

The detector cost forty minutes. Not shipping it saved considerably more than
that, and I would not have known which of the two paths was which without
building the thing and watching it fail in a specific, numbered, reproducible
way.

Negative results are cheap to produce and almost nobody publishes them. That
asymmetry seems like a mistake.
