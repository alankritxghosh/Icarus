# Brick 6 — The recordable demo (Phase 1 exit artifact) — Prep & Script

> Brick 6 is **the take**, not new code. Brick 5 (`demo/`) is the stage; this doc
> locks the two questions, their expected on-screen results, the recording flow,
> and the caveats — so the recording can be shot in one sitting the moment the
> free quota is available. No brain or demo-code change is required.

## The shot (two questions, back to back)

The honest "I don't know" is the hero. Show a confident cited answer first, then
the honest refusal — the contrast is the point.

### 1. Cited answer (proven live 2026-06-29)
- **Ask:** `What concrete use case drove the PauseChain primitive in llm?`  (= q03)
- **Expect:** a grounded answer — *"...driven by a need for Datasette Agent to
  pause a tool call mid-execution to ask the user for confirmation, surviving
  server restarts so the chain can resume..."* — with citation
  **[pr:1482](https://github.com/simonw/llm/pull/1482)** rendered as a clickable
  link. Click it on camera to show the citation lands on the real PR.

### 2. Honest unknown — the hero (q07; abstains reliably, recall 100% every run)
- **Ask:** `Why is the maximum conversation-name length set to 32 characters specifically?`
- **Expect:** the calm hero card — **"No one wrote this down."** — with the muted
  *"Searched: …"* line showing it actually looked (transparent abstention). The
  point to narrate: the value 32 exists in the code, Icarus found the code, and it
  *still* refuses to invent a reason that was never written.

## Why these two
- q03 is the **reliable** cited answer on the free writer. **Do NOT use q01** (the
  Responses-API question) on camera — the free model abstains on it some runs
  (an honest false-abstention, but it won't show the cited-answer card).
- q07 is the **cleanest realistic-unrecorded** question: it sounds like it must
  have a reason, so the honest refusal is most striking. Backup: q08 (the 16-byte
  blake2b digest size). Avoid q09/q10 — too trivial to be compelling.

## Runtime checklist (the only prerequisites)
1. Free quota available (OpenRouter 50/day; resets 00:00 UTC) — or add 10 credits.
   See [[openrouter-free-tier-limits]].
2. Start the server:  `OPENROUTER_API_KEY=… python3 -m demo.server`
3. Open **http://127.0.0.1:8000** (the page, not the editor preview — the preview
   serves static HTML only and can't reach `/ask`).
4. Optional pre-flight (costs ~3 free requests, confirms the writer is answering
   today before you hit record):
   `OPENROUTER_API_KEY=… python3 -m unittest demo.test_demo_live`

## Caveats to keep the demo honest
- The free writer is non-deterministic; if q03 ever abstains on a take, re-ask or
  fall back to another answerable — never script around the gate or fake an answer.
- Spend stays $0 (free models); usage is request-count, not dollars (the
  OpenRouter dashboard's $0 is expected, not a sign of no usage).

## Definition of done (Phase 1 exit)
A single recording showing, back to back: one correctly-cited answer with a
working source link, and one honest "no one wrote this down" — the refusal as the
hero shot. That is "Phase 1 done" on screen.
