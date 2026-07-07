# Icarus — Session Handoff (2026-07-07 → 2026-07-08)

Read this first next session. It captures the current state, what's done vs. not,
and the gotchas for the **tester-feedback deeper-comprehension effort** — the
active body of work as of this handoff. (The private-repo effort from 2026-07-06
is a separate, already-shipped feature area; its history lives in
`docs/plans/2026-07-04-private-repos-*.md` and git log, not repeated here.)

**Required: use the `~/.claude/skills` this session used — do not freelance the
process.** Every brick in this effort was built with this skill set, in this
order, and the next session must continue the same way rather than reverting to
ad hoc implementation:
- `using-git-worktrees` — one isolated worktree per brick, at
  `.worktrees/<branch-name>`, before any task work starts (§5).
- `subagent-driven-development` — fresh implementer subagent per task (TDD,
  self-review, commit), never edited by the orchestrating session directly.
- `requesting-code-review` — every task gets an independent spec-compliance
  review (explicitly told not to trust the implementer's report) **then** a
  separate code-quality review, in that order — never combined, never skipped.
- `finishing-a-development-branch` — verify tests, then merge/clean up a brick's
  branch + worktree only once its final whole-brick review is clean.
- `playbook-planning` — risk-first sequencing, a probe before the build (Brick 0
  is the concrete example), a written not-doing list with reopen-triggers.
- `schedule` — for any genuine "resume this later, outside the current session"
  need (e.g. the quota-blocked retry in §1) — not `ScheduleWakeup`, which is
  scoped to `/loop` dynamic-pacing mode and doesn't apply here.

**Also required — the `playbook-*` reasoning skills, applied throughout, not
just invoked once:**
- `playbook-software-engineering` — scope minimally, verify with evidence, never
  green-wash.
- `playbook-debugging` — reproduce → localize → falsifiable hypotheses → prove
  cause by toggle (this is exactly how the `benawad/vsinder#253` bug in Brick B
  was confirmed before writing any fix code).
- `playbook-architecture` — constraints first, invariants enforced in code,
  walking skeleton before deep design.
- `playbook-product-design` — one promise + anti-promise, hero moment, written
  deferred list (the north star's honesty boundary and the Brick-by-brick
  not-doing lists are this in practice).
- `playbook-ux` — design the user's moment, truthful state, unhappy paths as
  first-class surfaces.
- `playbook-research` — research serves a decision, provenance per claim,
  explicit disconfirmation pass.
- `playbook-planning` — plan backward from the demo, risk-first bricks with
  binary done criteria.
- `playbook-decision-making` — reversibility classification, criteria before
  options, pre-mortem, reopen-triggers.
- `playbook-writing` — lead with the point, revise by deletion, readable over
  merely short.
- `playbook-startup-strategy` — wedge then expand, own the moat / rent the
  commodity, sequence by proof.
- `playbook-ai-agents` — evals before features, deterministic gates around the
  probabilistic core, fail safe not impressive (this is the honesty-gate
  discipline running through every brick in this effort).
- `playbook-systems-thinking` — behavior from structure, loops/stocks/
  incentives, leverage points, expect pushback.

If a skill listed above isn't available in a future session's `~/.claude/skills`,
say so explicitly rather than silently improvising a substitute.

---

## 0. TL;DR — where we are

Alankrit shipped the `.dmg` + web staging link to testers and got **nine
remarks back**. Those became `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md`
— read that file's "Brick" sections for full task-by-task detail; this handoff
is the orientation layer on top of it.

**Merged to `main` (2e4bfa6), fully done:**
- **Brick 0** — a code-comprehension eval set (`evals/comprehension_questions.json`)
  proving, with a measured RED baseline, that Icarus doesn't yet understand code
  from the code itself regardless of phrasing. Baseline: retrieval recall@k
  53.8%, citation correctness 30.8%, answer correctness 30.8%, abstention
  precision 20.0% — **both honesty gates 100%**. This is the number Bricks A/C
  exist to beat.
- **Brick A** — whole-codebase ingest (all languages/dirs, not just Python under
  one dir; line-window chunking with `#Lstart-Lend` refs; line-ranged citation
  links). Fixes tester remarks 1, 2, 4.
- **Brick B** — PR/Issue coverage. Fixes remark 5 — **and this was a real bug,
  reproduced and fixed**: `benawad/vsinder` issue `#253` (an open, standalone
  issue never linked from a merged PR) was completely invisible to ingestion.
  Confirmed live against the real repo, both before and after the fix.

**Built + reviewed, sitting on an UNMERGED branch (not yet in `main`):**
- **Brick C** (semantic retrieval, fixes remarks 6/8) — branch/worktree
  `brick-c-semantic-retrieval` at `.worktrees/brick-c-semantic-retrieval`, HEAD
  `eef8e6d`. Tasks C1 (`EmbeddingProvider`/`GeminiEmbeddingProvider`/
  `StaticEmbeddingProvider`), C2 (`SemanticRetriever`, cosine similarity), C3a
  (`HybridRetriever`, reciprocal-rank fusion of BM25 + semantic) are all built,
  independently spec- and code-quality-reviewed, hardened via real follow-up
  fixes. **225 tests pass on this branch (vs. 180 on `main`), 15 self-skip.**
- **C3b (the live proof) is the ONE thing blocking Brick C's merge** — see §1.

**Not started yet:** Brick Q (query-understanding: framing/grammar/spelling
robustness), Brick D (line-select → explain, remark 3), Brick S (structural
comprehension, deferred-gated, needs explicit go), Brick E (richer "why"
sources). See §4.

---

## 1. THE THING TO CHECK FIRST NEXT SESSION

A scheduled task, **`retry-brick-c-live-embedding-proof`**, is set to fire at
**2026-07-08T00:15:00Z** (UTC). Check whether it already ran:

```bash
# from any Claude session with the scheduled-tasks tool:
mcp__scheduled-tasks__list_scheduled_tasks
```

If `enabled: false` and `lastRunAt` is set, it fired — check the result:
1. `cd "/Users/alankritghosh/JARVIS /jarvis_engineering/.worktrees/brick-c-semantic-retrieval"` (if it still exists — the task was instructed to merge to `main` and remove the worktree/branch on success) and `git log --oneline -10`.
2. If the branch/worktree is GONE and `main`'s log shows a Brick C merge commit — **it worked**, Brick C is merged, tests should be green on `main`. Confirm with `python3 -m unittest discover -t . -s evals` from the repo root — expect the test count to have risen from 180 (roughly matching the branch's 225, since the merge should bring those tests over).
3. If the branch/worktree STILL exists — the task either didn't run yet, or ran and hit another blocker (read `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md`'s Brick C section, near the bottom, for whatever it recorded).

**If it hasn't fired yet** (still `enabled: true`, `nextRunAt` in the future),
just wait for it or check back later — don't manually re-trigger it or start a
duplicate live run; that risks burning more of the same daily embedding quota
this whole chain of blockers was about (see §2).

**What the scheduled task does autonomously if quota has genuinely reset:** runs
the real `evals.test_retrieval_eval` live test (`HybridRetrievalEvalTests`),
which embeds all 243 real committed corpus chunks via the real Gemini API
(paced at ~0.7s/call to respect the 100 req/min free-tier cap) and checks hybrid
retrieval's recall@k against a same-run BM25 baseline, with both gates still at
100%. If that holds, it records the real numbers in the plan doc, runs an
independent spec review + code-quality review + a final whole-brick review of
all of Brick C (mirroring how Bricks 0/A/B were closed out earlier in this
branch's history — see git log for the exact review-dispatch pattern used
throughout), fixes anything those reviews flag, and merges to `main`. It was
explicitly instructed: **never weaken the test's assertion to force a pass** —
if hybrid genuinely underperforms BM25 on the real labelled set, it's supposed
to stop and record that as a real, honest finding instead.

---

## 2. Why C3b got stuck (read before touching Gemini keys/quota again)

Three real, escalating discoveries, all recorded in the plan doc's Brick C
section (search for "Scoped before dispatch" and the nested status notes under
it) — summarizing here so you don't have to reconstruct it from commit history:

1. **`SemanticRetriever` embeds every corpus chunk serially at construction**
   (no batching — explicitly deferred, by design, out of this brick's scope).
   243 chunks × 1 call each hits Gemini's free-tier **100 requests/minute** cap
   partway through every time.
2. **Alankrit supplied a new `GEMINI_API_KEY` value** hoping a fresh key would
   have fresh quota. It didn't — a single probe call still 429'd, and the error
   body's `quotaId` (`...PerProject...`) revealed why: **the quota is scoped to
   the Google Cloud project, not the individual key.** A new key from the same
   project shares the same exhausted budget.
3. **This also sharpened an earlier, separate finding worth flagging beyond
   Brick C**: `GEMINI_API_KEY` and `GEMINI_PAID_API_KEY` in `.env` were
   discovered to hold the **identical value** — not two distinct credentials.
   Given point 2, genuine billing-enabled status is a property of the
   underlying Google Cloud *project* (which would show a different quota
   metric entirely, not one literally named `_free_tier_requests`), not
   something a differently-named env var alone can confer. **This touches the
   private-repo writer path** (`PaidGeminiProvider`, used to answer questions
   about a user's private repo) — if that key is *also* not genuinely
   billing-separated in production, the "private repos only reach a paid,
   no-training model" guarantee documented elsewhere may not currently hold as
   described. Alankrit's explicit call: flag it, don't investigate further this
   session. **Worth a real look before onboarding anyone else's private code.**

Net effect: the retry is gated purely on the **daily** project-wide quota
resetting (not per-key, not fixable by swapping keys), which is why the
scheduled task waits for a clean UTC-day boundary rather than retrying sooner.

**If you're debugging this fresh and quota is STILL exhausted after the
reset**: don't keep burning probe calls. Check `https://ai.google.dev/gemini-api/docs/rate-limits`
for the real per-day number for `gemini-embedding-001` (it was `1000` as of this
session), and consider whether OTHER things are also consuming the same
project's quota (the demo server, another test, etc.) before assuming the code
is broken.

---

## 3. What's actually built in Brick C (if you need to pick up C3b/C4 manually)

All in `evals/retriever.py` / `evals/provider.py`, on the `brick-c-semantic-retrieval`
branch (not yet in `main` — see §1 for whether that's changed):

- **`evals/provider.py`**: `EmbeddingProvider` (base, `private_safe=False`,
  `.embed(text) -> list`), `GeminiEmbeddingProvider` (model `gemini-embedding-001`,
  real REST API verified live before building, key in header not URL, reuses
  `_with_retry`), `StaticEmbeddingProvider` (content-addressable test double —
  dict-or-callable, NOT a sequential queue, since `.embed()` is called
  per-chunk/per-query in no fixed order), `PaidGeminiEmbeddingProvider` (mirrors
  `PaidGeminiProvider` exactly — built for C3b's now-moot paid-tier attempt, kept
  since it's correct and precedented, just currently unused by any test).
  `make_embedding_provider`/`has_embedding_provider_key` factories.
- **`evals/retriever.py`**: `SemanticRetriever(chunks, provider)` — cosine
  similarity, embeds every chunk ONCE at construction, vectors keyed by
  `chunk.ref` in a dict (NOT a list parallel to `chunks` — an early version had
  a silent-misalignment footgun there, fixed before merge). `HybridRetriever
  (lexical, semantic, rrf_constant=60)` — reciprocal-rank fusion, generic over
  any two `.search(query, k) -> List[str]`-compatible retrievers (proven with a
  fake, not just the two real classes), with a per-list dedup guard (an
  untrusted retriever returning a duplicate ref used to silently double-count
  its score — fixed, with a test that re-simulates the exact pre-fix bug).
- **`evals/test_retrieval_eval.py`**: `HybridRetrievalEvalTests` — the
  self-skipping live proof (see §1/§2), currently gated on `GEMINI_API_KEY` +
  the corpus existing, using a test-local `_PacedEmbeddingProvider` wrapper
  (sleeps ~0.7s/call) around the real `GeminiEmbeddingProvider`.

**Explicitly out of scope for C3/C4** (recorded in the plan doc, not silently
skipped): ingest-time vector persistence/caching for the demo (re-embedding 243+
chunks on every server start is a real product cost, but a separate concern
from proving the retrieval technique works), and wiring embeddings into the
demo's actual private-repo connect flow (no embedding provider touches
`demo/library.py` yet at all — C1/C2/C3 only touch the eval harness).

**C4 (gate untouched proof) has not been started** — it's the last item in
Brick C's original task list (explicitly assert the honesty gate + abstention
recall stay 100% with semantic retrieval on). Given `HybridRetrievalEvalTests`
already asserts both gates at 100% as part of its own test, C4 may turn out to
be largely already covered — verify this explicitly rather than assuming, the
same way Brick A/B repeatedly found "verify what's really needed" was cheaper
than blindly building more.

---

## 4. What's NOT started (the rest of the plan)

Full detail in `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md`
— read the relevant "Brick" section before starting any of these.

- **Brick Q — query-understanding layer** (any framing/grammar/spelling).
  Rides on Brick C (embeddings absorb most paraphrase/typo tolerance; a thin
  normalization layer covers the rest). Fixes nothing on its own in the
  tester-remarks table but is core to the refined north star ("answer any
  question... regardless of framing, grammar, or spelling").
- **Brick D — line-select → explain** (remark 3). Depends on Brick A's
  line-addressable refs (already done) and benefits from Brick C's semantic
  neighbors. Not started.
- **Brick S — structural comprehension** (AST/call-graph, the deep "reads the
  code" capability). **Deferred-gated** — CLAUDE.md lists this under
  "post-Phase-4 unless a task says so." Needs Alankrit's **explicit go** before
  any code, and the plan calls for a cheap stdlib-`ast` probe first to justify
  the investment. Do not start this without asking.
- **Brick E — richer "why" sources** (commit-message/blame provenance). Optional,
  sketched but not task-broken. After Brick C.
- **Remark 9** (Icarus writing/modifying real code) — **permanently off the
  table**, Alankrit's explicit, recorded decision. Do not build this or suggest
  it; a reopening would need its own deliberate strategy-pivot decision doc,
  post-Phase-4 at the earliest.

---

## 5. How this session worked (process note for continuity)

Every task in Bricks 0/A/B/C was built via **subagent-driven development**: a
fresh implementer subagent per task (TDD, self-review, commit), then an
independent spec-compliance reviewer (explicitly told not to trust the
implementer's report — re-run tests, re-derive claims, verify math/logic by
hand), then an independent code-quality reviewer, with follow-up fix rounds
dispatched back to the same implementer when either review found something
real. Each brick got a **final whole-brick review** across its entire diff
before merging. This pattern is worth continuing for Bricks Q/D/S/E — read the
git log on `main` (`git log --oneline --grep="Task "`) for concrete examples of
the review-prompt rigor used (independent re-verification, hand-recomputing
math, live-reproducing claims rather than trusting reports).

**Isolation convention**: one worktree per brick, at `.worktrees/<branch-name>`,
branched off `main`, merged via fast-forward when done, worktree removed +
branch deleted after merge. `.worktrees/` is gitignored.

---

## 6. Commands

```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"

# Full offline suite (main, post-Brick-B): 180 tests, 13 skipped
python3 -m unittest discover -t . -s evals
python3 -m unittest discover -t . -s demo

# On the brick-c-semantic-retrieval branch/worktree (if still unmerged): 225 tests, 15 skipped
cd .worktrees/brick-c-semantic-retrieval && python3 -m unittest discover -t . -s evals

# Check the scheduled retry's status
# (via the scheduled-tasks MCP tool: mcp__scheduled-tasks__list_scheduled_tasks)

# The live proof itself, once quota allows (DO NOT run repeatedly — costs real quota):
python3 -m unittest evals.test_retrieval_eval -v
```

---

## 7. Key files this session touched/created

- `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md` — the plan.
  **This is the primary source of truth for Bricks 0/A/B/C/Q/D/S/E** — richer
  and more current than this handoff for anything brick-specific. Read it.
- `evals/comprehension_questions.json` + `evals/test_comprehension_questions.py`
  — Brick 0's probe set (the RED baseline).
- `evals/ingest.py` — `classify_file` (A1), `chunk_text` (A2), whole-repo walk
  wiring (A3), `resolve_code_dir`, `fetch_all_issue_ids` (B1), `--state all` PR
  fetch (B2).
- `demo/links.py` — line-ranged + `doc:`/`config:` citation links (A4).
- `evals/test_ingest_smoke.py` — the live non-Python-repo proof (A5), against
  `sindresorhus/is-online`.
- `evals/provider.py`, `evals/retriever.py` — Brick C, see §3.
- `.env` — `GEMINI_API_KEY` was updated this session (see §2 for why the
  duplication with `GEMINI_PAID_API_KEY` matters); never committed, gitignored.

---

## 8. Gotchas specific to this effort

- **`evals/ingest.py`'s `--code-dir` default is now conditional**
  (`resolve_code_dir`): `None` → `"llm"` only for the pinned `simonw/llm` repo,
  `"."` (whole root) for any other repo. Explicit `--code-dir` always wins.
- **The committed `simonw/llm` corpus (`evals/corpus/chunks.jsonl`,
  `evals/corpus/meta.json`) is FROZEN** — no task in this entire effort ever
  overwrites it or runs a real ingest against it; all real-corpus proofs (A5,
  C3b) either use a scratch temp dir or read the committed corpus read-only.
  Don't break this invariant.
- **`ISSUE_LIMIT=500`/`PR_LIMIT=200` are silent, unguarded caps** — a repo with
  more issues/PRs than the limit truncates without any visible signal. Known,
  recorded, deliberately deferred (would need a return-shape change to
  `fetch_prs`/`fetch_all_issue_ids`).
- **`.json` is absent from the file-classifier's extension allowlist**
  (`evals/ingest.py`'s `_EXTENSION_SOURCES`) — `package.json`/`tsconfig.json`
  etc. are silently NOT ingested. A conspicuous gap for a "whole codebase, all
  languages" brick; recorded as a known limitation, not yet fixed.
- **`SemanticRetriever` has no batching or caching** — every construction
  re-embeds every chunk from scratch via a real network call each. Fine for a
  one-off eval run; a real cost/latency problem if wired into the demo's
  server-start path without first building the deferred caching layer (§3).
- **`GEMINI_API_KEY` == `GEMINI_PAID_API_KEY`** in `.env` as of this handoff —
  see §2, point 3. Flagged, not fixed.
