# Content pillars & the standing inventory

Two jobs. **Top half:** what each pillar is for. **Bottom half:** the standing
inventory — real, unposted material already sitting in the repo and the vault.

> **The rule this file exists to enforce:** inventing an idea while real ones sit
> unposted is a process failure. If a slot cannot be filled from below or from
> today's actual work, post fewer. (Vault § Sustainability.)

---

## The four pillars

| Pillar | /day | Job |
|---|---|---|
| Personal | 2 | Reach. The only category with measured outperformance. Sourced from **work done**, never defeats confessed. |
| AI / papers | 2 | Recruits the primary segment. Strictest verification standard in the system. |
| Agentic findings | 1 | Nearest-adjacent to the product without being an ad. Where the unique material lives. |
| Icarus | 1 | Deliberately smallest. Rotate insight → story → capability → limitation. Never two consecutive pure-product days. |

Weights and reasoning: vault § Cadence & mix. Do not re-derive them here.

### The Icarus rotation, tracked
Aug 13 insight → 14 capability → 15 story → 16 ask → 17 limitation → 18 insight.
**Next up: story or capability.** Two limitation-adjacent posts ran back to back
(Aug 17, 18); if both perform, that is a pattern worth reading (vault note).

---

## Standing inventory — unposted, verified, ready

Each entry: the fact, its source in the repo, and the pillar it belongs to.
Every number below was read out of the repo or the vault, not recalled.
**Strike an item when it ships**, and note where it went.

### Agentic findings (the strongest reserve — nobody else has this material)

1. **The 60-second timeout that looked like an internal fault.** Two `-32603
   Internal error` failures were a flat 60s ceiling, not a bug: transcript
   timings 61.1s and 60.2s against 16.1s for the same tool succeeding. Three
   live replays: 52.1 / 62.0 / 50.8s — one in three crosses the ceiling.
   *Source: `docs/experiments/2026-08-14-get-task-context-timeout-reproduction.md`.*
   **Angle:** a latency distribution straddling a timeout looks like a random
   internal error. Two defects stacked, the second hiding the first.

2. **An agent declared a live bug fixed because only the merge was visible.**
   *Source: `docs/experiments/2026-08-10-agent-mode-exp-d-efficiency.md`.*
   Contrast-shaped, and it is the single most legible statement of the wedge.

3. **The prediction that was wrong, in writing, before the run.** Directed
   consultation: the registered prediction said control would win; control did
   the better first-principles code reading *and would still have shipped an 8th
   duplicate*. One directed call surfaced seven prior attempts and flipped the
   recommendation to "do not write this."
   *Source: `docs/experiments/2026-08-10-agent-mode-exp-d-directed.md`.*
   **This is a finding about agents, not a confession** — the no-failure rule
   does not block it.

4. **Closed ≠ rejected, the 9-PR tally.** Eight of nine closed-unmerged PRs meant
   "already done another way." *Source: [[Agent Mode]], C2 results.* Already
   drafted at 215 chars in the vault; unused.

5. **Rejection conflation, second axis.** `review_required` is not evidence
   nobody reviewed — a dismissed approval, a resolved change request and a plain
   comment all land there. *Source: `evals/attempts.py`.* Harder to post,
   genuinely non-obvious, aimed squarely at the dev-tool-builder segment.

### AI / papers
6. Standing rule, not material: **title, authors, venue/arXiv id verified before
   drafting, every time.** Four papers already shipped this way (2605.21404 —
   drafted, unused; 2605.05726; 2602.02007; 2602.05892; 2602.11988).
   The unused twelve-benchmark disclosure audit (arXiv:2605.21404) is verified
   and ready.
   **The pipeline is the constraint here**, not the writing: 2/day needs ~14
   genuinely-read papers a week. If that is not happening, cut the slot to 1.

### Personal (work done, specifics intact)
7. **The repo as a number.** 16 pre-registered experiment records. 12 vault
   notes. 88 Python test files, 30 Swift. *Source: repo.* The angle that is
   actually interesting: **a written record of experiments that failed is a
   distribution asset almost nobody in this space has.**
8. **The vault/session loop** — already posted Aug 17. Do not repeat; extend it
   with what the loop caught that a person would have missed.
9. **Activity is not authority.** 172 contacts checked against who actually
   merges code; 41% could not merge anything. One repo: a single maintainer
   merged all 100 PRs sampled. *Source: [[Learning]].* Drafted, unused (274 chars).
10. **A raw count is not a human count.** 1,283 closed-unmerged PRs → 62 after
    filtering bots. 95% dependabot/renovate. *Source: [[Learning]].* Drafted,
    unused (249 chars).

### Icarus (insight / limitation slots — the deepest reserve)
11. **Groundedness proves a citation is real, never that it is true.** Posted
    Aug 17 as the limitation. The *unposted* half: a line-selection explain once
    cited a real Pydantic decision to explain an unrelated httpx helper — every
    citation resolved, so the gate passed it happily.
    *Source: `evals/test_explain_selection_eval.py`.*
12. **The detector that was anti-correlated with truth.** Built a lexical
    attribution detector; a plausible fabrication scores *higher* on overlap with
    its sources than an honest paraphrase, because it is assembled from the
    evidence's own words. Deleted it.
    *Source: `docs/experiments/2026-08-10-quotation-vs-composition-negative-result.md`.*
    **The single best post in this inventory.** Contrast, real number, a
    diagnosis rather than a defeat, and a mechanism the reader can reuse.
13. **The fabricated symbol.** Redis has no `HYPERVECTOR` type; real adjacent
    vector-set code let a writer answer as if it did. Fixed with an
    entity-presence guard. *Source: `evals/gate.py` guard (c).*
14. **Doc evidence reaching the writer at 16%.** A 9,549-char file arrived under
    a 1,500-char cap while code got 10,000 — one section survived, seven were
    cut, and nothing reported it, because a citation into the surviving 16%
    resolves. *Source: `evals/test_doc_evidence_truncation.py`.*
15. **Retrieval that fails on intent, not on words.** Phrasings that name the
    identifier or describe the task rank the right evidence 1st. Phrasing that
    shares no vocabulary with the evidence misses entirely.
    *Source: `evals/test_description_recall.py`.*
16. **The answer that was true in every clause and wrong in its first word.**
    "Yes, the maintainer intends to update…" answering a question whose answer
    in the cited chunk is *don't*. Every clause true, citation resolves, gate
    passes. *Source: `evals/test_writer_uses_evidence.py`.*
17. **A per-file relationship fanned across windows turned 30 real import edges
    into 56,056 emitted ones.** And resolving a Go package to its
    alphabetically-first file made 18.1% of sampled edges wrong.
    *Source: `demo/structure.py`.* 199 edges sampled after the fix, 0 unverified.
18. **93% of citations in a ten-repo onboarding probe came from history** (58
    commit + 17 pr + 14 issue) against 2 doc and 1 code. *Source:
    `evals/onboarding_probe.py`.* Argues the wedge with someone else's repos.

### Do not post
- Anything shaped as a changelog of our internals (standing rule, vault 2026-08-17).
- Anything where the interesting number is only interesting if you already care
  about our MCP surface.
- The 0-replies, 0-conversions, ~104-send outreach numbers, or any other zero of
  ours. (No-failure-disclosure rule.)

---

## Refill protocol

The inventory above is roughly **6–8 weeks at 1 Icarus + 1 agentic per day.**
It is not self-replenishing. It refills from exactly three places:
1. `docs/experiments/` — a new pre-registered run.
2. The vault's `Learning.md` — a reproduced failure and what it cost.
3. A live session that surprises you. **Capture it the same day**; the detail
   that makes it postable is the first thing you forget.
