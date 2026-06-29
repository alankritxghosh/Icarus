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

## evals/corpus_meta.py
Self-describing corpus provenance written next to `chunks.jsonl`. No classes.

- `write_meta(path, repo, commit, code_dir, counts)` — write
  `{repo, commit, code_dir, counts, generated_at}` (ISO-8601 UTC) as JSON.
- `load_meta(path)` — read it back, or None if the file is absent.

## evals/ingest.py
One-time tool that generates a corpus from a public repo into
`evals/corpus/chunks.jsonl` + `meta.json` (needs `gh` + `git`). Module constants:
`REPO`, `COMMIT`, `PR_LIMIT`, `OUT`, `META`, `ISSUE_REF`.

- `parse_args(argv)` — CLI: `--repo` (default `simonw/llm`), `--commit` (default
  None → HEAD), `--code-dir` (default `llm`).
- `resolve_commit(repo, commit)` — explicit commit wins; the default repo without
  one keeps the pinned `COMMIT` (reproducible board); any other repo resolves HEAD
  via `git ls-remote`.
- `_gh_json(args)` — run a `gh` subcommand and parse its JSON stdout (None empty).
- `fetch_prs(repo)` — merged PRs → chunks + referenced issue ids
  (`closingIssuesReferences` and `#NNN`).
- `fetch_issues(repo, issue_ids)` — fetch each referenced issue, skipping ids that
  are PRs.
- `fetch_code(repo, commit, code_dir)` — clone at the commit and return one chunk
  per `<code_dir>/**/*.py`.
- `ingest_repo(repo, out_dir, commit=None, code_dir="llm") -> counts` — fetch a
  public repo and write `chunks.jsonl` + `meta.json` into `out_dir`; returns the
  {pr, issue, code} counts. Reused by the CLI and the demo's per-repo cache.
- `main(argv=None)` — resolve args, call `ingest_repo` into the default corpus dir,
  print a count + provenance summary.

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
the pipeline). Stdlib `urllib` only; keys from env. Module constants: `_USER_AGENT`
(Groq's Cloudflare 403s the default urllib UA), `_RETRY_DELAY`.

- `_with_retry(call, retries=6, base=2.0)` — run `call()`, retrying on HTTP 429
  with backoff; waits a Retry-After header, else Gemini's body `retryDelay`, else
  `base*2**attempt` (capped 65s). Non-429 raises immediately.
- `_openai_chat(url, key, model, prompt, timeout) -> str` — one OpenAI-compatible
  chat-completions call (shared by OpenRouter + Groq), with UA + 429 retry.
- `_parse_gemini(data) -> str` — extract text from a Gemini generateContent reply.
- `make_provider(name) -> Provider` — factory: `groq`/`gemini`/`openrouter`;
  raises `ValueError` on an unknown name.
- `has_provider_key(name) -> bool` — whether that provider's env key is set.
- `class Provider` — interface: `complete(self, prompt) -> str`.
- `class StaticProvider(Provider)` — offline test double (queues, sticks on last).
- `class OpenRouterProvider(Provider)` — OpenRouter chat-completions; key
  `OPENROUTER_API_KEY`; raises `RuntimeError` when unset.
- `class GroqProvider(Provider)` — Groq chat-completions (OpenAI-compatible),
  default `llama-3.3-70b-versatile`; key `GROQ_API_KEY`; the default writer.
- `class GeminiProvider(Provider)` — Google Gemini `generateContent` (REST),
  default `gemini-2.5-flash-lite`; key `GEMINI_API_KEY` (as `?key=`); the default
  judge. All raise `RuntimeError` when their key is unset.

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
`DEFAULT_SET`, `CORPUS`.

- `_fmt(value) -> str` — format a metric value as a percentage (or `n/a` when
  None).
- `main(argv=None) -> int` — parse args (`--questions`, `--k`,
  `--pipeline {stub,retrieval,gated}`, `--writer {groq,gemini,openrouter}`,
  `--judge {gemini,groq,openrouter}`), build the chosen pipeline (`gated` wraps
  `make_provider(writer)`), build `Judge(make_provider(judge))` when that
  provider's key is set (else None → answer correctness stays PENDING), grade the
  board, print it, and return exit code 0 only when the honesty gates hold.

## Test modules
- `evals/test_corpus.py` — pins that `load_chunks` parses JSONL into `Chunk`s and
  tolerates blank lines.
- `evals/test_corpus_meta.py` — pins `write_meta`/`load_meta` round-trip and the
  missing-file → None case.
- `evals/test_ingest_args.py` — pins the ingest CLI defaults (reproduce the pin),
  overrides, and `resolve_commit` (explicit commit / default-repo pin).
- `evals/test_ingest_smoke.py` — skippable live proof: ingest a tiny public repo
  to a temp path and assert chunks + meta written (set `RUN_INGEST_SMOKE=1`).
- `evals/test_retriever.py` — pins tokenization plus BM25 behavior: relevant
  chunk ranked first, at-most-`k` results, no-match returns empty, deterministic
  ref-ascending tie-break, empty corpus, and zero-score dropping/truncation.
- `evals/test_pipeline.py` — pins that `RetrievalPipeline` populates `retrieved`
  yet still abstains with no citations (gates stay intact).
- `evals/test_provider.py` — pins `StaticProvider` queuing/sticking; the
  OpenRouter/Groq/Gemini providers raising without their keys; `_parse_gemini`;
  the `make_provider` factory + `has_provider_key`; and `_with_retry` (retries on
  429, gives up after N, ignores non-429).
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
- `evals/test_free_hosted_eval.py` — pins the free-hosted proof (Groq writer +
  Gemini judge): gates 100% and quality ≥ the OpenRouter baseline (skips without
  `GROQ_API_KEY`/`GEMINI_API_KEY` or the corpus).

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

## demo/library.py
The demo's active-repo state: which corpus is loaded, its pipeline, and the
switch status. Thread-safe (a lock guards the pipeline swap). Helpers `_pick_writer`,
`_default_build_pipeline`, `_slug`.

- `class Library` — `__init__(default_corpus_dir, cache_root, default_repo,
  build_pipeline=…, ingest_fn=ingest_repo)` builds the default pipeline and reads
  its meta.
  - `connect_sync(repo)` — switch the active repo (blocking): default repo → committed
    corpus; cache hit → instant rebuild; miss → `ingest_fn` into the cache then
    rebuild. On failure keeps the previous repo and sets status `error`.
  - `current_pipeline()` / `provenance()` / `status_snapshot()` — lock-guarded reads
    (`{state, repo, commit, counts, error}`).

## demo/server.py
A minimal local web face over a `Library`. Stdlib `http.server` only. Module
constants: `ROOT`, `CORPUS_DIR`, `CORPUS_META`, `CACHE_ROOT`, `QUESTIONS`,
`INDEX_HTML`, `_REPO_RE`.

- `make_handler(library, html_path)` — return a `BaseHTTPRequestHandler` subclass:
  GET `/` serves the page; GET `/status` returns the library snapshot; POST `/ask`
  returns `build_payload(library.current_pipeline().answer(q), *library.provenance())`;
  POST `/connect` validates `owner/name`, spawns `connect_sync` in a daemon thread,
  returns 202; bad input → 400; other paths → 404. (Quiet logging.)
- `resolve_provenance(meta_path, questions_path) -> (repo, commit)` — default repo
  from the committed `meta.json`, else the labelled set's `corpus` block.
- `serve(host="127.0.0.1", port=8000)` — build the `Library` (default = committed
  corpus) and run `HTTPServer`. Entry point: `python3 -m demo.server`.

## demo/ test modules
- `demo/test_links.py` — pins `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — pins the answer and honest-unknown payload shapes
  (citation URLs, order preserved, `searched`, url=None for unknown sources).
- `demo/test_library.py` — pins the `Library`: starts on the default repo, cache-hit
  switches without re-ingesting, a miss ingests, default uses the committed corpus,
  and an ingest failure keeps the previous repo answerable.
- `demo/test_server.py` — pins routing against a stub library (GET `/`, `/status`,
  POST `/ask` answer/unknown, POST `/connect` valid→202 / bad→400, missing question
  → 400, 404), and smoke-checks `index.html` hooks (`id="question"`, `id="ask"`,
  `/ask`, `id="repo"`, `/connect`, `/status`, the hero text).
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline (built via
  `Library`): an answerable question returns a cited answer with a github.com link,
  an unrecorded one returns the honest unknown (skips without a provider key/corpus).
