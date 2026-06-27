# JARVIS Engineering Intelligence

JARVIS Engineering Intelligence is a local-first system for understanding why
software is structured the way it is.

The first product slice is deliberately read-only. It analyzes a local checkout
of a public GitHub repository, pins the analysis to an immutable commit, and
produces evidence-backed findings about architecture and engineering decisions.

It does not write code, modify repositories, or access the personal JARVIS
memory stores.

## Product promise

JARVIS should help an engineering team answer:

- Why does this component exist?
- What evidence supports an architectural decision?
- Where do documentation and implementation disagree?
- Which important questions cannot be answered from current evidence?

Every material claim must cite repository evidence. Author intent is reported
as unknown unless it is explicitly documented.

## Isolation

This directory is a standalone project. It must never:

- import from the sibling `brain` package;
- read personal JSONL files;
- scan the parent workspace or home directory;
- share prompts, indexes, caches, credentials, or storage with personal JARVIS;
- write to an inspected repository.

The product can infer the local checkout and GitHub URL from the current Git
repository, but it never reads personal JARVIS memory stores and still refuses
protected paths.

## Current milestone

```text
Local Git checkout
+ engineering question
-> immutable repository identity
-> bounded evidence collection
-> observed / inferred / unknown findings
-> citations and warnings
```

Code generation, GitHub authentication, private repositories, issue ingestion,
agent execution, and pull requests are intentionally out of scope.

## Usage

Install the local console command:

```sh
pip install -e .
```

Set the safety boundary once before using the CLI. This should point at the
private workspace root that JARVIS must not inspect:

```sh
export JARVIS_PROTECTED_ROOT="/Users/alankritghosh/JARVIS "
```

Then ask from inside any allowed Git checkout:

```sh
cd /Users/alankritghosh/jarvis_test_repos/backstage
jarvis-engineering
```

Then chat normally:

```text
JARVIS Engineering online. Ask this repo a question. Type exit or quit to leave.

You > Why did Backstage choose Luxon?
```

JARVIS prints a short readable answer with evidence, limits, and warnings.
For one-shot use, you can still ask directly:

```sh
jarvis-engineering "Why did Backstage choose Luxon?"
```

For the full machine-readable evidence packet:

```sh
jarvis-engineering "Why did Backstage choose Luxon?" --format json
```

Or point at a checkout explicitly:

```sh
jarvis-engineering /Users/alankritghosh/jarvis_test_repos/backstage "Why did Backstage choose Luxon?"
```

If a repo has no canonical GitHub origin, pass the URL:

```sh
jarvis-engineering --github-url https://github.com/example/repo "Why was this decision made?"
```
