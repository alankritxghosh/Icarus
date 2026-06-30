# Brick 5 — Minimal web demo (question → answer → citations) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Each task is red→green: a failing test first, then the smallest code that turns it green. **Never weaken a test or the honesty gates to pass. This brick is PACKAGING ONLY — it must not change the gate, retriever, writer, grader, or labelled set.** Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work in an isolated worktree per [CLAUDE.md](../../CLAUDE.md).

**Goal:** A tiny local web page where you type a question about `simonw/llm` and get back either a **cited answer** or an **honest "no one wrote this down"** — driven by the existing `GatedPipeline`, with citations rendered as clickable links to the exact source at the pinned commit. This is the Phase-1 face over the proven brain; the honest "I don't know" is the hero state, shown as a confident, transparent result, never an error.

**Architecture:** `browser → GET / (static HTML+JS) → POST /ask {question} → server runs GatedPipeline.answer(question) → JSON {verdict, answer, citations:[{ref,url}], searched:[refs]} → page renders an answer card with citation links, OR the honest-unknown card listing what it searched.` The server is Python **stdlib `http.server`** (no web framework). The brain is untouched: the demo imports and calls it.

**Tech Stack:** Python 3 **stdlib only** — `http.server` for the server, a single static HTML file with vanilla `fetch` for the page. **No new dependency** (no Flask/FastAPI/React). Runtime needs `OPENROUTER_API_KEY` (the writer) and the committed corpus; public repos only while on free models.

---

## Task 0 — Prerequisite (human)

`OPENROUTER_API_KEY` exported (the demo calls the real writer at request time) and the corpus present (`evals/corpus/chunks.jsonl`). Verify (no secret printed): `python3 -c "import os;print('key set:', bool(os.environ.get('OPENROUTER_API_KEY')))"`. Tasks 1–4 are offline (stub pipeline); Task 5 is the live run.

---

## Decisions (recommend; confirm at review)

1. **Zero new deps — stdlib `http.server` + one static HTML page.** On-brand with "stdlib only as long as possible." Recommended.
2. **Lives in a new top-level `demo/` package**, separate from `evals/` (a demo is not an eval). Files: `demo/server.py`, `demo/links.py`, `demo/payload.py`, `demo/index.html`.
3. **Citations are clickable GitHub links at the pinned commit.** `pr:N → /pull/N`, `issue:N → /issues/N`, `code:path → /blob/<commit>/path`. Grounds the cite-or-unknown promise visibly.
4. **Honest-unknown is a first-class "hero" UI state**, not an error: a calm "No one wrote this down" card that also lists *what it searched* (the retrieved refs) so the abstention is transparent and auditable to the viewer.
5. **The judge does NOT run in the UI.** Answer-correctness is an eval-time quality dial (Brick 4), not part of the live answer path. The demo path is exactly retrieve → write → gate.

---

## Where we are (do not re-derive)

- Bricks 0–2, 4 merged. `evals/pipeline.py::GatedPipeline(retriever, chunks, provider)` returns `Result(verdict, answer, citations, retrieved)`. `evals/retriever.py::LexicalRetriever`, `evals/provider.py::OpenRouterProvider`, `evals/corpus.py::load_chunks`. Corpus pinned to `simonw/llm` @ `94769b8b076cde9392059d76bd766453cf900180`.
- The brain is already proven by the eval board; this brick adds no capability, only a face. Its tests target **packaging correctness** (payload shape, link mapping, routing, the honest-unknown rendering), run offline with a stub pipeline.

## Scope

In scope: a stdlib HTTP server, a question→Result→JSON payload builder, ref→URL mapping, the static page, run instructions, and a skippable live smoke test. Out of scope: any change to retrieval/gate/writer/grader; authentication; multi-repo; persistence; styling beyond clean-and-minimal; the translucent overlay (that's the Mac app, Phase 3).

---

### Task 1 — Citation ref → source URL (pure function; offline)

**Files:** Create `demo/links.py`, `demo/test_links.py`.

`ref_to_url(ref: str, repo: str, commit: str) -> str | None` maps a normalized `source:ref`:
- `pr:1435`   → `https://github.com/{repo}/pull/1435`
- `issue:506` → `https://github.com/{repo}/issues/506`
- `code:llm/models.py` → `https://github.com/{repo}/blob/{commit}/llm/models.py`
- unknown source → `None` (rendered as plain text, never a broken link).

**Tests:** each source maps correctly; an unknown prefix returns None; a ref with extra colons (`code:` paths) splits on the first colon only.

**Commit:** `Add citation ref -> GitHub source-link mapping`.

---

### Task 2 — Answer payload builder (pure function; offline)

**Files:** Create `demo/payload.py`, `demo/test_payload.py`.

`build_payload(result, repo, commit) -> dict` turns a `Result` into what the page needs:
```python
{
  "verdict": "answer" | "unknown",
  "answer": "<prose or ''>",
  "citations": [{"ref": "pr:1435", "url": "https://…"}, …],   # only for answers
  "searched": ["pr:1435", "issue:…", …],                       # retrieved refs (transparency)
}
```
For `unknown`, `answer` is empty, `citations` is empty, and `searched` carries the retrieved refs so the honest abstention shows what was looked at.

**Tests** (with hand-built `Result`s, no network): an answered Result yields citations each with a URL and the prose; an unknown Result yields empty answer + empty citations + populated `searched`; citations preserve order; a citation whose source has no URL still appears with `url: None`.

**Commit:** `Add question-answer payload builder over Result`.

---

### Task 3 — The stdlib HTTP server (routing; offline-tested with a stub pipeline)

**Files:** Create `demo/server.py`, `demo/test_server.py`.

- `make_handler(pipeline, repo, commit, html_path)` returns a `BaseHTTPRequestHandler` subclass:
  - `GET /` → 200, serves `index.html`.
  - `POST /ask` with JSON `{"question": "…"}` → 200, `build_payload(pipeline.answer(question), …)` as JSON. Empty/missing question → 400.
  - anything else → 404.
- `serve(host, port)` builds the real `GatedPipeline(LexicalRetriever(load_chunks(CORPUS)), chunks, OpenRouterProvider())` and runs `HTTPServer`. Pipeline construction is isolated from the handler so tests inject a stub.
- `python3 -m demo.server` runs it (default `127.0.0.1:8000`).

**Tests** (offline): start an `HTTPServer` on an ephemeral port (port 0) with a **stub pipeline** (returns a fixed answered `Result`, and a fixed unknown `Result`), hit it with stdlib `urllib`:
- `GET /` returns 200 and HTML containing the question input element id;
- `POST /ask` returns 200 and the expected payload JSON (answer + citation urls) for the answered stub; the unknown stub yields the honest-unknown payload;
- missing question → 400; unknown path → 404.

**Commit:** `Add stdlib http.server demo serving /ask over the gated pipeline`.

---

### Task 4 — The page (HTML + vanilla JS; hero "I don't know" state)

**Files:** Create `demo/index.html`; extend `demo/test_server.py` with a light smoke assertion.

One self-contained page: a heading, a question input + Ask button, and a result area. On Ask, `fetch('/ask', {POST, json})`, then render:
- **answer state:** the prose, then a "Citations" list of links (`ref` → its `url`);
- **honest-unknown state (the hero):** a calm card — *"No one wrote this down."* — plus a muted "Searched: <refs>" line so the abstention is transparent.
- a loading state while awaiting the writer; a network-error state.

Keep it minimal and legible (a little CSS, no framework). **Note:** browser JS is verified by the live run (Task 5); the unit test only asserts the served HTML contains the expected element ids/text so the contract with the JS doesn't silently break.

**Commit:** `Add minimal demo page with answer and honest-unknown states`.

---

### Task 5 — Live run + skippable smoke test (real model)

**Files:** Create `demo/test_demo_live.py` (self-skips without key/corpus); update run instructions.

**Step 1 — live smoke test:** with key + corpus, start `serve` on an ephemeral port against the **real** pipeline; `POST /ask` a known-answerable question (assert verdict `answer`, ≥1 citation with a github.com URL) and a known-unrecorded code question (assert verdict `unknown`). Skips without `OPENROUTER_API_KEY`/corpus. (This is a thin end-to-end guard; the brain's correctness is already proven by the eval board.)

**Step 2 — manual hero run (record the result):** `OPENROUTER_API_KEY=… python3 -m demo.server`, open `http://127.0.0.1:8000`, ask:
- an answerable "why" (e.g. q01 about the Responses API) → cited answer with working PR link;
- an unrecorded code question (one of the 4 unanswerable) → the honest "No one wrote this down" card.
Confirm both render correctly. **This is the Brick-6 hero shot in embryo.**

**Commit:** `Add live demo smoke test and run instructions`.

---

### Task 6 — Docs + indexes

Update `CLAUDE.md` (Commands — add `python3 -m demo.server`), regenerate `general_index.md` + `detailed_index.md` for the new `demo/` package.

**Commit:** `Document the web demo; regenerate indexes`.

---

## Brick 5 — Definition of done
- `OPENROUTER_API_KEY=… python3 -m demo.server` serves a page where an answerable question returns a cited answer with working source links, and an unrecorded question returns the honest "no one wrote this down" card listing what it searched.
- Offline suite green; the live smoke test self-skips without the key/corpus.
- **Zero change to `evals/` brain code** (gate, retriever, writer, grader, labelled set untouched) — verified by diff; the only new code is the `demo/` package.
- No new dependencies.

## What remains after this brick (Phase 1)
- Brick 6 — the recordable demo: one cited answer + one honest "I don't know," back to back (the honest refusal is the hero shot). Brick 5's page is the stage; Brick 6 is the take.
- (Brick 3 — embeddings — remains on the shelf, ready if/when paraphrase robustness is needed; see its plan.)
