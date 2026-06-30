# Icarus — Session Handoff (2026-06-29)

Read this first in the next session. It captures the *current* state, the
operating constraints, what shipped, what's planned/shelved, and what's next.
Pair it with `CLAUDE.md`, `general_index.md`, and the memory index.

---

## 1. TL;DR — where we are
The **brain is done and proven**, and there's a **working local web demo** with an
**in-app repo switcher**. Everything runs on **free hosted models** and **public
repos only**. What's left for the MVP demo is the **UI polish**, the **macOS app**,
and **voice** — then record.

Type a question about a public repo → get a **cited answer** or an honest **"No one
wrote this down."** The honesty gate is deterministic (can't bluff). Eval board on
the free stack reads **GREEN**: gates 100%, citation correctness 100%, answer
correctness ~83%.

## 2. What works today
- **Brain pipeline:** ingest (any public repo) → BM25 lexical retrieval → cite-or-abstain prompt → free hosted writer → **deterministic honesty gate** → cited answer or honest unknown.
- **Answer-correctness judge** (eval-time quality dial, different model from writer; never touches the gates).
- **Eval harness** proving it (`python3 -m evals.run --pipeline gated`).
- **Web demo** (`demo/`): proof-forward UI — answer + evidence chips (clickable GitHub citations), a big "No one wrote this down." signature state, calm macOS-style shell with Honest-Brutalism edges.
- **In-app repo switcher:** type `owner/repo` in the sidebar → it indexes once into a git-ignored per-repo cache → you query that repo; switching back to `simonw/llm` is instant; re-connecting a cached repo is instant.

## 3. Constraints & key decisions (the operating rules)
- **No paid APIs.** Free models only. Hardware = Apple Silicon Mac, **8 GB** (too small for big local models).
- **Brain = free HOSTED models:** **writer = Groq `llama-3.3-70b-versatile`** (`GROQ_API_KEY`); **judge = Gemini `gemini-2.5-flash-lite`** (`GEMINI_API_KEY`). Judge ≠ writer (cross-provider, avoids self-grading). OpenRouter (`cohere/north-mini-code:free`, 50/day) is the fallback only.
- **Public repos ONLY** — free tiers may train on inputs, so private code is off-limits. **Private-repo support is SHELVED** (would need local or paid models).
- **MVP target then demo:** brain ✅ → codebase reading (any public repo) ✅ → UI/UX (in progress) → **macOS app** → **voice** (Whisper STT + macOS TTS, free/local) → record the demo.
- The one non-negotiable: **cite-or-unknown, deterministic, never bluff** — preserved in every change.

## 4. Shipped this session (all merged to `main`)
Newest → oldest, by area:

**In-app repo switcher** (`dda93e4`…`7e32eca`, `936f470`): `ingest_repo()` helper; `demo/library.py` (`Library`: active-repo state + per-repo cache + thread-safe switch); `POST /connect` + `GET /status`; sidebar connect control + status polling; cache git-ignored. Live-proven on `simonw/json-flatten`. **Fix applied:** switched repos ingest with `code_dir="."` (whole repo), not simonw/llm's `llm/`.

**Proof-forward UI rebuild** (`85afdbb`): `demo/index.html` rebuilt — evidence/proof is the canvas center; honest-unknown is a full signature block; calm shell + hard borders/offset-shadow. Same `/ask` contract, no brain change. Live-verified.

**Brick 7 — any public repo** (`3f10e6a`…`e15b7a8`): `evals/corpus_meta.py` (self-describing corpus `meta.json`); `ingest --repo/--commit/--code-dir` (no-arg still reproduces the pinned `simonw/llm`); demo reads repo/commit from `meta.json` so citations follow the ingested repo; skippable smoke test.

**Free hosted providers** (`ed5ff81`…`e0076aa`): `GroqProvider` + `GeminiProvider` behind the `Provider` interface; `--writer`/`--judge` flags; board defaults to Groq writer + Gemini judge; **board went GREEN**. (Replaced the OpenRouter 50/day wall.)

**Brick 5 — web demo** (`52f09a1`…`2ff075a`, `ed67c28`): `links.py` (ref→GitHub URL), `payload.py` (`Result`→page JSON), stdlib `server.py`, `index.html`, live smoke test (later hardened to "≥1 answerable cites").

**Brick 4 — answer-correctness judge** (`59fd0f6`…`61a98ba`): reference answers added to the 6 answerable questions; `evals/judge.py`; `grade(..., judge=None)` additive; wired into board.

**Brick 2 — honesty gate + writer** was also executed earlier this session (provider/synth/gate/GatedPipeline) — foundation for all of the above.

## 5. How to run it
```
# Eval board (proves the brain) — GREEN on the free stack:
GROQ_API_KEY=… GEMINI_API_KEY=… python3 -m evals.run --pipeline gated

# Web demo (the face):
GROQ_API_KEY=… GEMINI_API_KEY=… python3 -m demo.server   # http://127.0.0.1:8000

# Point the CLI corpus at any public repo (overwrites the committed corpus):
python3 -m evals.ingest --repo OWNER/REPO [--commit SHA] [--code-dir DIR]

# Tests (all green; network/live tests self-skip without keys):
python3 -m unittest discover -t . -s evals -p "test_*.py"
python3 -m unittest discover -t . -s demo  -p "test_*.py"
```
The **demo's** in-app switcher (sidebar `owner/repo` → Connect) is the product-facing
way to change repos; it caches per-repo under `evals/corpus/cache/` (git-ignored).

## 6. GitHub auth — how "connect" works (important)
There is **no in-app GitHub login**. `ingest_repo` shells out to local **`git clone`**
(anonymous for public repos) and the **`gh` CLI** (authenticated once on this machine
via `gh auth login` — confirmed valid, `repo` scope). So connecting a repo borrows
*your machine's* `gh`/`git` credentials. Consequence: works for public repos from this
machine only. A real per-user "Sign in with GitHub" (GitHub App/OAuth) + private repos
is the **deferred adapter** (shelved).

## 7. Plans written & status (`docs/plans/`)
- `2026-06-28-brick-2-gate-and-writer.md` — DONE (merged).
- `2026-06-28-phase-1.md` — the master Phase-1 roadmap (Bricks 0–6).
- `2026-06-28-brick-3-embeddings.md` — **SHELVED.** Probe proved a real lexical gap on *paraphrased* questions (BM25 misses the gold PR), so the plan is eval-driven and ready — but deferred (lexical is 100% on the labelled set; not worth the embedding dependency yet).
- `2026-06-28-brick-4-answer-grading.md` — DONE (merged).
- `2026-06-28-brick-5-web-demo.md` — DONE (merged).
- `2026-06-28-brick-6-recordable-demo.md` — PREPARED (the recording script: cited-answer hero = PauseChain q03→pr:1482; honest-unknown hero = q07 "32 characters"). Not recorded yet.
- `2026-06-28-brick-7-any-repo-ingest.md` — DONE (merged).
- `2026-06-28-brick-8-9-private-repos.md` — **SHELVED** (paid/private; superseded by the public-repo MVP decision).
- `2026-06-29-free-hosted-providers.md` — DONE (merged).
- `2026-06-29-in-app-repo-switcher.md` — DONE (merged).

## 8. Design work
- `docs/UI_UX_BRIEF.md` — functional brief: states + the real payload fields the UI must use (`verdict`, `answer`, `citations:[{ref,url}]`, `searched`).
- `docs/DESIGN_VISION.md` — art direction: **"Honest Brutalism"** (calm Figma base + brutalist evidence edges; mono citations; the honest-unknown as the hero).
- **Figma wireframe reviewed** (file `Icarus-Wireframe---Honest-Brutalism`, via the Figma MCP — needs the Full-seat account `alankrit.ghosh@…christuniversity.in`, not the View-seat `ayushghosh2015@gmail.com`). Top-3 fixes I gave: (1) make proof the protagonist, (2) promote honest-unknown to a real signature state, (3) move the logo off the waveform (Route A reads as a generic voice app at icon size). The **proof-forward `index.html` rebuild already implements (1) and (2).**

## 9. Tests
All green. Offline suites self-skip the live/network tests without keys. Honesty
gates, `grader.py`, and `phase1_questions.json` were never weakened. No new
dependencies anywhere (stdlib only).

## 10. Operational gotchas
- **ROTATE THE KEYS** — Gemini, Groq, and OpenRouter keys were pasted into the chat transcript this session. Treat all three as exposed; rotate before sharing the transcript.
- **OpenRouter free tier = 50 requests/day** (resets UTC midnight). We moved off it to Groq/Gemini for headroom. Don't run real-model evals/demo concurrently — concurrent calls 429.
- **Groq needs a `User-Agent` header** (Cloudflare 403/1010 on default urllib UA) — handled in `provider.py`.
- **Gemini key format** here is `AQ.…` (not the usual `AIza…`); it works via `?key=`.
- **Dashboard shows $0** — free models cost $0; usage is request-count, not dollars. $0 ≠ unused.
- **Figma MCP requires the Full-seat account** (Dev Mode is gated behind an editor seat).

## 11. Next steps (pick up here)
1. **macOS app** — the "face" (hotkey, window, overlay) wrapping the brain. Biggest remaining build (Swift). *(Honest: largest new surface.)*
2. **Voice** — Whisper STT (local, free) + macOS `AVSpeechSynthesizer` TTS, on the app.
3. **Brick 6** — record the demo once UI/app/voice are in (script in its plan doc).
4. Optional polish: a visible "uses local `gh` auth · public repos" note in the demo; richer cited answers by connecting a repo with recorded PR rationale.
- **Shelved (need a constraint change):** Brick 3 embeddings (paraphrase robustness), Bricks 8–9 private repos (need local or paid models).

## 12. Key files
- Brain: `evals/{pipeline,gate,synth,provider,judge,grader,retriever,corpus,corpus_meta,ingest,run}.py`
- Demo: `demo/{server,library,payload,links,index.html}.py` + tests
- Corpus: `evals/corpus/{chunks.jsonl,meta.json}` (pinned `simonw/llm` @ `94769b8`); switched repos cached under `evals/corpus/cache/` (git-ignored)
- Labelled set: `evals/phase1_questions.json` (6 answerable w/ `reference_answer` + gold PRs, 4 unanswerable)

## 13. Memory
Session decisions are saved in the project memory index (`MEMORY.md`): see
`public-repo-mvp-direction.md` and `openrouter-free-tier-limits.md`.
