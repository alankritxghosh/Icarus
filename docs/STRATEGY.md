# Icarus — Build & Product Strategy

How we turn the vision into a shipped, sellable product — informed by how the
closest comparables were actually built. Read [COMPETITIVE.md](COMPETITIVE.md)
for the research this rests on.

---

## 1. The thesis (why this wins)

Three ingredients are each already proven *in market* — but never combined:

1. **The brain** — codebase Q&A with citations — is a real, paid category
   ([Unblocked](https://getunblocked.com/), [Glean](https://www.glean.com/) at
   ~$7.2B, [Greptile](https://www.greptile.com/)).
2. **The face** — global hotkey + voice + a translucent overlay + cloud-trust
   controls — was proven by [Wispr Flow](https://wisprflow.ai/) in a different
   category.
3. **The guarantee** — *it cannot bluff; it says "I don't know" when no one wrote
   it down* — nobody in this space sells this as the headline.

**Icarus = Wispr's interface playbook × Unblocked's brain × a deterministic
honesty guarantee, sold as a private-per-company brain.** Three proven parts,
one new combination.

## 2. Our defensibility (and the honest threat)

We are **not** defensible because "we answer codebase questions" — others already
do. We are defensible on:

- **The voice + overlay experience** (the magic nobody in the codebase-Q&A space
  has).
- **The "cannot bluff" brand** — deterministic, auditable honesty as the product,
  not a footnote.
- **Privacy posture** — per-company private cloud, never trained on, discarded
  after each request.

**The honest threat: [Unblocked](https://getunblocked.com/) is Icarus without
voice**, and is already pivoting toward agents/MCP. We do not beat them by being
broader. We beat them by being **narrower and deeper**: GitHub-only, the "why,"
provable honesty, and an interface they don't have. Going broad (every data
source, every surface) is how we *lose* to incumbents with more resources.

## 3. The core build principle

> **Build the brain as a service first. Sell it typed. Add the magic (voice,
> overlay) on top.**

Unblocked sells the *typed* brain successfully — so our revenue-capable MVP does
**not** require voice. Voice is the differentiation and the marketing magic; the
brain is the moat and the revenue. This sequencing means we have something real
and pilotable *before* we take on the hardest, riskiest part (voice + latency).

This is the same rule as [BUILD_ORDER.md](BUILD_ORDER.md), stated as strategy:
**never build the talker before the brain it speaks for.**

## 4. Architecture decisions (locked enough to start)

Drawn directly from how the comparables built theirs — see
[ARCHITECTURE.md](ARCHITECTURE.md) for the full map.

- **Index-first RAG** (the Greptile/Glean pattern): ingest once, embed, store,
  retrieve fast — don't analyze files on the fly at question time.
- **AST / function-level chunking** for code (the cAST finding), not line splits.
  Every chunk carries citation metadata (file, line range, source object) so the
  citation is built in, not reconstructed.
- **Rent the inference, own the pipeline** (the Wispr lesson): rent the LLM,
  embeddings, speech, and vector store; build the GitHub ingest, the honesty
  gate, and the evaluation harness — those are the moat.
- **Native Swift/AppKit Mac app** for the face (overlay-over-fullscreen + global
  hotkey need native APIs; also avoids Wispr's ~800MB Electron footprint).
- **One private brain per company** for v1 — sidesteps Glean's hardest problem
  (per-user permission mirroring) until we deliberately choose to take it on.

## 5. Recommended stack (with the genuinely-open calls flagged)

| Layer | Decision | Status |
|-------|----------|--------|
| Brain service | **Python** | locked |
| Synthesis LLM | **OpenRouter free models** behind a thin provider abstraction; `cohere/north-mini-code:free` is candidate #1. **The eval harness picks the model, not the spec sheet.** Claude deferred until proof-of-life + usage | locked (for demo) |
| Embeddings | **Local open model** (BGE/E5/nomic-class via sentence-transformers) — free, local, private; never via a free API | locked |
| Vector store | Start dead-simple/local (no service to manage or pay for early) | **open — exact choice in Phase 1** |
| Demo surface | **Minimal local web skin** — shows question, answer, citations panel (a taste of the overlay aesthetic) | locked |
| Mac app | Native Swift / AppKit — **deferred to Phase 2** | deferred |
| Speech (Phase 3) | Rent STT/TTS first; self-host only if latency forces it | deferred |
| GitHub access | Local export / `gh` CLI for the first slice, then PAT; GitHub App later | **open — decide in Phase 1** |
| Cloud provider / hosting | — | **open — decide later** |

**Two rules attached to the model choice:**
- **Public repos only while on free models.** Free routes may log/train on inputs — fine for
  public demo data, fatal for private code. Touching anyone's private code is the trigger to
  switch to a zero-retention provider. (This is our "every byte leaving the boundary is a
  deliberate decision" principle.)
- **The provider abstraction is load-bearing.** Swapping `north-mini-code:free` → Claude → a
  self-hosted model must be a one-line config change, never a rewrite.

**Sleeper advantage of an open-weights writer:** `north-mini-code` is Apache-2.0. If it holds
up on the eval set, the *same* model can serve the free-demo phase **and** later be
self-hosted inside a customer's trust boundary — something a rented Claude can never do. That
makes "rent now, own later" a real path for synthesis, not just embeddings.

Do not pre-commit the "open" rows. Decide them against real numbers, not vibes.

## 6. Sequencing (maps to BUILD_ORDER phases)

1. **Phase 1 — brain as a typed API** over one GitHub repo. Pilotable, sellable.
   See [PHASE_1_PLAN.md](PHASE_1_PLAN.md).
2. **Phase 2 — Mac app + overlay**, still typed.
3. **Phase 3 — voice** (where we copy Wispr's latency engineering, and keep a
   degraded-but-honest fallback so a cloud blip never makes Icarus go silent).
4. **Phase 4 — multi-company + trust** (isolation, permissions, SOC 2).

## 7. Risks I'm tracking (and the mitigation)

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| Building the talker before the brain | The classic fatal mistake | Voice is Phase 3, never sooner |
| Weak retrieval | "Cited" answers that cite the wrong thing — confident-wrong with a footnote | Eval harness exists *before* we trust anything ([EVALUATION.md](EVALUATION.md)) |
| Cloud dependency | Wispr's outage took every user offline at once | Graceful "can't reach the brain" state; never silent failure |
| Permissions complexity | Glean's moat *and* its heaviest burden | One brain per company in v1; defer per-user scoping |
| Latency | The magic dies if the loop is slow | Design streaming/"first word fast" into the response format from day one |
| Trust scandal | Wispr's silent screenshots became its reputation wound | Never capture the screen silently; opt-in and explicit, always |

## 8. What "started" looks like

The thinnest vertical slice of Phase 1: one public GitHub repo, a handful of
labelled "why" questions, a typed pipeline returning a cited answer or an honest
"I don't know," scored by the eval harness. That slice proves or kills the core
in days. Details in [PHASE_1_PLAN.md](PHASE_1_PLAN.md).

## 9. The first finish line: a recordable demo

The first goal is a **fast demo we can record and publish** as the product's
introduction — not a sellable system. How we aim it:

- **Brain-first, with a thin web skin.** The brain stays headless; Phase 1 gets a
  minimal local web page (question → answer → citations panel) so the recording
  looks intentional and previews the overlay aesthetic — *without* building the
  Mac app or voice. We get a polished clip from the brain alone.
- **The honest "I don't know" is the hero shot.** Everyone has seen an AI answer a
  question; almost nobody has seen one *refuse to invent* and show exactly where
  it looked. The demo shows one great cited answer **and** one honest refusal,
  back to back — that contrast *is* the pitch.
- **The tension we hold:** "publishable demo" pulls toward building the sexy
  voice/overlay early — the exact trap [BUILD_ORDER.md](BUILD_ORDER.md) warns
  against. The thin web skin is how we get a great recording while keeping the
  talker behind the brain.
