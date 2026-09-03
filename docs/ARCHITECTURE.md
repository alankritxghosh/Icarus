# Icarus — Architecture

Plain-language map of how Icarus is built. Written so a builder who vibecodes can
hold the whole shape in their head, not just an engineer.

---

## The one-line shape

**The Mac app is the *face*. The cloud is the *brain*.** The laptop does the
light, private things (listen while you hold the key, draw the overlay). All the
real thinking runs in **one unified cloud we operate**, where each company's data
is isolated per tenant.

```
  GitHub ──learns──▶  [ THE BRAIN — unified cloud, isolated per tenant ]
                          memory · search · AI writer · speech
                                    ▲        │
                          question  │        │  answer + citations
                                    │        ▼
                      [ THE FACE — the Mac app on the laptop ]
                          hotkey · microphone · translucent overlay
```

## The five pieces

### 1. The Face — the macOS app
Small and yours. It listens for the hotkey, records your voice while you hold the
key, plays the spoken answer back, and draws the translucent overlay showing the
citations. It holds **no** intelligence — it is a thin client that talks to the
brain. This is the part most comfortable to build first as an app.

The Chrome extension is another thin face for selected GitHub lines. When the
Mac app is installed, Chrome native messaging proxies bounded `ping`, `status`,
and `explain` requests through a one-request helper process. The GitHub token
stays in the Mac Keychain and is never returned to the extension. Installing
the bridge requires an explicit confirmation in the app, and its native-host
manifest allowlists exactly one Chrome extension origin. The extension's older
OAuth credential remains a fallback only when Chrome cannot launch the native
host; a real refusal from the app is authoritative.

### 2. The Agent Adapter — another thin face
A local MCP process inside the installed Mac app lets Claude Code, Codex,
Cursor, and compatible tools ask the existing HTTP brain for change context
before they edit. It owns no retrieval or answering logic, never switches
repositories, and never writes code. Its three read tools return the same cited
answer or honest unknown, plus bounded retrieved evidence when the agent
explicitly opts in. Its two append-only Agent Mode tools may submit one bounded
decision candidate or acknowledge that a turn made no decision. They cannot
confirm intent, mutate GitHub, or merge anything. It serves public AND private repositories
(decided 2026-08-07). Icarus cannot verify the calling client's model
provider's data-use posture, so private evidence crossing this boundary is an
exposure owned by whoever configures the client, not a guarantee Icarus makes
— see
[docs/decisions/2026-08-07-mcp-private-repository-access.md](decisions/2026-08-07-mcp-private-repository-access.md).

The app binary is both server and credential bridge. It exchanges the GitHub
bearer held in Keychain for a ten-minute Icarus session without placing either
credential in the MCP client's configuration. It refreshes once after an
expired grant, server restart, or repository switch. The brain binds the
session to the verified identity and active repository. The grant reaches only
`/status`, `/ask`, `/explain`, `/context`, the confirmed-intent projection, and
the two bounded capture endpoints. Confirmation and GitHub mutation require the
human's separately verified GitHub credential.

The first bridge stores grants in the issuing server process. Production is
therefore explicitly pinned to one warm Azure replica in `.gitlab-ci.yml`; this
is the accepted availability constraint until both corpora and sessions move to
shared storage. The installer registers Claude Code automatically, and the Mac
app's Settings window diagnoses, installs, or repairs that user-scoped
registration without editing Claude's configuration files itself. Claude Agent
Mode is a separate explicit, per-checkout opt-in: the user chooses the local
project in the Mac app, which safely merges project-local MCP, SessionStart,
and Stop hook configuration without replacing unrelated entries.

### 3. The Librarian — learning the codebase (cloud)
Connects to a company's GitHub, pulls in code + pull requests + review comments,
chops everything into small pieces, and turns each piece into a "fingerprint"
(an *embedding*) so it can be found **by meaning**, not just by keyword. The
fingerprints live in a **search database** (a vector store). It keeps itself
updated as the repo changes. This is what "Icarus learns your codebase" means.

### 4. The Brain — answering a question (cloud)
Takes the question, asks the Librarian for the most relevant pieces, and hands
them to an **AI writer** (a frontier model) that turns them into a
colleague-style sentence **and** returns the exact sources used. Between
retrieval and speaking sits the **honesty gate** (see below) — the part that
decides whether there's enough evidence to answer at all.

### 5. The Voice — ears and mouth (cloud)
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

Deployment is a spectrum, and where we draw the line is the whole game. **Decided
model: one unified cloud we operate, with per-tenant data isolation** (see
[decisions/2026-06-30-unified-cloud-per-tenant-isolation.md](decisions/2026-06-30-unified-cloud-per-tenant-isolation.md)).

- **Unified cloud + per-tenant isolation (the default).** One control plane we run
  and update, but every company's corpus, embeddings, and keys live in separate
  stores — never pooled across customers. Simplest to operate; isolation is
  enforced in software and tested.
- **Single-tenant / in-customer-cloud (enterprise upsell).** The customer's own
  isolated stack, or deployed into their cloud, for buyers who contractually
  require it. Stronger isolation, more ops — a paid tier, not the default.
- **Local tier.** Everything on the user's machine, for the most regulated /
  air-gapped customers. Degraded but still honest — cite-or-unknown never degrades.
- **Naive pooled multi-tenant — never.** Pooling one company's source with
  another's is the one thing we don't do.

When compute is remote, trust is held by **controls, not slogans**. Today that
means caller-scoped GitHub authorization on every private read, a dedicated
paid writer path whose terms prohibit product-improvement use, local embeddings,
counts-only analytics by default, content-free application logs, deletion,
secret references, and a persistent repository-scoped store. Zero data
retention is **not** a current claim: Google
may keep limited abuse-monitoring logs unless the project receives ZDR approval,
and Icarus deliberately retains the project memory it exists to preserve. Real
compliance, separate tenant keys/stores, audited break-glass operator access and
customer-held-key options remain sellability work. The customer's asset (source
code + decision history) is more sensitive than dictated text, so these controls
are the floor, not a premium add-on.

## The data journey of one question

1. You hold the hotkey and speak. *(laptop)*
2. Your voice becomes text. *(cloud)*
3. The Librarian finds the most relevant evidence. *(cloud)*
4. The honesty gate checks: is there enough to answer? If not → "no one recorded
   this." *(cloud)*
5. If yes, the AI writer turns the evidence into a colleague-style answer + the
   exact citations. *(cloud)*
6. The answer is spoken back; the overlay shows the proof. *(cloud → laptop)*
7. Icarus does not persist the answer body by default. The repo-scoped shared
   ledger retains the question, verdict, reason, citation refs, and timestamp
   without the asker's identity; this is what makes Memory Gaps observable.
   The indexed corpus and confirmed decisions remain durable until deletion.
   The paid writer may separately retain a limited abuse-monitoring record under
   its terms unless ZDR has been approved for the production project. *(cloud)*

When the result is an actionable `no_recorded_reason`, the engineer can
explicitly propose an engineering-memory record. The server verifies the
active opaque gap ID and caller, then uses that caller's in-memory GitHub
credential to create exactly one deterministic branch, one Markdown file, and
one pull request. Replays discover and return that same proposal, including
after an ambiguous GitHub response; they do not create duplicates. The server
persists the observed pull-request URL and moves the gap from `open` to
`proposed` before claiming success. It never merges. Only a later cited answer
after merge and re-index moves the gap to `resolved`.

For a coding agent, steps 1–2 and 6 become a structured MCP exchange: the agent
names the expected repository and asks a focused question, the adapter refuses a
repo mismatch, and the HTTP brain returns a self-identifying repo/commit payload.
If no development override is present, the adapter obtains its short-lived
public-read session from the signed-in Mac app; the GitHub credential never
enters the agent process. The honesty gate is unchanged. Retrieved-but-uncited
evidence can inform a plan, but it never becomes an asserted reason.

## The Claude-first Agent Mode capture loop

The first vertical slice observes one Claude Code checkout only after explicit
setup in the Mac app. `SessionStart` fetches a bounded repository-scoped intent
projection. `Stop` reads Claude's local JSONL transcript only long enough to
verify that the current user turn called exactly one of the two capture tools;
Icarus never sends or stores the raw prompt, assistant prose, or transcript.

One consequential choice becomes one pending card: a recommendation, rationale,
one to three alternatives, and up to twenty affected paths. The normal human
path is a single click; **Other** is the only path that asks for text, and **Not
sure** safely defers. Pending, rejected, and Not sure candidates are never
delivered to another agent session.

An accepted choice is written through the existing bounded GitHub writer as one
deterministic branch, one marked Markdown document, and one pull request. While
the document is absent from the active index, fresh sessions see it only as a
`human-confirmed · proposal · not indexed` receipt; absence does not claim the
pull request is still open. After merge and re-index, the active corpus—not the local
ledger—promotes the document to `human-confirmed · merged · cited`. The marker
and indexed citation also reconstruct that intent after local ledger loss. An
ordinary or unmarked document cannot enter this projection.

Capture measurement is counts-only: candidate, no-decision, and resolution
events, with the fixed resolution choice enum. Repository slugs, session IDs,
decision text, rationale, alternatives, affected paths, and Other text do not
leave through analytics.

## Open architecture questions (decide as we build, not now)

- Which embedding model and vector store to start with (rent vs open).
- How the Mac app authenticates each engineer to the company's private brain.
- How GitHub access is granted and scoped (PAT vs GitHub App) and how the
  initial ingest is kept fresh.
- Latency budget split across speech-in, retrieval, synthesis, and speech-out
  (see [METRICS.md](METRICS.md)).
