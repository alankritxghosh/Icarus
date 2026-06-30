# Brick — In-app repo switcher (connect any public repo from the UI) — Plan

> **For Claude:** REQUIRED SUB-SKILL: superpowers:executing-plans. Red→green. Never weaken a test or the honesty gates. Public repos only (free models). Packaging over the existing brain — no gate/retriever/writer change. Co-author trailer on every commit. Worktree/branch per CLAUDE.md.

**Goal:** From the demo UI, type `owner/repo` → Icarus indexes it (background, with an "indexing…" state) → you query *that* repo, citations following it. **One active repo at a time, cached per-repo locally** so switching back is instant and the committed `simonw/llm` demo corpus is never lost.

**Decision:** in-app switcher (Alankrit, 2026-06-29). Not multi-repo-at-once (that's a later brick).

**Architecture (all additive):**
- **Per-repo cache:** `evals/corpus/cache/<owner>__<repo>/chunks.jsonl` + `meta.json`, **git-ignored**. The built-in `simonw/llm` keeps using the committed `evals/corpus/` (the default at startup).
- **Reusable ingest:** `ingest_repo(repo, out_dir, commit=None, code_dir="llm") -> counts` — writes chunks+meta into any dir (refactor of `main`).
- **`Library` (demo state, thread-safe):** holds the active `GatedPipeline` + status (`idle|indexing|ready|error`) + active repo/commit. `connect_sync(repo)`: cache-hit → rebuild pipeline instantly; miss → ingest into cache, then rebuild. A lock guards swaps so `/ask` always sees a consistent pipeline.
- **Server endpoints:** `POST /connect {repo}` → start `connect_sync` in a background thread, return immediately; `GET /status` → state JSON; `POST /ask` → uses `Library`'s *active* pipeline; `GET /` → page.
- **UI:** header control — active-repo label + `owner/repo` input + Connect button; on submit POST `/connect`, poll `/status` until `ready`/`error`, show the indexing state, update the active-repo label.

## Tasks
1. **`ingest_repo` helper** — refactor `evals/ingest.py` so `main` calls `ingest_repo(repo, out_dir, commit, code_dir)`; the helper fetches + writes `chunks.jsonl`/`meta.json` to `out_dir`, returns counts. Test offline by monkeypatching `fetch_prs/fetch_issues/fetch_code` to fixed chunks → assert files written, counts + meta correct.
2. **`demo/library.py` — `Library`** — cache-path resolver, `build_pipeline(corpus_dir)`, `connect_sync(repo, ingest_fn=ingest_repo)` with cache-hit-instant / miss-ingest, status state machine, lock. Tests offline with a fake `ingest_fn` + temp cache + a pre-seeded cache dir (instant switch), and an ingest-raises path → `error` status; the committed `simonw/llm` resolves to the default corpus.
3. **Server wiring** — `make_handler` reads the active pipeline from a `Library`; add `POST /connect` (spawns thread) + `GET /status`; `serve()` builds the `Library` (default = committed corpus). Tests with a stub `Library`/ingest: `/connect` returns, `/status` transitions, `/ask` uses the active pipeline, bad repo → 400.
4. **UI** — add the connect control + status polling to `demo/index.html`; smoke-assert the new hooks (`id="repo"`, `/connect`, `/status`) plus the existing ones.
5. **gitignore + docs** — add `evals/corpus/cache/` to `.gitignore`; CLAUDE.md note; regenerate indexes.
6. **Live proof** — from the UI, connect a small public repo (e.g. `simonw/json-flatten`), ask a question, see a cited answer whose links point at *that* repo; switch back to `simonw/llm` instantly from cache.

## Definition of done
- UI: type `owner/repo` → indexing state → query that repo; citations follow it; switching back to `simonw/llm` is instant.
- Cache is git-ignored; committed `simonw/llm` corpus untouched; honesty gate/grader unchanged; offline suite green; no new deps.

## Honest limits
- One active repo at a time (no cross-repo answers yet). Public only. Python-only code chunks. Indexing a big repo takes up to a minute (hence the background state). First connect to a repo pays ingest cost; later switches hit cache.
