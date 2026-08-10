# Rejected-attempt signal — false-positive rate

Date: 2026-08-10
Corpus: committed `simonw/llm` @ `94769b8` (3,051 chunks)
N = 30 questions: the 10 board questions plus 20 realistic developer questions
across the repo.

**No writer calls.** The signal is computed from retrieved evidence, not from
the answer, so the measurement needs only retrieval — which made N=30 free and,
as it turned out, made it cheap to measure twice.

Criterion registered BEFORE any hit was seen:
- **RELEVANT** — the closed PR attempted work on the same feature/subsystem the
  question is about; a developer would want to know it exists and was refused.
- **FALSE POSITIVE** — unrelated area; knowing it would not change how they proceed.
- **BORDERLINE** — same file or module, different concern.

## Headline: on the serving path, 4/4 relevant. 0 false positives.

Measured through the retriever the product actually uses
(`demo.library._build_retriever` → hybrid BM25 + local semantic, wrapped in
`NormalizingRetriever`), `retrieved[:writer_k=5]`:

    questions asked      : 30
    questions that fired : 4  (13%)
    total listed PRs     : 4

| question | listed PR | verdict |
|---|---|---|
| `hide_reasoning` vs `-R/--no-reasoning` | pr:1434 `Experimental prompt.display_reasoning mechanism` | **RELEVANT** |
| how are model aliases resolved | pr:970 `Honor default model options when using aliases` | **RELEVANT** |
| what does the schema feature do | pr:66 `Add support for custom schemas` | **RELEVANT** |
| how does llm handle tool calls and their results | pr:581 `Support tool calling.` | **RELEVANT** |

Two of the four are abandoned attempts at *precisely* the feature asked about
(`Support tool calling.`, `Add support for custom schemas`) — the exact case
the signal exists for.

## I measured the wrong path first, and it said 42%

The first run used `LexicalRetriever` — BM25 only, which is **not** what serving
uses. It produced:

    questions that fired : 10 (33%)      total listed PRs : 12
    RELEVANT 5 | BORDERLINE 2 | FALSE POSITIVE 5     -> 42% false positive

I had written that up as the result, with "roughly half of what this signal
lists is noise", before closing the limitation I had disclosed at the bottom of
my own draft ("lexical retrieval only, not the hybrid serving path"). Closing it
reversed the conclusion. Recording that here because the near-miss is the
lesson: **a measurement of the wrong path is worse than no measurement**, since
it carries the authority of a number.

The lexical-only failures, kept because they explain the mechanism:

| question (abbrev) | listed PR | verdict |
|---|---|---|
| async tool calls to **missing** tools | pr:1532 `…template missing-variable detection` | FP — matched on "missing" |
| why is the loop counter named `i` | pr:441 `Add support for options in templates` | FP |
| why is `_human_readable_size` placed there | pr:1467 `fix(utils): skip nameless fields…` | FP |
| how is the CLI structured with click | pr:66 `Add support for custom schemas` | FP *(here)* |
| Response object lifecycle | pr:1164 `fallback for json.loads tool function args` | FP |

Note `pr:66` appears in BOTH tables — a false positive for "how is the CLI
structured" and a correct hit for "what does the schema feature do". The PR
never changed; the retrieval did.

## What this establishes

**Precision is retrieval's behaviour showing through**, exactly as the shipping
commit predicted ("relevance is retrieval's job, not this function's") — now
measured rather than asserted, and from both directions:

- Under weak (lexical) retrieval the parser is fed junk and faithfully lists
  junk. Notably three of the false positives came from the board's
  *unanswerable* questions — a variable name, a function's position in a file —
  where there is no subsystem to match and any closed PR in range is noise by
  construction.
- Under the real hybrid retriever those questions fire **zero** times, and every
  question that does fire names a real subsystem.

The parser itself never misjudged: every PR it listed genuinely was closed and
unmerged, in both runs. What varied was whether the evidence handed to it was
about the question.

## Consequences

1. **No relevance filter is warranted.** Precision on the serving path is
   already 4/4, and a filter would trade recall on the one case that justified
   the feature.
2. **Do not treat the count as a signal.** "3 attempts" is not more prior work
   than "1"; it reflects how many closed PRs ranked. Nothing should aggregate
   or score on it.
3. **Tell agents to judge each entry on its title** rather than assume
   relevance. Not because precision is bad — it is good on N=4 — but because
   N=4 is far too small to promise anything, and the lexical run shows what
   degraded retrieval does to it.

## Limits

- **4 hits.** That is the real caveat. 4/4 is consistent with high precision and
  also consistent with luck; it is not a rate.
- One corpus, one repo, and my own relevance judgements — the per-hit tables
  exist so each call can be disputed individually.
- The lexical run is retained deliberately: if retrieval ever degrades (a
  cold corpus served lexical-only during Stage 2, which is a real state this
  product enters on every connect), precision degrades with it. A question
  asked during the indexing window is exactly when this signal is least
  trustworthy.
