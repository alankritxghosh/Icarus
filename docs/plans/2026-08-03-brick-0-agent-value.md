# Brick 0 — does Icarus context change a coding agent's plan?

Run 2026-08-03, before any MCP work. Ordered by Alankrit's agent-memory plan
(Bricks 0–7). Brick 0's whole job is to decide whether Bricks 1–7 are worth
building, so nothing was built.

## Method

Repo: `simonw/llm` @ `94769b8` — the commit Icarus indexed, cloned locally so
the "agent alone" arm reads exactly the source Icarus read.

Four change tasks a person would plausibly hand an agent:

| | task |
|---|---|
| T1 | store API keys in the OS keychain instead of plaintext `keys.json` |
| T2 | parallelise `llm embed-multi` |
| T3 | store attachments as files on disk instead of BLOBs |
| T4 | add retry-with-backoff to model API calls |

**Arm A** (agent alone): plans written from source only and frozen to
`brick0_armA.md` *before* any Icarus call.
**Arm B**: two questions per task through the real serving pipeline
(`demo.library._build_gated_pipeline`, `gemini-paid`, hybrid retrieval,
honesty gate) — the same path `/ask` uses.

**Disclosed bias:** one agent (me) ran both arms, so arm B saw arm A's
reasoning. That biases toward *no* difference, so a positive result is
conservative and a null result proves less.

## Result 1 — the corpus the live brain serves is 9% of the repo

First run went through the live brain's default corpus and answered **1 of 8**.
Cause, verified rather than assumed:

    indexed (committed corpus, generated 2026-07-18):   141 PR ·  84 issue
    actually in the repo:                               518 PR · 961 issue

`5347b30` (2026-07-28, "index EVERY PR and issue") landed *after* the committed
corpus was generated, and the built-in `simonw/llm` always reloads from that
committed corpus — so the demo repo every new user meets first still answers
from a pre-fix index. `/status` reports `truncated: false`, i.e. it does not
know it is incomplete. Repos users connect themselves are unaffected.

Re-ingesting at the same commit with today's code (AST chunking on, matching
production) gives **519 PR · 961 issue · 1,091 commit · 470 code** chunks.
Every number below is from that corpus.

## Result 2 — 3 of 8 answered; one materially changed the plan

| | verdict | did it change the plan? |
|---|---|---|
| T1 keychain | answer ×2 | **yes** |
| T2 parallel embed | unknown ×2 | no — correctly, nothing is recorded |
| T3 attachments | unknown ×2 | no — but see under-find below |
| T4 retries | unknown / vacuous answer | no — **wrongly**, see below |

**T1 is the proof case Alankrit described.** Arm A's plan said, in writing,
"no evidence found in source that this was previously considered." Icarus
returned:

- `issue:1041` — **"Encrypt keys using keyring"**, still OPEN. The exact change,
  already proposed, unresolved.
- `issue:623` — the maintainer's own reasoning about key readability: he
  disliked keys being easy to read back out, then concluded `keys.json` "is
  readable by the current user anyway".

Both citations were verified against GitHub by hand: real, on-topic, correctly
resolved. An agent given this writes a different plan — it joins an existing
thread and argues against a stated position instead of opening a naive
duplicate.

## Result 3 — the agent-facing failure is a bare abstention, not a bluff

T4 asked why there is no retry/backoff. Icarus abstained. But it **retrieved
`issue:112` "Retries w/ exponential backoff" and `issue:850` "Add retry when
model is overloaded" at ranks 1 and 3** — both open, both in the corpus.

So this is not an under-find and not a coverage gap. Retrieval worked; the
writer had the evidence and returned nothing, because the question asked for a
*reason* and the evidence records a *request*.

For a person at a voice overlay, "no one wrote this down" is the right answer
and the honesty gate is doing its job. For an agent about to write code, the
useful answer is "two open requests exist for exactly this and no decision was
recorded" — that changes the plan; `unknown` does not.

**This is the design input for Brick 1.** `get_change_context` must return the
retrieved evidence set alongside the verdict, not the prose answer alone. The
payload already carries it (`Result.retrieved` / `searched` / `anchored`), so
this is a shaping decision at the MCP boundary, not a brain change — and it
takes nothing away from the honesty gate, which keeps governing what may be
*asserted*.

## Verdict

Go on Brick 1, with two corrections first:

1. **Refresh the default corpus** — the demo repo is 9% indexed and says
   `truncated: false`. Committing a re-ingest moves the frozen eval board, so
   this needs a deliberate call (re-baseline the board, or keep the board's
   corpus pinned and serve a separate current one for the demo).
2. **Brick 1 returns evidence, not just answers.** Measured above.

Not established by this run: whether it reduces human corrections or review
rounds (needs real tasks over time, not four synthetic ones), and anything
about latency at scale. Sample is 4 tasks / 8 questions on one repo.
