# Experiment A, run 1 — Icarus → Claude Code

Date: 2026-08-10
Repo: `astral-sh/uv` @ `6253839` (working clone) — Icarus corpus at `1881d307`
Task: [issue #20477](https://github.com/astral-sh/uv/issues/20477) — relative
`tool.uv.sources` paths written as absolute in `uv.lock` since 0.10.10.

## Protocol actually followed

1. Read the issue **title + body only**. The 6 comments and PR #18176 were
   deliberately not opened.
2. Explored the code cold (6 greps, ~8 min) and **froze written priors** before
   any Icarus call. This is what makes the comparison honest rather than
   retrospective.
3. Asked Icarus 3 questions (2 × `get_change_context`, 1 × `explain_code_context`).
4. **Verified every Icarus claim against the repo** rather than accepting it.

Corpus caveat, known going in: uv's ingest is truncated to the most recent
5,000 PRs and 5,000 issues (`gh ... --state all --limit 5000` sorts
newest-first), so ~6,711 PRs and ~4,197 issues of early history are not
indexed. This task's evidence is recent, so it fell inside the window.

## Result 1 — Icarus corrected a wrong prior. Load-bearing.

My cold read concluded absolute paths looked **deliberate**: `try_relative_to_if`
exists precisely to force some paths absolute, so I assumed I might be
reverting an intentional decision, and would have proceeded cautiously.

Icarus: PR #18176 is titled *"Preserve absolute/relative paths in lockfiles"*,
labelled `bug`, merged — it was **attempting the opposite**. The absolute
behaviour is a regression in a fix, not a design choice.

Verified: true, from the PR title/labels in the citation.

This is the single most valuable output of the run. It inverts the risk
assessment of the whole task, and I would not have got it without reading
PR #18176 myself.

## Result 2 — Icarus surfaced a real constraint I had missed

`was_given_absolute()` returns `false` for expanded URLs specifically to
preserve `${PWD}` / `${PROJECT_ROOT}` users.

Verified verbatim in the doc comment at `crates/uv-pep508/src/verbatim_url.rs:264-267`.

Honest discount: this is **in the code**, not in history. My grep window
started at the `pub fn` line and cut off the docstring above it. A careful cold
read finds this. So it counts as context-surfacing, not as engineering memory.

## Result 3 — FAILURE. Icarus asserted a rule that does not exist.

Asked what constraints exist on relative paths, Icarus answered that absolute
paths are preserved when the user gives an absolute `find-links` **"or when a
relative path would require traversing outside the project root (e.g. starting
with `..`)"**.

The second half is false at HEAD:

- `relative_to` (`uv-fs/src/path.rs:377`) calls the **infallible**
  `normalize_path`, not the erroring `normalize_absolute_path`.
- Its own doc-comment gives `../../marker.txt` as a valid return value.
- A sweep for `Component::ParentDir` across all crates finds no rule in the
  lock/sources write path that forces absolute for escaping paths.

This matters because the reporter's paths are exactly `../lib-a`. Had I taken
it at face value, I would have concluded the reported behaviour was working as
designed and closed the investigation on a fabricated constraint.

**Why the honesty gate did not catch it:** every citation resolves — `pr:17122`
really is about preserving absolute `find-links`, `issue:15417` really is about
relative-path inconsistency at different directory depths. The claim is an
*over-generalisation across two real sources*, not an invented citation.
Groundedness proves the evidence is real; it does not prove the answer follows
from it. This is the documented limit in CLAUDE.md ("writer-reliant beyond the
clear case") landing in practice, on the first real task.

Notably, I had killed the same `..`-escaping hypothesis myself during the cold
read — so on this point the unaided read was *more* correct than Icarus.

## Result 4 — the output is an answer, not a context package

Each response returns ~20 `searched` refs, but every one beyond the 2-4 cited
comes back with an **empty excerpt**. So the neighbourhood Icarus found
(`pr:17316`, `pr:18402`, `issue:16602`, `issue:9692`, `issue:19081`…) arrives as
bare numbers. To turn that into the handoff's context-package format I would
still have to fetch each one myself.

This is the concrete argument for Experiment B's `icarus.context(task)`: the
retrieval is already doing the hard part and then throwing the text away at the
interface.

## Scorecard against the 8 experiment questions

1. Materially better context? **Yes, partially** — one prior inverted (Result 1).
2. Fewer incorrect assumptions? **Mixed** — corrected one, introduced one (Result 3).
3. Less time searching? **Not yet measured**; I spent more time verifying Icarus
   than the 8 min of cold search.
4. Fewer irrelevant files touched? Not applicable at this stage.
5. Fewer iterations? Not yet reached.
6. Surfaced history Claude would miss? **Yes** — PR #18176's intent.
7. Identified unknowns before implementation? **Partially** — the
   `${PROJECT_ROOT}` constraint is a genuine pre-implementation risk.
8. Repeatable workflow? **Yes, with one hard rule**: every Icarus claim must be
   verified before use. See below.

## The rule this run establishes

**Treat Icarus output as a set of leads with citations, not as findings.**
Claims about *what a PR/issue says* were reliable (Results 1, 2). A claim about
*what the code rule is*, synthesised across several sources, was not (Result 3).
The cheap discipline is: accept history claims, verify behaviour claims against
the code.

## State / what is not done

- The root cause of #20477 is **still undiagnosed**. Neither the cold read nor
  Icarus located where the absolute path is actually written. Both produced a
  mechanism map (`try_relative_to_if` / `was_given_absolute`), not a diagnosis.
- Steps 4 (implement) and 5 (full evaluation) of the protocol are not done.
- Working clone: scratchpad `.../scratchpad/uv`; priors at
  `.../scratchpad/exp-a-priors.md`.
