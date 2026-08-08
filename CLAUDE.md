# Icarus

Standing orders for anyone (human or AI) building Icarus. Short on purpose —
this file points to the deep docs, it does not repeat them.

## Talking to Alankrit
- Start every response with "Alankrit,".

## Engineering principles (how to work)
1. **Think before coding.** Never assume — state assumptions explicitly. If
   uncertain, stop, name what's confusing, and ask. If multiple interpretations
   exist, present them rather than picking silently.
2. **Simplicity first.** The minimum that solves the problem. No features beyond
   what was asked. No abstractions for single-use code. If a senior engineer
   would call it overcomplicated, simplify.
3. **Surgical changes.** Touch only what you must. Don't refactor unrelated code.
   Fix only your own bugs; clean up only your own mess.
4. **Goal-driven execution.** Define clear success criteria (e.g. "write a test
   and make it pass"), not vague tasks. Loop to verify and refine.
   - Tie-breaker: **loop autonomously on _verification_; stop and ask on
     _ambiguity_.** Never loop confidently in the wrong direction on a misread.

## Things Claude must not do
- **Don't claim work is done, fixed, or passing without running it and seeing the
  result.** No "this should work."
- **Don't fabricate** file paths, function/API names, library methods, citations,
  command output, or test results. If you don't know, say so.
- **Don't make a test or eval pass by weakening it** — no deleting assertions,
  loosening thresholds, mocking away the thing under test, or skipping. Fix the
  code, not the test.
- Don't add dependencies, libraries, frameworks, or services without asking.
- Don't delete, overwrite, or move files you didn't create or weren't asked to
  touch — when in doubt, ask.
- Don't refactor, rename, or reformat code unrelated to the task.
- Don't ship placeholder, mock, or stub code as if it were real — flag stubs.
- Don't swallow errors (empty catch / bare except) to make things look green.
- Don't leave the repo broken or half-finished silently — say what's left.
- Don't commit, push, or run destructive/irreversible commands unless asked.
- Don't hardcode secrets, tokens, or keys.
- **Don't be a yes-man.** If a request is wrong, risky, or overcomplicated, say so
  before doing it.

## Codebase map (read these first)
Two index files give a fast map of the code so you reference real names, not
guessed ones:
- @general_index.md — every file + a 1–2 line description (auto-loaded each
  session).
- `detailed_index.md` — every class/function + its docstring/description. Large;
  **read it on demand**, do not auto-import it.

This index may or may not be up to date — verify before relying on it, and
**regenerate it after any structural change** (adding/removing/renaming files or
functions).

## Product identity
Icarus is a privacy-first conversational engineering brain a company can buy: it
learns a company's codebase and the decisions around it, and answers *why*,
*what*, *how* — spoken like a colleague, with citations in a translucent overlay,
and an honest "no one wrote this down" when the reason was never recorded.
v1 = GitHub source + macOS voice app + **one unified cloud we operate, with
per-tenant data isolation** (true single-tenant / in-customer-cloud is an
enterprise upsell). See [docs/VISION.md](docs/VISION.md) and
[docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md](docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md).

## The one non-negotiable: it cannot bluff
Icarus answers only from evidence it actually retrieved, and says "I don't know"
when the answer was never written down. The honesty gate stays **deterministic
and auditable**. Be precise (and honest) about what that guarantees:
- **Groundedness is fully provable in code** — every emitted citation resolves to
  a genuinely-retrieved ref with a valid, contained line window. Icarus can never
  cite invented or unretrieved evidence. This never degrades, on any tier, phase.
- **Abstention when unrecorded is code-enforced for the clear case, writer-reliant
  beyond it.** The gate deterministically refuses the sharpest dodge — a "why"
  answered from evidence that records no reason (see `evals/gate.py`'s (b) guard) —
  but it cannot semantically prove arbitrary evidence entails an arbitrary answer
  without becoming a model. For those cases abstention leans on the cite-or-abstain
  writer. Do **not** claim "I don't know is always provable in code" — that
  overclaims. No bluffed citations ever (proven); honest-unknown is guaranteed for
  the clear case and strongly encouraged, not code-proven, for every semantic case.

## Hard constraints (never OK)
- Never bluff / break cite-or-unknown.
- Never capture the screen silently — opt-in and explicit, always.
- Personal and commercial stay isolated — never read, ingest, or depend on any
  personal memory system (e.g. anything under `../brain/`).
- Never train on customer code; discard after each request.
- One unified cloud, but **per-tenant data isolation** — never pool one company's
  code or decisions with another's; isolated stores + keys per tenant.
- Never train an LLM from scratch — rent the LLM/speech; own the pipeline.
- A credential is a responsibility — every byte leaving the trust boundary is a
  deliberate, minimized decision.

## How we build (the strategic principle)
**Build the brain as a typed API first; sell it typed.** Never build the talker
before the brain — voice now exists, built only after the brain proved itself
honest. Rent the commodities, own the moat (ingest, honesty gate, evals, the
app). See [docs/STRATEGY.md](docs/STRATEGY.md).

Stack (decided): Python brain · local open embeddings (fastembed) · **one
model for all production serving** — `gemini-paid` (Gemini, billing-enabled,
private-safe), used for every public AND private repo alike; the free/paid
writer split was killed 2026-07-13, there is no free-tier serving path anymore.
The eval harness (`evals.run`) keeps its own separate writer/judge dials
(Groq/Gemini/OpenRouter, defaulting to free Groq) for cost-free quality
iteration — those dials never touch serving, don't confuse the two. Mac app,
voice, and the browser extension are built and shipping, not deferred. Full
table in STRATEGY.md (that doc needs a pass to match — flag if you read it).

## Current stage
Engineering core is done: honest retrieval + the deterministic honesty gate,
ingest across a dozen+ languages, public AND private repos, one deployed Azure
brain, a Mac app, and a browser extension — all shipped and live-tested against
real, unfamiliar repos (not just the frozen eval board).

**This file does not try to track the current priority day-to-day — read
[docs/HANDOFF.md](docs/HANDOFF.md) first, every session.** It's the one doc
actually kept current session-to-session; treat anything here about "what's
next" as background, not instruction. As of 2026-07-16 the stated priority is
business decisions (ICP, pricing, trust/legal, design-partner outreach), not
new engineering — unless live testing or a design partner surfaces a real gap,
in which case fix it the way the 2026-07-16 session did: reproduce it live,
root-cause it in the real code, fix it with a red→green test, verify at scale,
then deploy. Old JARVIS-era code archived at tag `jarvis-v0` — reference only,
not a dependency.

## Architecture in one line
The Mac app is the *face* (hotkey, mic, overlay); the cloud is the *brain*
(librarian, search, AI writer, speech), run in one unified cloud we operate with
each company's data isolated, never trained on, discarded after each request. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Working within one model's limits
One model (Claude) does everything until a basic product exists — no agent roles
yet. To fight token limits, hallucinations, and context decay:
- **The files are the memory; the chat is just the workspace.** When we decide
  something, it goes into a doc immediately.
- Work **one brick/phase at a time** so each session loads only what it needs.
- Start a fresh chat for a new chunk of work instead of one endless thread.

## Required workflow
Before and after every change, follow [docs/WORKFLOWS.md](docs/WORKFLOWS.md):
- Prove the gap with a failing eval before changing the brain (red → green).
- Never weaken the eval to pass.
- Keep edits scoped to the current phase.
- After changes: run evals/tests, then report files changed, results, risks, and
  the next recommended brick. No success claims without evidence.

## Do not build yet (unless a task, tester feedback, or a design partner says so)
- Data sources beyond GitHub (Slack, Linear, Notion, org-wide ingestion).
- Deep structural code understanding / dependency tracing — e.g. "explain this
  file's relationship to the rest of the codebase," not just what's in it
  (raised 2026-07-16, still genuinely deferred; see docs/VISION.md's "later"
  column).
- Autonomous coding-agent behavior.
- Any use of personal JARVIS memory.

**Already built, despite what older docs elsewhere might still say — don't
re-litigate or rebuild these:** voice, the Mac app, the browser extension, and
cloud hosting/deployment (one unified cloud, per-tenant isolation, live on
Azure Container Apps). Naive pooled multi-tenancy is still never the answer,
even though hosting itself is long since decided and shipped.

## Commands
Run **all** tests (from repo root — the `-t .` is required so the `evals.`/`demo.`
package-relative imports resolve; plain `unittest discover` without it fails):
- `python3 -m unittest discover -t . -s evals`
- `python3 -m unittest discover -t . -s demo`

Phase 1 eval harness (Python stdlib only, run from repo root):
- `python3 -m evals.run` — run the eval board against the verified labelled set.
  Exits non-zero **only** if an honesty gate (groundedness / abstention recall)
  breaks; quality below target is the expected red baseline, not a build failure.
- `python3 -m evals.run --k 10` — change the retrieval recall@k cut-off.
- `GROQ_API_KEY=… GEMINI_API_KEY=… python3 -m evals.run --pipeline gated` — run
  the board against the real brain (retrieve → cite-or-abstain prompt → rented LLM
  writer → deterministic honesty gate). Default free hosted models: **writer =
  Groq** `llama-3.3-70b-versatile` (`GROQ_API_KEY`), **judge = Gemini**
  `gemini-3.1-flash-lite` (`GEMINI_API_KEY`) — judge ≠ writer, cross-provider.
  Override with `--writer {groq,gemini,gemini-paid,openrouter}` / `--judge
  {gemini,groq,openrouter}`. Keys never committed; **public repos only on the
  free writers** (free tiers may train on inputs); `gemini-paid` is the
  billing-enabled, private-safe writer (`GEMINI_PAID_API_KEY`) — see the
  private-repo plan. Providers retry on HTTP 429 with backoff (free tiers cap
  RPM). The judge is a quality dial only — it never touches the honesty gates.
  Model default bumped Gemini 2.5 → 3.1 (2026-07-05), verified against the live
  `/v1beta/models` list and the eval board (`--writer gemini-paid`: gates 100%,
  citation correctness 100%, answer correctness 100%) before landing.
- `python3 -m unittest evals.test_grader` — test the harness conscience itself
  (proves the gates fire on a bluff or an ungrounded citation).
- `python3 -m unittest evals.test_gate` — test the honesty gate's conscience
  (proves it fails safe to abstention on every ambiguous reply).
- `python3 -m unittest evals.test_judge` — test the answer-correctness judge
  (proves its verdict parser fails safe to "incorrect" on an ambiguous reply).
- `GEMINI_PAID_API_KEY=… python3 -m unittest evals.test_paid_writer_eval` — prove
  the paid writer holds both honesty gates at 100% on the public board (self-skips
  without the key).
- `python3 -m unittest evals.test_investigation_grader` — the INVESTIGATION
  harness's conscience (proves its four gates fire on a bluffer). Always runs.
- `GEMINI_PAID_API_KEY=… python3 -m unittest evals.test_investigation_eval` — the
  live investigation board (self-skips without the key; ~4 min, costs money).
  Measured 2026-08-08: gates 100%/100%/100%/100%, citation correctness 75%, hop
  recall 87.5%, mean 6 steps, 0 duplicate steps. See
  [docs/plans/2026-08-08-investigation-engine.md](docs/plans/2026-08-08-investigation-engine.md).

Web demo (the Phase 1 face over the gated brain; stdlib `http.server`, no deps):
- `GEMINI_PAID_API_KEY=… python3 -m demo.server` — serve the demo at
  `http://127.0.0.1:8000`: type a question about `simonw/llm` and get a cited
  answer (citations link to GitHub at the pinned commit) or an honest "no one
  wrote this down". Writer is the one production model, `gemini-paid` — no
  free-tier fallback in serving (that split was killed 2026-07-13; see Stack
  above). Pure packaging over `GatedPipeline` — no brain change. Needs the paid
  key and the committed corpus. **In-app repo switch:** type any public
  `owner/repo` in the sidebar → it indexes once into a git-ignored cache
  (`evals/corpus/cache/`) and switches; the built-in `simonw/llm` always reloads
  from the committed corpus. One active repo at a time (`demo/library.py`).
- `python3 -m unittest demo.test_demo_live` — end-to-end live guard (cited answer
  + honest unknown); self-skips without a provider key/corpus.

Ingest (point the demo at any **public** repo; needs `gh` authed + `git`):
- `python3 -m evals.ingest` — reproduce the pinned `simonw/llm` corpus (no args =
  the frozen eval corpus; the board depends on it).
- `python3 -m evals.ingest --repo OWNER/REPO [--commit SHA] [--code-dir DIR]` —
  ingest any public repo into `evals/corpus/chunks.jsonl` (overwrites it) and
  write `evals/corpus/meta.json` (provenance). `--commit` defaults to repo HEAD;
  `--code-dir` is the subtree walked for every supported source extension
  (default `llm`). The demo reads repo/commit from `meta.json`, so citation
  links follow the ingested repo. **Back up the committed `chunks.jsonl`/
  `meta.json` first** if you want the `simonw/llm` board back. **Not
  Python-only** — Python, JS/JSX/MJS/CJS, TS/TSX, Go, Rust, Java, Ruby, C/C++,
  Objective-C/C++ (`.m`/`.mm` — added 2026-07-17 for React Native; `.h` was
  already indexed, so iOS declarations were visible while implementations were
  not), Swift, Kotlin, PHP, C#, Scala, and Shell all chunk as code (see
  `_EXTENSION_SOURCES` in `evals/ingest.py`). This specific CLI targets public
  repos; a private repo's ingest goes through the server's own `/connect` path
  with the caller's token instead (see Private repos below).
- `RUN_INGEST_SMOKE=1 python3 -m unittest evals.test_ingest_smoke` — live ingest a
  tiny public repo to a temp path (self-skips by default).

Private repos (hosted, per-user isolated; needs the `repo`-scoped GitHub login —
sign out/in once if you signed in before this landed, see `docs/DISTRIBUTION.md`):
- Sign in with GitHub, then `POST /connect {"repo": "owner/name"}` for a repo your
  token can read. The server checks `GET /repos/{owner}/{repo}` **as the caller**
  first (200-or-refuse, fail-safe); a private repo routes to a per-user storage
  root, isolated from the shared public cache — but both public and private
  repos are answered by the same one model (`gemini-paid`), per the one-model
  decision above. `GET /status` reports `"private": true/false` for the
  caller's active repo.
- `POST /disconnect` — deletes the caller's own on-disk corpus and resets their
  library to the public default. Never touches another user's data.
- **Loud warnings:** never commit `data/` (git-ignored, holds per-user corpora —
  Task 4 of the private-repo plan); the deterministic trust interlock
  (`evals/trust.py`) still refuses any provider that isn't `private_safe=True`
  before it ever touches a private repo, never inferred from a key string —
  this stays enforced even though there's only one writer now, since the
  interlock is what makes "only one writer, and it happens to be safe" a
  provable guarantee instead of a coincidence; the caller's GitHub token is
  used in-memory only for the duration of the request — never written to
  argv, disk, or logs (`evals/ingest.py`'s leak-safe env-based auth).

Labelled set: `evals/phase1_questions.json` (corpus pinned to `simonw/llm`
@ `94769b8`; the 6 answerable questions carry a `reference_answer` the judge
scores against). On the free Groq-writer eval dial the board reads **GREEN**:
gates 100%, citation correctness 100%, answer correctness ~83% — that's the
eval harness's own free iteration path, separate from serving. Every repo,
public or private, is served by the same paid, private-safe writer
(`gemini-paid`) — see Stack above; there is no free-tier serving path. The Mac
app's private-repo surface (Brick G) is built — badge, disconnect, repo
persistence, lost-connection banner. Voice and the browser extension are also
built and shipping. Next real bricks are business-gated — check
[docs/HANDOFF.md](docs/HANDOFF.md) before starting new engineering, not this
file.
