# Agent Mode, live — firecrawl/firecrawl #4054

**Registered BEFORE any Icarus call**, per `PROTOCOL.md` §3. Nothing below the
"Prediction" heading may be edited after the first tool call; results go in a
separate section underneath.

## Setup

| | |
|---|---|
| Repository | `firecrawl/firecrawl`, connected in the Mac app |
| Index | 3,283 PRs · 959 issues · 6,162 commits · 8,199 code · 206 config · 150 doc |
| Brain | hosted, revision deployed 2026-08-21 (carries the writer decision fix) |
| Surface | Claude Code MCP, user-scope, `/Applications/Icarus.app --mcp` |
| Task | `#4054` — "dify Create Monitor: error type HTTPError, Failed to create monitor: Bad Request" |
| Issue state | opened 2026-07-17, **0 comments**, no referencing PR, no AI-contribution policy in CONTRIBUTING.md |

**Contamination disclosure.** I have not read firecrawl's source, its pull
requests, or anything about monitors before writing this. What I have read is
the issue body, which is two screenshots and one line of prose ("List Monitor
Checks is running normally") — no stack trace, no request payload, no code.
That is deliberately the same starting position an agent handed this ticket
would have.

## Prediction

Written blind, before the first call.

1. **Icarus will answer rather than abstain** on a question about how monitor
   creation validates its request — the repo is large and monitors are a real
   feature, so evidence should exist. *Confidence: moderate.*
2. **It will NOT surface a prior attempt** (a closed-unmerged or open PR) aimed
   at this specific bug. The issue has zero comments and no referencing PR, and
   the two live sessions so far found prior attempts only where the issue
   already pointed at one. *Confidence: high.*
3. **The decisive fact, if there is one, will be a validation contract** — a
   required field or a schema mismatch between what the Dify integration sends
   and what the create-monitor endpoint accepts — rather than a recorded
   decision. This is a shape-of-answer prediction, and it is the one most
   likely to be wrong.
4. **By-description retrieval will underperform by-identifier**, consistent
   with `evals/test_description_recall.py`. Concretely: asking "why does
   creating a monitor reject a request" will return less useful evidence than
   naming a specific file or PR number would.

## What counts as a result

- **Hit** — Icarus surfaces something that changes what I would have written,
  and it is verifiable against GitHub independently.
- **Neutral** — it confirms what reading the code would have shown anyway.
- **Miss** — it answers plausibly and the answer is wrong, incomplete in a way
  that matters, or omits something a later read finds.

Every claim it makes gets checked against the repository before it is believed,
per `PROTOCOL.md` §1: an agent's self-report — including mine — is not evidence.

## Results

**Icarus contributed nothing material to this task.** Recorded as measured, not
as a disappointment — it is one task on one repository.

### Call 1 — `get_change_context`

*"Why would creating a monitor fail with a 400 Bad Request while listing monitor
checks works?"* → **verdict `unknown`**, zero citations, reason
`writer_found_no_reason`.

Two things worth separating. The abstention is CORRECT: no chunk in that
repository records why this specific request is rejected, and inventing one is
the failure the product exists to refuse. And the reason code is the one
shipped earlier the same day (`ABSTAIN_WRITER_NO_REASON`), so this also
confirms the deployed brain is running the new code.

It retrieved 21 refs including `issue:4054` itself, `monitoring/queue.ts` and
`rust-sdk/src/monitor.rs` — the right neighbourhood, no answer in it.

### Call 2 — `get_task_context`

- `decisions`: **0**
- `citations`: `issue:4054`, `issue:1299`
- `unknowns`: 25, and the first is the question itself — *"Why the Dify
  integration monitor creation specifically triggers a 400 Bad Request."*
- `constraints`: includes **"reached the maximum number of reasoning calls"** —
  the budget was exhausted, and it says so rather than presenting a truncated
  investigation as a complete one.
- `risks`: **4, and all four are noise** — user-agent handling in Playwright
  (`pr:3031`, `pr:3030`), a crawl 404 race (`pr:2853`), URL-validation regex
  (`pr:1546`). Nothing to do with monitors. This is the relevance-noise axis
  already measured in `2026-08-10-rejected-attempt-false-positive-rate.md`, at
  a worse rate than the "up to one in three" recorded there.

### The mechanism, found by reading the schema

`apps/api/src/services/monitoring/types.ts:190` — `createMonitorBaseSchema` is a
**`z.strictObject`**, so any unrecognised key in the body is a 400. A
third-party integration sending one extra field would see exactly this, while
`listMonitorChecks` (a GET with no body) keeps working. A second candidate sits
at `requireGoalForSearchTargets`: a `search` target with no non-empty `goal` is
also rejected.

Both are plausible and **neither is confirmed**, because the issue contains two
screenshots and one line of prose — no payload, no response body, no trace.

### Outcome: not a patch

The honest contribution here is a diagnostic comment asking for the request
payload and the full error body, naming both candidate causes. Loosening
`strictObject` is an API design decision, not a bug fix, and nobody should make
it from a screenshot.

### Predictions, scored

1. *"Icarus will answer rather than abstain"* — **WRONG**. It abstained, and it
   was right to.
2. *"It will not surface a prior attempt"* — **CORRECT**, though the four it did
   surface were unrelated, which is a different defect from the one predicted.
3. *"The decisive fact will be a validation contract"* — **CORRECT in substance**
   (strictObject), but found by reading code, not by Icarus.
4. *"By-description will underperform by-identifier"* — **CONSISTENT**: the
   description-shaped question returned unknown while retrieval clearly reached
   the right neighbourhood.

### What this changes

Nothing about the honesty guarantees, which held throughout — no bluff, no
invented decision, budget exhaustion disclosed.

It does sharpen where the value is claimed. On a task whose answer is not
recorded anywhere in the repository, Icarus correctly says so and the agent is
no better off than without it. The measured wins so far
(`docs/experiments/2026-08-10-agent-mode-exp-d-directed.md`) all came from tasks
where somebody HAD tried something before. That is the shape of task to select
for, and the shape to claim.

---

## Second run — an independent Claude Code session, same issue

A separate session in Alankrit's VS Code loop took the same issue, made the
same two calls, and then went further: it found the ACTUAL defect, which the
run above stopped short of.

**The real mechanism (theirs, verified here independently).**
`apps/api/src/index.ts:236-247` is a shared ZodError handler whose user-facing
`error` field is chosen by three branches: top-level `unrecognized_keys` → a
readable message; else FIRST issue is `custom` → its message; else the literal
constant `"Bad Request"`. Every other Zod code — `invalid_type`, `too_small`,
`invalid_union` — collapses to that constant. The real issues stay in
`details`, which no SDK surfaces.

Create-monitor is the worst case, because `targets` is a `z.union` of three
`strictObject`s, and in Zod v4 a bad target yields ONE top-level
`invalid_union` with the branch failures nested underneath — so an unknown key
INSIDE a target structurally cannot reach the `unrecognized_keys` branch.

**Verified here, not taken on trust.** Installed zod 4.1.12 and ran the shapes:

    bad key inside a target  -> ["invalid_union"]      -> "Bad Request"
    retentionDays: "30"      -> ["invalid_type"]       -> "Bad Request"
    unknown TOP-level key    -> ["unrecognized_keys"]  -> readable message

Also verified: `pr:2954` is real, CLOSED, never merged; nine assertions across
`parsers.test.ts` and `system-prompt-rejection.test.ts` pinned the exact string
`"Bad Request"` — tests that passed while clients got nothing actionable, which
is how this survived.

**Two corrections to their write-up.** `DIFY = "dify"` DOES exist in
`apps/api/src/utils/integration.ts:4` as an integration enum value, so "no Dify
integration exists here" overstates it — no plugin code, but the API knows Dify
as a caller. And the blast radius reaches v1 paths through the same shared
handler, which makes the message change a wider contract decision than v2
monitors alone.

### What Icarus contributed, measured twice

| | run 1 (this session) | run 2 (separate session) |
|---|---|---|
| `get_change_context` | `unknown`, reason `writer_found_no_reason` | `unknown`, reason `ungrounded_citations`, all claims `unsupported` |
| `get_task_context` risks | 4, all unrelated | `pr:2954` — real, closed unmerged |
| decisions | 0 | 0 |
| unknowns | 25 restatements | 21 restatements |
| Net | nothing material | one genuine refused-attempt flag |

**Same repository, same day, same question shape, two different abstention
reason codes and two disjoint risk sets.** The engine is non-deterministic
across runs in what it surfaces, which is worth knowing before any claim is
made about what it "will" find.

### The open question they raised, now closed

Their honest self-criticism was that they never called `explain_code_context`
on `index.ts:236-247` — the line-scoped tool aimed at the exact lines being
changed — and that it "might also have come back unknown".

**Tested here. It comes back unknown.** Verdict `unknown`, empty answer, reason
`ungrounded_citations`, and its one drafted claim — a correct plain-English
restatement of the three branches — labelled `unsupported` and dropped. It
anchored `code:apps/api/src/index.ts#L201-L314` correctly, so the LOCATION
resolution worked; there is simply no recorded reason for the fallback string
anywhere in the repository, and the tool refuses to invent one.

Its `rejected_attempts` returned three PRs — Playwright user-agent, a RabbitMQ
fallback, a SELF_HOSTED_DOMAIN config — none related to error formatting. Third
run, third disjoint noise set.

So all three tools were tried on this task and none contributed to the fix. The
diagnosis came from `gh issue view`, grep, and a node one-liner against real
Zod. Recorded as the result, not as a footnote.

---

## Third task — issue #4375 / PR #4376, and the first WRONG answer

A different session took `#4375` (self-hosted `/v2/search` returns an empty
success when DuckDuckGo extraction throws). Pre-flight caught within seconds
that **PR #4376 was already open and approved** for half 1 of the issue, so no
duplicate was built — the check that cost a full Rust build to learn on uv now
costs one API call.

Half 2 — *"do not report `success: true` when the search backend threw"* — is
untouched by that PR and remains open.

### Icarus performed much better here, and was wrong

Verdict `answer`, real excerpts, a populated `rejected_attempts`. Its
conclusion: the swallowing "was not deliberate… developers have actively worked
to surface these failures", citing commit **229141a** ("surface real search
failures instead of silent no-changes", 2026-06-18).

**Verified independently here, since another agent's report is not evidence
either:**

    229141a  2026-06-18  added onFailure to search/v2/index.ts     (4 lines)
    2fc41237 2026-06-19  removed it, "isolate search monitor from core" (4 lines)
    HEAD                 occurrences of onFailure/searchDegraded: 0

The cited commit was **reverted the next day**, with a stated rationale. Icarus
presented a reverted change as evidence of ongoing effort — the exact opposite
of the recorded intent.

### The failure class: a commit is not a description of HEAD

This is new, and it is not any of today's other defects. Nothing was bluffed —
`229141a` is real, its message says what Icarus said it says, and the citation
resolves. The error is that **a commit is evidence something happened once,
never that it is still true.**

The MCP tool description already carries exactly this warning for ISSUES —
*"an ISSUE is a request or a bug report: it is evidence that somebody WANTED
something, never that anybody built it"*. The same warning does not exist for
COMMITS, and this run is the case that shows it should, plus a mechanism:
the brain holds the indexed code at HEAD, so it can check whether text a cited
commit ADDED still appears there. A commit whose additions are absent at HEAD
is a commit that was undone.

Worth noting what did work: the per-claim self-report flagged the sentence
`composed` + `rests_on_unlanded`, because its citations were `issue:4375` and
`pr:4376` — both unlanded. The flag fired for a true reason and a reader who
heeded it would have checked. It just cannot see the revert.

### Where the intent actually lives, read precisely

`2fc41237` is binding but narrower than "search must stay silent": it was about
architectural coupling — the monitor reaching into shared internals — not a
ruling that `/v2/search` should report crashes as empty successes. Re-adding an
`onFailure` hook would redo something deliberately undone; changing `search()`'s
own contract uniformly is a different proposal, and one that needs owner
sign-off rather than a speculative pull request.

Confirmed at HEAD: `search/v2/index.ts` ends in a bare
`catch { logger.error(...); return {} }`, and `execute.ts:361` hardcodes
`isSuccessful: true`, so a failed search is recorded as a success in telemetry
as well. Same silent-failure class, separate fix.
