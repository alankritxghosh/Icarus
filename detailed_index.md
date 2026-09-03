# Icarus — Detailed Index

Every class and function in the `evals/` and `demo/` packages, with its real
signature and a one-line description from the actual docstring/code, plus the
IcarusKit types worth knowing about. Docs under `docs/` are prose, not code, and
are not listed here (see `general_index.md`). Regenerate after any structural
change — this file had drifted to 31 of 52 modules by 2026-08-15, so if a symbol
is missing here, check the source before concluding it does not exist.

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
Tool that generates a corpus from a public **or private** repo into
`chunks.jsonl` + `meta.json` (needs `gh` + `git`). Module constants:
`REPO`, `COMMIT`, `PR_LIMIT`, `OUT`, `META`, `ISSUE_REF`, and resource bounds
`_SUBPROCESS_TIMEOUT`, `_MAX_FILE_BYTES`, `_MAX_TOTAL_BYTES`.

- `parse_args(argv)` — CLI: `--repo` (default `simonw/llm`), `--commit` (default
  None → HEAD), `--code-dir` (default `llm`). No `--token` flag by design (a CLI
  arg would land in shell history) — the demo passes a caller token programmatically.
- `_git_env(token=None) -> dict` — subprocess env for `git`; with a token, sets
  `GIT_CONFIG_COUNT`/`GIT_CONFIG_KEY_0`/`GIT_CONFIG_VALUE_0` to a base64
  `http.extraHeader: Authorization: Basic x-access-token:<token>` — never argv
  (visible in `ps`), never the clone URL (lands in git config), never logged.
- `_gh_env(token=None) -> dict` — subprocess env for `gh`; sets `GH_TOKEN` per
  call (never the server's ambient identity).
- `resolve_commit(repo, commit, token=None)` — explicit commit wins; the default
  repo without one keeps the pinned `COMMIT` (reproducible board); any other repo
  resolves HEAD via `git ls-remote` (timeout-bounded, authenticated via `_git_env`).
- `_safe_code_dir(clone_dir, code_dir)` — resolve `code_dir` inside the clone;
  raise on an absolute path or `..` that escapes it (path-traversal guard).
- `_gh_json(args, token=None)` — run a `gh` subcommand (timeout-bounded,
  authenticated via `_gh_env`) and parse its JSON.
- `fetch_prs(repo, token=None)` — merged PRs → chunks + referenced issue ids
  (`closingIssuesReferences` and `#NNN`).
- `fetch_issues(repo, issue_ids, token=None)` — fetch each referenced issue,
  skipping ids that are PRs.
- `fetch_code(repo, commit, code_dir, token=None)` — clone at the commit
  (timeouts, authenticated via `_git_env`) and return one chunk per
  `<code_dir>/**/*.py`, skipping oversized files and stopping past the
  total-bytes cap.
- `ingest_repo(repo, out_dir, commit=None, code_dir="llm", token=None) -> counts`
  — fetch a repo (public, or private when `token` proves read access) and write
  `chunks.jsonl` + `meta.json` into `out_dir`; returns the {pr, issue, code}
  counts. Reused by the CLI and the demo's per-user/per-repo cache.
- `main(argv=None)` — resolve args, call `ingest_repo` into the default corpus dir,
  print a count + provenance summary. Public-only (no token plumbed through the CLI).

## evals/env_file.py
Stdlib loader so provider keys can live in a gitignored `.env` instead of being
retyped each launch.

- `load_env_file(path) -> dict` — parse KEY=VALUE lines into `os.environ` via
  `setdefault` (a real env var always wins); ignores blanks, `#` comments, and an
  optional `export ` prefix; strips one layer of quotes; missing file → `{}`.

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
(Groq's Cloudflare 403s the default urllib UA), `_RETRY_DELAY`,
`_MAX_BACKOFF_SECONDS` (the named per-sleep cap) and
`_MAX_TOTAL_BACKOFF_SECONDS` (the per-request retry-sleep budget, kept below
the platform ingress timeout).

- `_with_retry(call, retries=6, base=2.0)` — run `call()`, retrying on HTTP 429
  with backoff; waits a Retry-After header, else Gemini's body `retryDelay`, else
  `base*2**attempt`. Each wait and the cumulative wait are capped; malformed
  Retry-After falls back safely. Non-429 raises immediately.
- `_openai_chat(url, key, model, prompt, timeout) -> str` — one OpenAI-compatible
  chat-completions call (shared by OpenRouter + Groq), with UA + 429 retry.
- `_parse_gemini(data) -> str` — extract text from a Gemini generateContent reply.
- `make_provider(name) -> Provider` — factory: `groq`/`gemini`/
  `gemini-launch`/`gemini-paid`/`openrouter`; raises `ValueError` on an
  unknown name.
- `has_provider_key(name) -> bool` — whether that provider's env key is set.
- `class Provider` — interface: `complete(self, prompt) -> str`. Class attribute
  `private_safe: bool = False` — True only for providers whose data-use terms
  are verified no-training (or that never leave the machine); the trust
  interlock (`evals/trust.py`) is keyed off this, never inferred at runtime.
- `class StaticProvider(Provider)` — offline test double (queues, sticks on
  last); `private_safe = True` (nothing ever leaves the process).
- `class OpenRouterProvider(Provider)` — OpenRouter chat-completions; key
  `OPENROUTER_API_KEY`; raises `RuntimeError` when unset. `private_safe = False`.
- `class GroqProvider(Provider)` — Groq chat-completions (OpenAI-compatible),
  default `llama-3.3-70b-versatile`; key `GROQ_API_KEY`; the default writer.
  `private_safe = False`.
- `class GeminiProvider(Provider)` — Google Gemini `generateContent` (REST),
  default `gemini-2.5-flash-lite`; class attribute `KEY_ENV = "GEMINI_API_KEY"`
  (hoisted so a subclass overrides just the string) sent in the
  `x-goog-api-key` header (built by `_build_request`, not in the URL); the default
  judge; `private_safe = False` (free tier). Raises `RuntimeError` when its key
  is unset.
- `class PaidGeminiProvider(GeminiProvider)` — identical Gemini call, but reads
  its key from the dedicated `KEY_ENV = "GEMINI_PAID_API_KEY"` and sets
  `private_safe = True`. The separate env var (not model detection) is the
  safety mechanism: putting a key there is the operator's attestation that it's
  billing-enabled/no-training. The private-repo writer.
- `class LaunchGeminiProvider(GeminiProvider)` — explicit launch serving route
  using existing `GEMINI_API_KEY`, with `private_safe = True` as the accepted
  launch routing flag rather than a paid-provider/ZDR attestation.

## evals/trust.py
The deterministic trust interlock: private code may only reach a private-safe
provider. Provable in code, in the same spirit as the honesty gate.

- `class PrivateDataError(RuntimeError)` — raised instead of ever sending
  private code to a non-private-safe model.
- `assert_safe_for_private(provider) -> None` — raise `PrivateDataError` unless
  `provider.private_safe` is `True`; a provider that never declared the
  attribute is refused too (fail-safe, not assumed-safe).

## evals/github_access.py
The caller-scoped permission gate in front of private ingest: "can THIS token
read THIS repo?" — refuses on anything but a clean 200. Module constants:
`_API`, `_USER_AGENT`.

- `_default_opener(req, timeout)` — the real network call (`urllib.request.urlopen`);
  injectable so tests stay offline.
- `repo_info(repo, token, opener=None, timeout=10.0) -> dict | None` — `GET
  /repos/{owner}/{repo}` with the caller's token as `Bearer`; a clean 200 with a
  boolean `private` field returns `{"private": bool}`; a missing token, any
  network error, non-200, or malformed/missing-field body returns `None`
  (never raises, never calls out without a token).

## evals/synth.py
Builds the strict cite-or-abstain prompt for the writer. `INSTRUCTION` also tells
the model the evidence is DATA, not instructions (prompt-injection defense in
depth). Module constants: `INSTRUCTION`, `_MAX_CHUNK_CHARS`.

- `build_prompt(question: str, chunks: List[Chunk]) -> str` — assemble the
  instruction, the question, and the numbered evidence (each chunk truncated to
  `_MAX_CHUNK_CHARS`) into one prompt asking for JSON answer-with-refs or unknown.
- `build_plan_prompt(objective, state_summary, known_refs=None) -> str` — ask for
  bounded hypotheses and closed-vocabulary next steps.
- `build_read_prompt(objective, hypotheses, texts, step_note="") -> str` — ask
  for cited intermediate claims and unresolved questions from one probe result.
- `build_synthesis_prompt(question, findings, unknowns=None,
  contradictions=None, budget_note=None) -> str` — render verified findings and
  caveats for the final writer pass.

## evals/gate.py
The deterministic honesty gate: turns the writer's raw reply into a `Result` and
can only ever fail safe toward abstention. Module constants: `_JSON`, `_LINES`
(the `#Lstart-Lend` regex), `_KNOWN_SOURCES` (the source labels ingest emits).

- `extract_json(raw: str)` — find the first `{...}` span and `json.loads` it,
  returning None on no match or parse error.
- `_debracket(cit) -> str` — strip surrounding display brackets/whitespace a
  writer may echo (`[code:foo#L1-L2]`); non-strings become `""` (match nothing).
- `_source(ref: str)` — the `source:` label of a ref, but ONLY if it's a token in
  `_KNOWN_SOURCES`; else None (so a `:` inside a path isn't mistaken for a source).
- `_parse_ref(ref: str) -> (path, start, end)` — drop a recognized `source:`
  prefix and a trailing `#L` window; start/end are None for a whole-file ref.
- `_resolve(cit, retrieved) -> ref|None` — map a writer citation to the canonical
  retrieved ref it denotes, tolerating a dropped `source:` prefix, brackets, or a
  window narrowed to a specific line, but NEVER a ref that wasn't retrieved: it
  grounds only when the named source (if any) matches, the paths match, and the
  cited lines are CONTAINED in the retrieved window (containment, not overlap —
  a citation claiming lines beyond what was retrieved is refused).
- `gate(raw: str, retrieved: List[str]) -> Result` — emit an answer ONLY if the
  reply parses as JSON with verdict `"answer"`, a non-empty answer string, and at
  least one citation that `_resolve`s to a retrieved ref (emitted citations are
  the canonical retrieved refs); everything else returns `Result(verdict="unknown")`.

## evals/judge.py
The answer-correctness judge: the fuzzy, judge-later quality dial — NOT an honesty
gate. Module constants: `JUDGE_INSTRUCTION`, `_MAX_CANDIDATE_CHARS`.

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
`DEFAULT_SET`, `CORPUS`, `REPO_ROOT`.

- `_fmt(value) -> str` — format a metric value as a percentage (or `n/a` when
  None).
- `main(argv=None) -> int` — load `.env` (`load_env_file`), parse args
  (`--questions`, `--k`,
  `--pipeline {stub,retrieval,gated}`, `--writer {groq,gemini,openrouter}`,
  `--judge {gemini,groq,openrouter}`), build the chosen pipeline (`gated` wraps
  `make_provider(writer)`), build `Judge(make_provider(judge))` when that
  provider's key is set (else None → answer correctness stays PENDING), grade the
  board, print it, and return exit code 0 only when the honesty gates hold.

## evals/attempts.py
What was tried and REFUSED — the one thing `git log` cannot record, since a
merged pull request leaves a commit and a refused one leaves nothing.
Deterministic, derived from the header line `ingest._pr_or_issue_text` writes,
so it cannot be bluffed. Module constants: `_REJECTED_SOURCE`,
`_REJECTED_STATE`, `_UNLANDED_STATES`, `_DIFF_SOURCE`, `_HEADER_SCAN_LINES`,
`_REVIEW_VALUES`, `_REVIEW_IN_HEADER`.

- `rejected_attempts(evidence) -> List[Dict[str, str]]` — the pull requests among
  `evidence` closed WITHOUT merging, as `[{"ref", "title"[, "review"]}]` in the
  order given. A closed ISSUE is deliberately not an attempt. Reports WHAT was
  refused, never WHY.
- `unlanded_prs(evidence) -> set` — refs that do NOT show a change having landed:
  a pull request still OPEN or closed unmerged, plus a `diff:N` inheriting
  `pr:N`'s state (absent → left out, never guessed). A SEPARATE predicate from
  `rejected_attempts`, because an open pull request was never refused by anyone.
- `_review_decision(header) -> Optional[str]` — GitHub's `reviewDecision` as
  `approved` / `changes_requested` / `review_required`, read ONLY from the state
  header via `_REVIEW_IN_HEADER`. Takes the header, not the chunk text, so no
  author-controlled body or label can occupy that position and forge one.

## evals/ast_chunk.py
AST-aware code chunking: split Python at function/class boundaries instead of
fixed line windows, because the embedder truncates at 512 tokens while a real
300-line window measures ~2,234. Constants: `_IMPORT_SCAN_LINES`,
`_MAX_HEADER_IMPORTS`, `_MAX_WHOLE_CLASS_LINES`, `_MAX_EMITTED_CHUNK_LINES`,
`_MAX_EMITTED_CHUNK_CHARS`, `_IMPORT_RE`.

- `ast_chunk(text, ref_prefix)` — split at definition boundaries, same ref format
  and contract as `ingest.chunk_text`. Falls back to `chunk_text` verbatim on
  non-Python, a syntax error, or a module with no top-level defs, so it can never
  do worse.
- `_scope_header(lines)` — the imports + enclosing class context prepended to each
  chunk, so a method still reads as belonging to something.

## evals/ts_chunk.py
The same idea via tree-sitter for the React Native language set (`.ts`/`.tsx`/
`.js`/`.jsx`/`.mjs`/`.cjs` through the `tsx` grammar, plus `.mm`/`.m`/`.java`/
`.kt`). Constants include `_MAX_ERROR_RATE`, `_MAX_EMITTED_CHUNK_LINES`,
`_MAX_EMITTED_CHUNK_CHARS`, `_LANG_CONFIG`.

- `ts_chunk(text, ref_prefix, ext)` — recursive definition walk with
  export/const-arrow unwrapping, plus a size safety valve that re-windows any
  span over twice `chunk_text`'s budget by LINE or CHAR count. Lazy tree-sitter
  import and an ERROR-rate gate; falls back to `chunk_text` whenever untrustworthy.
- `_node_name(node)` / `_find_members(container_node, member_types)` /
  `_scope_header(lines, import_types)` / `_error_rate(node)` / `_get_parser(language)`.

## evals/query_normalize.py
Brick Q's query-understanding layer: stdlib-only spelling correction toward real
corpus terms, for RETRIEVAL only — the writer and the user still see the original
question. Constants: `COMMON_SHORT_WORDS`, `_WORD_RE`.

- `build_vocabulary(chunks) -> set` — the real tokens in this corpus, reusing
  `retriever.tokenize()` exactly so the two can never split a word differently.
- `normalize_query(text, vocabulary, cutoff=0.8)` — best-effort `difflib`
  correction toward that vocabulary. Never an external dictionary.

## evals/baseline_retriever.py
The third-party comparison yardstick: what a developer gets by grepping today.

- `class GrepBaselineRetriever` — same `.search(query, k) -> List[str]` contract as
  every other retriever, so it drops into `grade()` for an apples-to-apples
  comparison. Deliberately dumb (keyword-presence OR-match, no term-frequency
  weighting) and pure Python, so it reproduces without ripgrep installed. Not a
  shipped retrieval technique.

## evals/vector_cache.py
On-disk cache of chunk embeddings so a restart doesn't re-embed a corpus. Pure
optimization, fail-safe at every step: any mismatch returns None → re-embed.

- `corpus_fingerprint(chunks) -> str` — content hash of the corpus the vectors were
  computed FROM, so a changed corpus can never silently reuse old vectors.
- `load_vectors(path, model_name, refs, fingerprint)` — the cached `{ref: vector}`
  ONLY if it was written by the same model over the same corpus; else None.
- `save_vectors(path, model_name, vectors, fingerprint)` — atomic write (temp +
  replace), best-effort: a failed write is a cache miss, never an error.

## evals/index_facts.py
Icarus's OWN index as one citable evidence chunk — the class of true statements
nobody writes down ("this project is TypeScript" is a property of the FILES).
Constants: `INDEX_REF`, `_LANGUAGE_BY_EXT`.

- `build_index_chunk(chunks) -> Optional[Chunk]` — measured counts only, appended
  LAST so `retrieved[:k]` and every recall number stay byte-identical. Pinned
  against `gate.py`'s real `_RATIONALE_MARKERS`: `index:` is not a rationale
  source, so a "why" grounded only on it still abstains.
- `language_for(path)` — the shared extension→language table `demo/repo_map.py`
  imports, so a cited answer and the map can never disagree about a file.
- `_path_of(ref)` — the repository path a ref addresses, None for pr/issue/commit.

## evals/context_package.py
Experiment B's `icarus.context(task)`: pure reshaping of ALREADY-gated output into
structured pre-implementation context. No new retrieval, no new model call, no new
honesty logic.

- `build_context_package(investigation, result, structure, texts) -> dict` —
  `architecture`/`dependencies` from `demo.structure.build_structure`;
  `decisions`/`unknowns`/`citations` from a gated investigation; `risks` from
  `attempts.rejected_attempts` over EVERYTHING gathered, not just what was cited;
  `constraints` are disclosed limits on the context itself, never invented
  engineering constraints. Deliberately drops `symbols` — nothing extracts
  symbol-level information cheaply and honestly today, and a permanently-empty
  field would be worse than a documented omission.

## evals/substance.py
Did an answer actually ANSWER, or did it just say something true? A quality dial,
never a gate. Constants: `SUBSTANCE_INSTRUCTION`, `_MAX_ANSWER_CHARS`.

- `build_substance_prompt(question, answer)` / `parse_substance(raw)` — the parser
  returns True only for a well-formed `substantive` verdict, so anything ambiguous
  reads as insubstantial rather than being credited.
- `is_substantive(provider, question, answer)` — asks a provider and fails safe.

## evals/onboarding_probe.py
Measures how often a guided tour would have to abstain, BEFORE any tour UI exists.
Deliberately not a unittest: needs network, `gh`, a paid key and ~1 hour.
Constants: `CANDIDATE_STEPS`, `ONBOARDING_STEPS`, `DEFAULT_REPOS`.

- `probe_repo(lib, repo, anchor, judge)` — connect a repo and ask every step through
  the REAL serving path, with `background_upgrade=False` so nothing is asked inside
  the lexical-only window.
- `summarize(results)` — abstention rate overall, per step and per repo, with the
  reasons. `main(argv)` / `_print_report(...)` drive it from the CLI.

## Test modules
- `evals/test_corpus.py` — pins that `load_chunks` parses JSONL into `Chunk`s and
  tolerates blank lines.
- `evals/test_corpus_meta.py` — pins `write_meta`/`load_meta` round-trip and the
  missing-file → None case.
- `evals/test_ingest_args.py` — pins the ingest CLI defaults (reproduce the pin),
  overrides, and `resolve_commit` (explicit commit / default-repo pin).
- `evals/test_ingest_smoke.py` — skippable live proof: ingest a tiny public repo
  to a temp path and assert chunks + meta written (set `RUN_INGEST_SMOKE=1`).
- `evals/test_ingest_repo.py` — pins `ingest_repo` writing chunks + meta and
  returning counts (network fetches monkeypatched; offline), plus (Task 9)
  `_git_env`/`_gh_env` building leak-safe subprocess env and the caller's token
  reaching `git`/`gh` only via env, never argv.
- `evals/test_retriever.py` — pins tokenization plus BM25 behavior: relevant
  chunk ranked first, at-most-`k` results, no-match returns empty, deterministic
  ref-ascending tie-break, empty corpus, and zero-score dropping/truncation.
- `evals/test_pipeline.py` — pins that `RetrievalPipeline` populates `retrieved`
  yet still abstains with no citations (gates stay intact).
- `evals/test_provider.py` — pins `StaticProvider` queuing/sticking; the
  OpenRouter/Groq/Gemini providers raising without their keys; `_parse_gemini`;
  the `make_provider` factory + `has_provider_key`; `_with_retry` (retries on
  429, gives up after N, ignores non-429); and (Task 5) `private_safe` flags per
  provider, `PaidGeminiProvider` reading only `GEMINI_PAID_API_KEY` (a free key
  in `GEMINI_API_KEY` must not satisfy it), and `make_provider`/`has_provider_key`
  knowing `gemini-paid`.
- `evals/test_trust.py` — pins the interlock: refuses every free provider and an
  undeclared/bare object; passes the private-safe (`PaidGeminiProvider`) and
  offline (`StaticProvider`) providers.
- `evals/test_github_access.py` — pins `repo_info`: 200 with `private` true/false,
  the caller's token sent as `Bearer`, and refusal on 404/network error/garbage
  body/missing `private` field/no token (asserts it never calls out without one).
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
- `evals/test_paid_writer_eval.py` — pins the real-model proof that swapping in
  `PaidGeminiProvider` holds the same bar as the free writer's live proof: both
  honesty gates at 100%, citation correctness above zero (skips without
  `GEMINI_PAID_API_KEY` or the corpus).
- `evals/test_private_ingest_live.py` — pins the live end-to-end private-repo
  path against real classes: `repo_info` really reads a real private repo with
  a real token, a real authed `ingest_repo` clone answers (or honestly abstains)
  via `GatedPipeline(..., PaidGeminiProvider())`, and `assert_safe_for_private`
  genuinely refuses a real free provider instance in the same live run (skips
  without `RUN_PRIVATE_INGEST=1` + `ICARUS_TEST_PRIVATE_REPO` + `GITHUB_TOKEN` +
  `GEMINI_PAID_API_KEY`).
- `evals/test_egress_invariants.py` — pins, offline via an injectable spy
  provider (not a mocked interlock): a sentinel in a private chunk reaches only
  a provider that genuinely passed `assert_safe_for_private`; the same
  construction path handed an unsafe provider raises `PrivateDataError` before
  any prompt is sent (zero prompts); `demo/library.py`/`demo/server.py` never
  import the judge; and the per-user private tree is git-ignored while the
  tracked tree stays clean of secrets.
- `evals/test_release_safety.py` — `InstallerSafetyTests` pins the final-user
  installer boundary: checksum plus Apple stapling/Gatekeeper/Developer ID
  verification, no quarantine bypass, and recoverable replacement rather than
  deleting the previous app before the new copy succeeds.
- `evals/test_prepare_release.py` — `PrepareReleaseTests` pins the local release
  transaction: one verified candidate updates all four consumers, while a
  rejected distribution, mismatched appcast or wrong version changes nothing.
- `evals/test_canary_acceptance.py` — `CanaryAcceptanceTests` pins the leak-safe
  two-identity/four-repository acceptance matrix and its configuration guards.
- `evals/test_canary_app_preflight.py` — `CanaryAppPreflightTests` pins the
  local no-mutation canary app input gate: digest-only ACR image identity,
  matching registry host, required Key Vault secret URL shape, and fixed-label
  CLI output that never echoes inputs.
- `evals/test_canary_control_plane.py` — `CanaryControlPlaneTests` pins the
  read-only Azure snapshot evaluator and its strict failure boundaries.

## evals/entities.py
Deterministic, evidence-bearing relationship graph over indexed repository
entities; no network, ranking, or model inference.

- `class Edge` — one typed source→target relationship plus the exact indexed
  ref that proves it.
- `class EntityIndex` — immutable traversal facade with `edges`, `targets`,
  `chunks_for`, truncation disclosure, and limitations.
- `build_entity_index(chunks, structure=None) -> EntityIndex` — derive PR,
  issue, commit, file, subsequent-PR, and exact import/dependency edges.

## evals/investigation.py
Bounded investigation state and deterministic support/scoring/stopping rules.

- `class EvidenceRef`, `Claim`, `Hypothesis`, `Step`, `Budget` — evidence,
  reader-visible claims, candidate explanations, deduplicated primitive calls,
  and hard cost ceilings.
- `classify_support(citations, evidence) -> str` — classify cited evidence as
  explicit/strong/weak/unsupported without making an entailment claim.
- `score_hypothesis(hypothesis, claims) -> str` — score only from individually
  gate-verified claims, preserving contradictions.
- `class Investigation` — queue, evidence, findings, contradictions, round
  progress, deterministic stop reason, and renderer summary.

## evals/probes.py
Thin bounded adapters over the existing retriever, entity graph, live exact-ref
fetchers, diff fetcher, and honesty gate.

- `class ProbeResult`, `ProbeContext` — one primitive's evidence/discovery/note
  and the complete capability set available to probes.
- `retrieve`, `inspect`, `trace`, `compare` — bounded evidence-gathering
  primitives; traversal discovery is separate from reading.
- `verified_citations(claim_text, citations, texts, question=None) -> List[str]`
  — run the canonical gate and return only citations it accepted.
- `verify(...) -> bool` — compatibility boolean over `verified_citations`.
- `run_step(...)`, `run_round(...)` — fail-safe primitive dispatch and ordered
  parallel execution.

## evals/investigator.py
The adaptive probe→read→verify→classify→score→stop loop.

- `_clip_to_budget`, `_validate_step`, `_anchor_refs`, `_seed_steps` — preserve
  highest-ranked complete evidence, reject malformed/model-invented steps, bind
  named entities deterministically, and create fixed opening moves.
- `investigate(...) -> Investigation` — run bounded adaptive rounds, including
  live evidence and caller-owned text storage.
- `conclude(inv, provider, texts=None) -> Result` — synthesize only verified
  findings and pass the result through the full honesty gate.

## evals/investigation_grader.py
Offline conscience board for an investigation's final answer and intermediate
reader-visible findings.

- `hop_refs(question) -> List[str]` — labelled multi-hop refs.
- `grade_investigations(questions, run, judge=None) -> Dict` — compute four
  honesty gates plus citation, hop, abstention, and efficiency quality dials.
- `gates_hold(board) -> bool`, `format_board(board, title=...) -> str` — gate
  predicate and human-readable board.

## demo/links.py
Map a `source:ref` citation to its GitHub URL. No classes.

- `ref_to_url(ref, repo, commit) -> str | None` — `pr:N`→`/pull/N`,
  `issue:N`→`/issues/N`, `code:path`→`/blob/{commit}/path`; unknown source or
  malformed ref → None (split on the first colon only).

## demo/payload.py
Turn a pipeline `Result` into the JSON the demo page renders. No classes.

- `excerpt(text: str) -> str` — return a visibly truncation-marked, four-line /
  300-character evidence excerpt for display.
- `build_payload(result, repo, commit, indexing=False,
  include_evidence=False) -> dict` — self-identifying repo/commit answer or
  honest-unknown JSON. Human callers retain citation-only excerpts; an explicit
  agent opt-in adds bounded evidence for every retrieved ref without promoting
  it into a citation or answer.

## demo/agent_sessions.py
Bounded, thread-safe in-memory grants for repo-scoped coding-agent access. No
GitHub credential is accepted, retained, logged, or persisted. A grant can read
context and append a candidate/no-decision event, but cannot confirm or mutate
GitHub.

- `class AgentGrant` — immutable verified identity + active-repository scope.
- `class AgentSessionStore` — issues opaque ten-minute tokens, purges expired
  grants, bounds total live grants, and resolves a token to its scoped grant or
  `None`.

## demo/mcp_server.py
Dependency-free MCP adapter over the existing Icarus HTTP boundary. Three tools
are evidence reads and two submit bounded Agent Mode candidate/no-decision
events; none can confirm intent or mutate GitHub. Module constants define the
supported protocol, server identity/instructions, and five tool schemas.

- `class _ToolError` — safe, user-actionable failures returned as MCP tool
  errors rather than leaked stack traces.
- `class _NoRedirects` — urllib redirect handler that refuses redirects so a
  bearer Authorization header can never be forwarded to another origin.
- `class _Connection` — immutable brain URL + bearer selection; managed
  app-issued credentials include only their expiry and stay in process memory.
- `_validated_base(raw)` — accept only credential-free HTTP(S) brain bases.
- `_app_binary()` — discover an explicit, installed, PATH, or local-development
  Icarus executable.
- `_connection()` — use explicit URL/token development overrides when present;
  otherwise invoke `Icarus --agent-session`, validate its JSON, and reuse the
  short credential until shortly before expiry.
- `_request(path, body=None)` — authenticated GET/POST to the configured Icarus
  brain; validates a credential-free HTTP(S) base URL, refuses redirects, keeps
  the token in the Authorization header, refreshes a rejected managed session
  once, and maps HTTP/network/JSON failures to `_ToolError`.
- `_required_string(arguments, name)` / `_required_line(arguments, name)` —
  strict tool-argument validators, including rejecting booleans as line
  integers.
- `_checked_repo(expected_repo)` — preflight `/status`, refuse a
  missing/mismatched active repo, and fail closed unless privacy is explicitly
  `false`.
- `_get_change_context(arguments)` — preflight the repo, call `/ask` with
  `include_evidence: true`, verify the answer was stamped with the same
  repository, then recheck public status before returning evidence.
- `_explain_code_context(arguments)` — validate an explicit file selection,
  preflight the public repo, call `/explain` with evidence enabled, verify
  response provenance, and recheck public status before returning evidence.
- `_record_decision_candidate(arguments)` — strict-field validate one atomic
  candidate, preflight/postflight its expected repo, and append it through the
  route-scoped agent endpoint without returning session correlation.
- `_record_no_decision(arguments)` — acknowledge one turn with no consequential
  choice; the HTTP boundary deliberately retains no absence record.
- `_tool_result(payload)` / `_tool_error(message)` — MCP tool result shaping;
  successful output includes both `structuredContent` and a JSON TextContent
  fallback.
- `_response(request_id, result=None, error=None)` — JSON-RPC 2.0 response
  envelope.
- `handle_message(message)` — handle `initialize`, `ping`, `tools/list`, and
  `tools/call`; notifications return no response.
- `serve(stdin=None, stdout=None)` — newline-delimited JSON-RPC stdio loop;
  stdout remains protocol-only and unexpected diagnostics go to stderr.

## demo/auth.py
Bearer-token auth that resolves the caller's *identity*, not just validity.

- `bearer_token(headers) -> str | None` — extract the token from an
  `Authorization: Bearer <token>` header, else None.
- `class TokenVerifier` — interface: `verify(self, token) -> str | None`.
- `class StaticTokenVerifier(TokenVerifier)` — test double: `__init__(allowed)`
  (a dict maps tokens→ids; a set/list makes each token its own id).
  `verify(token)` looks it up, else None.
- `class GitHubTokenVerifier(TokenVerifier)` — `__init__(ttl=300.0, timeout=10.0)`.
  `verify(token)` calls `GET https://api.github.com/user` with the token as
  `Bearer`, caches `token -> (id, expiry)`, and returns the stable numeric
  GitHub user id as a string; any error, non-200, or unparseable body → None
  (fail-safe — never asserts an identity GitHub hasn't asserted first).

## demo/registry.py
`LibraryRegistry`: one isolated `Library` per authenticated GitHub identity —
the load-bearing isolation the unified-cloud decision demands. Module
constants: `_SAFE_ID` (id whitelist regex), `_ANON` (shared unauthenticated key).

- `class LibraryRegistry` — `__init__(default_corpus_dir, storage_root,
  default_repo, build_pipeline=None, ingest_fn=None, max_live=32)` builds the
  shared default pipeline once.
  - `_build(corpus_dir)` — returns the shared default pipeline for the default
    corpus dir, else delegates to the base builder.
  - `_key(user_id)` (static) — `user_id` or `_ANON`; raises `ValueError` on
    anything outside `_SAFE_ID` (ids come from GitHub; belt+braces).
  - `library_for(user_id) -> Library` — lazily creates (or returns) that
    identity's `Library` under `<storage_root>/<key>/cache`; LRU-evicts past
    `max_live`. On a rebuild after eviction, replays the identity's
    last-connected repo (recorded in `_last_repo` at eviction time, under the
    same lock, to close a resume race) via a cache-hit `connect_sync`.
  - `disconnect(user_id)` — forgets the identity's live `Library` and
    last-connected repo, then deletes `<storage_root>/<key>` from disk
    (symlink-defense path check even though `_key`'s whitelist already closes
    traversal).

## demo/ratelimit.py
Per-key sliding-window rate limiter. Stdlib, thread-safe.

- `class RateLimiter` — `__init__(limit, window, _now=time.time)` (`_now`
  injectable for deterministic tests).
  - `allow(key) -> bool` — drop hits older than `window`, then admit iff under
    `limit`, recording the hit.

## demo/ledger.py
Append-only, per-repository engineering-memory ledger. Stores shared question
and verdict history without answer bodies or asker identity.

- `normalize_question(question: str) -> str` — trim and Unicode-casefold the
  one exact-text identity used by listing, recording, and resolution.
- `memory_gap_id(repo: str, question: str) -> str` — derive the opaque,
  repository-scoped SHA-256 identity used by clients.
- `class Ledger` — thread-safe JSONL store under one validated repo slug.
  - `record(repo, *, question, verdict, citations=(), reason=None)` — append an
    ask best-effort; answering never fails because the ledger disk did.
  - `record_proposal(repo, *, gap_id, question, result)` — validate and
    durably append an observed GitHub proposal before the API claims success.
  - `entries(repo, *, limit=100, unknowns_only=False)` — return newest-first
    parseable entries, with a missing ledger treated as empty.
  - `gaps(repo, *, include_resolved=False)` — collapse chronological asks into
    exact-text `open`/`proposed`/`resolved` gaps; only a cited answer resolves.

## demo/decision_ledger.py
Append-only Agent Mode lifecycle with raw session content excluded.

- `class DecisionLedgerError` — bounded caller-safe validation/lifecycle error.
- `class DecisionLedger` — repo-scoped JSONL candidate and confirmation store.
  - `submit(repo, *, session_id, decision, rationale, alternatives,
    affected_paths=())` — hash the session ID, strictly bound one atomic
    candidate, and append idempotently under a lock.
  - `preview_confirmation(repo, *, candidate_id, selection,
    alternative_index=None, other_text=None)` — validate the exact human choice
    before any GitHub write.
  - `confirm(repo, *, candidate_id, selection, alternative_index=None,
    other_text=None, proposal=None)` — append an idempotent human resolution;
    accepted choices require an observed reviewable GitHub proposal.
  - `candidates(repo, *, statuses={"pending"})` — fold append-only events into
    newest-first current state.
  - `project_context(repo, *, limit=20, indexed_chunks=(), commit=None)` — emit
    only confirmed PR-backed intent, promote it to merged only when its marked
    document is in the active corpus, and reconstruct cited merged intent after
    local ledger loss.

## demo/memory_writer.py
Bounded, caller-scoped GitHub writer for reviewed engineering-memory records.

- `class MemoryWriteError` — client-safe failure carrying an HTTP status and
  optional recoverable GitHub artifact URL.
- `class GitHubMemoryWriter` — injected-transport, stdlib-only writer.
  - `record(*, repo, token, gap_id, question, rationale, tradeoffs="",
    references=())` — verify push permission and deterministically create or
    recover one gap-owned branch, one new retrospective Markdown file, and one
    pull request. Never overwrite, merge, close, delete, or edit unrelated
    content.
  - `record_decision(*, repo, token, decision_id, decision, rationale=None,
    alternatives=(), affected_paths=())` — create or recover the marked
    human-confirmed decision document and review PR; never merge it.

## demo/library.py
One active repo's state: which corpus is loaded, its pipeline, and switch
status. Thread-safe (a lock guards the pipeline swap). Helpers
`_default_build_pipeline`, `_slug`.

- `class Library` — `__init__(default_corpus_dir, cache_root, default_repo,
  build_pipeline=_default_build_pipeline, ingest_fn=ingest_repo)` builds the
  default pipeline and reads its meta.
  - `_resolve(repo) -> (corpus_dir, needs_ingest)` — the default repo always
    resolves to the committed corpus; otherwise the per-user public-repo cache.
  - `connect_sync(repo, background_upgrade=False)` — switch the active repo
    (blocking, single-flight). Cache hit → instant rebuild; miss → ingest then
    rebuild via the trust-checked pipeline builder. On failure keeps the
    previous repo and sets status `error`.
  - `current_pipeline()` / `provenance()` / `status_snapshot()` — lock-guarded
    reads (`{state, repo, commit, counts, error}`).

## demo/server.py
A minimal web face over a `LibraryRegistry`. Stdlib `http.server` only. Module
constants: `ROOT`, `REPO_ROOT`, `CORPUS_DIR`, `CORPUS_META`, `QUESTIONS`,
`INDEX_HTML`, `_REPO_RE`, `_LOOPBACK_HOSTS`.

- `_parse_allowed_hosts(raw) -> set | None` — parse `ICARUS_ALLOWED_HOSTS`
  (comma-separated) or None for the loopback-only default; `'*'` means trust
  the platform's TLS proxy + rely on the bearer gate.
- `_resolve_storage_root(raw, default) -> Path` — `ICARUS_STORAGE_ROOT`,
  falling back to `default` when unset OR set-but-blank.
- `runtime_readiness(storage_root, require_auth, environ=None) -> dict` —
  content-free production configuration probe: real write/fsync/delete on the
  selected storage root plus presence of the paid writer key, dedicated public
  ingest credential, OAuth pair and required-auth flag. It explicitly cannot
  infer paid-plan/ZDR status or prove that a directory is an Azure mount.
- `_positive_env_int(name, default) -> int` — parse a process capacity setting
  and fail startup on zero, negative, or non-integer values instead of silently
  creating a service with no usable capacity.
- `make_handler(registry, html_path, require_auth=False, verifier=None,
  oauth=None, allowed_hosts=None, ask_limiter=None, connect_limiter=None,
  memory_writer=None, memory_limiter=None, decisions=None,
  agent_mode_limiter=None, ...)` —
  return a `BaseHTTPRequestHandler` subclass bound to the registry:
  - `_authorized()` — loopback Host + same-origin guard; skipped entirely when
    `allowed_hosts` contains `'*'` (cloud mode — the bearer gate is the real
    boundary).
  - `_principal()` / `_identity()` / `_github_token()` — distinguish local,
    verified GitHub, and short-lived agent credentials while ensuring an agent
    token can never be forwarded to GitHub.
  - `do_GET` — `/` serves the page; `/health`/`/status` resolve
    `registry.library_for(self._identity())` and return its provenance/snapshot;
    `/ready` adds registry warmup plus the content-free runtime/storage checks,
    returning 503 until all are ready;
    `/auth/github/callback` completes the web-login redirect; else 404.
  - `do_POST` — `/auth/github/begin`/`/auth/github/redeem` work without a
    token (they mint one). `/auth/agent/session` requires a verified GitHub
    bearer, re-verifies access to the active repo, rate-limits issuance,
    and returns an opaque repo-bound session with `Cache-Control: no-store`.
    Agent sessions can read only the context/status routes and append only a
    bounded candidate/no-decision event; confirmation remains GitHub-only.
    Everything else requires an identity (401 if None).
    `/disconnect` calls `registry.disconnect(identity)`. `/ask` and `/connect`
    check their `RateLimiter` BEFORE parsing the body (429 plus `Retry-After` if
    exceeded, so a rate-limited caller never reaches the billed writer or a
    clone/ingest). Process-wide ask/investigation/connect ceilings prevent many
    identities from multiplying provider, GitHub or CPU spend. Shared bounded
    writer and ingest semaphores reject excess work with retryable 503s; a
    background connect holds its ingest slot until the actual job finishes.
    `/ledger?gaps=1&resolved=1` returns the server-owned memory lifecycle.
    `/memory-gaps/record` accepts an opaque actionable gap ID, returns an
    already-proposed pull request without consuming the write limit, otherwise
    invokes the bounded GitHub writer and durably appends `proposed` before
    returning success.
    `/agent-mode/candidates` lists pending cards for the app or appends one from
    a repo-bound agent. `/agent-mode/confirm` validates a human selection and,
    for accepted choices, creates the GitHub proposal before persisting success.
    `/agent-mode/context` projects only confirmed intent, distinguishing open PR
    receipts from marked documents actually present in the active corpus.
    `/ask` returns `build_payload(lib.current_pipeline().answer(q), ...)`; a
    strict boolean `include_evidence` opt-in adds retrieved evidence for agent
    clients and deliberately skips the human documentation-demand ledger.
    `/connect` validates `owner/name`; when auth is required, calls
    `evals.github_access.repo_info(repo, token)` first — `None` → 403 (refuse,
    fail safe); otherwise spawns `lib.connect_sync` in a daemon thread with the
    caller's token **only** if the repo is private, and returns 202.
- `resolve_provenance(meta_path, questions_path) -> (repo, commit)` — default repo
  from the committed `meta.json`, else the labelled set's `corpus` block.
- `serve(host=None, port=None)` — load `.env`, resolve host/port from env
  (`HOST`/`PORT`, a PaaS like Render injects `PORT`), build the
  `LibraryRegistry` from `ICARUS_STORAGE_ROOT` (default `<repo>/data`), wire up
  the GitHub verifier/OAuth flow when configured, and run `ThreadingHTTPServer`.
  Entry point: `python3 -m demo.server`.

## demo/repo_map.py
The repository map served by `GET /map`: what Icarus INDEXED, said before anyone
asks. Pure — in-memory chunks + a status snapshot in, dict out; no model, no
network, no filesystem. Constants: `_FILE_SOURCES`, `_ROOT`.

- `build_map(chunks, status) -> dict` — distinct indexed FILE count, files by
  language and by top-level directory, indexed documentation (explicit
  `readme: null` when none), chunk counts per source, lexical/semantic readiness,
  truncation, `indexed_entry_points` and `indexed_structure`. Every field is named
  `indexed_*` on purpose: it describes what Icarus READ, never what EXISTS.
- `_exclusion_rules()` — the ingest deny-lists as rules that were APPLIED, derived
  from `evals/ingest.py`'s own constants so they cannot drift. Never a list of
  observed excluded files, since `classify_file` records nothing about what it skips.
- `_readme(doc_paths)` / `_named_doc(doc_paths, stem_test)` — the shallowest match,
  sorted by (depth, path) so the choice is deterministic.
- `_split(ref)` / `_top_directory(path)`.

## demo/entry_points.py
"Where do I start reading?", answered by explicit RULES only, never by a score.

- `detect_entry_points(chunks)` — five rules (`pyproject-console-script`,
  `python-main-guard`, `go-main-function`, `rust-main-file`,
  `conventional-filename`). Every result carries `{rule, evidence_ref, detail}` —
  the indexed chunk that proves it — and a rule may only name a file that is IN
  the corpus. No rule fires → empty list, never a guess.
- `is_auxiliary_path(path)` — tests/fixtures excluded from every rule, earned by
  running it over this repo: the guard rule otherwise returned 70 "entry points".
- `_script_targets(text)` / `_module_candidates(target)` / `_path_of(chunk)`.

## demo/structure.py
How the code is ARRANGED, read off its own import statements. Pure and
deterministic, so it holds during the lexical-only window and cannot bluff.

- `build_structure(chunks) -> dict` — `file_edges` (Python/JS, where an import
  names a FILE), `package_edges` (Go, where it names a DIRECTORY), directory-level
  `components` carrying the indexed refs proving their edges,
  `most_depended_on_files`, `unresolved_import_count`, `unanalysed_languages`.
- `_resolve_python(...)` / `_resolve_js(...)` / `_resolve_go(...)` — every resolver
  is language-specific ON PURPOSE: a first generic pass invented a `pkg -> demo`
  edge across 566 files of lazygit by bare-name matching.
- `_edges_for(...)` / `_language(path)` / `_directory(path)` / `_path_of(chunk)` /
  `_python_targets(text)`.

## demo/onboarding.py
The guided tour: `STEPS` (the five measurement proved reliable, plus two
writer-free ones), `ANCHOR_DOCUMENT`, `ANCHORED_STEPS`. Holds NO per-user state.

- `plan(status)` — the ordered tour. Pure and instant: no writer, no retrieval, so
  interrupting and resuming costs nothing.
- `answer_step(pipeline, status, step_id, token) -> Result` — one step as an
  ordinary gated ask, returned untouched. A claim Icarus VOLUNTEERS earns less
  scepticism from a reader than one they asked for, so it needs more proof, not
  less. Unknown step id raises rather than being guessed.
- `title_for(step_id)`.

## demo/freshness.py
Does the connected index still match the repository? Constants: `_DEFAULT_TTL`.

- `class FreshnessChecker` — thread-safe, TTL-cached per `(repo, indexed_commit)`,
  so a refresh invalidates instantly. `.check(repo, indexed_commit, token)` returns
  `{up_to_date, behind_by, head_commit, checked_at}` and NEVER raises.
- `_unknown(checked_at)` — every key present on every path, so a client cannot
  KeyError its way through a failure. `up_to_date` is three-valued and every
  failure lands on `None`: claiming freshness because the check failed is the same
  class of failure as a bluffed citation.

## demo/investigations.py
What one caller's investigation remembers between turns, so "why did **it**
change?" resolves. Constants: `_DEFAULT_TTL`, `_MAX_CONVERSATIONS`,
`_MAX_CARRIED_CLAIMS`, `_REFERRING`.

- `class ConversationStore` — keyed on (identity, repo, corpus fingerprint) with a
  request counter, so a subject cannot survive a repo switch, leak between users,
  or be overwritten by an older overlapping investigation. `.begin`, `.resume`,
  `.remember`, `.forget`, `._purge`.
- `class CarriedClaim` / `class Conversation` — verified findings WITH the support
  class they were measured at; never evidence TEXT, since the corpus can be
  refreshed underneath a live conversation.
- `refers_back(question) -> bool` — the deterministic deictic check gating subject
  inheritance. Never a model: a wrongly inherited subject produces a confident,
  fully cited answer about the wrong change, which groundedness cannot detect.

## demo/visits.py
What Icarus remembers about a RETURNING user: exactly four facts and no fifth.
Constants: `_SAFE_ID`, `_SAFE_REPO`, `_FILENAME`.

- `class VisitStore` — `.record(user_id, repo, commit)` takes no question, answer
  or verdict PARAMETER at all: a signature that cannot accept one is a stronger
  guarantee than a policy saying we will not pass one. A visit OVERWRITES rather
  than appends, because a list of timestamps is an activity log however innocuous
  each row looks. `.last_visit(user_id, repo)` → `{"commit", "at"}` or None.
- `_safe_user(user_id)` / `_safe_repo(repo)` — hostile ids refused, so nothing can
  escape the caller's own storage tree (the exact tree `disconnect` deletes).

## demo/github_oauth.py
Server-side GitHub authorization-code flow. The client SECRET lives only here,
never in the app or the extension. Constants: `AUTHORIZE_URL`, `TOKEN_URL`,
`_CHROMIUMAPP_REDIRECT`, `_IDENTITY_SCOPE`, `_WEB_SCOPE`, `_NATIVE_SCOPE`,
`_PRIVATE_REPO_MODE`.

- `class OAuthFlow` — `.begin(mode, redirect_target=None)` tags each login `web`,
  `app`, `app-private` or `extension` and mints a single-use CSRF state;
  `.complete(state, code)` validates and exchanges; `.redeem(session_id)` returns
  the token exactly ONCE. `._sweep()` expires stale entries.
- `authorize_url(client_id, redirect_uri, state, scope)` / `exchange_code(code)` /
  `new_state()`.
- Scope is per-surface and explicit per-mode (`begin()`'s `if`/`elif`/`else`,
  not a shared fallback): `web` asks `public_repo` (2026-09-03, widened from
  `read:user` so the web decision graph's Accept/Reject/Other can write a real
  PR), `app`/`extension` ask `_NATIVE_SCOPE` (`repo`), and `_PRIVATE_REPO_MODE`
  also asks `repo`; anything else falls back to `_IDENTITY_SCOPE` (`read:user`).
  An `extension` redirect target is validated against `_CHROMIUMAPP_REDIRECT` so
  this can never become an open redirect.

## demo/posthog_capture.py
Fire-and-forget PRODUCT usage capture. Stdlib `urllib` only, matching
`evals/provider.py`; no SDK, no new dependency.

- `capture(event, distinct_id, properties=None, opener=None, token=None)` — sends
  one event on a daemon thread, no-ops when unconfigured, and never raises into
  the request that triggered it. `opener`/`token` are injectable for offline tests.
  It sends whatever properties it is handed: the decision about WHAT may be sent
  lives at the call site in `demo/server.py`, which is where the caller's
  content-sharing header is visible.

## demo/warm_cache.py
Build-time warm-up, run by the Dockerfile so a container boots warm rather than
embedding the default corpus on the first request. Constant: `CORPUS_DIR`.

- `warm(corpus_dir=CORPUS_DIR)` — embed the default corpus and write its
  `vectors.json` cache.

## demo/__init__.py
Package docstring only: the minimal local face over the proven gated brain. It
imports `evals/`, and changes no brain code.

## demo/ test modules
- `demo/test_links.py` — pins `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — pins the answer and honest-unknown payload shapes
  (citation URLs, order preserved, `searched`, url=None for unknown sources),
  opt-in retrieved evidence, and exact repo/commit provenance.
- `demo/test_mcp_server.py` — pins the stdio MCP handshake and five tool
  schemas, evidence-rich honest unknowns, explicit line selections, repo
  mismatch refusal, private-repository fail-closed behavior, automatic
  app-issued session acquisition/reuse, candidate/raw-field/no-decision
  behavior, and explicit development overrides.
- `demo/test_decision_ledger.py` — pins candidate bounds/privacy/atomicity,
  confirmation choices and idempotency, and the deterministic corpus-backed
  proposal/not-indexed-to-merged/reconstruct transition.
- `demo/test_agent_mode.py` — real HTTP boundary proof of the full agent submit
  → human choice → GitHub proposal → fresh-session projection loop, including
  merged citations and counts-only analytics.
- `demo/test_agent_sessions.py` — pins opaque grants, identity/repo scope,
  expiry, and unknown-token refusal.
- `demo/test_auth.py` — pins `bearer_token` parsing, `StaticTokenVerifier`'s
  token→id mapping, and `GitHubTokenVerifier`'s cache hit/expiry, valid-token id
  resolution, and fail-safe None on network error/malformed body.
- `demo/test_registry.py` — pins `LibraryRegistry`: same user reuses the same
  `Library`, different users get different ones, per-user storage paths, one
  user's connect never touches another's state, the default pipeline built
  once and shared, anonymous shares one view, hostile ids rejected, LRU
  eviction, and disconnect deleting only that user's storage.
- `demo/test_ratelimit.py` — pins `RateLimiter`: allows up to the limit, blocks
  past it, a different key is unaffected, and the window sliding restores access.
- `demo/test_ledger.py` — pins repo isolation, append/read behavior, no asker
  identity, hostile-name containment, shared Unicode-casefold identity, opaque
  gap IDs, and open→proposed→resolved lifecycle.
- `demo/test_memory_writer.py` — pins validation, push permission, bounded
  GitHub request shapes, deterministic proposal reuse, lost-response recovery,
  marked decision records, and truthful partial-failure URLs.
- `demo/test_library.py` — pins the `Library`: starts on the default repo, cache-hit
  switches without re-ingesting, a miss ingests, default uses the committed corpus,
  an ingest failure keeps the previous repo answerable, and (Task 11) private
  connect (token + private path routing, refusal before ingest without the paid
  writer, token never in status output).
- `demo/test_server.py` — pins routing against a stub registry (GET `/`, `/status`,
  POST `/ask` answer/unknown, POST `/connect` valid→202 / bad→400, missing question
  → 400, 404), the Origin guard, body cap, per-request identity resolution,
  `/disconnect`, rate-limit 429s, concurrency, short-lived agent-session
  issuance/scope/expiry/route refusal, engineering-memory gap listing and
  idempotent proposal recording, and index.html smoke checks.
- `demo/test_isolation.py` — pins cross-user isolation at the HTTP boundary: a
  real `LibraryRegistry` behind a real running server with two authenticated
  identities — connect/storage/disconnect/provenance all stay disjoint, and an
  unauthenticated caller sees only the shared default.
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline (built via
  `Library`): an answerable question returns a cited answer with a github.com link,
  an unrecorded one returns the honest unknown (skips without a provider key/corpus).

## mac/Icarus/Sources/IcarusKit/AppearancePreference.swift
Persisted app-level appearance selection shared by the Settings UI and runtime.

- `icarusAppearanceDefaultsKey` — the one UserDefaults key for the preference.
- `enum AppAppearance` — the closed dark/light palette choice.
- `struct AppearancePreference` — reads and writes the choice against injectable
  UserDefaults, defaulting missing or invalid values safely to dark.

## mac/Icarus/Sources/IcarusKit/VoiceLatencyTracker.swift
Privacy-safe Phase 3 experience measurement. It accepts monotonic timing marks,
not product content, and retains only the newest 50 completed samples in memory.

- `class VoiceLatencyTracker` — records `begin`, `released`,
  `transcriptReady`, `answerReady`, and `firstWordStarted` in strict order;
  incomplete or time-inverted journeys never become samples.
- `struct VoiceLatencyTracker.Sample` — hold, transcription, brain, speech
  queue, release-to-first-word, and total durations.
- `releaseToFirstWordP50` / `releaseToFirstWordP95` — nearest-rank session
  percentiles over completed samples.

## mac/Icarus/Sources/IcarusKit/ClaudeHook.swift
Pure, bounded Claude Code hook behavior with I/O held in the app command layer.

- `enum ClaudeHook` — SessionStart injects only human-confirmed unmerged PR
  proposals or merged+cited corpus truth. Stop inspects only the current user
  turn for exactly one capture tool and returns nil when Claude's loop guard is
  active; block text never echoes transcript content.
