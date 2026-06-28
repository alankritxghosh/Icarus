# Icarus

This repository is **Icarus**, the commercial engineering-brain product. It is
not Alankrit's personal JARVIS, and not the personal memory system under the
parent workspace.

## Product identity

Icarus is a privacy-first **conversational engineering brain** a company can buy.
It learns a company's codebase and the decisions around it, and lets engineers
hold a hotkey and ask *why*, *what*, or *how* — answering out loud like a
colleague, with citations shown in a translucent overlay, and an honest
"no one wrote this down" when the reason was never recorded.

Version 1: **GitHub** as the source, a **macOS app + voice (hotkey) + overlay** as
the interface, running on a **per-company private cloud** brain.

Read [docs/VISION.md](docs/VISION.md) for the north star.

## The one non-negotiable

**Icarus cannot bluff.** It answers only from evidence it actually retrieved, and
says "I don't know" when the answer was never written down. The honesty gate
stays primarily **deterministic and auditable** — "I don't know" must be provable
in code, never a black-box guess. This property never degrades, on any tier, in
any phase. Every change must preserve it.

## Current stage

**Pre-build / planning.** The repository currently holds the foundation docs
only. Building starts at Phase 1 in [docs/BUILD_ORDER.md](docs/BUILD_ORDER.md):
the brain in text — type a question about one GitHub repo, get a cited answer or
an honest unknown, measured by the evaluation harness.

The previous product (JARVIS Engineering Intelligence) is archived in git: tag
`jarvis-v0`, branch `archive/jarvis-v0`. It is reference history, not a
dependency — do not build on it.

## Hard boundaries

- **Personal and commercial stay isolated, always.** Do not read, edit, ingest,
  summarize, migrate, or depend on any personal memory system (e.g. anything
  under `../brain/`). Never mix personal context into Icarus.
- **Do not touch files outside this repository** unless explicitly asked.
- **Do not add model calls, vector stores, servers, UIs, agents, or integrations
  ahead of the phase that approves them** in [docs/BUILD_ORDER.md](docs/BUILD_ORDER.md).
- **Do not claim capabilities the evaluation harness hasn't proven** (structural
  analysis, dependency tracing, org-wide reasoning, autonomous coding). Until
  proven, the honest answer is "unsupported."
- **A credential is a responsibility.** Every credential and every byte that
  leaves the trust boundary is a deliberate, minimized decision.

## Architecture in one line

The Mac app is the *face* (hotkey, mic, overlay); the cloud is the *brain*
(librarian, search, AI writer, speech), rented privately per company, never
trained on, discarded after each request. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), including what we rent vs build.

## Required workflow

Before changing code, and after, follow [docs/WORKFLOWS.md](docs/WORKFLOWS.md).
The short version:

- **Prove the gap with a failing eval before changing the brain** (red → green).
- **Never weaken the benchmark to pass.**
- **Keep edits scoped to the current phase.**
- **After changes:** run the evals/tests, then report files changed, results,
  risks, and the next recommended brick. No success claims without evidence.

## Out of scope for now (post-Phase-4 unless a task says otherwise)

- Data sources beyond GitHub (Slack, Linear, Notion, org-wide ingestion).
- Deep structural code understanding / dependency tracing.
- Autonomous coding-agent behavior.
- Managed multi-tenant deployment as a default.
- Any use of personal JARVIS memory.

## Commands

The toolchain will be defined when Phase 1 begins (the build stack — Mac app
language, cloud service language, eval runner — is an open decision in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)). This section gets filled in with
the real test and run commands as soon as there is code.
