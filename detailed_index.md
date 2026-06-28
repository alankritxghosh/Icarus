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

## evals/grader.py
Deterministic grading of pipeline Results against the labelled set: the two
honesty gates (groundedness, abstention recall) plus the quality dials.

- `gold_refs(question: dict) -> List[str]` — the question's gold citations,
  normalized as `"source:ref"`.
- `_pct(flags: List[bool], empty_value: Optional[float]) -> Optional[float]` —
  percentage of True in `flags`, or `empty_value` when there is nothing to score.
- `grade(questions: List[dict], pipeline: Pipeline, k: int = 5) -> Dict` — run
  the pipeline over every question and compute the full metric board (gates,
  quality dials, status, per-question verdicts; answer correctness left PENDING).

## evals/run.py
CLI entry point that runs and prints the Phase 1 eval board. Module constants:
`DEFAULT_SET`, `CORPUS`.

- `_fmt(value) -> str` — format a metric value as a percentage (or `n/a` when
  None).
- `main(argv=None) -> int` — parse args (`--questions`, `--k`, `--pipeline`),
  build the chosen pipeline, grade the board, print it, and return exit code 0
  only when the honesty gates hold.

## Test modules
- `evals/test_corpus.py` — pins that `load_chunks` parses JSONL into `Chunk`s and
  tolerates blank lines.
- `evals/test_retriever.py` — pins tokenization plus BM25 behavior: relevant
  chunk ranked first, at-most-`k` results, no-match returns empty, deterministic
  ref-ascending tie-break, empty corpus, and zero-score dropping/truncation.
- `evals/test_pipeline.py` — pins that `RetrievalPipeline` populates `retrieved`
  yet still abstains with no citations (gates stay intact).
- `evals/test_grader.py` — pins the conscience: the stub holds gates but fails
  quality; a bluff on an unanswerable breaks abstention recall; an ungrounded
  citation breaks groundedness; an oracle goes fully green.
- `evals/test_retrieval_eval.py` — pins the real red→green against the committed
  corpus: retrieval recall@k rises above zero without dropping either gate (skips
  if the corpus is not generated).
