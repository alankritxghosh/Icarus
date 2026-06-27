# JARVIS Engineering Intelligence

This repository is the commercial JARVIS product, not Alankrit's personal JARVIS.

## Product Identity

JARVIS Engineering Intelligence is a local-first, privacy-centric engineering intelligence system for software teams. The first product wedge is documented-decision retrieval:

> Ask a local Git checkout why an engineering decision was made, and get cited evidence or an honest unknown.

The product is not an AI coding assistant yet. It is not an autonomous engineer. It is not the personal memory system under the parent workspace.

## Hard Boundaries

- Do not read, edit, ingest, summarize, migrate, or depend on personal JARVIS data under `../brain/`.
- Do not mix Alankrit's personal memory context into this commercial product.
- Do not touch files outside this repository unless the user explicitly asks.
- Do not add model calls, vector databases, servers, UIs, agents, or integrations unless a task specifically approves that scope.
- Do not claim the product can do dependency impact analysis, organizational reasoning, or autonomous coding until the implementation proves it.

## Current Architecture

- Python package under `src/jarvis_engineering`.
- Standard library only.
- CLI-first entry point from `pyproject.toml`.
- Inspects an explicit local Git checkout under an allowlisted repository root.
- Pins answers to immutable Git `HEAD`.
- Reads committed Git blobs, not dirty working-tree contents.
- Emits JSON reports with repository metadata, evidence, findings, warnings, and error codes.

## Current Priorities

1. Safety: commercial repo context must stay isolated from personal JARVIS.
2. Honesty: unsupported capabilities must return unknown or unsupported, not fake analysis.
3. Evidence quality: every material claim needs cited repository evidence.
4. Tests before expansion: prove gaps with tests before changing source behavior.
5. Narrow wedge: make documented engineering decisions reliable before building broader intelligence.

## Required Workflow

Before changing code:

1. Read `docs/PROJECT_STATE.md`.
2. Read `docs/AGENT_PROTOCOL.md`.
3. Run `git status --short`.
4. Identify whether the task is review, test-writing, implementation, or verification.
5. Keep edits scoped to the requested task.

After changing code:

1. Run `PYTHONPATH=src python3 -m unittest discover tests -v`.
2. Report changed files, tests run, failures, risks, and the next recommended step.

## Agent Roles

- Opus: principal architect and adversarial reviewer. Use for product wedge, architecture, security, privacy, and scope critique.
- Sonnet: implementation reviewer, adversarial test writer, and bounded implementer when explicitly asked.
- Codex: deterministic fixer, verifier, and integration worker.

If role instructions conflict, prefer the narrowest safe interpretation and report the conflict.

## Out Of Scope For The Current Brick

- AI coding assistant behavior.
- Multi-agent runtime inside the product.
- Slack, Linear, Notion, GitHub API, or company-wide ingestion.
- Web UI, server, API layer, or dashboard.
- Vector database or semantic retrieval.
- Personal JARVIS memory features.

## Commands

Run tests:

```sh
PYTHONPATH=src python3 -m unittest discover tests -v
```

Run the CLI:

```sh
PYTHONPATH=src python3 -m jarvis_engineering <github_url> <checkout> "Why was this decision made?" --repositories-root <root>
```
