# Quotation-vs-composition: built, measured, killed

Date: 2026-08-10
Status: **NEGATIVE RESULT. Nothing shipped.** `evals/attribution.py` was
written, calibrated against the real recorded cases, found anti-correlated with
truth, and deleted. This document is the deliverable.

## The hypothesis

Across the four Agent Mode runs, one predictor separated the six accurate
answers from the one fabrication and one scope inflation: accurate answers
restated a **single** cited chunk; the fabrication asserted a rule assembled
from two real sources that individually stated neither. So: label each sentence
`quoted` / `merged` / `unsupported` by lexical overlap with the cited chunks,
advisory only, never touching the verdict. A caller then verifies selectively.

## What was built

`attribute(answer, citations, evidence)`: sentence split, content tokens via
`retriever.tokenize` (the same splitter retrieval uses), per-sentence coverage
against each cited chunk; best-chunk coverage ≥ threshold → `quoted`, union ≥
threshold → `merged`, else `unsupported`. Plus a separate `scope_hedges` list,
since scope inflation is invisible to overlap by construction.

## What measurement showed

Calibrated on five real cases with real evidence text (three from the uv runs
via `gh`, two from the committed `simonw/llm` corpus):

| case | truth | bag-of-words coverage | label given |
|---|---|---|---|
| run 1 Q2 — the `..` rule | **fabricated** | **1.00** | `quoted` |
| run 2 Q2 — root-group precedence | accurate | 0.65 / 0.91 | `quoted` |
| probe Q0 — `tool_call_id` | accurate | 0.83 | `quoted` |
| run 3 — maintainer rationale | accurate | 0.53 | `unsupported` |
| probe Q1 — plugin "rule" | scope-inflated | 0.33 | `unsupported` |

Two false alarms, and the single true fabrication scored a **perfect 1.00** —
higher than every accurate answer. Suspecting bag-of-words had dissolved word
order, I tested phrase-level (trigram) overlap as a second mechanism:

    run 1 FABRICATION          trigram overlap 0.57   <- highest
    run 2 accurate                              0.26
    run 3 accurate (paraphrase)                 0.04
    probe Q1 scope-inflated                     0.00

The ranking is **exactly inverted** under both mechanisms.

## Why it fails, and why no threshold fixes it

A fabrication only survives to be noticed if it is *plausible*, and it is
plausible precisely because it was assembled out of the evidence's own
vocabulary and phrases. High lexical overlap is therefore a property of good
fabrications. A faithful paraphrase, meanwhile, restates in the writer's own
words and scores low — run 3 said "difficult to make the alternative intuitive"
where the maintainer wrote "hard to make intuitive".

So in this failure mode lexical similarity is **anti-correlated with
truthfulness**. That is structural. No threshold separates a 1.00 fabrication
from a 0.53 accurate answer in the right direction, and tuning would only
choose which errors to make.

The deeper point: the distinction I was chasing — restating one source vs.
merging several — is **semantic, not lexical**. A merge of two sources is
lexically indistinguishable from a quotation of a source that happens to
contain both vocabularies. Proving otherwise requires entailment, i.e. a model,
which is exactly what CLAUDE.md forbids the deterministic layer from becoming.
The experiment did not discover a bug in the implementation; it re-derived that
constraint from the other side, with numbers.

## What survives

The **observation** stands (7 answers, 1 fabrication, 1 inflation, and the
quotation/composition split describes them). What fails is the attempt to
*detect* it deterministically after the fact.

Three honest options, cheapest first:

1. **Question-shape guidance — zero code, available now.** "Why was X done?"
   was reliable across all runs; "What is the rule for X?" produced both
   failures. The caller controls question generality, so this is directly
   actionable in Agent Mode prompting today.
2. **Writer self-report.** Have the writer emit, per claim, the single ref it
   is restating, and deterministically check that ref resolves. This does not
   prove entailment, but it makes composition visible *by construction* rather
   than inferred after the fact — the writer knows whether it is paraphrasing
   one chunk or merging several, and today that knowledge is discarded at the
   interface. This is the one worth building, and it is a prompt + schema
   change, not a new model.
3. **A model judge as an advisory dial**, in the manner of `evals/judge.py` —
   never a gate, never in the serving honesty path.

Recommendation: (1) now, (2) next. Not (3) until (2) is measured.

## Cost

~40 minutes, one deleted file, no change to the gate, the board, or serving.
The board was re-run before this work started and stands GREEN at 100% across
all six metrics.
