# Icarus — Phase 1 Plan (the brain, in text)

The concrete first build. Goal: **type a question about one GitHub repo, get a
cited answer or an honest "I don't know" — and have the evaluation harness prove
it.** No voice, no Mac app, no multi-company. Just the defensible core.

This is the detailed version of Phase 1 in [BUILD_ORDER.md](BUILD_ORDER.md),
following the approach in [STRATEGY.md](STRATEGY.md).

---

## The one goal

A command-line (or tiny local web) tool where:

```
$ icarus ask "why do we mock requests with MSW instead of stubbing fetch?"

> We use MSW because stubbing fetch broke whenever the client switched
> transports; MSW intercepts at the network layer so tests stay valid.
>
>   evidence:
>   • PR #482 "Migrate test mocks to MSW" — description, lines 3-8
>   • review comment by @maya on PR #482
>
$ icarus ask "why is the retry limit set to 5?"

> No one wrote this down. I looked at: PR history for retry config,
> code comments in http/retry.ts. The reason was never recorded.
```

That's the whole Phase 1. If this works and the eval harness agrees, we have a
brain. If it doesn't, voice and overlays would just be lipstick on it.

## The thinnest first slice (do this before anything fancy)

1. **One public repo**, cloned locally (e.g. a mid-size repo with good PR
   history). No GitHub API yet — read PRs from a local export or the `gh` CLI to
   start, so we're not blocked on auth.
2. **~10 labelled questions**: ~6 answerable-with-evidence (we record *where* the
   answer lives), ~4 genuinely-unrecorded (correct behavior = "I don't know").
3. A pipeline that returns, for each: an answer (or unknown) + the citations it
   used.
4. The **eval harness** scores all 10. Green = the slice works.

Build this slice end-to-end before optimizing any single part. A working thin
line beats a perfect ingest with no answer.

## The pipeline (build order within Phase 1)

1. **Ingest** — pull the repo's code + PRs + linked issues + commit messages into
   a local corpus. (Inline **review comments** are deferred: the chosen corpus
   repo `simonw/llm` is solo-maintained, so its "why" lives in PR descriptions,
   linked issues, and commits, not review threads. The review-comment path is a
   later addition once the pipeline works — it does not affect cite-or-unknown.)
2. **Chunk** — AST / function-level for code (the cAST finding); natural chunks
   for PR text. Every chunk carries metadata: source file, line range, PR/review
   id — this is what makes citations real.
3. **Embed + store** — turn chunks into vectors in a vector store. Rent the
   embedding model; start with a managed/simple vector store.
4. **Retrieve** — given a question, fetch the top candidate chunks (semantic +
   keyword/hybrid).
5. **Honesty gate** — *the part we own most deliberately.* Decide deterministically
   whether the retrieved evidence is strong enough to answer at all. If not →
   "I don't know," plus what was searched. This is auditable code, not a model.
6. **Synthesize** — hand the retrieved evidence to Claude with a strict
   instruction: *answer only from this evidence, cite it, never add facts.*
   Return answer + citations.
7. **Evaluate** — the harness runs the labelled set and reports the metrics in
   [EVALUATION.md](EVALUATION.md).

## The stack for Phase 1 (decided)

- **Brain:** Python.
- **Synthesis writer:** OpenRouter **free** models behind a thin provider
  abstraction (swap-in-one-line). First candidate: `cohere/north-mini-code:free`
  (256K context, structured/JSON output, Apache-2.0 open weights). **The eval
  harness picks the model** — keep it only if it holds cite-or-unknown.
- **Embeddings:** a **local open model** (BGE/E5/nomic via sentence-transformers)
  — free, local, private. Not via a free API.
- **Vector store:** start dead-simple/local (exact choice TBD).
- **Demo surface:** a minimal local **web page** (question → answer → citations).
- **Public repos only** while on free models (free routes may train on inputs).

## What we rent vs build (Phase 1)

| Rent / use off-the-shelf | Build ourselves |
|--------------------------|-----------------|
| OpenRouter free LLM (the writer) | GitHub/PR ingest |
| Local open embedding model | AST chunker + citation metadata |
| Simple/local vector store | The model-provider abstraction |
| | The honesty gate |
| | The evaluation harness + labelled set |
| | The minimal web demo skin |

We touch **no** Mac code, **no** voice, **no** Claude API, **no** multi-tenant
infra in Phase 1.

## Definition of done (Phase 1)

- On the labelled set: **100% groundedness** (every claim cites real retrieved
  evidence) and **100% abstention recall** (never bluffs on an unrecorded
  question) — the non-negotiables from [METRICS.md](METRICS.md).
- Answerable questions return correct, correctly-cited answers at a rising rate.
- It runs in the minimal web UI against one repo: question → answer → citations.
- The eval harness is the gate — a capability is "done" when a red case goes
  green, never because a demo looked good.
- **A recordable demo exists:** one great cited answer and one honest "I don't
  know," back to back — the honest refusal is the hero shot (see
  [STRATEGY.md](STRATEGY.md) §9).

## Open decisions still to make at the start of Phase 1

Most of the stack is now decided (above). These remain genuinely open — settle on
real numbers, not vibes:

1. **Vector store** — which simple/local option to start with.
2. **Which embedding model** specifically (BGE vs E5 vs nomic-class).
3. **Confirm OpenRouter data settings** for the free model before any code runs
   (public repos only regardless).

### Decided
- **Corpus repo: `simonw/llm`** (public, ~2 MB, Python, LLM-CLI domain). Chosen
  for fast thin-slice iteration and a domain the builder can judge. Rationale
  sources = PR descriptions + linked issues + commits (review comments deferred,
  see Ingest step above).
- **Labelling method (evidence-first):** never invent a question and hope evidence
  exists — read real PRs/issues, then write the question whose answer lives there.
  - *Answerable (~6):* answer must rest on a PR/issue span we record as the gold
    citation, **not** something also in the README (avoids the README-only trap).
  - *Unanswerable (~4):* ~2 realistic-unrecorded (a real choice where a documented
    search of PRs/issues/commits/code-comments finds no rationale) + ~2
    definitionally-unrecorded (a trivial naming/ordering choice nobody documents).
  - *Schema:* one record per question — `id`, `question`, `label`,
    `gold_citations` (answerable), `searched` (unanswerable, proves the gap),
    `notes`. Lands as `evals/phase1_questions.yaml` when the harness is drafted.
  - *Roles:* Claude drafts candidates (questions + gold citations) from the real
    repo; the builder verifies every label, especially the unanswerable ones.

## Guardrails (unchanged, restated)

- Prove the gap with a failing eval before changing the brain (red → green).
- Never weaken the eval set to pass.
- Keep every edit inside Phase 1 — no Slack/Linear/Notion, no structural code
  analysis, no Mac app, no voice.
- cite-or-unknown never degrades.
