# Product Contract

## Vision

JARVIS Engineering Intelligence helps engineering teams recover the reasoning
inside a codebase.

The product is not trying to become an autonomous engineer first. It is trying
to become the trusted local intelligence layer an engineer can ask:

> Why was this engineering decision made?

The answer should come from the repository itself. If the repository does not
contain enough evidence, JARVIS should say that plainly instead of inventing a
rationale.

## Product Goal

The first product goal is narrow and commercial:

> Ask a local Git checkout why an engineering decision was made, and JARVIS
> answers with cited repository evidence or says it does not know.

This goal is intentionally smaller than the long-term vision. V1 should make
one promise very reliable before adding broader intelligence: local,
read-only, reproducible repository evidence for architecture, rationale,
decision, and evolution questions.

The intended user experience should eventually feel simple:

```text
Open repo
Call JARVIS
Ask in natural language
Get cited answer or honest unknown
```

## User

The initial user is a founder, CTO, or engineer at a software company with
roughly 5 to 20 engineers.

They have a real codebase, limited time, and a practical question about why the
system became the way it is.

## Problem

The codebase records what exists. It rarely preserves why a choice was made,
what evidence supported it, what alternatives were rejected, or whether the
original assumption remains true.

This creates recurring engineering drag:

- New engineers can see the implementation but not the reasoning.
- Founders and CTOs lose decision memory as the team moves quickly.
- Old assumptions stay embedded in code after their context disappears.
- Teams over-trust guesses because checking the repository manually is slow.

## First Job

Given a public repository, explicit local checkout, configured safety boundary,
and engineering question, JARVIS returns a reproducible evidence packet tied to
an immutable commit.

For V1, supported questions are about documented decisions, rationale,
architecture, and project evolution. Unsupported questions are refused or
reported as unknown.

## Inputs

- Public GitHub repository URL.
- Explicit local checkout path.
- Configured root containing allowed checkouts.
- Configured protected root that must never be inspected.
- Architecture, decision, rationale, or evolution question.

## Outputs

- Repository URL and commit SHA.
- Evidence items with hashes and line locators.
- Findings classified as `observed`, `inferred`, or `unknown`.
- Confidence expressed as `high`, `medium`, or `low`.
- Citations for every material claim.
- Missing evidence, conflicts, and warnings.
- Clear refusal for question types V1 does not support.

## Trust Rules

1. Repository evidence outranks model knowledge.
2. A rationale requires explicit decision language.
3. Absence of evidence is not evidence of absence.
4. Conflicting evidence is shown, not silently reconciled.
5. Unsupported conclusions become `unknown`.
6. Unsupported product capabilities are refused.
7. The inspected checkout is never modified.
8. Personal JARVIS data is never read, imported, or scanned.

## Not This Milestone

- An AI coding assistant.
- An autonomous engineer.
- A Mac app, voice interface, or general UI.
- Company-wide Slack, Notion, Linear, email, or GitHub API ingestion.
- A vector database.
- A multi-agent runtime.
- Model calls.
- Dependency graph tracing or change-impact prediction.
- Semantic organization-wide code intelligence.
- Commercial use of personal JARVIS memory.
- A replacement for architecture review.

## Acceptance

The milestone is complete when the same checkout and commit produce the same
evidence report, every material claim is traceable, unsupported rationale and
unsupported capability requests are refused or marked unknown, and isolation
tests prove personal JARVIS data cannot be read.
