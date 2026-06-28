# Icarus — Engineering Workflows

How we work while building Icarus. The product's promise is honesty; the way we
build it has to be honest too. These are the rules of the road for every change,
human or agent.

---

## The prime directive

**One honest brick at a time.** Each change moves toward the vision without
breaking the one property that makes Icarus worth trusting: it knows the
difference between what it can prove and what it's guessing. If a change can't
explain how it preserves cite-or-unknown, it doesn't ship.

## Tests and evals before expansion

- **Prove the gap before you fill it.** A new capability starts as a failing
  evaluation case (see [EVALUATION.md](EVALUATION.md)), then becomes code that
  turns it green. Red first, then green.
- **Never weaken the benchmark to pass.** If an eval is red, fix the brain, not
  the test. Deleting or softening a failing case is forbidden.
- **No capability is claimed before it's proven.** We do not say Icarus can do
  structural code analysis, dependency tracing, or org-wide reasoning until an
  eval demonstrates it. Until then the honest answer is "unsupported."

## Before changing anything

1. Read [VISION.md](VISION.md), [ARCHITECTURE.md](ARCHITECTURE.md), and
   [BUILD_ORDER.md](BUILD_ORDER.md) — know which phase you're in.
2. Check the current git state.
3. Identify the task type: planning, evaluation-writing, implementation, or
   verification. Keep edits scoped to that task.
4. Confirm the change belongs to the **current** phase, not a future one.

## After changing anything

1. Run the evaluation harness and the test suite.
2. Report: files changed, evals/tests run, failures, risks, and the next
   recommended brick.
3. State plainly what is proven and what is still unknown. No success claims
   without evidence.

## Scope discipline (the hard boundaries)

- **Personal and commercial stay isolated, always.** Do not read, ingest,
  summarize, or depend on any personal memory system. Icarus is the commercial
  product; it never mixes in personal context.
- **Don't touch files outside this repository** unless explicitly asked.
- **Don't add infrastructure the current phase hasn't approved** — no new model
  calls, vector stores, servers, UIs, or integrations ahead of their phase in
  [BUILD_ORDER.md](BUILD_ORDER.md).
- **A credential is a responsibility.** Every new credential (GitHub first) and
  every byte that leaves the trust boundary is a deliberate, minimized decision.

## Agent roles

- **Opus** — principal architect and adversarial reviewer. Product wedge,
  architecture, privacy/security, and scope critique.
- **Sonnet** — implementation reviewer, adversarial eval/test writer, and bounded
  implementer when explicitly asked.
- **Codex** — deterministic fixer, verifier, and integration worker.

If role instructions conflict, prefer the narrowest safe interpretation and
report the conflict.

## Definition of done (for any brick)

A brick is done when:
1. A previously-failing eval or test is now green, and nothing else regressed.
2. The change is scoped to the current phase.
3. cite-or-unknown is provably intact.
4. The next recommended brick is written down.

Anything short of all four is "in progress," and we say so.
