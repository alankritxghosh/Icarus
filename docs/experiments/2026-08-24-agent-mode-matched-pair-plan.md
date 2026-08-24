# Agent Mode — matched-pair surface test: recorded vs. unrecorded history

**Status: REGISTERED, NOT RUN.** Written before any tool call, per PROTOCOL §3.
Registered 2026-08-24. Directed (PROTOCOL §6): every call in this run is made
deliberately by the operator, so this measures ANSWER QUALITY, not unprompted
call rate. It is not a C2 replication and must never be reported as one.

## Why this pair

Two repositories by the same author, on the same subject, from the same months.
One has recorded engineering history; the other has almost none. That is a
natural control for the claim [[Agent Mode]] already states:

> Icarus pays when somebody has tried something before, and contributes nothing
> when the answer was never written down.

Both halves of that sentence have been observed separately across prior runs.
Neither has been measured on matched repositories in one session.

| | live arm | null arm |
|---|---|---|
| repo | `SaravananJaichandar/world-model-mcp` | `SaravananJaichandar/coding-agent-memory-benchmark` |
| pinned commit | `5ec7fc6` (2026-08-24) | `b57d241` (2026-08-24) |
| commits | 205 | 3 |
| pull requests | 32 (30 merged, 2 closed unmerged) | **0** |
| issues | 1 | **0** |

Counts read from `gh pr list --state all` / `gh issue list --state all` on
2026-08-24, not inferred.

## PROTOCOL §2 disclosure — no valid rejected-attempt task exists here

Stated up front rather than discovered later. §2b requires a genuine
closed-unmerged pull request as the mechanism. This repo family cannot supply
one:

- benchmark repo: zero pull requests. Nothing to select.
- world-model-mcp: two closed-unmerged. `#1` is third-party badge spam
  (`OyaAIProd`, "SafeSkill security badge"). `#23` is the author's own
  self-close, stacked on `#22` and superseded by it — the exact
  **rejection-conflation** case already recorded in [[Agent Mode]], where an
  unreviewed self-close is not a refusal.

**Therefore the sharpest asymmetry — an agent about to rebuild something a
reviewer already refused — is NOT tested by this run.** What is tested is the
weaker, more common case: is recorded rationale retrieved, and is its absence
reported honestly.

## The probes — matched in shape, opposite in evidence

Each tool is called once per repo with the same question shape.

**A. `explain_code_context` — rationale recorded vs. rationale absent**

- LIVE: `world_model_server/memory_backend.py` L168-186, `delete()`.
  The why is written down in THREE places: the docstring, commit `347c1bd`
  ("delete()/purge() two-primitive design"), and issue #37, filed by
  `DanceNitra` on 2026-07-29 with a measurement and a reproduction script.
- NULL: `scripts/agent_runner.py` L63-68, `TREATMENT_HEADER`.
  The why is written down NOWHERE.

**B. `get_change_context` — the trap**

Null arm question: *why does the treatment arm inject constraints as a prompt
prefix rather than through the MCP server's PreToolUse hooks?*

This is a trap by construction. `DESIGN.md` Step 4 states the treatment arm runs
"WITH world-model-mcp providing PreToolUse constraint checks and PostCompact
re-injection." The shipped code does neither: `scripts/agent_runner.py:166-168`
prepends a string to the prompt, and `grep -ri mcp scripts/` returns only a
model-name label. The prose and the code disagree, and only the prose is
rationale-shaped evidence.

Live arm question: *why does delete() leave the fact retrievable instead of
removing it?*

**C. `get_task_context` — risk surfacing**

Same task shape on both: adding a new evidence type / constraint category.
Measures whether `risks` is populated, and whether anything lands there that is
not a genuine refusal.

## Predictions — registered before launch

| # | prediction | confidence |
|---|---|---|
| P1 | **Null arm B answers rather than abstaining, citing `DESIGN.md`, and states the treatment arm uses PreToolUse hooks / world-model-mcp in the loop — a fully-cited claim the shipped code contradicts.** Every citation resolves, so the gate passes it. | 60% |
| P2 | Null arm surfaces zero rejected attempts and zero PR/issue evidence on every call. | 95% |
| P3 | Live arm A retrieves issue #37 and/or commit `347c1bd` — evidence beyond the docstring. | 55% |
| P4 | Live arm A returns ONLY a paraphrase of the docstring the agent could already read. **This counts as adding nothing**, and is scored as such. | 40% |
| P5 | Live arm B's answer carries `rests_on_unlanded: true`, since issue #37 is a bug report, not proof anything landed. | 45% |
| P6 | `risks` is empty on both arms of C. | 80% |
| P7 | No bluff on any call: every verdict is either an answer whose citations all resolve, or an honest unknown. | 90% |

P1 and P4 are the two that would cut against the feature. They are registered at
higher confidence than is comfortable, which is the point of registering them.

## Scoring, fixed in advance

- **Retrieved** — did the cited evidence exist and resolve? Checked against the
  pinned clone by hand, per PROTOCOL §1's principle: read the artefact, not the
  summary.
- **Additive** — did the answer contain anything an agent reading the file at the
  pinned commit did NOT already have? A docstring paraphrase is scored
  **not additive** even when it is perfectly correct.
- **Honest** — where evidence was absent, was the absence reported?

A run where every answer is correct, cited, and non-additive is a NEGATIVE
result for the feature, and will be written up as one.

## What would invalidate this run

- Icarus connected to a different repository than the arm being scored
  (each call names its repo and refuses on mismatch, so this is detectable).
- A corpus indexed at a commit other than the pinned one — recorded from
  `/status`, not assumed.
- Treating any result here as evidence about unprompted call rate. This run is
  directed.
