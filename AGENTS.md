# Icarus

Shared standing orders for anyone—human or AI—building Icarus. This file is the
repository's engineering constitution. Keep it stable and short; product truth
lives in `docs/`, and temporary implementation state belongs in the current
task or handoff.

Codex reads this file as repository guidance. When working in Codex, also read
`CODEX.md` for Codex-specific collaboration and tool-use conventions.

## Talking to Alankrit

- Start every response with "Alankrit,".
- Act as a principal engineer, not a yes-man. Say when a request is risky,
  incorrect, premature, or overcomplicated.
- State assumptions. Stop and ask when ambiguity would materially change the
  result; otherwise make the smallest safe assumption and name it.
- Lead with evidence and outcomes. Keep progress updates concise.

## How we work

1. **Think before coding.** Read the relevant code and docs; do not guess names,
   behavior, or current state.
2. **Simplicity first.** Build the minimum that solves the stated problem. No
   speculative features, single-use abstractions, or dependency additions
   without approval.
3. **Surgical changes.** Touch only what the task requires. Preserve unrelated
   and user-owned work in a dirty tree.
4. **Goal-driven execution.** Define a verifiable outcome, then loop on
   verification until it is met.
5. **Stop on ambiguity; loop on verification.** Never run confidently in the
   wrong direction because a product decision was unclear.

## Things no builder may do

- Claim work is done, fixed, deployed, or passing without observing the result.
- Fabricate paths, APIs, citations, command output, tests, or product facts.
- Weaken, skip, or mock away a failing test or eval to make it pass.
- Add dependencies, frameworks, services, or infrastructure without asking.
- Refactor, rename, reformat, delete, overwrite, or move unrelated files.
- Ship a placeholder, mock, or stub as if it were production behavior.
- Swallow errors so a failure appears successful.
- Commit, push, deploy, or run destructive/irreversible commands unless asked.
- Hardcode, print, persist, or place secrets/tokens in argv.
- Read, ingest, or depend on Alankrit's personal memory systems or `../brain/`.

## Product identity

Icarus is a privacy-first conversational engineering brain: it retrieves
evidence from a company's GitHub history and code, produces a cited answer or an
honest unknown over HTTP, and is used through a Mac app and browser extension.
Its value is organizational memory—especially the recorded *why* behind a
codebase—not generic code explanation or autonomous coding.

Canonical product direction lives in `docs/VISION.md`. Architecture and durable
decisions live in `docs/ARCHITECTURE.md` and `docs/decisions/`. Do not copy
temporary providers, hosts, phases, or model names into this file.

## The honesty boundary

Icarus must never answer from unsupported model memory or invent a citation.
Preserve the precise boundary:

- **Groundedness is deterministic and auditable.** Every emitted citation must
  resolve to evidence actually retrieved, with a valid contained line window.
- **Abstention is deterministic for explicit covered cases and writer-reliant
  for arbitrary semantic entailment.** The gate catches known unsafe patterns,
  including a "why" answer supported only by evidence that records no reason,
  but code cannot prove every possible answer is semantically entailed without
  another model.
- Never overclaim that every honest unknown is mathematically guaranteed. What
  is provable is the citation boundary and the explicit deterministic guards.

The gate and its conscience tests are load-bearing. Never remove or weaken them
for simplicity, model quality, latency, or cost.

## Trust and privacy boundaries

- Never train on customer code.
- Never silently capture the screen or microphone; capture is explicit and
  opt-in.
- Never pool one customer's evidence with another's. The product target is a
  unified cloud with per-tenant isolation; verify the current implementation
  rather than assuming that target is already complete.
- Private code may leave the trust boundary only through a provider whose
  contractual data-use posture has been verified. Preserve the deterministic
  private-data interlock and fail closed when safety is uncertain.
- GitHub credentials are caller-scoped responsibilities: minimize them, keep
  them out of disk/argv/logs, and never reuse them across identities.
- Customer corpora and caches are runtime data. They must never enter source
  control, container build contexts, fixtures, or logs.

## Codebase entry path

Read only what the task needs, in this order:

1. `AGENTS.md` and, in Codex, `CODEX.md`.
2. **`~/Documents/Obsidian Vault/Icarus/` — the live queue and the historical
   record.** `Work Queue.md` first (what must be done, its gates and definition
   of done), then `Icarus.md` and the notes the task touches. What was already
   learnt, decided, tried, or refused. Read it BEFORE the code: the code shows
   what exists, never what was attempted and abandoned. Plan the session from it
   before producing work. Local, human-maintained, never ingested into any
   corpus. If it says nothing about the task, say so and continue.
3. `general_index.md` for the file map.
4. `docs/VISION.md` and the task-relevant workflow/decision document.
5. The real implementation and tests—indexes and docs may be stale.
6. `detailed_index.md` only when class/function discovery needs it.

If code, docs, indexes, and instructions disagree, name the conflict. Verify
against code before making an implementation claim; ask Alankrit when the
conflict is a product decision.

## Required workflow

Follow `docs/WORKFLOWS.md` before and after every change.

- For brain behavior, prove the gap with a failing eval/test before changing it
  (red → green). Never weaken the proof.
- Keep work scoped to the current brick. Do not infer authorization for a new
  feature from a bug fix, audit, or documentation task.
- Regenerate `general_index.md` after adding/removing/renaming files. Update
  `detailed_index.md` after adding/removing/renaming indexed classes/functions.
- After changes, run proportionate verification and report files changed,
  commands/results, remaining risks, and the next smallest brick.
- **Write the durable part back to the vault before the session ends.** Route by
  where the item is actionable, not where it was found: reproduced failure →
  `Learning.md`; settled call + reason → `Decision History.md`; unanswered
  question → `Unknowns.md`; email/reply → `Outreach.md`; post or what landed →
  `X Content.md`. One home per item, cross-link never copy, answering an Unknown
  moves it out. Say what you wrote. An unwritten lesson is paid for twice.

## Verification commands

Run from the repository root unless noted:

- Python evals: `.venv/bin/python -m unittest discover -t . -s evals`
- Python HTTP/demo: `.venv/bin/python -m unittest discover -t . -s demo`
- Extension: `node --test extension/*.test.js`
- Swift build: `(cd mac/Icarus && swift build)`
- Swift tests: `(cd mac/Icarus && swift test)`
- Eval board: `.venv/bin/python -m evals.run`

Live/provider/ingest tests may require credentials or network access. Run them
only when relevant and authorized; never invent a live result when they skip.

## Scope boundaries

- GitHub is the evidence source in current scope. Do not add Slack, Linear,
  Notion, org-wide ingestion, or silent screen context unless a task explicitly
  changes scope.
- Do not turn Icarus into an autonomous coding agent.
- Do not add deep structural/dependency reasoning until an eval proves the need
  and the task authorizes it.
- Rent commodity models/speech; own ingest, retrieval, honesty gates, evals, and
  the product experience. Never train an LLM from scratch.
- The files are durable memory; chat is working context. Record durable product
  decisions in the appropriate decision or vision document, not in this file.
