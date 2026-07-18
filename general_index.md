# Icarus — General Index

A fast map of every tracked file in the repo with a 1–2 line description.
Grouped by directory. Regenerate this after any structural change (adding,
removing, or renaming files). For class/function-level detail see
`detailed_index.md`.

## Repo root
- `CLAUDE.md` — Claude Code's project instructions and working context.
- `AGENTS.md` — canonical shared engineering constitution: collaboration rules,
  honesty/trust boundaries, codebase entry path, workflow, and verification.
- `CODEX.md` — thin Codex-specific adapter covering collaboration style, task
  startup, tool conventions, verification/reporting, and instruction drift.
- `README.md` — the pitch and one-paragraph overview of Icarus plus its honesty
  promise.
- `general_index.md` — this file: every tracked file + a short description.
- `detailed_index.md` — every class/function in the `evals/` package + its
  description, drawn from real docstrings/signatures.
- `.gitignore` — ignored paths (secrets/`.env`, caches, build artifacts); the
  committed `.env.example` is explicitly un-ignored.
- `.env.example` — committed template (NO real keys) to copy to a gitignored
  `.env`; separates the one serving credential from optional eval-provider keys.
- `requirements.txt` — the sole Python dependency: `fastembed` (local, free,
  offline semantic-retrieval embeddings; ONNX Runtime + tokenizers, no PyTorch). Lazily
  imported, so everything else runs pure-stdlib without it. Install into a venv.

## Cloud deployment (host the brain on Azure Container Apps)
- `Dockerfile` — container for the brain: `python:3.12-slim` + `git`/`gh` (for
  repo-switch ingest), non-root UID 1000 (required by some hosts, harmless on
  others), `RUN python -m demo.warm_cache` bakes the fastembed model + default
  corpus's embeddings in at build time (boots warm on any host), runs
  `python -m demo.server`; binds `0.0.0.0`/`$PORT`. The image runs on Azure
  Container Apps (live) or a local Docker daemon.
- `.dockerignore` — keeps the image slim (only `evals/`+`demo/`+committed corpus;
  excludes local data/worktrees, tooling, clients, docs, `.git`, caches, `.env`).

## Security automation (per-commit + CI)
- `scripts/scan_secrets.sh` — deterministic secrets scan; `--staged` (pre-commit)
  or tracked-files (CI) mode. Exits non-zero on a provider-token or secret-shaped
  hit so it can block a commit/build.
- `scripts/install_hooks.sh` — one-time wire of `core.hooksPath` → `.githooks`.
- `scripts/private_flow_smoke.py` — manual, leak-safe live smoke of the brain's
  PRIVATE-repo HTTP path (/status→/connect→/ask→/disconnect) the Mac app drives;
  token from `GH_BEARER` env (never argv/logs), repo from `ICARUS_PRIVATE_REPO`.
- `.githooks/pre-commit` — commit gate: a staged secret hard-blocks; failing
  tests only warn (never block).
- `.github/workflows/security.yml` — CI backstop on push/PR: secrets scan +
  Python suites (evals, demo) + Swift build/test.

## docs/
- `docs/VISION.md` — product vision: the conversational engineering brain, what
  it answers, and the v1 scope (GitHub + Mac voice app + private cloud).
- `docs/ARCHITECTURE.md` — plain-language map of how Icarus is built (the Mac app
  is the face; the cloud is the brain).
- `docs/STRATEGY.md` — build & product strategy: sell the typed brain first, rent
  the commodities, own the moat. Includes the decided stack.
- `docs/COMPETITIVE.md` — competitive landscape: how comparable products were
  built, what to steal, what to avoid.
- `docs/BUILD_ORDER.md` — the phase-by-phase build order; never build the talker
  before the brain.
- `docs/PHASE_1_PLAN.md` — the concrete Phase 1 build: cited answer or honest
  unknown about one GitHub repo, proven by the harness.
- `docs/EVALUATION.md` — how Icarus proves it isn't bluffing; the gates and
  quality dials, plus the disclosed prompt-injection limitation.
- `docs/METRICS.md` — the numbers that tell us we're winning, grouped by what
  they protect (honesty first, then retrieval, experience, trust).
- `docs/WORKFLOWS.md` — the rules of the road for every change (red → green,
  never weaken the eval, scoped edits, report results).
- `docs/DESIGN_VISION.md` — the "Honest Brutalism" design language for the app.
- `docs/UI_UX_BRIEF.md` — UI/UX brief and intent behind the app surfaces.
- `docs/HANDOFF.md` — session handoff: current state, how to run it, what's done
  vs. not, and the gotchas.
- `docs/DISTRIBUTION.md` — runbook to share Icarus without an Apple Developer ID:
  host the brain on Azure Container Apps (minimal serving secrets + OAuth
  callback), build the DMG, and pass Gatekeeper once; lists alpha tradeoffs.

## docs/decisions/
- `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md` — the hosting
  model: one unified cloud we operate with per-tenant data isolation.
- `docs/decisions/2026-06-30-organizational-memory-positioning.md` — positioning
  (Icarus is organizational memory; explanation is the wedge) + roadmap.

## docs/plans/
- `docs/plans/2026-06-28-phase-1.md` — the Phase 1 plan.
- `docs/plans/2026-06-28-brick-2-gate-and-writer.md` — gate + writer brick.
- `docs/plans/2026-06-28-brick-3-embeddings.md` — embeddings brick.
- `docs/plans/2026-06-28-brick-4-answer-grading.md` — answer-grading brick.
- `docs/plans/2026-06-28-brick-5-web-demo.md` — web demo brick.
- `docs/plans/2026-06-28-brick-6-recordable-demo.md` — recordable-demo brick.
- `docs/plans/2026-06-28-brick-7-any-repo-ingest.md` — any-repo ingest brick.
- `docs/plans/2026-06-28-brick-8-9-private-repos.md` — private-repos bricks.
- `docs/plans/2026-06-29-free-hosted-providers.md` — free hosted providers (Groq/
  Gemini) plan.
- `docs/plans/2026-06-29-in-app-repo-switcher.md` — in-app repo switcher plan.
- `docs/plans/2026-06-30-github-auth-workflow.md` — GitHub device-flow auth plan.
- `docs/plans/2026-06-30-macos-app.md` — the macOS app plan (A0–A6).
- `docs/plans/2026-07-02-security-hardening.md` — the security-audit fix plan
  (server threading, auth, ingest limits, key hygiene, per-commit gate).
- `docs/plans/2026-07-02-full-app-shell.md` — the full windowed app-shell plan
  (five surfaces, all wired to real data, no fabricated values).
- `docs/plans/2026-07-04-private-repos-per-user-isolation.md` — the private-repo
  scoping doc (hosted, multi-user): per-user library registry, private-safe writer +
  trust interlock, caller-authorized leak-safe PAT ingest, isolation/egress proofs.
- `docs/plans/2026-07-04-private-repos-implementation.md` — the executable
  task-by-task TDD plan for the above: 16 tasks across Bricks A–F with exact code,
  tests, commands, and commits; Brick G (app) outlined.
- `docs/plans/2026-07-06-brick-g-private-repo-ui.md` — Brick G, built: the Mac
  app's private-repo surface (private flag, disconnect, repo persistence across
  launches, client-side lost-connection banner) — historical; the private flag
  was retired from the current public-repository alpha.
- `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md` — turns the nine
  tester remarks + the refined north star ("understand code from the code itself,
  answer any phrasing, JARVIS per developer") into a probe-first build order: Brick
  0 (code-comprehension eval set), A (whole-codebase ingest), B (PR/Issue coverage),
  C (semantic retrieval), Q (query-understanding: framing/grammar/spelling), D
  (line-select explain), S (structural comprehension, deferred-gated), E (richer
  "why"). Governed by the what/how-vs-why honesty boundary; remark 9 (writing code)
  stays off the table.
- `docs/plans/2026-07-10-hugging-face-spaces-migration.md` — plan to move the
  hosted brain off Render's free tier (0.1 CPU, verified the actual root cause
  of a live incident: a 216-chunk private-repo connect never finished inside a
  15-minute embed timeout) onto Hugging Face Spaces' free Docker tier (2 vCPU/
  16GB, verified). Enumerates every real touchpoint (Dockerfile non-root user,
  hardcoded Render URLs in extension/, GitHub OAuth callback, docs) found by
  grep, not guessed; task-ordered smallest-loop-first. Not started.

## evals/ (the Phase 1 eval harness — Python stdlib only)
- `evals/__init__.py` — package docstring: the harness is the product's
  conscience (cited-answer correctness + honest abstention).
- `evals/corpus.py` — the `Chunk` dataclass, `load_chunks` (read the committed
  corpus, one evidence unit per line with a citation ref), and
  `chunk_covers_lines(chunk, path, start, end)` (Brick D: does a chunk cover a
  GitHub line selection? Handles both a windowed `#Lstart-Lend` ref and a
  whole-file ref with no suffix -- the committed corpus's actual shape).
- `evals/ingest.py` — corpus generator from a public **or private** repo (PRs,
  linked issues, source code) → `chunks.jsonl` + `meta.json`. Code chunking is
  NOT Python-only — `_EXTENSION_SOURCES` maps Python, JS/JSX/MJS/CJS, TS/TSX,
  Go, Rust, Java, Ruby, C/C++, **Objective-C/C++ (`.m`/`.mm`)**, Swift, Kotlin,
  PHP, C#, Scala, and Shell to "code" (`.md`/`.rst`/`.txt` → "doc",
  `.yaml`/`.yml`/`.toml`/`.cfg`/`.ini`/`.sql`/`.gradle`/`.podspec` → "config").
  `.json` is deliberately EXCLUDED (2026-07-17) — on a real React Native app it
  is dominated by Xcode asset catalogs and i18n locale bundles, which would skew
  BM25/IDF corpus-wide; allowlist the filename if `package.json` ever matters. Subprocess timeouts, per-file (512KB) + total-byte (100MB) + total-
  chunk (50k, bounds lexical stage-1 memory on a hostile many-short-lines repo)
  caps that log to stderr when they truncate, a `code_dir`
  path-traversal guard, and an optional caller `token` threaded leak-safe into
  `git`/`gh` subprocess **env** (`_git_env`/`_gh_env` — never argv, never the
  clone URL, never logged). Needs `gh` + `git`. `chunk_text`'s windowing is
  character- as well as line-aware (2026-07-17 fix): a single PHYSICAL line
  that alone exceeds the char budget (a machine-generated file with one huge
  object-literal line -- measured live up to ~250,000 chars) is truncated
  in place with a visible marker and a stderr log, rather than shipped whole
  -- found because the prior floor-of-one-line-of-progress guarantee only
  ever checked MULTI-line windows, never a single oversized line by itself.
  `_chunk_code` (T4) dispatches a CODE file to `ast_chunk`/`ts_chunk` behind
  `ICARUS_AST_CHUNKING` (env flag, default OFF -- the committed board and
  every existing corpus keep chunking unchanged unless deliberately turned
  on); `.py` → `ast_chunk`, the React Native language set → `ts_chunk`,
  everything else (doc/config sources, `.h`, Go/Rust/Ruby/...) stays on
  `chunk_text`. Both chunkers are imported lazily INSIDE the dispatcher, not
  at module level -- required, not stylistic: both import `chunk_text`/
  `_CHUNK_MAX_CHARS` FROM this module, so an eager top-level import would be
  circular. Verified end-to-end against a real cloned repo (wix/react-native-
  navigation's `ios/`): 1,624 real chunks, `.mm` files split from 1 whole-file
  chunk to per-method chunks (e.g. `RNNCommandsHandler.mm` 1→19), `.h` stayed
  on `chunk_text` unchanged.
- `evals/ast_chunk.py` — `ast_chunk(text, ref_prefix)`: AST-aware code chunking,
  splitting Python at function/class boundaries (stdlib `ast`, NO new
  dependency) instead of `ingest.chunk_text`'s fixed 300-line windows. Exists
  because the embedder (`bge-small-en-v1.5`) truncates at 512 tokens while a
  real 300-line window measures p50 ~2,234 -- so semantic retrieval silently
  read ~the first quarter of every window. Same contract/ref format as
  `chunk_text`; falls back to it on non-Python, syntax errors, or a module with
  no top-level defs, so it can never do worse. Emits a scope header (imports +
  enclosing class) per chunk and keeps module/class-level constants as evidence.
  **Proven, NOT yet wired into `fetch_code`** -- see docs/HANDOFF.md.
- `evals/ts_chunk.py` — `ts_chunk(text, ref_prefix, ext)`: tree-sitter-backed
  AST chunking for the React Native language set (`.ts`/`.tsx`/`.js`/`.jsx`/
  `.mjs`/`.cjs` via the `tsx` grammar -- measured 96% fewer parse errors than
  `javascript` on real Flow-typed RN code; `.mm`/`.m`/`.java`/`.kt`).
  Same contract as `ast_chunk.ast_chunk`. Recursive definition walk +
  export/const-arrow unwrapping (measured: `export const Foo = () => {}`
  outnumbers `function Foo(){}` ~30:1 in real code) + a size-based safety
  valve (any emitted span over 2x `chunk_text`'s window, by LINE COUNT **or**
  CHAR COUNT, gets re-windowed via `chunk_text` itself, checked against the
  final emitted text including its scope header -- found live: a Jest
  `describe()` block, invisible to the definition scheme, produced a single
  ~950,000-char chunk without the line check; a 125-line file with one
  ~250,000-char generated line needed the char check too, since line count
  alone never trips on a pathologically long single line). `.h` deliberately
  unsupported (neither the `c` nor `objc` grammar parses real RN headers
  cleanly). Lazy tree-sitter import, ERROR-rate gate, falls back to
  `chunk_text` whenever untrustworthy. **Proven (27 tests, T1+T2 of
  docs/plans/2026-07-17-ast-chunking-all-languages.md; verified max chunk
  size across 17,657 real RN files is 19,991 chars), NOT yet wired into
  `fetch_code` and no per-language recall eval yet (T3/T4 pending).**
- `evals/corpus_meta.py` — `write_meta`/`load_meta` for the self-describing corpus
  provenance the demo reads for citation links. `write_meta` also stamps a
  `"chunking"` field (`"chunk_text"` or `"ast"`, default `"chunk_text"` so
  existing callers don't need updating) -- T6 of docs/plans/2026-07-17-ast-
  chunking-all-languages.md, read by `demo/library.py`'s staleness check so a
  corpus chunked by a scheme that's since changed gets refreshed on its next
  connect instead of silently staying stale forever.
- `evals/retriever.py` — `LexicalRetriever` (stdlib BM25 keyword retriever) plus
  a `tokenize` helper, `SemanticRetriever` (cosine similarity over an
  `EmbeddingProvider`'s vectors; optional `vectors=` param + `.vectors` property
  to supply/persist precomputed chunk embeddings), `HybridRetriever` (RRF
  fusion of BM25 + semantic), and `NormalizingRetriever` (Brick Q: wraps any
  retriever, running `query_normalize.normalize_query` on the query before
  delegating -- "wire ahead of the retriever") -- all share the
  `.search(query, k) -> List[str]` contract, drop-in for each other.
- `evals/query_normalize.py` — Brick Q's query-understanding layer:
  `build_vocabulary(chunks)` (reuses `retriever.tokenize()` exactly),
  `normalize_query(text, vocabulary, cutoff=0.8)`, a stdlib-only (`difflib`)
  fuzzy spelling corrector toward real corpus terms -- never an external
  dictionary, and `COMMON_SHORT_WORDS` (shared with `baseline_retriever.py`).
  Retrieval-only preprocessing; the writer/user still see the original
  question text.
- `evals/baseline_retriever.py` — `GrepBaselineRetriever`: the third-party
  comparison yardstick -- what a developer gets by grepping the repo today,
  with none of Icarus's ranking/semantics. Deliberately dumb (keyword-presence
  OR-match, no term-frequency weighting, no typo tolerance), pure Python (no
  subprocess call to a real grep/rg binary, so it's reproducible without
  ripgrep installed). Same `.search(query, k)` contract, drops into `grade()`
  for an apples-to-apples comparison; not a shipped retrieval technique.
- `evals/vector_cache.py` — `load_vectors`/`save_vectors`: the on-disk embedding
  cache (JSON sidecar tagged by model name) so the demo doesn't re-embed a corpus
  on every start. Pure optimization, fail-safe: any miss/model-change/corpus-
  change/corrupt file returns None → re-embed. Cache (`vectors.json`) is derived,
  gitignored, never committed.
- `evals/provider.py` — the `Provider` abstraction for the rented writer/judge:
  `GroqProvider`, `GeminiProvider` (key in the `x-goog-api-key` header, not the
  URL), `OpenRouterProvider`, `StaticProvider`, and `PaidGeminiProvider` (a
  billing-enabled, `private_safe=True` Gemini on its own `GEMINI_PAID_API_KEY`);
  `make_provider` factory + 429 backoff. Stdlib `urllib`; keys from env. Also the
  `EmbeddingProvider` family for semantic retrieval: `StaticEmbeddingProvider`
  (test double) and **`LocalEmbeddingProvider`** (the decided FREE route: local
  ONNX transformer via `fastembed` (bge-small-en-v1.5), `private_safe=True`, no
  key/network/quota, lazily imported); `make_embedding_provider` factory. (The
  hosted `GeminiEmbeddingProvider`/`PaidGeminiEmbeddingProvider` were removed
  2026-07-18 — nothing selected them once serving standardized on the local
  embedder.)
- `evals/trust.py` — the deterministic trust interlock: `assert_safe_for_private`
  raises `PrivateDataError` unless a provider declares `private_safe=True`
  (never inferred from a key string) — private code's only gate to a writer.
- `evals/github_access.py` — `repo_info`: the caller-scoped permission check
  (`GET /repos/{owner}/{repo}` as the caller's own token); 200 → `{"private":
  bool}`, anything else (403/404/network/malformed) → `None` (fail-safe refuse).
- `evals/env_file.py` — `load_env_file`: stdlib loader that reads a gitignored
  `.env` into `os.environ` without overriding real env vars.
- `evals/synth.py` — `build_prompt`, the strict cite-or-abstain prompt (also tells
  the writer to treat evidence as data, not instructions). Truncates prose chunks
  to `_MAX_CHUNK_CHARS` (1500) but CODE chunks to `_MAX_CODE_CHUNK_CHARS` (10000)
  so a 300-line code window stays visible to the writer instead of ~40 lines.
- `evals/gate.py` — the deterministic honesty gate: emits an answer ONLY if it
  parses, claims "answer", has prose, and cites ≥1 retrieved ref; else "unknown".
  Citation matching is tolerant-but-safe (`_parse_ref`/`_resolve`): it grounds a
  citation the writer reformatted — dropped `code:` prefix, display brackets, or
  narrowed a chunk's `#L1-L300` window to the specific `#L21` line — when paths
  match AND the cited lines are CONTAINED in the retrieved window, but still forces
  unknown on an unretrieved path, an out-of-window line, or a MALFORMED range
  (line 0/negative, end<start), so groundedness holds. It also applies the (b)
  rationale guard: when given the question + evidence, a "why" question whose
  grounded evidence records no reason (a bare code constant, not pr/issue/doc or
  rationale prose) is forced to "unknown" — catching the why→what dodge.
  And the (c) entity-presence guard (added 2026-07-18): a question naming a
  DISTINCTIVE code identifier (snake_case / camelCase / long non-acronym
  ALL-CAPS, reduced to its leaf symbol) that appears NOWHERE in the evidence the
  writer saw is forced to "unknown" — catching a fabricated symbol grounded to
  adjacent real code (found live: Redis has no `HYPERVECTOR` type, but its real
  vector-set code let the writer answer as if it did). Fail-safe, evidence-gated,
  off for `.explain()`; single Title-case words are deliberately not flagged.
  A named source prefix must equal the retrieved ref's source (`code:1489` never
  grounds to `pr:1489`); only a bare-body citation gets the prefix-drop tolerance.
- `evals/judge.py` — the answer-correctness judge (quality dial, NOT a gate):
  `build_judge_prompt`, `parse_verdict` (fails safe to "incorrect"), `Judge`.
- `evals/pipeline.py` — the `Result`/`Pipeline` contract, plus `StubPipeline`,
  `RetrievalPipeline`, and `GatedPipeline` (retrieve → writer → gate → Result;
  `.answer()` and Brick D's `.explain(path, start, end, question=None)` --
  location-resolved evidence instead of a `.search()` query -- both funnel
  through the shared `_answer_from` writer→gate core, so `.explain()` opens no
  new honesty path). `.explain()`'s neighbor search uses the caller's
  `question` when given (proven live to reproduce `.answer()`'s exact top-k
  for the same question), else the anchor chunk's own text.
- `evals/grader.py` — deterministic grading against the labelled set: the two
  honesty gates + quality dials; optional `judge` fills answer_correctness.
- `evals/run.py` — CLI that runs the eval board and prints it (loads `.env`
  first); exits non-zero only when a gate breaks. `--pipeline/--writer/--judge`.
- `evals/test_corpus.py` — `load_chunks` parses JSONL into `Chunk`s (tolerates
  blank lines); `chunk_covers_lines` across windowed/whole-file/malformed refs,
  path mismatches, and non-file-addressable (pr/issue) sources.
- `evals/test_ast_chunk.py` — `ast_chunk`'s unit contract (stdlib-only,
  always-run): per-function/class splitting, chunk_text-identical ref/shape,
  scope headers, a big class splitting per method while its docstring +
  class-level attributes survive under the CLASS's ref (never leaking into the
  module preamble's whole-file ref), module constants preserved, chunks
  dramatically smaller than a line window, and the fallbacks (non-Python,
  syntax error, no-defs module, null bytes) returning `chunk_text` verbatim.
- `evals/test_ast_chunking_eval.py` — AST chunking's live board proof
  (self-skips without fastembed/corpus): same-run, never-hardcoded comparison
  against `chunk_text`, holding PR/issue chunks and source text identical and
  varying ONLY the code chunker. Proves the mechanism (median line-window
  EXCEEDS the 512-token embed budget; AST chunks fit) and the payoff (strictly
  better semantic recall@5), plus a guard that lexical recall never regresses.
  Scores FILE-LEVEL recall on purpose -- `grader.grade`'s exact-ref
  recall would score AST 0 against whole-file gold citations for reasons
  unrelated to quality.
- `evals/test_ts_chunk.py` — `ts_chunk`'s unit contract, self-skips without
  tree-sitter-language-pack: per-language fixtures for TS/TSX (const-arrow
  functions, small vs. large classes), Flow-typed `.js` (parses via `tsx`,
  not `javascript`), ObjC (`.mm` method nesting), Java, Kotlin (name-field
  fallback regression guard -- proven by reverting the fix and watching the
  test fail), the size-based safety valve (Jest `describe()` block, a giant
  single function, and a few-line/huge-single-line file each proven red→green
  by disabling the relevant check), and the chunk_text fallbacks (unsupported
  `.h`, garbage input, no definitions, missing tree-sitter).
- `evals/test_ts_chunking_eval.py` — T3's live per-language proof: for each of
  TSX/Kotlin/ObjC/Java, same-run file-level recall@5 (semantic) comparing
  `ts_chunk` against `chunk_text`'s window-300 baseline over the committed
  real fixture corpora (`evals/fixtures/ts_chunk_eval/`), plus the mechanism
  proof (median token length under the 512-token embed budget per language).
  Gold files are deliberately 400-550+ real lines -- an earlier draft using
  short (~250-line) targets found both chunkers hit 100% identically, since a
  file that short never triggers the truncation this brick fixes. Measured:
  tsx 66.7%→100%, java 33.3%→66.7% (the one java miss is a real, disclosed
  semantic-competition case -- other real Fab-named files outrank the one
  method that merely references Fab -- not a chunking defect), kotlin/objc
  tied at 100% (no regression, ceiling effect at this corpus scale). Self-skips
  only on missing fastembed/tree-sitter -- the fixture corpus is committed.
- `evals/ts_chunk_eval_questions.json` — T3's 12 hand-verified questions (3 per
  language), each checked against the real fixture source in full before its
  reference_answer was written; questions target content positioned LATE in
  each gold file, which is what actually exercises the truncation difference.
- `evals/fixtures/ts_chunk_eval/` — real, MIT-licensed source files (~70/lang,
  java capped at 47, its directory's whole bounded pool) from wix/react-
  native-navigation, facebook/react-native, and bluesky-social/social-app,
  committed verbatim for T3's deterministic, no-network eval -- see
  `MANIFEST.md` for exact commit provenance and file-selection rationale.
- `evals/test_corpus_meta.py` — `write_meta`/`load_meta` round-trip; missing meta
  returns None; the "chunking" field round-trips and defaults to "chunk_text"
  for callers that omit it (T6).
- `evals/test_ingest_args.py` — ingest CLI defaults/overrides, commit resolution,
  and `_safe_code_dir` path-traversal rejection.
- `evals/test_ingest_chunking.py` — `chunk_text`'s pure line-window contract:
  short-file/exact-boundary/single-line/empty-text whole-chunk cases, the
  overlap/coverage/uniqueness invariants of a multi-window split, a dense-but-
  short file splitting by char budget, and (2026-07-17) a single PHYSICAL
  line that alone exceeds the char budget being truncated in place with a
  visible marker rather than shipped whole -- reproduces a live bug (a
  machine-generated file with one ~250,000-char line became one oversized
  chunk) and proves refs stay unique post-truncation (load-bearing:
  `SemanticRetriever` keys embeddings by `chunk.ref`) and GitHub-linkable.
- `evals/test_ingest_repo.py` — `ingest_repo` writes chunks + meta and returns
  counts (network fetches monkeypatched; offline); meta.json's "chunking"
  field reflects the flag (T6). Also T4's wiring tests: `_chunk_code`'s
  dispatch decision in isolation (mock.patch on ast_chunk/ts_chunk -- default
  OFF never calls either; every truthy env-var spelling routes `.py`→ast_chunk
  and the RN language set→ts_chunk; `.h` and other languages stay on
  chunk_text even with the flag on), plus the same wiring exercised through
  the real `fetch_code` walk (doc/config sources never reach the dispatcher;
  the flag-off path matches plain chunk_text byte-for-byte, protecting the
  committed board's reproducibility).
- `evals/test_ingest_smoke.py` — skippable live ingest of a tiny public repo
  (`RUN_INGEST_SMOKE=1`).
- `evals/test_env_file.py` — the `.env` loader: parses KEY=VALUE, doesn't override
  real env, tolerates comments/quotes/export, no-ops on a missing file.
- `evals/test_retriever.py` — tokenization + BM25 ranking, truncation, zero-score
  dropping, deterministic tie-breaking; plus `SemanticRetriever`/`_cosine` tests,
  including the core proof that cosine similarity finds a paraphrased chunk with
  zero keyword overlap where BM25 provably returns nothing.
- `evals/test_pipeline.py` — `RetrievalPipeline` populates `retrieved` yet still
  abstains.
- `evals/test_provider.py` — `StaticProvider` queuing, no-key errors, the retry
  budget, and the Gemini key going in the header not the URL; `private_safe`
  flags per provider and `PaidGeminiProvider`'s dedicated key env.
- `evals/test_trust.py` — the trust interlock refuses every free provider and an
  undeclared one, and passes the private-safe/static providers.
- `evals/test_github_access.py` — `repo_info` across 200 (public/private),
  sends the caller's token as Bearer, and refuses on 404/network error/garbage
  body/missing `private` field/no token (never calls out without one).
- `evals/test_synth.py` — the prompt includes question/refs/text, offers the
  unknown path, truncates long chunks.
- `evals/test_gate.py` — the gate passes grounded answers and fails safe to
  abstention on everything ambiguous.
- `evals/test_grader.py` — the harness conscience: gates hold for an honest
  abstainer/oracle and fire for a bluffer.
- `evals/test_gated_pipeline.py` — `GatedPipeline` end to end with a
  `StaticProvider` (answer, abstention, forced-unknown bluff).
- `evals/test_gated_explain.py` — Brick D's `.explain()`: anchor resolution
  (windowed + whole-file chunks), semantic neighbors, honest unknown with no
  coverage, the shared honesty gate (grounded answer / forced-unknown bluff /
  writer abstention -- proves no new honesty path), the default vs. caller-
  supplied question, question-preferred-over-anchor-text neighbor search (the
  real bug this brick found+fixed: an earlier version always searched on the
  anchor's own code text even with a real question, live-verified to find
  measurably worse neighbors than /ask), and a regression guard that
  `.answer()`'s behavior is byte-identical after the `_answer_from` refactor.
- `evals/test_vector_cache.py` — the embedding cache round-trips and fails safe
  to None (re-embed) on every mismatch/corruption; the `SemanticRetriever`
  `vectors=` param skips chunk embedding yet still embeds the query live.
- `evals/test_gated_semantic.py` — the honesty-gate proof for the SEMANTIC/HYBRID
  retrieval path (Brick C): a `GatedPipeline` + real writer over
  `SemanticRetriever`/`HybridRetriever` evidence emits a grounded answer but
  forces an ungrounded citation to abstention. Deterministic
  `StaticEmbeddingProvider` (offline, always-on), so it proves the gate is
  retriever-agnostic without needing fastembed.
- `evals/test_query_normalize.py` — Brick Q's `normalize_query`/
  `build_vocabulary`: corrects real typos, leaves correct/unmatched/common-short
  words alone, deterministic (incl. a genuine-scoring-tie case, not a vacuous
  no-tie fixture), and `TokenizerLockstepTests` -- an always-run guard proving
  `query_normalize`'s word-splitter stays byte-identical to
  `retriever.tokenize()` (catches the exact filename-corruption bug class this
  brick fixed, without needing fastembed). Stdlib only, always runs.
- `evals/test_baseline_retriever.py` — `GrepBaselineRetriever`'s unit tests:
  keyword OR-matching, count-based ranking (no term-frequency weighting, unlike
  BM25 -- proven by a chunk repeating a keyword 50x NOT outranking one
  mentioning it once), case-insensitivity, common-word skipping, determinism.
- `evals/test_grep_comparison_eval.py` — the third-party comparison proof:
  Icarus's retrieval (hybrid + normalized) beats the grep baseline on the
  comprehension board, both phrasings, same-run recall@5, gates 100%
  throughout. Self-skips without fastembed/the corpus/comprehension set.
- `evals/test_query_normalization_eval.py` — Brick Q's live board proof: wrapping
  hybrid retrieval with `NormalizingRetriever` never regresses recall on either
  phrasing and closes messy-phrasing recall@5 up to the clean baseline in
  aggregate (same-run boards, gates 100% throughout). Self-skips without
  fastembed/the corpus/comprehension set.
- `evals/test_code_answering_gap.py` — regression guard for the two code-answering
  gaps found+fixed 2026-07-13: the gate grounds a code citation the writer
  reformatted (dropped `code:` prefix / display brackets / narrowed a chunk's
  `#L1-L300` window to the specific `#L21` line it used) yet still forces unknown
  on an unretrieved path or an out-of-window line; and `build_prompt` shows code
  past the old 1500-char cap so a mid-window answer isn't truncated out. Started
  as a RED failing eval (red→green, deterministic, no live model).
- `evals/test_retrieval_eval.py` — end-to-end red→green: retrieval recall@k rises
  without dropping a gate (skips without the corpus).
- `evals/test_gated_eval.py` — real-model proof: citation correctness > 0 with
  both gates 100% (skips without a key/corpus).
- `evals/test_reference_answers.py` — every answerable question has a
  `reference_answer`, every unanswerable one has none.
- `evals/test_judge_prompt.py` — `build_judge_prompt` includes question/reference/
  candidate and truncates long candidates.
- `evals/test_judge.py` — `parse_verdict` + `Judge` over a `StaticProvider`.
- `evals/test_answer_correctness.py` — `grade(..., judge=…)` scores answer
  correctness and leaves the gates untouched; PENDING without a judge.
- `evals/test_answer_correctness_eval.py` — real-model proof: answer correctness
  > 0 while both gates stay 100% (skips without a key/corpus).
- `evals/test_free_hosted_eval.py` — real-model proof on the free hosted stack
  (Groq writer + Gemini judge).
- `evals/test_paid_writer_eval.py` — real-model proof: the paid Gemini writer
  holds both honesty gates at 100% with citation correctness > 0 on the public
  board (self-skips without `GEMINI_PAID_API_KEY`).
- `evals/test_private_ingest_live.py` — live end-to-end private-repo proof: the
  access gate, an authed clone, a paid-writer answer, and the free-provider
  interlock refusal, all against a real repo (self-skips without
  `RUN_PRIVATE_INGEST=1` + a real repo/token/paid key).
- `evals/test_egress_invariants.py` — proves, offline with a spy provider, that
  private text reaches only a genuinely private-safe provider, an unsafe one
  raises before any prompt is sent, the serve path never imports the judge, and
  the per-user private tree is git-ignored.

## evals/ data files
- `evals/phase1_questions.json` — the verified labelled question set (pinned to
  `simonw/llm` @ `94769b8`): labels, gold citations, notes, reference answers.
- `evals/corpus/chunks.jsonl` — the committed corpus (one JSON object per line).
- `evals/corpus/meta.json` — provenance for the committed corpus.

## demo/ (the Phase 1 web face — stdlib only, packaging over the gated brain)
- `demo/__init__.py` — package docstring: the minimal local face over the gated
  brain; imports `evals/`, changes no brain code.
- `demo/links.py` — `ref_to_url`, mapping a `source:ref` citation to its GitHub
  URL; unknown/malformed → None.
- `demo/payload.py` — `build_payload`, turning a `Result` into the page JSON.
- `demo/library.py` — `Library`: one active repo's state + pipeline. Builds a
  `HybridRetriever` (BM25 + local semantic) via `_build_retriever`, wrapped in a
  `NormalizingRetriever` (Brick Q query normalization, wired into serving
  2026-07-18) so messy/typo'd query phrasing is corrected toward real corpus
  terms before retrieval; backed by a
  process-shared `_shared_embedder` (the fastembed model loads ONCE; falls back
  to lexical-only if fastembed is unavailable) and the `evals/vector_cache`
  on-disk cache so restarts/reconnects don't re-embed. `connect_sync`
  reuses a cache or ingests once, single-flight and thread-safe, serving a
  generic error on failure. The one writer is constructed through the trust
  interlock (`evals/trust.py`); the public alpha has no dormant private-connect
  branch in `Library`. T6: `connect_sync` also refreshes an already-cached
  corpus whose `meta.json` "chunking" scheme has since changed
  (`Library._corpus_is_stale`) -- but never for the committed default repo
  (exempt), and never for a private repo with no token available (the
  tokenless eviction-replay resume in `registry.py`, which must never fail or
  silently downgrade to the public default). `_resolve` itself deliberately
  stays pure availability ("does a corpus exist"), never staleness -- see the
  plan doc's "What T6 found" for why that separation is load-bearing.
- `demo/registry.py` — `LibraryRegistry`: one isolated `Library` per GitHub
  identity under `<storage_root>/<user_id>/…`; the shared public default is
  built once and reused read-only. LRU-bounded (`max_live`); an evicted user's
  library rebuilds from its on-disk cache and the registry replays their last
  connect so eviction never silently reverts them to the demo repo. `disconnect`
  deletes a user's storage + forgets their last-connected repo and surfaces any
  deletion failure other than an already-absent directory.
- `demo/ratelimit.py` — `RateLimiter`: per-key sliding-window limiter (stdlib,
  thread-safe, injectable clock) bounding how often an identity can hit `/ask`
  (bills the writer) or `/connect` (shells out to git/gh).
- `demo/auth.py` — bearer-token auth that resolves *identity*, not just
  validity: `bearer_token`, `GitHubTokenVerifier` (returns the caller's stable
  GitHub user id via `/user`, cached, fail-safe to `None`), and
  `StaticTokenVerifier` (test double mapping tokens to ids). Enforced only in
  the auth mode.
- `demo/github_oauth.py` — server-side GitHub web-login flow: `authorize_url`
  (identity-only `read:user` scope for the public-repo alpha), `exchange_code`
  (uses the client SECRET, injectable opener), and `OAuthFlow` (single-use
  state/session, TTL). `begin(mode, redirect_target=None)` tags each login
  `app` (Mac app), `web` (browser), or Brick D's `extension` (a browser
  extension's `chrome.identity.launchWebAuthFlow`, which needs its own
  `redirect_target` -- validated by `_CHROMIUMAPP_REDIRECT` against
  `https://<32 a-p chars>.chromiumapp.org/` so a caller can never turn this
  into an open redirect to an arbitrary URL); `complete` returns `(session_id,
  mode, redirect_target)` so the callback knows where to send the user. The
  secret lives only here, never in the app or extension.
- `demo/server.py` — stdlib `http.server` over a `LibraryRegistry`: `make_handler`
  (loopback Host/Origin guard, 64KB body cap, per-request identity resolution,
  optional GitHub bearer on `/ask`+`/connect`+`/disconnect`, per-identity rate
  limits via `demo/ratelimit.py`, web-login endpoints), `resolve_provenance`,
  `serve` (ThreadingHTTPServer, loads `.env`, builds the registry from
  `ICARUS_STORAGE_ROOT`). `GET /`,`/health`,`/status`,`/auth/github/callback`;
  `POST /ask`,`/connect` (checks `evals.github_access.repo_info` with the
  caller's token and refuses private repos before ingest; `sync_connect`/`ICARUS_SYNC_CONNECT`
  makes it block on `connect_sync` and return its final status directly instead
  of backgrounding it and returning 202 -- needed on request-scoped-CPU hosts
  like Cloud Run/Azure Container Apps, where a background thread's embed work
  after the response returns isn't reliably resourced; `connect_sync` itself is
  unchanged, this only changes who waits for it),`/disconnect`,`/auth/github/begin`
  (reads a `mode`: `web` → callback returns to `/?session=`, `app` →
  `icarus://`, Brick D's `extension` → the caller-supplied, validated
  `redirect_target`; a bad/missing `redirect_target` for `extension` mode is a
  clean 400, not a crash),`/auth/github/redeem`. `POST /explain` (Brick D, `_handle_explain`)
  — `{repo, path, start, end[, question]}` for a GitHub line selection; shares
  `/ask`'s billed-writer rate limit; refuses (409) unless `repo` matches the
  caller's currently connected repo, never silently answering about or
  switching to a different one; calls `lib.current_pipeline().explain(...)`
  and reuses `build_payload` unchanged (identical response shape to `/ask`).
- `demo/index.html` — the single-page UI: question box, cited-answer card, the
  honest-unknown hero, an `owner/repo` connect control, and **browser GitHub
  sign-in** (web-mode OAuth → session redeemed for a token held in
  sessionStorage, sent as `Authorization: Bearer` on `/ask`+`/connect`+`/status`),
  a public-alpha badge, and vanilla
  `fetch`. This is the typed **web staging link** (no voice/overlay — native only).
- `demo/test_links.py` — `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — `build_payload` for answer and honest-unknown shapes.
- `demo/test_auth.py` — the bearer helpers: `bearer_token` parsing, the verifier's
  token→id mapping, cache hit/expiry, and network-error fail-safe (offline).
- `demo/test_github_oauth.py` — the web-login flow: authorize-url building
  (including the identity-only scope), offline token exchange, and the single-use
  state/session lifecycle. Brick D's `extension` mode: the redirect_target
  carried through `begin`→`complete`, and the open-redirect guard rejecting a
  missing/non-chromiumapp.org/malformed-id target.
- `demo/test_library.py` — the `Library`: default repo, cache-hit vs. ingest,
  single-flight concurrent connect, generic (non-leaking) ingest errors, and
  private connect (token/private routing, refusal without the paid writer,
  token never in status output). T6 staleness: `_resolve` stays availability-
  only regardless of a stale corpus (the registry's tokenless eviction-replay
  safety invariant -- proven by deliberately re-merging staleness into
  `_resolve` live and confirming the guard fails), `_corpus_is_stale`'s scheme
  comparison (including a pre-T6 corpus with no "chunking" field at all), and
  `connect_sync`'s real refresh behavior: a stale public repo refreshes
  automatically, a stale private repo refreshes when a token is present, a
  stale private repo WITHOUT a token is served as-is rather than attempting a
  doomed re-ingest, and the committed default repo is never touched
  regardless of the flag.
- `demo/test_registry.py` — the registry: per-user isolation, per-user storage
  paths, the shared default pipeline built once, hostile-id rejection, LRU
  eviction, and disconnect deleting only that user's storage.
- `demo/test_ratelimit.py` — the limiter: allows up to the limit, blocks past
  it, a different key is unaffected, and the window sliding restores access.
- `demo/test_server.py` — routing against a stub registry, plus the Origin guard
  (403), body cap (413), bearer-auth gate (401), per-request identity, rate
  limiting (429), `/disconnect`, concurrency, and index.html smoke checks.
  `/explain` (Brick D): cited answer with a line-ranged citation URL, honest
  unknown for uncovered locations, optional-question pass-through, wrong-repo
  refusal (409, never reaches the pipeline), and input validation (missing
  fields, non-integer/non-positive/inverted start-end, blank path).
- `demo/test_isolation.py` — cross-user isolation proven at the HTTP boundary: a
  real `LibraryRegistry` behind a real server with two authenticated identities
  — connect, storage, disconnect, and provenance all stay disjoint.
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline; skips
  without a key or the corpus.
- `demo/test_semantic_wiring.py` — proves Brick C's semantic retrieval is wired
  into the SERVING pipeline: the demo builds a `HybridRetriever` when the embedder
  is present, falls back to `LexicalRetriever` when it isn't, and a second build
  over the same corpus dir embeds zero chunks (cache hit). Live tests self-skip
  without fastembed/the corpus.

## extension/ (Brick D — Chrome browser extension, Manifest V3, no build step)
- `extension/manifest.json` — MV3 manifest: `identity`+`storage` permissions,
  host permissions for `github.com` and the local brain (`127.0.0.1:8000` --
  TODO once hosted), a content script matching `github.com/*/*/blob/*` pages
  loading `lib.js` then `content.js`, a background service worker
  (`background.js`), and a toolbar popup (`popup.html`).
- `extension/lib.js` — the pure, DOM-free parse/gate functions
  `parseLineHash`, `parseBlobPath`, `isConnectedRepo` -- dual CommonJS/browser-
  global export so the SAME file runs unmodified as a plain `<script>` in the
  extension and under `node --test` (no bundler, no npm install).
- `extension/render.js` — Brick D4's pure HTML-string builders
  (`renderAnswerHtml`, `renderUnknownHtml`, `renderLoadingHtml`,
  `renderSignedOutHtml`, `renderErrorHtml`), same dual-export pattern as
  `lib.js`. Mirrors `demo/index.html`'s voice/structure (citation chips by
  source type, "No one wrote this down.") and labels the public alpha without
  paid-writer or training claims.
- `extension/content.js` — the on-page logic: gates on the caller's connected
  repo (`GET /status`, cached per repo not per line-selection), listens for a real line selection via
  the Navigation API's `navigate` event (live-verified: covers both SPA
  file-to-file navigation and hash-only line changes; GitHub's `popstate`/
  Turbo/pjax events do NOT fire for this -- checked live, none did), and
  drives a real state machine (trigger -> loading -> answer/unknown/error/
  signed-out) via `showTrigger`/`showPanel`, with a close button. The trigger
  is a bar (`showTrigger`), not a bare button: a line selection also renders
  an optional question input alongside "Ask Icarus" -- empty submits
  `/explain`'s default "what does this code do, and why is it here?"; typed
  text is forwarded as `/explain`'s optional `question` field (server-side
  support pre-existed; this just exposes it). All brain calls
  (`fetchConnectedRepoStatus`, `askIcarus`) go through `chrome.runtime.
  sendMessage` to `background.js`, never a direct `fetch()` here -- a content
  script's fetch runs inside the GitHub page's own document, so it's bound by
  the page's CORS policy and, since github.com is https and the brain can be
  a loopback address, Chrome's Private Network Access preflight too; our
  brain has no CORS/OPTIONS handling, so a direct fetch failed with a bare
  "Failed to fetch" before any response arrived, silently -- live-verified
  the first time the extension was actually exercised end to end (D5), fixed
  by relaying every brain call through the background service worker
  instead, which isn't a "document" and isn't subject to either restriction.
  Two earlier live-testing bugs, still fixed: the stylesheet was injected
  lazily only inside `showPanel` (the first trigger a user ever saw was
  completely unstyled), and an inline `panel.style.position="relative"`
  silently overrode the CSS class's `position:fixed` (the panel rendered
  off-screen, `left:-24px` in a 1440px viewport) -- both confirmed live via
  `getBoundingClientRect()`/`getComputedStyle`, not guessed from a screenshot.
- `extension/background.js` — MV3 service worker: the GitHub sign-in flow via
  `chrome.identity.launchWebAuthFlow`, using `demo/github_oauth.py`'s new
  `extension` OAuth mode; stores the token in `chrome.storage.local`. Also the
  ONLY place that fetches the brain (`fetchStatus`, `fetchExplain`, plus
  `signIn`'s own calls) -- a service worker isn't bound by the CORS/Private
  Network Access restrictions that block a content script's direct fetch (see
  `content.js`); `content.js` relays every brain call here via
  `chrome.runtime.onMessage`/`sendMessage` instead of fetching directly.
- `extension/popup.html` / `extension/popup.js` — a minimal "Sign in with
  GitHub" toolbar popup (a real user gesture is required to open the sign-in
  flow -- it can never happen silently).
- `extension/lib.test.js` — `node --test` (Node's built-in test runner, zero
  npm installs, mirrors the Python side's stdlib-only ethos): 13 tests over
  `parseLineHash`/`parseBlobPath`/`isConnectedRepo`, including the D0-derived
  edge cases (inverted range, PR-diff-view path, case-insensitive repo match).
- `extension/render.test.js` — 16 tests over `render.js`: HTML-escaping,
  every citation shape (with/without a URL), the private/public repo label,
  and the guard against reintroducing the "paid writer"/"trained" claim.
  Run both: `node --test extension/*.test.js`.

## mac/ (the macOS app — SwiftPM, SwiftUI + AppKit)
- `mac/.gitignore` — ignores SwiftPM build artifacts and the assembled `.app`.
- `mac/Icarus/Package.swift` — SwiftPM manifest: `IcarusKit` (testable logic) +
  `Icarus` (the app), dependency on KeyboardShortcuts.
- `mac/Icarus/Package.resolved` — pinned dependency versions.
- `mac/Icarus/Icarus-Info.plist` — bundle Info.plist (mic + speech usage strings)
  assembled into `Icarus.app` for TCC.
- `mac/Icarus/scripts/bundle.sh` — wraps the SwiftPM binary into an ad-hoc-signed
  `Icarus.app` (required for microphone access).
- `mac/Icarus/scripts/package_dmg.sh` — builds a shareable `Icarus.dmg`: runs
  `bundle.sh`, stamps `ICARUS_BRAIN_URL` into the bundle Info.plist (re-signs),
  and lays out a drag-to-Applications DMG with a first-open `READ ME FIRST.txt`.

### mac/Icarus/Sources/IcarusKit (UI-free, unit-tested)
- `Models.swift` — the brain's JSON contract: `Verdict`, `Citation`,
  `AskResponse`, `RepoStatus`, and
  `IndexCounts` (real `/status` counts).
- `BrainClient.swift` — the HTTP client to the brain (`/ask`,`/connect`,
  `/disconnect`,`/status`,`/auth/github/begin`,`/auth/github/redeem`); attaches
  an `Authorization: Bearer` from a shared token; injectable URLSession.
- `SavedConnection.swift` — persists the last-connected repo
  (injectable UserDefaults) and the pure `isLost` check behind the
  eviction/restart lost-connection banner.
- `BrainEndpoint.swift` — resolves the brain URL from the bundle's
  `ICARUS_BRAIN_URL` Info.plist key (stamped at package time → hosted brain),
  falling back to `127.0.0.1:8000` for dev; pure + unit-tested.
- `WebAuth.swift` — the `WebAuthenticating` protocol (abstracts the auth sheet) +
  `parseCallbackSession` (pull the one-time session id from the `icarus://` URL).
- `TokenStore.swift` — the token-store protocol + an in-memory test double (the
  real store is `KeychainTokenStore`).
- `SpeechRecognizer.swift` — streaming speech-to-text protocol + a stub.
- `VoiceModel.swift` — `@Observable` push-to-talk orchestrator: live
  `partialTranscript`, silence → empty → not emitted.
- `AskHistory.swift` — the real in-session ask record (most-recent-first,
  `unknowns` filter, `citedRate` nil until the first ask); powers the shell.
- `ShellNav.swift` — `ShellSurface`, the five sidebar surfaces + their titles.

### mac/Icarus/Sources/Icarus (the executable app)
- `IcarusApp.swift` — `@main`; no window, delegates to `AppDelegate`.
- `AppConfig.swift` — app-wide config; `brainBaseURL` resolves the brain via
  `BrainEndpoint` over `Bundle.main` (hosted in a shipped build, local otherwise).
- `AppDelegate.swift` — app wiring: activation policy, menu-bar item, hotkey,
  push-to-talk, shared models (auth/connect/voice/history/status), and the
  primary shell window (setup is folded into its Home gate).
- `OverlayController.swift` — owns the ⌘⇧I ask overlay + ask/voice/speak wiring;
  records each ask into the shared `AskHistory`.
- `FloatingPanel.swift` — a translucent, non-activating, chromeless `NSPanel` that
  floats above other apps (hidden transparent title bar).
- `OverlayView.swift` — the overlay UI: question, cited answer, honest unknown.
- `AskModel.swift` / `AuthModel.swift` / `ConnectModel.swift` — `@Observable`
  state for asking, GitHub web login (Keychain-persisted token), and repo connect
  (public alpha; saves/resumes the connection via `SavedConnection`,
  `disconnect()` deletes server-side data, `.lost` when the server drops the
  session). Shared via `AppDelegate`.
- `AppleWebAuth.swift` — the real `ASWebAuthenticationSession` sheet (GitHub login,
  captures the `icarus://` callback); ephemeral browser session so Sign out → pick
  another GitHub account. Completion handler is non-isolated (fires off-main).
- `KeychainTokenStore.swift` — the real `TokenStore`: the GitHub token in the login
  Keychain (`WhenUnlocked`), so sign-in persists across launches; Sign out deletes it.
- `IconArt.swift` — the Signal Spine app icon + menu-bar glyph in Core Graphics.
- `IconExport.swift` — headless `--render-iconset` renderer (invoked by `bundle.sh`)
  that bakes `IconArt.appIcon()` into a static `AppIcon.icns` so the Dock/Finder/DMG
  aren't a blank tile before first launch; `Main` (in `IcarusApp.swift`) intercepts it.
- `Theme.swift` — the "Quiet Native Memory v2" tokens + shared views
  (`MonoLabel`, `CitationChip`, `PrimaryButton`, `FlowLayout`).
- `AppleSpeechRecognizer.swift` — `SFSpeechRecognizer` + `AVAudioEngine`; uses
  on-device recognition when available and Apple's service otherwise.
- `PushToTalkMonitor.swift` — hold Right Option (⌥) to talk via a global
  `.flagsChanged` monitor.
- `Speaker.swift` — `AVSpeechSynthesizer`; speaks the answer and the honest
  unknown, with barge-in.

### mac/Icarus/Sources/Icarus/Shell (the full app shell — the primary window)
- `ShellView.swift` — sidebar + content router across the five surfaces (passes
  auth/connect through to Home for its setup gate).
- `SidebarView.swift` — brand mark, nav rows, the real connected-repo footer
  (with the public-alpha badge), Disconnect
  repo + Sign out controls. Real macOS traffic-lights float over its top; no
  decorative dupes.
- `HomeView.swift` — until a repo is connected, the `SetupView` gate; once ready,
  the dashboard: hero (real ⌥ trigger), metrics (real `/status` counts + session
  cited-rate), recent asks, and the proof drawer — all real/honest data.
- `SetupView.swift` — the in-shell setup gate (Sign in with GitHub → connect a
  public repo), driving the shared `AuthModel`/`ConnectModel`; hosts
  the lost-connection banner (server restart/eviction → explicit Reconnect,
  never a silent fallback to the public default). Replaces the old separate
  onboarding window.
- `ShellSurfaces.swift` — Decision history, Unknowns, Privacy boundary (true
  claims), and Ask-by-voice surfaces, with honest empty states.
- `ShellComponents.swift` — shared shell views (`MarkView`, `NavRow`,
  `VerdictPill`, `HistoryRow`, `ShellCard`).
- `StatusModel.swift` — polls `/status` for the real repo + index counts.
- `MainWindowController.swift` — hosts the shell as the primary window with a
  chromeless (transparent, full-size-content) title bar.

### mac/Icarus/Tests/IcarusKitTests
- `WebAuthTests.swift` — `parseCallbackSession` pulls the session id from the
  `icarus://` callback; nil on a malformed/session-less URL.
- `ModelsTests.swift` — decoding the brain's JSON, including real `IndexCounts`
  and the `private` flag (absent → public default).
- `TokenStoreTests.swift` — the in-memory token store's save/load/delete.
- `VoiceModelTests.swift` — push-to-talk states; silence → no question.
- `AskHistoryTests.swift` — record order, unknowns filter, cited-rate (nil first).
- `BrainClientTests.swift` — the bearer token is sent when present, omitted when
  absent; `/disconnect` POSTs with the bearer and decodes the fresh snapshot
  (URLProtocol stub).
- `ShellNavTests.swift` — the five surfaces' order, titles, and stable ids.
- `BrainEndpointTests.swift` — `BrainEndpoint.resolve` uses a valid hosted URL,
  falls back on missing/empty/invalid, and honors an explicit fallback.
- `SavedConnectionTests.swift` — the saved-connection store round-trip/clear and
  every branch of the `isLost` downgrade check (ready-elsewhere = lost;
  indexing/error/no-save = not lost; case-insensitive repo match).

## .claude/agents/ and .codex/agents/
- `.claude/agents/opus-architect.md` — the opus-architect agent (principal
  architect / adversarial reviewer).
- `.claude/agents/sonnet-test-writer.md` — the sonnet-test-writer agent
  (adversarial test writer / bounded implementer).
- `.codex/agents/opus-architect.toml` / `.codex/agents/sonnet-test-writer.toml` —
  the same two agents defined for the Codex tooling.
