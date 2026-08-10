# Rejected-attempt signal — false-positive rate

Date: 2026-08-10
Three runs: `simonw/llm` on lexical retrieval, `simonw/llm` on the serving
(hybrid) retriever, and `astral-sh/uv` on the serving retriever at 5.4× the
closed-PR pool. **The third run is the one to trust**, and it contradicts the
"no filter needed" conclusion the first two supported. Read to the bottom.

**No writer calls.** The signal is computed from retrieved evidence, not from
the answer, so the measurement needs only retrieval — which made N=30 free and,
as it turned out, made it cheap to measure twice.

Criterion registered BEFORE any hit was seen:
- **RELEVANT** — the closed PR attempted work on the same feature/subsystem the
  question is about; a developer would want to know it exists and was refused.
- **FALSE POSITIVE** — unrelated area; knowing it would not change how they proceed.
- **BORDERLINE** — same file or module, different concern.

## Run 1: `simonw/llm` on the serving path — 4/4 relevant. 0 false positives.

N = 30 questions (the 10 board questions plus 20 realistic developer
questions). Superseded as "the" result by Run 3 below; kept because the
lexical-vs-hybrid contrast in this section is still real and instructive.

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

## Run 3: `astral-sh/uv` on the serving path — 5/9 relevant. 33% false positive.

Local ingest of `astral-sh/uv` into a temp corpus (never touching the
committed `simonw/llm` one): 23,194 chunks, **697 closed-unmerged PRs** — 5.4×
`simonw/llm`'s pool of 129 — against 3,248 closed issues. N = 40 questions,
frozen and written from uv's actual subsystems (resolver, lockfile, Python
installs, workspaces, indexes, caching, build backend, tools, pip
compatibility, publishing) BEFORE any hit was seen, so they could not be
selected to flatter the result. No writer calls. Same serving retriever as
Run 1 (`_build_retriever` → hybrid BM25 + local semantic, normalized).

    questions asked      : 40
    questions that fired : 8  (20%)
    total listed PRs     : 9

Every one of the 9 verified genuinely `CLOSED` (not merged) directly against
GitHub — the parser holds at 5.4× the scale with zero drift.

| question | listed PR | verdict |
|---|---|---|
| how does uv handle dependency overrides | pr:18743 `Respect dependency-metadata overrides in uv pip check` | **RELEVANT** |
| how are constraints applied during resolution | pr:20158 `Preserve context in resolution errors` | **FALSE POSITIVE** — error formatting, not constraint application |
| how are path dependencies represented in the lockfile | pr:14003 `…take account of indexes defined as sources…` | **FALSE POSITIVE** — index validation, not path deps |
| how are path dependencies represented in the lockfile | pr:20625 `Support lockfiles without package.metadata` | **FALSE POSITIVE** — metadata field, not path deps |
| how does uv use keyring for index credentials | pr:14559 `Enable system keyring integration via --keyring-provider native` | **RELEVANT** — exact match |
| how does uv handle HTTP retries and timeouts | pr:16953 `Clarify UV_HTTP_TIMEOUT format…` | **RELEVANT** — exact env var |
| how does uv pip compile differ from pip-tools | pr:17219 `Make uv pip compile always attempt to honour --python` | **BORDERLINE** — same subsystem, doesn't address the comparison asked |
| how does uv publish upload distributions | pr:14307 `Transition "Uploading" to "Uploaded" in uv publish` | **RELEVANT** — exact match |
| how does uv handle the PATH when installing tools | pr:18080 `Add uv tool dir to PATH in uv docker images` | **RELEVANT** — exact match |

**5/9 relevant, 3/9 false positive, 1/9 borderline — 33% clean false-positive
rate.** Materially worse than Run 1's 0%, and this is the run that should
carry more weight: more than twice the hits, 5.4× the closed-PR pool to draw
noise from, and real subsystem breadth instead of one small, tightly-scoped
repo where "hybrid retrieval got it right" may just mean there was little room
to get it wrong.

The false positives share a shape worth naming: each is topically ADJACENT —
resolution errors sit beside constraint application, lockfile metadata sits
beside path-dependency serialization — close enough to rank in the top-5 on a
semantic-plus-lexical index, not close enough to be what the question asked.
That is a harder failure mode to filter than Run 1's lexical keyword collision,
because the retrieval genuinely isn't wrong to rank them nearby.

## Consequences (revised after Run 3)

1. **Run 1's "no filter needed" does not hold.** It was one clean result on a
   small, simple corpus, stated as if it generalized. It didn't.
2. **A relevance filter was prototyped and killed.** Two deterministic
   candidates tested against the 13 labelled hits across Runs 1 and 3
   (question vs. PR-title shared content tokens; retrieval rank position),
   neither separates RELEVANT from FALSE POSITIVE:
   - **Token overlap**: several genuine RELEVANT hits share ZERO tokens with
     the question (`"tool_call_id"` vs. `"Support tool calling."`; `"schema"`
     vs. `"schemas"` — a stemming gap), while FALSE POSITIVE hits share a
     generic word that recurs across the corpus (`"resolution"`, `"lockfile"`)
     and would pass any threshold ≥1.
   - **Rank position**: `pr:14003` (FALSE POSITIVE) sits at rank 1, the same
     rank as a genuine RELEVANT hit (`pr:18080`); no cutoff isolates the noise
     without also cutting true hits.

   No code shipped from this. Same shape as the quotation/composition
   negative result (`2026-08-10-quotation-vs-composition-negative-result.md`):
   a cheap deterministic signal was the right thing to TRY, and the honest
   result is that this particular relevance judgement needs something with
   more semantic understanding than token overlap or rank — likely a model
   call, which is a real cost/latency tradeoff to weigh deliberately, not
   something to sneak in via a "cheap" filter that doesn't actually work.
3. **Do not treat the count as a signal.** Unchanged: "3 attempts" is not more
   prior work than "1"; it reflects how many closed PRs ranked, now further
   supported by the false positives above ranking for reasons unrelated to
   actual prior-attempt count.
4. **Tell agents to judge each entry on its title.** Already shipped in the
   MCP description (this commit). At 33% false positive on the larger,
   harder corpus, that instruction is now load-bearing, not a hedge.

## Limits

- **Run 3 has 9 hits.** Better than Run 1's 4, still small for a rate. The
  honest range this session supports is "0% to 33% false positive depending on
  corpus and retrieval quality" — not a single number.
- Three corpora tested, all Python-ecosystem repos with GitHub-native PR
  workflows. Untested: a repo with a different review culture, or one whose
  closed PRs are dominated by bot/dependency-bump noise.
- My own relevance judgements throughout — every per-hit table exists so each
  call can be individually disputed, and Run 3's borderline call (pr:17219) is
  the one most worth someone else re-checking.
- The lexical-only failure mode (Run 1's first measurement) is retained
  deliberately: a cold corpus is served lexical-only during Stage 2 embedding,
  which is a real state this product enters on every connect. A question asked
  during that window is exactly when this signal is least trustworthy, and
  Run 3 didn't test that window at all — it measured the fully-embedded state.
