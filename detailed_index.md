# Icarus — Detailed Index

Every class and function in the `evals/` package, with its real signature and a
one-line description from the actual docstring/code. Docs under `docs/` are prose,
not code, and are not listed here (see `general_index.md`). Regenerate after any
structural change.

## evals/__init__.py
Package docstring only — no classes or functions. Declares the harness as the
product's conscience: it measures whether the brain answers documented "why"
questions with correct citations and abstains honestly when nothing was recorded.

## evals/corpus.py
The corpus: chunks of evidence, each carrying a citation ref.

- `class Chunk` — dataclass for one retrievable unit. Fields: `ref: str` (the
  normalized `"source:ref"` citation, e.g. `"pr:1435"`), `source: str`
  (`"pr" | "issue" | "code"`), `text: str`.
- `load_chunks(path) -> List[Chunk]` — read a JSONL file into a list of `Chunk`s,
  tolerating blank lines.

## evals/ingest.py
One-time tool that generates the Phase 1 corpus from `simonw/llm` into
`evals/corpus/chunks.jsonl` (needs `gh` + `git`). Module constants: `REPO`,
`COMMIT`, `PR_LIMIT`, `OUT`, `ISSUE_REF`.

- `_gh_json(args)` — run a `gh` subcommand and parse its JSON stdout (None when
  empty).
- `fetch_prs()` — list recent merged PRs and return their chunks plus the set of
  referenced issue ids (from `closingIssuesReferences` and `#NNN` mentions).
- `fetch_issues(issue_ids)` — fetch each referenced issue and return its chunks,
  skipping ids that turn out to be PRs, not issues.
- `fetch_code()` — clone the repo at the pinned commit and return one chunk per
  `llm/**/*.py` source file.
- `main()` — generate PR, issue, and code chunks, write them to `chunks.jsonl`,
  and print a count summary.

## evals/retriever.py
BM25 lexical retriever over corpus chunks. Stdlib only. Module constant: `_TOKEN`.

- `tokenize(text: str) -> List[str]` — lowercase and split text into `[a-z0-9_]`
  word tokens.
- `class LexicalRetriever` — BM25 keyword ranker over a list of `Chunk`s.
  - `__init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75)` —
    precompute per-doc token counts, lengths, average length, term frequencies,
    and idf.
  - `_score(self, q_tokens: List[str], i: int) -> float` — BM25 score of document
    `i` against the query tokens.
  - `search(self, query: str, k: int = 20) -> List[str]` — return up to `k`
    chunk refs ranked by score (desc), ties broken by ref (asc), dropping
    zero-score chunks.

## evals/provider.py
The `Provider` abstraction for the rented answer-writer (we rent the model, own
the pipeline). Stdlib only; key from `OPENROUTER_API_KEY`. Module constant on
`OpenRouterProvider`: `URL`.

- `class Provider` — interface: `complete(self, prompt: str) -> str` (raises
  `NotImplementedError`).
- `class StaticProvider(Provider)` — offline test double.
  - `__init__(self, responses)` — accept a single string or a list of strings.
  - `complete(self, prompt: str) -> str` — return queued responses in order,
    sticking on the last.
- `class OpenRouterProvider(Provider)` — calls an OpenRouter chat-completions
  model over stdlib `urllib`.
  - `__init__(self, model: str = "cohere/north-mini-code:free", timeout: float = 60.0)`.
  - `complete(self, prompt: str) -> str` — POST the prompt at temperature 0 and
    return the message content; raises `RuntimeError` when the key is unset.

## evals/synth.py
Builds the strict cite-or-abstain prompt for the writer. Module constants:
`INSTRUCTION`, `_MAX_CHUNK_CHARS`.

- `build_prompt(question: str, chunks: List[Chunk]) -> str` — assemble the
  instruction, the question, and the numbered evidence (each chunk truncated to
  `_MAX_CHUNK_CHARS`) into one prompt asking for JSON answer-with-refs or unknown.

## evals/gate.py
The deterministic honesty gate: turns the writer's raw reply into a `Result` and
can only ever fail safe toward abstention. Module constant: `_JSON`.

- `_extract_json(raw: str)` — find the first `{...}` span and `json.loads` it,
  returning None on no match or parse error.
- `gate(raw: str, retrieved: List[str]) -> Result` — emit an answer ONLY if the
  reply parses as JSON with verdict `"answer"`, a non-empty answer string, and at
  least one citation in the retrieved set (citations filtered to that set);
  everything else returns `Result(verdict="unknown")`.

## evals/judge.py
The answer-correctness judge: the fuzzy, judge-later quality dial — NOT an honesty
gate. Module constants: `JUDGE_INSTRUCTION`, `_MAX_CANDIDATE_CHARS`, `_JSON`.

- `build_judge_prompt(question: str, reference: str, candidate: str) -> str` —
  assemble the grading instruction with the question, reference, and (truncated)
  candidate, asking for a JSON `correct`/`incorrect` verdict.
- `parse_verdict(raw: str) -> bool` — True only if the reply parses as JSON with
  verdict `"correct"`; fails safe to False (incorrect) on anything ambiguous.
- `class Judge` — wraps a `Provider` into a judge.
  - `__init__(self, provider)` — store the provider.
  - `is_correct(self, question, reference, candidate) -> bool` — build the prompt,
    call the provider, and return `parse_verdict` of the reply.

## evals/pipeline.py
The pipeline interface the harness calls, plus the Phase-1 baselines.

- `class Result` — dataclass: what every pipeline returns for one question.
  Fields: `verdict: str` (`"answer"` or `"unknown"`), `answer: str = ""`,
  `citations: List[str]` (must be a subset of `retrieved`), `retrieved: List[str]`
  (candidate refs, best-first, used for retrieval recall@k).
- `class Pipeline` — interface; implementations answer one question at a time.
  - `answer(self, question: str) -> Result` — interface method (raises
    `NotImplementedError`).
- `class StubPipeline(Pipeline)` — the honest red baseline: always abstains and
  retrieves nothing, trivially holding both gates while failing every quality
  dial.
  - `answer(self, question: str) -> Result` — returns `Result(verdict="unknown")`.
- `class RetrievalPipeline(Pipeline)` — retrieves candidate evidence but does not
  yet answer (still abstains so the gates stay trivially intact).
  - `__init__(self, retriever, top_n: int = 20)` — store the retriever and the
    candidate cut-off.
  - `answer(self, question: str) -> Result` — abstain, but populate `retrieved`
    from `retriever.search(question, top_n)`.
- `class GatedPipeline(Pipeline)` — the real brain: retrieve → writer → gate.
  - `__init__(self, retriever, chunks, provider, recall_n: int = 20, writer_k: int = 6)`
    — store the retriever, a `ref -> Chunk` map, the provider, and the cut-offs.
  - `answer(self, question: str) -> Result` — retrieve `recall_n` refs, prompt the
    provider with the top `writer_k` chunks, run the reply through `gate`, and set
    `retrieved` to the full list so recall@k stays measurable on any verdict
    (local imports of `build_prompt`/`gate` avoid a circular import).

## evals/grader.py
Deterministic grading of pipeline Results against the labelled set: the two
honesty gates (groundedness, abstention recall) plus the quality dials.

- `gold_refs(question: dict) -> List[str]` — the question's gold citations,
  normalized as `"source:ref"`.
- `_pct(flags: List[bool], empty_value: Optional[float]) -> Optional[float]` —
  percentage of True in `flags`, or `empty_value` when there is nothing to score.
- `grade(questions: List[dict], pipeline: Pipeline, k: int = 5, judge=None) -> Dict`
  — run the pipeline over every question and compute the full metric board (gates,
  quality dials, status, per-question verdicts). Optional `judge` (exposing
  `is_correct(question, reference, candidate)`) turns `answer_correctness` from
  the PENDING string into a number over the answerable (abstention/wrong = 0);
  the judge never affects the deterministic gates.

## evals/run.py
CLI entry point that runs and prints the Phase 1 eval board. Module constants:
`DEFAULT_SET`, `CORPUS`, `JUDGE_MODEL` (`poolside/laguna-m.1:free`).

- `_fmt(value) -> str` — format a metric value as a percentage (or `n/a` when
  None).
- `main(argv=None) -> int` — parse args (`--questions`, `--k`,
  `--pipeline {stub,retrieval,gated}`), build the chosen pipeline (`gated` wraps
  an `OpenRouterProvider`), build a `Judge(JUDGE_MODEL)` when `OPENROUTER_API_KEY`
  is set (else None → answer correctness stays PENDING), grade the board, print
  it, and return exit code 0 only when the honesty gates hold.

## Test modules
- `evals/test_corpus.py` — pins that `load_chunks` parses JSONL into `Chunk`s and
  tolerates blank lines.
- `evals/test_retriever.py` — pins tokenization plus BM25 behavior: relevant
  chunk ranked first, at-most-`k` results, no-match returns empty, deterministic
  ref-ascending tie-break, empty corpus, and zero-score dropping/truncation.
- `evals/test_pipeline.py` — pins that `RetrievalPipeline` populates `retrieved`
  yet still abstains with no citations (gates stay intact).
- `evals/test_provider.py` — pins `StaticProvider` queuing/sticking (single
  string or list) and that `OpenRouterProvider` raises without an API key.
- `evals/test_synth.py` — pins that `build_prompt` includes the question, refs,
  and text, offers the unknown path, and truncates very long chunks.
- `evals/test_gate.py` — pins the gate's conscience: grounded answers pass,
  unretrieved citations are dropped, and empty/unparseable/explicit-unknown/
  only-unretrieved replies all fail safe to abstention.
- `evals/test_gated_pipeline.py` — pins `GatedPipeline` end to end with a
  `StaticProvider`: grounded answer, abstention, forced-unknown bluff, and
  `retrieved` populated for recall.
- `evals/test_grader.py` — pins the conscience: the stub holds gates but fails
  quality; a bluff on an unanswerable breaks abstention recall; an ungrounded
  citation breaks groundedness; an oracle goes fully green.
- `evals/test_retrieval_eval.py` — pins the real red→green against the committed
  corpus: retrieval recall@k rises above zero without dropping either gate (skips
  if the corpus is not generated).
- `evals/test_gated_eval.py` — pins the real-model proof: the gated pipeline
  lifts citation correctness above zero with both honesty gates at 100% (skips
  without `OPENROUTER_API_KEY` or the corpus).
- `evals/test_reference_answers.py` — pins that answerable questions carry a
  non-empty `reference_answer` and unanswerable ones carry none.
- `evals/test_judge_prompt.py` — pins that `build_judge_prompt` includes the
  question/reference/candidate, asks for a verdict, and truncates long candidates.
- `evals/test_judge.py` — pins `parse_verdict` (correct/incorrect, embedded JSON,
  fail-safe to incorrect) and `Judge` over a `StaticProvider`.
- `evals/test_answer_correctness.py` — pins that `grade(..., judge=…)` scores
  answer correctness over the answerable (abstention/wrong = 0), stays PENDING
  without a judge, and never breaks the gates.
- `evals/test_answer_correctness_eval.py` — pins the real-model proof: with the
  judge, answer correctness becomes a number > 0 while both gates stay 100%
  (skips without `OPENROUTER_API_KEY` or the corpus).

## demo/links.py
Map a `source:ref` citation to its GitHub URL. No classes.

- `ref_to_url(ref, repo, commit) -> str | None` — `pr:N`→`/pull/N`,
  `issue:N`→`/issues/N`, `code:path`→`/blob/{commit}/path`; unknown source or
  malformed ref → None (split on the first colon only).

## demo/payload.py
Turn a pipeline `Result` into the JSON the demo page renders. No classes.

- `build_payload(result, repo, commit) -> dict` — `{verdict, answer, citations:
  [{ref,url}], searched:[refs]}`. Answers carry prose + citation URLs; the honest
  unknown carries empty answer/citations but always the retrieved `searched` refs.

## demo/server.py
A minimal local web face over the gated brain. Stdlib `http.server` only. Module
constants: `ROOT`, `CORPUS`, `QUESTIONS`, `INDEX_HTML`.

- `make_handler(pipeline, repo, commit, html_path)` — return a
  `BaseHTTPRequestHandler` subclass: GET `/` serves the page; POST `/ask` with
  `{"question": …}` returns `build_payload(pipeline.answer(question), …)`; empty
  question → 400; other paths → 404. (Quiet logging.)
- `serve(host="127.0.0.1", port=8000)` — read repo/commit from the labelled set,
  build the real `GatedPipeline(LexicalRetriever(corpus), corpus, OpenRouterProvider())`,
  and run `HTTPServer`. Entry point: `python3 -m demo.server`.

## demo/ test modules
- `demo/test_links.py` — pins `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — pins the answer and honest-unknown payload shapes
  (citation URLs, order preserved, `searched`, url=None for unknown sources).
- `demo/test_server.py` — pins routing against a stub pipeline (GET `/`, POST
  `/ask` answer/unknown, 400 on missing question, 404) and smoke-checks that
  `index.html` keeps the front-end hooks (`id="question"`, `/ask`, the hero text).
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline: an
  answerable question returns a cited answer with a github.com link, an
  unrecorded one returns the honest unknown (skips without key/corpus).
