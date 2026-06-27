# Engineering Delegation

Models have different jobs. No model is allowed to become an unreviewed source
of truth.

## Claude Opus 4.8, high effort

Role: principal architect and adversarial reviewer.

Use for:

- challenging the product boundary;
- reviewing domain models and workflow state;
- threat modelling;
- identifying unsupported product claims;
- reviewing major architectural changes before implementation.

Opus proposes and reviews. It does not silently broaden scope or directly
approve its own implementation.

## Claude Sonnet 4.6

Role: implementation reviewer and repository analyst.

Use for:

- tracing unfamiliar code paths;
- reviewing bounded patches;
- generating additional test cases;
- checking documentation against implementation;
- preparing repository-specific analysis fixtures.

Sonnet should receive a precise file scope and acceptance criteria.

## Codex 5.5, medium effort

Role: implementation owner and verifier.

Use for:

- writing deterministic product code;
- enforcing filesystem and process boundaries;
- implementing schemas and validators;
- building tests and benchmark harnesses;
- running complete verification and integrating review findings.

Codex owns the final patch and must verify model suggestions against code and
tests.

## Required handoff format

Every delegated task must state:

- objective;
- files owned;
- files forbidden;
- inputs and expected output;
- acceptance tests;
- security constraints;
- explicit non-goals.

## Current machine status

Claude Code is installed, but must be authenticated before Opus or Sonnet tasks
can run. Until then, their assignments remain review gates rather than build
dependencies.

