# Brick 7 — Point Icarus at any (public) repo, in one command — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Each task is red→green: a failing test first, then the smallest code that turns it green. **Never weaken a test or the honesty gates. Do NOT change the committed `simonw/llm` corpus or `phase1_questions.json` — the eval harness depends on them being frozen.** Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work in an isolated worktree per [CLAUDE.md](../../CLAUDE.md).

**Goal:** Make `python3 -m evals.ingest --repo OWNER/REPO` build a corpus for *any public repo* and have the web demo automatically describe and link to *that* repo — without hand-editing two files and without breaking the frozen eval corpus.

**Why:** today running on another repo means editing hardcoded constants in `evals/ingest.py` **and** the `corpus` block of `evals/phase1_questions.json` (the demo reads repo/commit from there to build citation links), plus the code glob is hardwired to `llm/**`. Three coupled edits, easy to get wrong. This brick removes that friction.

**This is "source adapter v0," not the full adapter.** Still `gh` + `git` (your local auth), still **public repos only** (free-model trust boundary), still **Python-only** for code chunks. PAT auth, private repos, incremental sync, and non-Python languages stay deferred.

**Tech Stack:** Python 3 stdlib only. No new dependency. `gh` CLI + `git` for ingest (unchanged). `OPENROUTER_API_KEY` only for the demo at runtime.

---

## The core idea (one decision, locked)

The corpus becomes **self-describing**: ingest writes a tiny `evals/corpus/meta.json` next to `chunks.jsonl` recording *which repo/commit/code-dir produced it*. The demo reads repo/commit from that meta (not from the labelled set), so the corpus and its citation links always agree, whatever repo you ingested. The eval board keeps using `phase1_questions.json` and is untouched.

**Reproducibility guard:** running `python3 -m evals.ingest` with **no args** still targets `simonw/llm` @ the pinned commit with `--code-dir llm` exactly as today. Overrides are opt-in. (Note: `gh pr list` fetches *current* PRs, so re-ingesting is never bit-identical — the committed `chunks.jsonl` remains the source of truth; this brick does not regenerate it.)

---

## Task 0 — Prerequisite (human)
`gh auth status` is logged in; `git` available. For the demo run: `OPENROUTER_API_KEY` exported. Public repos only.

---

### Task 1 — Corpus metadata (self-describing corpus; offline)

**Files:** Create `evals/corpus_meta.py`, `evals/test_corpus_meta.py`, and a committed `evals/corpus/meta.json` for the existing corpus.

- `write_meta(path, repo, commit, code_dir, counts: dict) -> None` — write a JSON
  object `{repo, commit, code_dir, counts, generated_at}` (ISO-8601 UTC).
- `load_meta(path) -> dict | None` — read it back; return None if the file is absent.

**Step 1 (RED):** `test_corpus_meta.py` — write to a temp path then load it back and
assert the fields round-trip; `load_meta(missing_path)` returns None.

**Step 2 (GREEN):** implement the two functions (stdlib `json`, `datetime`).

**Step 3:** hand-write `evals/corpus/meta.json` describing the *existing* committed
corpus so the demo has provenance without re-ingesting:
`{"repo":"simonw/llm","commit":"94769b8b076cde9392059d76bd766453cf900180","code_dir":"llm", …}`.

**Commit:** `Add self-describing corpus metadata (meta.json) + read/write helpers`.

---

### Task 2 — Parameterize ingest (`--repo / --commit / --code-dir`; writes meta)

**Files:** Modify `evals/ingest.py`; create `evals/test_ingest_args.py`.

- Factor a **pure** `parse_args(argv) -> Namespace` with:
  - `--repo` (default `simonw/llm`),
  - `--commit` (default `None` → resolve the default-branch HEAD via
    `git ls-remote` at run time; the pinned SHA stays the default *only* for the
    default repo so no-arg runs are unchanged),
  - `--code-dir` (default `llm`) — the subtree to glob for `*.py`.
- Generalize `fetch_code(repo, commit, code_dir)` to glob `Path(clone, code_dir).rglob("*.py")`.
- `fetch_prs(repo)` / `fetch_issues(repo, ids)` take the repo.
- `main(argv=None)` wires args → fetches → writes `chunks.jsonl` **and**
  `write_meta(..., repo, commit, code_dir, counts)`.

**Step 1 (RED):** `test_ingest_args.py` (pure, no network): no args → repo
`simonw/llm`, code_dir `llm`; `--repo a/b --code-dir src` → those values;
unknown/typo'd commit handling. (The `gh`/`git` fetches stay tool-verified by the
real run in Task 4 — they are network tools, not unit-tested, same as today.)

**Step 2 (GREEN):** implement; keep the network functions thin.

**Commit:** `Parameterize ingest by repo/commit/code-dir; write corpus meta`.

---

### Task 3 — Demo describes whatever corpus is loaded (offline)

**Files:** Modify `evals/.../` — actually `demo/server.py`; extend `demo/test_server.py`.

- In `serve()`, resolve repo/commit from `load_meta(CORPUS_META)` first, falling
  back to `phase1_questions.json`'s `corpus` block if meta is absent (back-compat).
- Factor a tiny `resolve_provenance(meta_path, questions_path) -> (repo, commit)`
  so it's unit-testable without the network.

**Step 1 (RED):** test `resolve_provenance`: meta present → its repo/commit; meta
absent → the questions-file fallback.

**Step 2 (GREEN):** implement; `make_handler` already takes repo/commit, so only
`serve()` wiring changes. Citation links now follow the ingested repo automatically.

**Commit:** `Demo reads repo/commit from corpus meta (links follow the ingested repo)`.

---

### Task 4 — Prove it on a second public repo (manual/skippable; network + quota)

**Files:** add run notes to `CLAUDE.md` (in Task 5); optional skippable
`evals/test_ingest_smoke.py` that, when `RUN_INGEST_SMOKE=1`, ingests a *tiny*
public repo into a temp dir and asserts `chunks.jsonl` + `meta.json` were written
with the right repo. (Default-skips so CI/offline never hits the network.)

**Manual proof (record the result):**
```
python3 -m evals.ingest --repo OWNER/SMALL_PUBLIC_REPO --code-dir <pkg-or-.>
OPENROUTER_API_KEY=… python3 -m demo.server      # open http://127.0.0.1:8000
```
Ask a "why" about that repo → expect a cited answer whose link points at
**OWNER/SMALL_PUBLIC_REPO** (proving meta drives the links), and an unrecorded
question → the honest unknown. **Back up `evals/corpus/chunks.jsonl` +
`meta.json` first** (ingest overwrites them; restore to keep the simonw/llm demo).

**Commit:** `Add skippable ingest smoke test`.

---

### Task 5 — Docs + indexes

`CLAUDE.md`: add the "run on any public repo" recipe (`ingest --repo …` → restore
note → `demo.server`) and the honest limits (public-only, Python-only code, no
eval net on new repos). Regenerate `general_index.md` + `detailed_index.md` for
`corpus_meta.py`, `meta.json`, the new ingest flags, and the demo change.

**Commit:** `Document run-on-any-repo; regenerate indexes`.

---

## Brick 7 — Definition of done
- `python3 -m evals.ingest --repo OWNER/REPO [--commit SHA] [--code-dir DIR]`
  builds `chunks.jsonl` + `meta.json` for that repo.
- `python3 -m demo.server` then serves answers whose **citation links point at the
  ingested repo**, with no edit to `phase1_questions.json`.
- No-arg `ingest` still targets the pinned `simonw/llm` corpus; the eval board and
  the frozen labelled set are unchanged; offline suite green.
- No new dependencies.

## Honest limits (unchanged by this brick — call them out)
- **Public repos only** (free-model trust boundary); private repos need paid/private models + real auth (the deferred PAT adapter).
- **Python-only** code chunks (`*.py`); other languages get PRs/issues but no code.
- **No eval net on a new repo** — the deterministic honesty gate still can't bluff, but answer/citation *quality* is unmeasured without a labelled set for that repo.
- Free quota 50/day; one writer call per question.
