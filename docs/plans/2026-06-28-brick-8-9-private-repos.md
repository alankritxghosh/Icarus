> **⛔ SHELVED 2026-06-29 — superseded by the Public-Repo MVP decision.** No paid
> APIs and an 8GB Mac mean private repos aren't feasible now (private code can't go
> to free hosted models, and local models are too heavy for 8GB). Current direction:
> free hosted writers on **public repos only** — see
> [2026-06-29-free-hosted-providers.md](2026-06-29-free-hosted-providers.md).
> Revisit this plan when there's a paid zero-retention budget or local-capable
> hardware.

# Bricks 8 & 9 — Private repos, safely (zero-retention model + PAT read) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Red→green per task. **Never weaken a test or the honesty gates. Never commit a private repo's corpus, a token, or any customer code. Never send private code to a model that is not marked private-safe.** Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Isolated worktree per [CLAUDE.md](../../CLAUDE.md).

**This is two bricks, planned together because neither is useful alone:**
- **Brick 8 — a private-safe writer:** swap the free OpenRouter model for a paid model under a **no-training / zero-retention** agreement, behind the same `Provider` interface, with a deterministic **trust interlock** so private code can *only* ever reach a private-safe model.
- **Brick 9 — private-repo read (PAT-first):** read a chosen **private** repo with a scoped Personal Access Token, ingest it into a **local, git-ignored** corpus, and answer over it — gated by the Brick 8 interlock.

**Decisions locked (with Alankrit):** paid zero-retention API · PAT-first auth · local/single-tenant (no hosted cloud yet).

**Depends on:** Brick 7 (parameterized `ingest --repo/--commit/--code-dir` + `meta.json`). Build order: **7 → 8 → 9.**

**Still deferred after this (do NOT build here):** GitHub App/OAuth, multi-repo, multi-language code, live/incremental sync, hosted per-company cloud/multi-tenant, true ephemeral discard-after-request. Those are Bricks 10–13+.

**Tech stack:** Python 3 stdlib only (the paid API is called over `urllib`, like OpenRouter — no new dependency). Secrets from env: `ANTHROPIC_API_KEY` (or chosen provider), `GITHUB_TOKEN`. Never hardcoded, never committed, never logged.

---

## The non-negotiables this plan must preserve

1. **Cite-or-unknown is unchanged.** Brick 8 only swaps *which* model writes; the deterministic honesty gate is untouched. A better model may answer more, but it still can't bluff.
2. **Private code never touches a training model.** New, auditable in code: a private repo + a non-private-safe provider → **hard refusal**, not a silent send. This is a *deterministic interlock*, in the same spirit as the honesty gate.
3. **Private data never enters git.** Private corpora and tokens live only in git-ignored local paths / env. A committed private corpus or token is a build failure.

---

## Task 0 — Prerequisites (HUMAN; before the live parts)
- **Pick the provider and verify its data policy in writing**: the API tier must contractually **not train on inputs/outputs** and ideally offer **zero-retention**. Record the policy link in the plan. (Default candidate: Anthropic Claude API — confirm the zero-retention/no-train terms for your account before sending any private code.)
- Export `ANTHROPIC_API_KEY` (or the chosen provider's key).
- Create a **fine-grained PAT**, **read-only**, scoped to *only* the repo(s) you'll test; export as `GITHUB_TOKEN`. Pick one small private repo to use as the test subject.

Tasks 8.1–8.2 and 9.1–9.2 need **no** network/secret; the live tasks self-skip without keys.

---

# BRICK 8 — A private-safe writer + trust interlock

### Task 8.1 — Paid provider behind the Provider interface (offline-testable)
**Files:** modify `evals/provider.py`; modify `evals/test_provider.py`.

- Add `class AnthropicProvider(Provider)` — calls the Messages API over `urllib`,
  key from `ANTHROPIC_API_KEY`, model configurable (default a current Claude id;
  "the eval harness picks the model"). Returns the text completion.
- Add a class attribute `private_safe: bool` to `Provider` (default `False`);
  `AnthropicProvider.private_safe = True` (under the verified zero-retention
  agreement); `OpenRouterProvider.private_safe = False` (free tier may train);
  `StaticProvider.private_safe = True` (offline, no data leaves).

**RED:** test that `AnthropicProvider().complete(...)` raises `RuntimeError`
without the key (mirrors the OpenRouter test); test the `private_safe` flags are
set as above. **GREEN:** implement over `urllib`. Live call stays in a skippable
test (Task 8.3). **Commit:** `Add zero-retention AnthropicProvider + private_safe trust flag`.

### Task 8.2 — The trust interlock (deterministic; offline)
**Files:** create `evals/trust.py`, `evals/test_trust.py`.

- `assert_safe_for_private(provider) -> None` — raise `PrivateDataError` if
  `not provider.private_safe`. Pure, auditable.
- (Used by Brick 9's private ingest/answer paths.)

**RED:** test it raises for `OpenRouterProvider`, passes for `AnthropicProvider`
and `StaticProvider`. **GREEN:** implement. **Commit:**
`Add deterministic trust interlock (private code -> private-safe provider only)`.

### Task 8.3 — Prove the paid writer on the eval board (live; skippable)
**Files:** create `evals/test_anthropic_eval.py` (skips without `ANTHROPIC_API_KEY`);
allow `evals.run --writer {openrouter,anthropic}`.

Run the **public** labelled board with the paid writer: assert **both gates stay
100%** and citation/answer correctness are ≥ the free-model baseline. Proves the
swap preserves honesty and doesn't regress quality. **Commit:**
`Wire the paid writer into the board behind --writer; gates hold`.

---

# BRICK 9 — Private-repo read (PAT-first), locally

### Task 9.1 — Token + private clone helpers (offline; secret-safe)
**Files:** create `evals/github_auth.py`, `evals/test_github_auth.py`.

- `read_token(env="GITHUB_TOKEN") -> str` — return the token or raise; never log it.
- `private_clone_args(repo, commit, token) -> list[str]` — build `git` args that
  authenticate via **`-c http.extraHeader=Authorization: Bearer <token>`** (NOT a
  token-in-URL, which leaks into `git remote`/process lists). The token is passed
  to the subprocess, never written to disk.

**RED:** test the args carry an Authorization header and **never** put the token
in the clone URL; `read_token` raises when unset and returns the value when set;
the token never appears in any log/`__repr__`. **GREEN:** implement. **Commit:**
`Add PAT token reader + leak-safe private clone args`.

### Task 9.2 — Private corpus stays out of git (offline)
**Files:** modify `.gitignore`; modify `evals/ingest.py` (private output path);
create `evals/test_private_corpus_path.py`.

- Private ingests write to a **git-ignored** path, e.g.
  `evals/corpus/private/<owner>__<repo>/chunks.jsonl` (+ `meta.json`); add
  `evals/corpus/private/` to `.gitignore`.
- `ingest --private` selects that path; the public default path is unchanged.

**RED:** test that the private corpus dir is matched by `.gitignore` (parse it)
and that `--private` routes output there, not into the committed corpus. **GREEN:**
implement. **Commit:** `Route private corpora to a git-ignored local path`.

### Task 9.3 — Wire private ingest + the interlock end to end (live; skippable)
**Files:** modify `evals/ingest.py` (use `read_token` + `private_clone_args` +
authenticated `gh` via `GH_TOKEN` for PRs/issues when `--private`); ensure the
demo/answer path on a private corpus calls `assert_safe_for_private(provider)`
before any model call; create `evals/test_private_ingest_live.py`
(skips unless `RUN_PRIVATE_INGEST=1`, `GITHUB_TOKEN`, `ANTHROPIC_API_KEY`).

- Live test: ingest the chosen small **private** repo into the git-ignored path,
  assert chunks + meta written; then answer a question with the
  `AnthropicProvider` and assert a cited answer; assert that attempting the same
  with `OpenRouterProvider` **raises** `PrivateDataError` (the interlock fires).

**RED→GREEN:** the interlock-refusal half is also unit-testable offline (Task 8.2
covers the core; here assert the ingest/answer path actually calls it). **Commit:**
`Private-repo ingest over PAT, gated by the trust interlock (live-proven)`.

### Task 9.4 — Docs + indexes
`CLAUDE.md`: a "private repo" recipe (`ANTHROPIC_API_KEY` + `GITHUB_TOKEN`
+ `ingest --repo OWNER/PRIVATE --private` → `demo.server`), the data-policy note,
and the loud warnings (never commit private corpora/tokens; public corpus uses the
free writer, private uses the paid one). Regenerate the indexes. **Commit:**
`Document private-repo ingestion; regenerate indexes`.

---

## Definition of done (Bricks 8 & 9)
- Public board with `--writer anthropic`: both honesty gates 100%, quality ≥ free baseline.
- `ingest --repo OWNER/PRIVATE --private` (with `GITHUB_TOKEN`) writes a corpus to a **git-ignored** path; the demo answers questions about that private repo with **cited** answers, using the **paid private-safe** model.
- The interlock provably refuses private code on a non-private-safe provider (test).
- Offline suite green; live tests self-skip without keys; no token/private corpus is committed; the honesty gate is unchanged.
- No new dependencies.

## Honest limits after this (so the demo's scope is clear)
- **One private repo at a time, Python code only**, manual ingest, **persisted locally** (true discard-after-request is later). PRs/issues come via authenticated `gh`; code via authenticated `git`.
- **No hosted cloud** — runs on your machine (single-tenant). Multi-repo, multi-language, live sync, GitHub App, and the per-company cloud are Bricks 10–13+.
- **Cost:** the paid model bills per request (no more free 50/day cap, but real $).
