# Contributing to Icarus

Icarus answers questions about a codebase, cites its evidence, and says "no one
wrote this down" when the answer was never recorded. That last part is the
product. Everything below exists to protect it.

This repository is private and pre-launch. In practice you are here because you
are working on Icarus directly, or you are an AI agent doing so. Either way the
rules are the same, and they are enforced by tests rather than by review.

If you only read one thing: **never make a test or an eval pass by weakening
it.** Fix the code, not the check.

---

## The one non-negotiable

Icarus must not bluff. Concretely:

- **Groundedness is provable in code.** Every citation resolves to evidence
  that was genuinely retrieved, with a valid, contained line window. This is
  enforced deterministically in [`evals/gate.py`](evals/gate.py) and it must
  never degrade on any path, tier, or surface.
- **Abstention is code-enforced for the clear case and writer-reliant beyond
  it.** Be precise about this when you write or speak about it. Do not claim
  "I don't know is always provable in code" — that overclaims. See the honesty
  section in [`CLAUDE.md`](CLAUDE.md).

Any change that touches retrieval, the writer prompt, or the gate must show the
eval board still green **before** it lands. A change that improves an answer
while dropping citation correctness is not an improvement.

---

## Setting up

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # add your own keys; .env is git-ignored
./scripts/install_hooks.sh    # wires .githooks (secrets scan on every commit)
```

Run the hook installer. The pre-commit hook **blocks** a commit containing
anything secret-shaped and **warns** (never blocks) on failing tests.

Most of the brain is Python standard library. The only runtime dependency is
`fastembed` for local embeddings, plus `tree-sitter` for AST chunking. That is
deliberate — see "Adding a dependency" below.

---

## Running the checks

Run all of these before you claim anything works. From the repo root:

```bash
python3 -m unittest discover -t . -s evals    # the brain + honesty harness
python3 -m unittest discover -t . -s demo     # the server, map, tour, ledger
```

The `-t .` is required — without it the package-relative imports fail.

```bash
python3 -m evals.run                          # the eval board, offline baseline
./scripts/scan_secrets.sh                     # what the pre-commit hook runs
```

The board against the real writer, which is what actually proves the honesty
gates (needs `GEMINI_PAID_API_KEY`):

```bash
.venv/bin/python3 -m evals.run --pipeline gated --writer gemini-paid
```

It exits non-zero **only** when an honesty gate breaks. Quality below target is
a red baseline to improve, not a build failure.

Other surfaces:

```bash
cd mac/Icarus && swift test                   # the Mac app's testable logic
node --test extension/*.test.js               # the browser extension
```

---

## How to make a change

**1. Prove the gap first.** Write a failing test or eval that demonstrates the
problem before you touch the code. Red, then green. If you cannot write a check
that fails today, you probably do not yet understand the problem.

**2. Keep it surgical.** Touch what you must. Do not refactor unrelated code,
rename things you are passing through, or reformat files you are editing.

**3. Prefer the simplest thing that works.** No abstractions for single-use
code, no configuration for a value that never changes, no interface with one
implementation.

**4. Verify before you claim.** Run it and read the output. "This should work"
is not a result. Do not report a test as passing, a command as succeeding, or a
deploy as live without having seen it.

**5. State what you did not do.** A half-finished change that says so is fine.
A half-finished change presented as complete is not.

### Measurement before mechanism

When something looks wrong, measure it before building machinery to fix it.
This repo has repeatedly found that the obvious fix was wrong:

- A pre-flight repo-size check was designed and then **dropped on evidence** —
  `facebook/react` is 1,038 MB and indexes fine while `rust-lang/rust` is
  955 MB and runs out of memory. Size does not predict failure, so any
  threshold would have blocked a repo that demonstrably works.
- The onboarding tour's steps were chosen by running seven candidates over ten
  real repositories, not by taste. Two were cut for scoring badly.
- A prompt rule added to fix one reported case dropped board citation
  correctness from 100% to 83%, confirmed by reverting and re-running.

**Do not change the writer prompt to fix a single case.** It has been tried
three times and regressed the board every time. Fix it in code, with a
measurement behind it.

---

## Things that will get a change rejected

- Weakening a test or eval to make it pass — deleting assertions, loosening
  thresholds, mocking away the thing under test, or skipping.
- Fabricating anything: file paths, function names, library methods, command
  output, test results, citations. If you do not know, say so.
- Swallowing errors (`except:` with a bare pass) to make output look clean.
- Shipping placeholder or stub code without flagging it as such.
- Hardcoding secrets, tokens, or keys. Ever.
- Committing anything under `data/` (per-user corpora) or a generated corpus
  cache.
- Reading, ingesting, or depending on any personal memory system outside this
  repository.

## Adding a dependency

Ask first. The brain is close to pure standard library on purpose: it keeps the
container small, the cold start fast, and the supply chain short. If a few
lines of stdlib will do, write the few lines.

---

## Conventions that are easy to miss

**Regenerate the index after structural changes.**
[`general_index.md`](general_index.md) lists every tracked file with a
description and is auto-loaded into every AI session. If you add, remove, or
rename a file, update it in the same commit.

**Write decisions down as you make them.** The files are the memory; a chat is
not. A decision that only exists in someone's head will be re-litigated.
[`docs/HANDOFF.md`](docs/HANDOFF.md) is the one document kept current
session-to-session — read it first, and update it when you finish something.

**Comments explain *why*, not *what*.** The valuable comment in this codebase
is the one recording the measurement, the bug that forced a line, or the
approach that was tried and failed. Several of them have saved hours.

**Prefer server-side.** The Mac app is a renderer. Anything that can live in
the brain — content, ordering, wording, evidence resolution — should, because
improving it then costs a deploy instead of a release cycle that every user has
to install.

**Every app release must bump `CFBundleVersion`** in
`mac/Icarus/Icarus-Info.plist`. Sparkle compares that number; ship two builds
at the same value and nobody is offered the second.

**Never re-run `mac/Icarus/scripts/make_signing_cert.sh`** now that builds are
published. A new certificate changes the app's designated requirement and costs
every existing user another Keychain prompt.

---

## Commits

Conventional prefixes (`feat:`, `fix:`, `docs:`, `test:`), scoped where it
helps (`feat(app):`, `fix(map):`).

Write the body for the person who runs `git blame` in six months. What was
broken, what evidence you have that it is fixed, what you deliberately did not
fix, and what it cost. The best commit messages here read like short incident
reports, and they are the reason old decisions can still be understood.

Do not commit, push, or deploy unless that was asked for.

---

## Where to start reading

- [`CLAUDE.md`](CLAUDE.md) — the standing engineering rules, in full.
- [`docs/HANDOFF.md`](docs/HANDOFF.md) — current state and what is in flight.
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — the Mac app is the face, the
  cloud is the brain.
- [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) — the rules of the road for a change.
- [`docs/EVALUATION.md`](docs/EVALUATION.md) — how Icarus proves it is not
  bluffing.
- [`general_index.md`](general_index.md) — every file, one line each.
