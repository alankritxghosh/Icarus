# Icarus — Architecture

Plain-language map of how Icarus is built. Written so a builder who vibecodes can
hold the whole shape in their head, not just an engineer.

---

## The one-line shape

**The Mac app is the *face*. The cloud is the *brain*.** The laptop does the
light, private things (listen while you hold the key, draw the overlay). All the
real thinking runs in a cloud space rented privately per company.

```
  GitHub ──learns──▶  [ THE BRAIN — private cloud, per company ]
                          memory · search · AI writer · speech
                                    ▲        │
                          question  │        │  answer + citations
                                    │        ▼
                      [ THE FACE — the Mac app on the laptop ]
                          hotkey · microphone · translucent overlay
```

## The four pieces

### 1. The Face — the macOS app
Small and yours. It listens for the hotkey, records your voice while you hold the
key, plays the spoken answer back, and draws the translucent overlay showing the
citations. It holds **no** intelligence — it is a thin client that talks to the
brain. This is the part most comfortable to build first as an app.

### 2. The Librarian — learning the codebase (cloud)
Connects to a company's GitHub, pulls in code + pull requests + review comments,
chops everything into small pieces, and turns each piece into a "fingerprint"
(an *embedding*) so it can be found **by meaning**, not just by keyword. The
fingerprints live in a **search database** (a vector store). It keeps itself
updated as the repo changes. This is what "Icarus learns your codebase" means.

### 3. The Brain — answering a question (cloud)
Takes the question, asks the Librarian for the most relevant pieces, and hands
them to an **AI writer** (a frontier model) that turns them into a
colleague-style sentence **and** returns the exact sources used. Between
retrieval and speaking sits the **honesty gate** (see below) — the part that
decides whether there's enough evidence to answer at all.

### 4. The Voice — ears and mouth (cloud)
One model turns speech into text (Whisper-class). Another turns the written
answer back into speech. Both are rented.

## The honesty gate (the part that makes it Icarus)

This is the most important component and the one we own most deliberately.

- The AI writer is only allowed to talk about pieces the Librarian actually
  retrieved. If the retrieved evidence does not support an answer, Icarus says
  **"no one wrote this down"** — it does not guess.
- **The gate stays primarily deterministic and auditable**, not a black-box
  classifier. "I don't know" must be something we can prove in code — *did
  retrieval return evidence above a grounding threshold? do the claims in the
  answer map back to retrieved spans?* A learned signal may assist, but never
  replaces the gate. (This is the lesson from reviewing the neural-net plan:
  making abstention a neural net would trade our auditable guarantee for a
  probabilistic one, on the exact axis that is our whole brand.)

## What we rent vs build

Build the parts that are *ours*; rent the commodities. Trying to build the AI
model or the speech models yourself is the trap.

| Piece | Rent (at first) | Build ourselves |
|-------|-----------------|-----------------|
| AI writer (synthesis) | ✅ Claude API | the honesty gate around it |
| Speech-to-text / text-to-speech | ✅ Whisper + a TTS service | — |
| Search database (vector store) | ✅ a hosted store | — |
| Embeddings (fingerprints) | ✅ hosted or open model | (later) fine-tune per customer |
| The Face (Mac app) | — | ✅ ours |
| The Librarian (GitHub ingest) | — | ✅ ours |
| The honesty gate + evaluation | — | ✅ ours — the moat |

> **Never train an LLM from scratch.** A from-scratch model is a multi-million,
> many-GPU effort that would be worse than a two-year-old open model. We fine-tune
> and evaluate; we do not forge base models.

## Where compute runs (the trust model)

Deployment is a spectrum, and where we draw the line is the whole game.

- **Local tier.** Everything on the user's machine. Maximum privacy, limited by
  hardware. Kept deliberately for regulated / air-gapped customers. Degraded but
  still honest — cite-or-unknown never degrades.
- **Private cloud / single-tenant (the default target for heavy work).**
  Inference runs in the customer's own cloud or an isolated single-tenant
  environment. Compute is solved; the source never enters a shared pool.
- **Managed multi-tenant.** Easiest UX, largest liability. A deliberate, later,
  eyes-open choice for lower-trust segments only — **never the foundation.**

When compute is remote, trust is held by **controls, not architecture**:
zero-data-retention, never-train-on-customer-data, discard-after-request, and
real compliance (SOC 2, ISO 27001, BAA where needed). The customer's asset
(source code + decision history) is more sensitive than dictated text, so these
controls are the floor, not a premium add-on.

## The data journey of one question

1. You hold the hotkey and speak. *(laptop)*
2. Your voice becomes text. *(cloud)*
3. The Librarian finds the most relevant evidence. *(cloud)*
4. The honesty gate checks: is there enough to answer? If not → "no one recorded
   this." *(cloud)*
5. If yes, the AI writer turns the evidence into a colleague-style answer + the
   exact citations. *(cloud)*
6. The answer is spoken back; the overlay shows the proof. *(cloud → laptop)*
7. Nothing is retained — the request data is discarded. *(cloud)*

## Open architecture questions (decide as we build, not now)

- Which embedding model and vector store to start with (rent vs open).
- How the Mac app authenticates each engineer to the company's private brain.
- How GitHub access is granted and scoped (PAT vs GitHub App) and how the
  initial ingest is kept fresh.
- Latency budget split across speech-in, retrieval, synthesis, and speech-out
  (see [METRICS.md](METRICS.md)).
