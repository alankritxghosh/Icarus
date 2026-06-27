# Agent Protocol

Use this protocol when Opus, Sonnet, Codex, or another coding agent works on this repository.

## Role Boundaries

- Opus: product and architecture reviewer. It should challenge the wedge, find security/privacy risks, and recommend bounded next tasks.
- Sonnet: implementation reviewer and test writer. It should write adversarial `unittest` coverage and handle small bounded changes only when explicitly asked.
- Codex: deterministic fixer and verifier. It should make scoped source changes against failing tests and run verification.

Do not let one agent silently take over another agent's role.

## Required Start Checklist

Every agent must start by checking:

1. `CLAUDE.md`
2. `docs/PROJECT_STATE.md`
3. This file
4. `git status --short`
5. The user's latest task

## Handoff Format

Every handoff must include:

- What changed.
- Files touched.
- Tests or checks run.
- Known failures or risks.
- Exact next recommended step.

If no files changed, say that clearly.

## Conflict Rules

- If docs and code disagree, report the mismatch and treat code/tests as the current truth.
- If product claims exceed implementation, narrow the claim or mark the capability unsupported.
- If personal JARVIS context conflicts with commercial JARVIS context, commercial repo context wins inside `jarvis_engineering`.
- If an instruction would touch `../brain/`, stop and ask for explicit confirmation.

## Safety Rules

- Do not edit unrelated files.
- Do not introduce dependencies without explicit approval.
- Do not add hidden network calls.
- Do not write product code during a review-only task.
- Do not change source during a test-writer-only task.
- Do not treat passing tests as proof of product value.

## Work Sequence

Default sequence:

1. Opus reviews strategy, architecture, and risks.
2. Sonnet writes failing adversarial tests.
3. Codex fixes source against those tests.
4. Run the complete test suite.
5. Update `docs/PROJECT_STATE.md` only when the real state changes.
