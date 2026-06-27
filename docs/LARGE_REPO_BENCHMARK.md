# Large Repo Benchmark

This benchmark is the product exam for JARVIS Engineering Intelligence.

Small fixtures prove the code path works. Large, old public repositories prove
whether the product can handle the kind of engineering context gap that real
teams feel.

## Purpose

The benchmark asks real engineering-context questions against large local Git
checkouts. Each question should prove one of three things:

- JARVIS can find documented decisions and rationale.
- JARVIS can cite the strongest available evidence.
- JARVIS refuses unsupported questions instead of pretending.

The benchmark lives in `benchmarks/large_repos.json`.

## Repositories

The first benchmark set uses:

- `pallets/flask`
- `backstage/backstage`
- `open-telemetry/opentelemetry-specification`
- `zalando/restful-api-guidelines`
- `alphagov/govuk-design-system`

The local checkouts are expected under:

```text
~/jarvis_test_repos
```

## Question Types

Supported question types:

- documented decision
- architecture decision
- decision evolution
- honest unknown

Unsupported question types:

- change-impact analysis
- dependency tracing
- reverse dependency tracing
- protected personal-data traversal

Unsupported questions are intentional. They protect the product boundary.
JARVIS should return an unsupported or isolation error, not a fake answer.

## Scoring

Each supported question is scored out of 10:

- 2 points: finds the strongest relevant evidence
- 2 points: cites the evidence clearly
- 2 points: answers in plain English
- 2 points: avoids hallucinated claims
- 1 point: states limitations honestly
- 1 point: finishes in acceptable time

Readiness guide:

- 8-10: demo-usable
- 6-7: promising, but needs repair
- below 6: not demo-ready

Unsupported questions pass only when JARVIS refuses them clearly.

## Day 1 Scope

Day 1 creates the exam paper only:

- benchmark data
- expected evidence hints
- refusal cases
- plain-English benchmark documentation

Day 1 does not build the full benchmark runner, a Mac app, voice input, an index,
or model-based synthesis.

## Next Step

The benchmark runner is available as:

```sh
jarvis-benchmark
jarvis-benchmark --format text
jarvis-benchmark --repo backstage/backstage --format text
jarvis-benchmark --question backstage-luxon --format text
```

It executes `large_repos.json` against the local checkouts and records:

- pass/fail by question
- cited evidence paths
- unknown findings
- unsupported refusals
- runtime

That runner is the weekly measure of whether the evidence engine is actually
improving on real repositories.

The runner supports JSON for automation and text output for a human scoreboard.
The next improvement is speed: full large-repo runs are slow because they inspect
real large checkouts repeatedly.
