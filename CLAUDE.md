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
- `general_index.md` — every file + a 1–2 line description.
- `detailed_index.md` — every class/function + its docstring/description. Large;
  **read it on demand**, do not auto-import it.

This index may or may not be up to date — verify before relying on it, and
**regenerate it after any structural change** (adding/removing/renaming files or
functions). *(These files don't exist yet; they're generated as the first
housekeeping step of Phase 1. Once `general_index.md` exists, switch this line to
`@general_index.md` so it auto-loads each session.)*

## Product identity
Icarus is a privacy-first conversational engineering brain a company can buy: it
learns a company's codebase and the decisions around it, and answers *why*,
*what*, *how* — spoken like a colleague, with citations in a translucent overlay,
and an honest "no one wrote this down" when the reason was never recorded.
v1 = GitHub source + macOS voice app + per-company private cloud. See
[docs/VISION.md](docs/VISION.md).

## The one non-negotiable: it cannot bluff
Icarus answers only from evidence it actually retrieved, and says "I don't know"
when the answer was never written down. The honesty gate stays **deterministic
and auditable** — "I don't know" must be provable in code, never a black-box
guess. This never degrades, on any tier, in any phase. Every change preserves it.

## Hard constraints (never OK)
- Never bluff / break cite-or-unknown.
- Never capture the screen silently — opt-in and explicit, always.
- Personal and commercial stay isolated — never read, ingest, or depend on any
  personal memory system (e.g. anything under `../brain/`).
- Never train on customer code; discard after each request.
- Never train an LLM from scratch — rent the LLM/speech; own the pipeline.
- A credential is a responsibility — every byte leaving the trust boundary is a
  deliberate, minimized decision.

## How we build (the strategic principle)
**Build the brain as a typed API first; sell it typed; voice is Phase 3.** Never
build the talker before the brain. Rent the commodities, own the moat (ingest,
honesty gate, evals, the app). See [docs/STRATEGY.md](docs/STRATEGY.md).

Stack (decided): Python brain · OpenRouter **free** models behind a one-line
provider abstraction (`cohere/north-mini-code:free` is candidate #1; the eval
harness picks the model) · local open embeddings · **public repos only** while on
free models · Claude / voice / Mac app deferred. Full table in STRATEGY.md.

## Current stage
Pre-build. Next brick = Phase 1: type a question about one GitHub repo, get a
cited answer or an honest unknown, proven by the eval harness, with a recordable
demo (honest "I don't know" is the hero shot). See
[docs/PHASE_1_PLAN.md](docs/PHASE_1_PLAN.md). Old code archived at tag
`jarvis-v0` / branch `archive/jarvis-v0` — reference only, not a dependency.

## Architecture in one line
The Mac app is the *face* (hotkey, mic, overlay); the cloud is the *brain*
(librarian, search, AI writer, speech), rented privately per company, never
trained on, discarded after each request. See
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

## Do not build yet (post-Phase-4 unless a task says so)
- Data sources beyond GitHub (Slack, Linear, Notion, org-wide ingestion).
- Deep structural code understanding / dependency tracing.
- Autonomous coding-agent behavior.
- Voice or the Mac app before their phase.
- Managed multi-tenant deployment as a default.
- Any use of personal JARVIS memory.

## Commands
Phase 1 eval harness (Python stdlib only, run from repo root):
- `python3 -m evals.run` — run the eval board against the verified labelled set.
  Exits non-zero **only** if an honesty gate (groundedness / abstention recall)
  breaks; quality below target is the expected red baseline, not a build failure.
- `python3 -m evals.run --k 10` — change the retrieval recall@k cut-off.
- `python3 -m unittest evals.test_grader` — test the harness conscience itself
  (proves the gates fire on a bluff or an ungrounded citation).

Labelled set: `evals/phase1_questions.json` (corpus pinned to `simonw/llm`
@ `94769b8`). Current pipeline is `StubPipeline` — the next brick replaces it
with the real ingest→retrieve→gate→synthesize brain to turn the quality dials
green without dropping a gate.
