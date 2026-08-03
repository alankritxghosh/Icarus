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
honesty guarantee, sold as a brain whose data stays isolated per company.** Three proven parts,
one new combination.

## 2. Our defensibility (and the honest threat)

We are **not** defensible because "we answer codebase questions" — others already
do. We are defensible on:

- **The voice + overlay experience** (the magic nobody in the codebase-Q&A space
  has).
- **The "cannot bluff" brand** — deterministic, auditable honesty as the product,
  not a footnote.
- **Privacy posture** — per-tenant data isolation in one unified cloud, never
  trained on, discarded after each request.

**Explanation is the wedge; organizational memory is the product.** "Chat with your
repo" is crowded; *preserving the why behind a codebase* is not. We sell **"Git
remembers what changed. Icarus remembers why"** — reduced onboarding, preserved
institutional knowledge, confidence to change things. Explanation (answer-when-asked)
is the low-risk trojan horse that earns the right to sit on a team's memory; the
defensible core is **capture** (getting the rationale recorded — most "why"s never hit
a PR) and, later, **push** (surfacing stale decisions before anyone asks). See
[decisions/2026-06-30-organizational-memory-positioning.md](decisions/2026-06-30-organizational-memory-positioning.md).

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
- **Line-window chunking** for code, not AST/function-level — the cAST finding
  was the original plan, but what actually shipped
  (`evals/ingest.py::chunk_text`) is simpler: overlapping 300-line windows,
  also char-bounded since 2026-07-16 (a live bug found a dense-but-short file
  could produce one chunk that silently exceeded the writer's per-chunk read
  budget). Every chunk still carries citation metadata (file, line range,
  source tag) built into its `ref`, not reconstructed. True AST-aware chunking
  remains a real, undone idea if line windows ever prove too coarse — not yet
  needed.
- **Rent the inference, own the pipeline** (the Wispr lesson): rent the LLM,
  embeddings, speech, and vector store; build the GitHub ingest, the honesty
  gate, and the evaluation harness — those are the moat.
- **Native Swift/AppKit Mac app** for the face (overlay-over-fullscreen + global
  hotkey need native APIs; also avoids Wispr's ~800MB Electron footprint).
- **One isolated tenant per company** for v1 (one unified cloud, data separated
  per company) — sidesteps Glean's hardest problem (per-user permission mirroring)
  until we deliberately choose to take it on.

## 5. Recommended stack (with the genuinely-open calls flagged)

This table is the original Phase 1 plan. Status column shows where each row
actually landed as of 2026-07-16 — several rows resolved differently than
planned, which is exactly what "decide against real numbers, not vibes" (below)
was for.

| Layer | Original plan | Status |
|-------|----------|--------|
| Brain service | **Python** | shipped |
| Synthesis LLM | OpenRouter free models, `cohere/north-mini-code:free` candidate #1, Claude deferred | **superseded 2026-07-13** — one model for everyone, `gemini-paid` (billing-enabled, private-safe), free/paid split killed outright once private repos became the real product. The eval harness keeps free writer dials (Groq/Gemini/OpenRouter) for cost-free quality iteration; those never touch serving. |
| Embeddings | Local open model (BGE/E5/nomic-class) | shipped — fastembed (`bge-small-en-v1.5`), free, local, on-disk vector cache so a restart doesn't re-embed |
| Vector store | Start dead-simple/local | shipped as planned — an on-disk JSON cache (`evals/vector_cache.py`), no managed vector DB needed |
| Demo surface | Minimal local web skin | shipped, and exceeded — a Mac app and a browser extension too |
| Mac app | Native Swift/AppKit, deferred to Phase 2 | shipped |
| Speech | Rent STT/TTS, self-host only if latency forces it | shipped — Apple's on-device STT when the Mac has the model, automatic cloud fallback otherwise (zero user setup); `AVSpeechSynthesizer` for TTS |
| GitHub access | Local export/`gh` CLI first, then PAT, GitHub App later | shipped — OAuth (web + device flow), `repo`-scoped for private access. **GitHub App (per-repo, read-only) is still the real trust upgrade, still not built** — business-gated, see docs/HANDOFF.md |
| Cloud provider / hosting | Model decided (unified cloud + per-tenant isolation), provider TBD | shipped — Azure Container Apps, live |

**What actually happened to the model choice:** the free-model plan above
(public repos only, `north-mini-code`/OpenRouter) was the Phase 1 starting
point, not the ending state. Once private repos became the real product, the
free/paid split was killed outright — one paid, private-safe writer
(`gemini-paid`) now serves every repo, public or private, enforced by a
deterministic trust interlock (`evals/trust.py`) rather than by policy. The
one piece of the original plan that paid off exactly as intended: the provider
abstraction really did make this a one-line swap, not a rewrite.

## 6. Sequencing (maps to BUILD_ORDER phases) — status as of 2026-07-16

1. **Phase 1 — brain as a typed API** over one GitHub repo. ✅ shipped. See
   [PHASE_1_PLAN.md](PHASE_1_PLAN.md).
2. **Phase 2 — Mac app + overlay**. ✅ shipped.
3. **Phase 3 — voice**. Implementation shipped — on-device STT when available,
   automatic cloud fallback otherwise, degraded-but-honest by design. Latency
   instrumentation is shipped; Phase 3 acceptance still requires the real-device
   baseline defined in [METRICS.md](METRICS.md).
4. **Phase 4 — multi-company + trust** (per-tenant isolation, permissions,
   SOC 2). **Partial:** per-tenant isolation and private-repo permissions are
   shipped and live-tested. Note the tenant changed on **2026-07-27**: it is now
   the **repository**, not the individual. One index per repo, shared by whoever
   GitHub says can read it, entitlement re-checked on every read — so a company
   gets one brain rather than one copy per employee. Companies are still never
   pooled. See docs/plans/2026-07-27-organisation-brain.md. **SOC 2 is
   explicitly not pursued yet** — it's the target for the first
   security-conscious paying customer, not a current claim (see
   docs/VISION.md §5).

## 7. Risks I'm tracking (and the mitigation)

| Risk | Why it matters | Mitigation |
|------|----------------|------------|
| Building the talker before the brain | The classic fatal mistake | Voice is Phase 3, never sooner |
| Weak retrieval | "Cited" answers that cite the wrong thing — confident-wrong with a footnote | Eval harness exists *before* we trust anything ([EVALUATION.md](EVALUATION.md)). **This risk materialized for real, 2026-07-16**: two live-reproduced bugs (a writer-visibility gap, an exact-ID retrieval miss) found by testing against unfamiliar real repos, not the frozen board — neither broke an honesty gate, both were fixed same-session with red→green tests. The frozen board didn't catch either; live testing beyond it is what actually did. |
| Cloud dependency | Wispr's outage took every user offline at once | Graceful "can't reach the brain" state; never silent failure. **Also materialized for real**: a CPU-pinning incident made a genuinely-succeeding connect look like "can't reach the brain" — root-caused and fixed. |
| Permissions complexity | Glean's moat *and* its heaviest burden | Per-user private-repo access (own token, isolated storage) is now shipped, not deferred — but full permission *mirroring* inside a shared private repo (who on the team can see what) is still deferred; that's the harder Glean-style problem this row originally meant. |
| Latency | The magic dies if the loop is slow | Design streaming/"first word fast" into the response format from day one |
| Trust scandal | Wispr's silent screenshots became its reputation wound | Never capture the screen silently; opt-in and explicit, always |
| **Low usage frequency** | Explanation is *pull* — you only ask when confused; low frequency is fatal for SaaS | **Push**: proactively surface stale decisions (v5) so Icarus is a daily-touch tool, not break-glass |

## 8. What "started" looks like

*(Historical — describes the actual Phase 1 slice as scoped at the time; kept
for the record, not as a forward-looking plan. It shipped.)*

The thinnest vertical slice of Phase 1: one public GitHub repo, a handful of
labelled "why" questions, a typed pipeline returning a cited answer or an honest
"I don't know," scored by the eval harness. That slice proves or kills the core
in days. Details in [PHASE_1_PLAN.md](PHASE_1_PLAN.md).

## 9. The first finish line: a recordable demo

*(Historical — this demo shipped. Kept for the record of how it was scoped.)*

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
