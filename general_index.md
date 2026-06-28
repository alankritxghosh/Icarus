# Icarus — General Index

A fast map of every tracked file in the repo with a 1–2 line description.
Grouped by directory. Regenerate this after any structural change (adding,
removing, or renaming files). For class/function-level detail see
`detailed_index.md`.

## Repo root
- `CLAUDE.md` — standing orders for anyone (human or AI) building Icarus:
  engineering principles, hard constraints, codebase map, and the eval commands.
- `README.md` — the pitch and one-paragraph overview of Icarus (the engineering
  brain a company can buy) plus its honesty promise.
- `general_index.md` — this file: every tracked file + a short description.
- `detailed_index.md` — every class/function in the `evals/` package + its
  description, drawn from real docstrings/signatures.
- `.gitignore` — ignored paths for the repo.

## docs/
- `docs/VISION.md` — product vision: the conversational engineering brain, what
  it answers, and the v1 scope (GitHub + Mac voice app + private cloud).
- `docs/ARCHITECTURE.md` — plain-language map of how Icarus is built (the Mac app
  is the face; the cloud is the brain).
- `docs/STRATEGY.md` — build & product strategy: sell the typed brain first, rent
  the commodities, own the moat. Includes the decided stack.
- `docs/COMPETITIVE.md` — competitive landscape: how comparable products were
  built, what to steal, what to avoid. Research behind STRATEGY.md.
- `docs/BUILD_ORDER.md` — the phase-by-phase build order; never build the talker
  before the brain. Each phase ends in something demoable.
- `docs/PHASE_1_PLAN.md` — the concrete Phase 1 build: type a question about one
  GitHub repo, get a cited answer or an honest unknown, proven by the harness.
- `docs/EVALUATION.md` — how Icarus proves it isn't bluffing; defines the gates
  and quality dials the eval harness enforces.
- `docs/METRICS.md` — the numbers that tell us we're winning, grouped by what
  they protect (honesty first, then retrieval, experience, trust).
- `docs/WORKFLOWS.md` — the rules of the road for every change (red → green,
  never weaken the eval, scoped edits, report results).

## evals/ (the Phase 1 eval harness — Python stdlib only)
- `evals/__init__.py` — package docstring: the harness is the product's
  conscience (measures cited-answer correctness and honest abstention).
- `evals/corpus.py` — the `Chunk` dataclass and `load_chunks`, which read the
  committed corpus (one retrievable evidence unit per line, each with a citation
  ref).
- `evals/ingest.py` — one-time generation tool that builds the corpus from
  `simonw/llm` (PR descriptions, linked issues, Python source) into
  `corpus/chunks.jsonl`. Needs `gh` + `git`.
- `evals/retriever.py` — `LexicalRetriever`, a stdlib BM25 keyword retriever over
  corpus chunks, plus a `tokenize` helper.
- `evals/provider.py` — the `Provider` abstraction for the rented answer-writer:
  `OpenRouterProvider` (calls OpenRouter over stdlib `urllib`) and
  `StaticProvider` (offline test double). Key from `OPENROUTER_API_KEY`.
- `evals/synth.py` — `build_prompt`, the strict cite-or-abstain prompt the writer
  must answer as JSON (answer-with-refs or explicit unknown).
- `evals/gate.py` — the deterministic honesty gate: parses the writer's reply and
  emits an answer ONLY if it parses, claims "answer", has prose, and cites ≥1
  retrieved ref; everything else fails safe to "unknown".
- `evals/judge.py` — the answer-correctness judge (fuzzy quality dial, NOT a
  gate): `build_judge_prompt`, a deterministic `parse_verdict` (fails safe to
  "incorrect"), and `Judge` wrapping a `Provider`. Default judge model differs
  from the writer to avoid self-grading bias.
- `evals/pipeline.py` — the `Result`/`Pipeline` contract the harness grades,
  plus `StubPipeline` (honest red baseline), `RetrievalPipeline` (retrieves
  candidates but still abstains), and `GatedPipeline` (retrieve → writer → gate
  → Result).
- `evals/grader.py` — deterministic grading of pipeline Results against the
  labelled set: the two honesty gates plus the quality dials. Optional `judge`
  turns `answer_correctness` from PENDING into a real number.
- `evals/run.py` — CLI entry point that runs the eval board and prints it; exits
  non-zero only when an honesty gate breaks. `--pipeline {stub,retrieval,gated}`.
- `evals/test_corpus.py` — tests that `load_chunks` parses JSONL into `Chunk`s
  (and tolerates blank lines).
- `evals/test_retriever.py` — tests for tokenization and BM25 ranking,
  truncation, zero-score dropping, and deterministic tie-breaking.
- `evals/test_pipeline.py` — tests that `RetrievalPipeline` populates `retrieved`
  yet still abstains (no citations).
- `evals/test_provider.py` — tests `StaticProvider` queuing/sticking and that
  `OpenRouterProvider` raises without an API key (offline).
- `evals/test_synth.py` — tests the prompt builder includes question/refs/text,
  offers the unknown path, and truncates very long chunks.
- `evals/test_gate.py` — tests the gate's conscience: grounded answers pass,
  everything ambiguous (unparseable, empty, unretrieved citations) fails safe to
  abstention; unretrieved citations are dropped.
- `evals/test_gated_pipeline.py` — tests `GatedPipeline` end to end with a
  `StaticProvider`: grounded answer, abstention, forced-unknown bluff, and that
  `retrieved` is populated for recall.
- `evals/test_grader.py` — tests the harness conscience: gates hold for an honest
  abstainer/oracle and fire for a bluffer or an ungrounded citation.
- `evals/test_retrieval_eval.py` — end-to-end red→green: against the committed
  corpus, retrieval recall@k rises above zero without dropping a gate (skips if
  the corpus isn't generated).
- `evals/test_gated_eval.py` — real-model proof: the gated pipeline lifts
  citation correctness above zero with both honesty gates at 100% (skips without
  `OPENROUTER_API_KEY` or the corpus).
- `evals/test_reference_answers.py` — tests that every answerable question has a
  non-empty `reference_answer` and every unanswerable one has none.
- `evals/test_judge_prompt.py` — tests `build_judge_prompt` includes the
  question/reference/candidate, asks for a verdict, and truncates long candidates.
- `evals/test_judge.py` — tests `parse_verdict` (correct/incorrect, embedded
  JSON, fails safe to incorrect) and `Judge` over a `StaticProvider`.
- `evals/test_answer_correctness.py` — tests that `grade(..., judge=…)` scores
  answer correctness over the answerable (abstention/wrong = 0) and leaves the
  gates untouched; stays PENDING without a judge.
- `evals/test_answer_correctness_eval.py` — real-model proof: with the judge,
  answer correctness becomes a number > 0 while both gates stay 100% (skips
  without `OPENROUTER_API_KEY` or the corpus).

## evals/ data files
- `evals/phase1_questions.json` — the verified labelled question set (corpus
  pinned to `simonw/llm` @ `94769b8`): each question's label, gold citations,
  notes, and (for answerable questions) a `reference_answer` the judge scores
  against. Data, not code.
- `evals/corpus/chunks.jsonl` — the committed corpus: one JSON object per line
  (`ref`, `source`, `text`) generated by `ingest.py`. Data, not code.

## demo/ (the Phase 1 web face — stdlib only, packaging over the gated brain)
- `demo/__init__.py` — package docstring: the minimal local face over the proven
  gated brain; imports `evals/`, changes no brain code.
- `demo/links.py` — `ref_to_url`, mapping a `source:ref` citation to its GitHub
  URL (pr/issue/code) at the pinned commit; unknown/malformed → None.
- `demo/payload.py` — `build_payload`, turning a `Result` into the page JSON
  (verdict, answer, citations-with-urls, and `searched` refs for transparency).
- `demo/server.py` — stdlib `http.server` demo: `make_handler` (GET `/` serves
  the page, POST `/ask` runs the pipeline) and `serve` (builds the real
  `GatedPipeline`). Run `python3 -m demo.server`. No brain change.
- `demo/index.html` — the single-page UI: question box, cited-answer card, and
  the honest "no one wrote this down" hero state; vanilla `fetch`, no framework.
- `demo/test_links.py` — tests `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — tests `build_payload` for the answer and honest-unknown
  shapes (citation URLs, order, `searched`).
- `demo/test_server.py` — tests routing against a stub pipeline (GET `/`, POST
  `/ask` answer/unknown, 400, 404) plus a smoke check that `index.html` keeps the
  front-end hooks.
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline (cited
  answer + honest unknown); skips without `OPENROUTER_API_KEY` or the corpus.

## .claude/agents/
- `.claude/agents/opus-architect.md` — definition for the opus-architect agent
  (principal architect / adversarial reviewer).
- `.claude/agents/sonnet-test-writer.md` — definition for the sonnet-test-writer
  agent (adversarial test writer / bounded implementer).
