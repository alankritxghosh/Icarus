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
`_MAX_BACKOFF_SECONDS` (the named per-sleep cap).

- `_with_retry(call, retries=6, base=2.0)` — run `call()`, retrying on HTTP 429
  with backoff; waits a Retry-After header, else Gemini's body `retryDelay`, else
  `base*2**attempt` (capped at `_MAX_BACKOFF_SECONDS`). Non-429 raises immediately.
- `_openai_chat(url, key, model, prompt, timeout) -> str` — one OpenAI-compatible
  chat-completions call (shared by OpenRouter + Groq), with UA + 429 retry.
- `_parse_gemini(data) -> str` — extract text from a Gemini generateContent reply.
- `make_provider(name) -> Provider` — factory: `groq`/`gemini`/`gemini-paid`/
  `openrouter`; raises `ValueError` on an unknown name.
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
  default_repo, build_pipeline=None, ingest_fn=None, max_live=32,
  build_private_pipeline=None, private_ready=None)` builds the shared default
  pipeline once.
  - `_build(corpus_dir)` — returns the shared default pipeline for the default
    corpus dir, else delegates to the base builder.
  - `_key(user_id)` (static) — `user_id` or `_ANON`; raises `ValueError` on
    anything outside `_SAFE_ID` (ids come from GitHub; belt+braces).
  - `library_for(user_id) -> Library` — lazily creates (or returns) that
    identity's `Library` under `<storage_root>/<key>/cache`; LRU-evicts past
    `max_live`. On a rebuild after eviction, replays the identity's
    last-connected repo (recorded in `_last_repo`/`_last_private` at eviction
    time, under the same lock, to close a resume race) via `connect_sync` — a
    cache hit, so it never re-ingests; a private repo only resumes when its
    on-disk cache still exists (no token to re-ingest with), otherwise the
    fresh Library stays honestly on the default rather than ever silently
    reporting `private: False` for what the user believes is still private.
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

## demo/library.py
One active repo's state: which corpus is loaded, its pipeline, and switch
status. Thread-safe (a lock guards the pipeline swap). Helpers `_pick_writer`,
`_default_build_pipeline`, `_default_build_private_pipeline`,
`_default_private_ready`, `_slug`.

- `class Library` — `__init__(default_corpus_dir, cache_root, default_repo,
  build_pipeline=_default_build_pipeline, ingest_fn=ingest_repo,
  build_private_pipeline=_default_build_private_pipeline,
  private_ready=_default_private_ready)` builds the default pipeline and reads
  its meta.
  - `_cache_dir(repo)` / `_resolve(repo, private=False) -> (corpus_dir,
    needs_ingest)` — the default repo always resolves to the committed corpus;
    otherwise a public or private on-disk cache path.
  - `connect_sync(repo, token=None, private=False)` — switch the active repo
    (blocking, single-flight). If `private` and the paid writer isn't
    configured, refuses BEFORE any clone (status `error`, generic message).
    Cache hit → instant rebuild; miss → `ingest_fn(..., token=token)` then
    rebuild via the private or public pipeline builder. `token` is a LOCAL
    VARIABLE ONLY — never stored on `self`, never logged, never in any
    error/status output. On failure keeps the previous repo and sets status
    `error`.
  - `current_pipeline()` / `provenance()` / `status_snapshot()` — lock-guarded
    reads (`{state, repo, commit, counts, error, private}`).

## demo/server.py
A minimal web face over a `LibraryRegistry`. Stdlib `http.server` only. Module
constants: `ROOT`, `REPO_ROOT`, `CORPUS_DIR`, `CORPUS_META`, `QUESTIONS`,
`INDEX_HTML`, `_REPO_RE`, `_LOOPBACK_HOSTS`.

- `_parse_allowed_hosts(raw) -> set | None` — parse `ICARUS_ALLOWED_HOSTS`
  (comma-separated) or None for the loopback-only default; `'*'` means trust
  the platform's TLS proxy + rely on the bearer gate.
- `_resolve_storage_root(raw, default) -> Path` — `ICARUS_STORAGE_ROOT`,
  falling back to `default` when unset OR set-but-blank.
- `make_handler(registry, html_path, require_auth=False, verifier=None,
  oauth=None, allowed_hosts=None, ask_limiter=None, connect_limiter=None)` —
  return a `BaseHTTPRequestHandler` subclass bound to the registry:
  - `_authorized()` — loopback Host + same-origin guard; skipped entirely when
    `allowed_hosts` contains `'*'` (cloud mode — the bearer gate is the real
    boundary).
  - `_identity() -> str | None` — `"local"` when auth is off; the verified
    GitHub user id when auth is on and the token verifies; `None` otherwise
    (fail safe).
  - `do_GET` — `/` serves the page; `/health`/`/status` resolve
    `registry.library_for(self._identity())` and return its provenance/snapshot;
    `/auth/github/callback` completes the web-login redirect; else 404.
  - `do_POST` — `/auth/github/begin`/`/auth/github/redeem` work without a
    token (they mint one). Everything else requires an identity (401 if None).
    `/disconnect` calls `registry.disconnect(identity)`. `/ask` and `/connect`
    check their `RateLimiter` BEFORE parsing the body (429 if exceeded, so a
    rate-limited caller never reaches the billed writer or a clone/ingest).
    `/ask` returns `build_payload(lib.current_pipeline().answer(q), ...)`.
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

## demo/ test modules
- `demo/test_links.py` — pins `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — pins the answer and honest-unknown payload shapes
  (citation URLs, order preserved, `searched`, url=None for unknown sources).
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
- `demo/test_library.py` — pins the `Library`: starts on the default repo, cache-hit
  switches without re-ingesting, a miss ingests, default uses the committed corpus,
  an ingest failure keeps the previous repo answerable, and (Task 11) private
  connect (token + private path routing, refusal before ingest without the paid
  writer, token never in status output).
- `demo/test_server.py` — pins routing against a stub registry (GET `/`, `/status`,
  POST `/ask` answer/unknown, POST `/connect` valid→202 / bad→400, missing question
  → 400, 404), the Origin guard, body cap, per-request identity resolution,
  `/disconnect`, rate-limit 429s, concurrency, and index.html smoke checks.
- `demo/test_isolation.py` — pins cross-user isolation at the HTTP boundary: a
  real `LibraryRegistry` behind a real running server with two authenticated
  identities — connect/storage/disconnect/provenance all stay disjoint, and an
  unauthenticated caller sees only the shared default.
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline (built via
  `Library`): an answerable question returns a cited answer with a github.com link,
  an unrecorded one returns the honest unknown (skips without a provider key/corpus).
