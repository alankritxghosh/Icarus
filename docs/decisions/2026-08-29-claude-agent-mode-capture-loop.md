# Claude-first Agent Mode capture loop

- **Date:** 2026-08-29
- **Status:** Accepted for the one-repository vertical slice.

## Decision

Agent Mode is not a prompt tweak or an autonomous coding agent. Its first slice
is a continuity and judgment scaffold for a novice builder using Claude Code:
explicitly observe decision-shaped turns, propose one atomic interpretation,
let the person confirm it with one click or choose an alternative, Other, or Not
sure, and carry only confirmed intent into a fresh session.

A `CLAUDE.md` file remains useful for telling Claude when to act, but it cannot
be the product boundary. It cannot independently provide a human confirmation
surface, keep raw-session data out of durable memory, enforce repository and
credential scope, create a reviewable receipt, distinguish an open proposal
from merged truth, or reconstruct accepted intent after a fresh session.

## Lifecycle and receipts

| State | Authority | May enter a fresh session? | Receipt |
|---|---|---:|---|
| Agent recommendation | coding agent | No | pending candidate ID |
| Not sure or rejected | person | No | append-only resolution event |
| Human-confirmed proposal | person + observed GitHub write | Yes, labelled proposal/not indexed | pull-request URL; current PR state not inferred |
| Accepted project intent | merged, re-indexed repository | Yes, labelled merged and cited | indexed `doc:` ref at commit |

The coding-agent grant may read existing context and append a bounded candidate
or no-decision acknowledgement. It cannot confirm a choice and never receives a
GitHub credential. Confirmation is a Mac-app action authenticated with the
caller's GitHub bearer. The GitHub writer creates but never merges one
deterministic branch, document, and pull request.

The generated Markdown carries a versioned decision marker. When that exact
document appears in the active indexed corpus, Icarus can promote and reconstruct
the decision using a real citation even if the local operational ledger was
lost. Until then it remains visibly absent from indexed truth; Icarus does not
infer from that absence whether the pull request is open, merged, or later
removed. No model decides this transition.

## Observation and privacy boundary

Setup is explicit and project-local. The SessionStart hook requests only the
bounded confirmed-intent projection. The Stop hook reads the Claude JSONL file
locally and scans only the current turn for the two capture tool names. It has a
loop guard and never exports or persists raw prompt text, assistant prose,
transcript content, secrets, or user identity.

Durable candidate fields are limited to decision, rationale, one to three
alternatives, and up to twenty repository-relative paths. The raw Claude session
ID is hashed before local persistence. Analytics receives counts, surface, an
optional salted repository pseudonym, and the fixed resolution enum only.

## Scope and deliberate omissions

This slice is Claude-first and one repository at a time. It does not silently
watch the screen, ingest arbitrary conversations, merge pull requests, judge
whether a confirmed choice was technically good, build the eventual graph UI,
or react to every push. Those belong only after this loop's capture rate,
accept/correct/defer rate, latency, and trust failures are observed in real use.

The cite-or-unknown boundary is unchanged: ordinary historical answers still
pass through the existing gate. Agent Mode adds a separate deterministic state
boundary, and a decision becomes merged truth only when its marked document is
actually present in the active repository corpus.
