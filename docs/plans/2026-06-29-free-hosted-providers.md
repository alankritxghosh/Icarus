# Brick — Free hosted providers (Gemini + Groq), replacing the 50/day writer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Red→green per task. **Never weaken a test or the honesty gates.** Public repos only (these free tiers may train on inputs — fine for public code, never private). Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Isolated worktree per [CLAUDE.md](../../CLAUDE.md).

**Decision context:** Public-Repo MVP on free hosted models (Alankrit, 2026-06-29). No paid APIs; 8GB Mac so no big local model. Private-repo reading is intentionally out of scope (would require local or paid models). The paid private-repo plan ([2026-06-28-brick-8-9-private-repos.md](2026-06-28-brick-8-9-private-repos.md)) is **shelved**.

**Goal:** Add two free hosted writers — **Gemini 2.5 Flash** (~1,500 req/day) and **Groq** (Llama 3.3 70B, fast) — behind the existing `Provider` interface, and make them the default writer + judge so the board and demo stop hitting OpenRouter's 50/day cap and give better answers. **Judge stays a different model/provider than the writer** (no self-grading). Honesty gate unchanged.

**Tech stack:** Python 3 stdlib only — both APIs called over `urllib` (Groq is OpenAI-compatible; Gemini is a simple REST endpoint). No new dependency. Keys from env: `GEMINI_API_KEY`, `GROQ_API_KEY` — never hardcoded/committed.

---

## Task 0 — Prerequisite (HUMAN; free, no credit card)
- **Gemini:** create a key at Google AI Studio (ai.google.dev) → export `GEMINI_API_KEY`.
- **Groq:** create a key at console.groq.com → export `GROQ_API_KEY`.
- Verify (no secret printed): `python3 -c "import os;print('gemini',bool(os.environ.get('GEMINI_API_KEY')),'groq',bool(os.environ.get('GROQ_API_KEY')))"`.

Tasks 1–3 are offline (test double + pure parse helpers); Task 4 self-skips without keys.

---

### Task 1 — GroqProvider (OpenAI-compatible; offline-testable)
**Files:** modify `evals/provider.py`; modify `evals/test_provider.py`.

Groq's endpoint is OpenAI-compatible — same shape as OpenRouter. To avoid
duplication, factor a small module helper `_openai_chat(url, key, model, prompt,
timeout) -> str` and have both `GroqProvider` and `OpenRouterProvider` use it
(OpenRouter's existing behavior/tests must stay green).

- `class GroqProvider(Provider)` — URL `https://api.groq.com/openai/v1/chat/completions`,
  key `GROQ_API_KEY`, default model `llama-3.3-70b-versatile`. `private_safe = False`.

**RED:** `GroqProvider().complete(...)` raises `RuntimeError` without `GROQ_API_KEY`
(temporarily unset in the test, restore after). **GREEN:** implement via the shared
helper. **Commit:** `Add GroqProvider (OpenAI-compatible) over shared chat helper`.

### Task 2 — GeminiProvider (REST; offline-testable parse)
**Files:** modify `evals/provider.py`; modify `evals/test_provider.py`.

Gemini's response shape differs, so factor a **pure** parser to unit-test offline:
- `_parse_gemini(data: dict) -> str` — return `data["candidates"][0]["content"]["parts"][0]["text"]`.
- `class GeminiProvider(Provider)` — POST
  `…/v1beta/models/{model}:generateContent?key=…`, body
  `{"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0}}`,
  default model `gemini-2.5-flash`, key `GEMINI_API_KEY`, `private_safe = False`.

**RED:** test `_parse_gemini` extracts text from a canned response dict, and that
`GeminiProvider().complete(...)` raises without the key. **GREEN:** implement.
**Commit:** `Add GeminiProvider (REST) with offline-tested response parser`.

### Task 3 — Make them the defaults in the board + demo (offline)
**Files:** modify `evals/run.py`, `demo/server.py`; extend tests as needed.

- `evals/run.py`: `--writer {gemini,groq,openrouter}` (default **gemini**) and
  `--judge {groq,gemini,openrouter}` (default **groq**, i.e. judge ≠ writer). Build
  the chosen providers; keep the existing `--pipeline gated` flow.
- `demo/server.py`: `serve()` builds the writer from `GEMINI_API_KEY` (Gemini) by
  default, falling back to OpenRouter only if Gemini's key is absent (back-compat).
- Offline tests: the selection logic picks the right provider class for each flag
  (pure factory function `make_provider(name)`), no network.

**Commit:** `Default the board and demo to Gemini (writer) + Groq (judge)`.

### Task 4 — Prove on the public board (live; skippable)
**Files:** create `evals/test_free_hosted_eval.py` (skips without both keys + corpus).

Run the **public** labelled board with writer=Gemini, judge=Groq: assert **both
gates 100%**, and citation/answer correctness **≥ the OpenRouter free baseline**
(citation ≥ 33%, answer ≥ 50% — the numbers we recorded). Proves the swap keeps
honesty and doesn't regress quality, with far higher daily limits.

**If quality regresses:** try a different free model id (Groq Llama variants /
Gemini Flash-Lite) — "the eval harness picks the model"; never weaken the
assertions. **Commit:** `Prove Gemini+Groq board: gates hold, quality >= baseline`.

### Task 5 — Docs + indexes
`CLAUDE.md`: update the Commands/stack notes — free writer = Gemini, judge = Groq,
keys `GEMINI_API_KEY`/`GROQ_API_KEY`, public-repos-only rationale. Regenerate
`general_index.md` + `detailed_index.md` for the new providers and flags.
**Commit:** `Document Gemini+Groq free providers; regenerate indexes`.

---

## Definition of done
- `GEMINI_API_KEY=… GROQ_API_KEY=… python3 -m evals.run --pipeline gated` runs on
  Gemini (writer) + Groq (judge): both gates 100%, quality ≥ baseline, **no 50/day
  wall**.
- `python3 -m demo.server` answers on the free hosted writer.
- Offline suite green (live test self-skips); OpenRouter path still works; honesty
  gate, grader, and labelled set unchanged. No new dependencies.

## Out of scope (so the MVP line is clear)
- Private repos (needs local/paid — shelved). Embeddings (Brick 3, shelved).
- This is the brain's model layer only. UI redesign, the macOS app, and voice are
  the subsequent MVP bricks; this unblocks them with a reliable free writer.
