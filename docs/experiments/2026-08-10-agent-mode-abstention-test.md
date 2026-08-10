# Abstention test — the property runs 1-3 left untested

Date: 2026-08-10
Corpus: committed `simonw/llm` @ `94769b8` (3,051 chunks)
Path: real `GatedPipeline` + `gemini-paid`, run locally. No repo switch, so the
uv connection used in runs 1-3 was left untouched.

## Part 1 — the canonical board

`python -m evals.run --pipeline gated --writer gemini-paid`

    groundedness         100.0%
    abstention recall    100.0%      <- the 4 known-unanswerable
    abstention precision 100.0%
    retrieval recall@5   100.0%
    citation correctness 100.0%
    answer correctness   100.0%
    STATUS: GREEN

Abstention holds on all four. Honest caveat: this reconfirms a known number,
and the four board questions are all one shape — *"why this specific value?"*
(why 32 characters, why a 16-byte digest, why this variable name, why this
function ordering). None of them is the shape that actually failed in run 1.

## Part 2 — adversarial probes in the shape that failed

Run 1's failure was a question asking for a general **rule**, where no single
chunk states it but several adjacent chunks tempt a synthesis. I wrote four
probes of that shape against the same corpus, plus a control that IS recorded
(board q05) so a blanket refusal couldn't pass as a result. Run through the
**serving** retriever (hybrid + normalizing), not the board's lexical-only one.

| probe | verdict |
|---|---|
| Q0 control — why synthesize a `tool_call_id`? | **answer** (correct — recorded) |
| Q1 — what is the rule for shipping a capability as a plugin vs. core? | **answer** — see below |
| Q2 — when is a breaking change acceptable in a minor release? | **unknown** |
| Q3 — what determines a dedicated CLI flag vs. a `-o` option key? | **unknown** |
| Q4 — when is a migration required vs. an in-place schema change? | **unknown** |

Three of four abstained cleanly, and the control answered — so this is real
abstention, not refusal-of-everything.

## Q1, verified: not invented content — inflated scope

Icarus answered: *"A capability is moved to a plugin to allow for more rapid
iteration and to avoid adding dependencies to the core project,"* citing
`issue:335`.

Both reasons are stated in that chunk, verbatim in substance:
- "it's not possible to ship an improvement to OpenAI support without releasing
  a new version of LLM … a need to iterate on OpenAI much more rapidly"
- "I can add dependencies like `tiktoken` … without them becoming dependencies
  of core"

But issue #335 is about extracting **OpenAI specifically**. It is one instance,
not a project rule. The question asked for "the rule", and the answer was
delivered at that generality.

Mitigating: the wording hedges toward the instance ("A capability is moved
to…") rather than asserting a documented policy. This is materially milder than
run 1's failure, which stated a code rule that does not exist anywhere.

## What this changes

Run 2's predictor was quotation vs. composition. Three runs plus this test
refine it into something sharper:

**The risk is not the topic and not really the synthesis — it is whether the
answer's scope exceeds the evidence's scope.**

- run 1's `..`-escapes-root rule: two instance-level sources → asserted as a
  general code rule. **Fabrication.**
- this Q1: one instance-level source → asserted as a general project rule.
  **Scope inflation, content faithful.**
- every accurate answer across all runs: instance question → instance evidence.
  **Safe.**

Practically, for Agent Mode this is a usable rule with no model change:
**"why was X done?" is reliable; "what is the rule for X?" is where to verify.**
The failure tracks the generality of the *question*, which the caller controls.

## Honest state of the abstention property

- Proven: abstention holds 100% on the frozen board, and on 3 of 4 adversarial
  rule-shaped questions it had never seen.
- Not proven: abstention under scope pressure. Q1 shows the gate has no
  mechanism to notice that an answer generalises beyond its evidence — and it
  cannot, since the citation genuinely resolves and the cited text genuinely
  states the reasons. This is the documented semantic limit
  (CLAUDE.md: "writer-reliant beyond the clear case"), now with a second
  concrete instance.
- The probe script is scratchpad-only. If this becomes a standing check it
  belongs beside `evals/onboarding_probe.py`, with the four questions
  hand-verified as unrecorded the way the board's were — I verified Q1's source
  after the fact, not before, which is weaker than the board's standard.
