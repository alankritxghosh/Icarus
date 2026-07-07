# Tester Feedback → Deeper Codebase Comprehension — Phased Plan

> **For Claude:** REQUIRED SUB-SKILL: superpowers:executing-plans. Every task is
> red→green: a failing eval/test first, then the smallest code that turns it
> green. **Never weaken a test or either honesty gate. Do NOT change the committed
> `simonw/llm` corpus or `phase1_questions.json` — the eval board depends on them
> being frozen.** Every commit appends
> `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work one brick at a
> time in an isolated worktree per [CLAUDE.md](../../CLAUDE.md).

**Context:** Alankrit shipped the `.dmg` + web staging link to testers. Nine
remarks came back. This doc turns them into a sequenced, eval-first build order,
keeping the non-negotiable identity intact: **cite-or-unknown, retrieval-only,
never touch customer code, discard after each request.**

---

## The nine remarks → five themes, one bug, one refusal

| # | Remark | Theme |
|---|---|---|
| 2, 4 | Index the whole codebase, not just PRs/Issues | **A. Whole-codebase ingest** |
| 1 | Old codebases have no docs → we look redundant | **A / positioning** (see reframe) |
| 5 | Not all Issues/PRs read; issue titles not picked up | **B. PR/Issue coverage** (bug) |
| 6, 8 | Context-based retrieval, not text matching | **C. Semantic retrieval** |
| 3 | Select a line → get an explanation | **D. Line-select explain** |
| 7 | Answer *why*, explain failures | **E. Positioning + richer sources** |
| 9 | Remove restrictions on touching real code | **REFUSED — see below** |

### Grounding (what the code does today, verified)
- `evals/ingest.py` globs only `*.py` + `*.md` under a **single** `--code-dir`
  (default `llm`). No other languages, no other directories, no whole-repo pass.
- `fetch_prs` reads only **merged** PRs (limit 200); `fetch_issues` reads only
  issues **linked from those PRs** (`closingIssuesReferences` / `#N` in the body).
  Standalone issues and open PRs are never ingested. **Titles *are* captured**
  (`fetch_issues` writes `{title}\n\n{body}`) — so remark 5's "titles dropped" is
  almost certainly *coverage* (an issue we never ingested), not a title bug. Brick
  B verifies this against the tester's specific repo before writing code.
- `evals/retriever.py` is BM25 — literally keyword/text matching. Remarks 6/8 are
  correct: no semantics.

---

## The reframe on remark 1 (read this before building)

"You're redundant on undocumented legacy code" reads as an argument *against* the
honesty wedge. It is the opposite — **but only if we also index the code itself.**

- Today the "why" leans on PRs/decisions/docs. A legacy repo with none of those
  leaves Icarus with little to retrieve → looks empty → looks redundant.
- The fix is **not** to abandon the honest unknown. It is: index *all the source*
  so **what/how** questions work on any repo, and let **why** honestly return
  *"no one wrote this down"* when the record is genuinely empty. That honest
  unknown is the hero shot, not the failure — it is exactly what a code-search
  competitor bluffs through.

So Brick A (whole-codebase ingest) is what makes remark 1 land in our favor.
Nothing in this plan weakens the abstention gate to paper over thin retrieval.

---

## Remark 9 — off the table (Alankrit's call, recorded)

Icarus **writing or modifying real code** is not a brick in this plan. It is a
different product (a coding agent) and it detonates the moat: cite-or-unknown,
retrieval-only, "never train on / act on customer code, discard after each
request." If it is ever revisited it is a deliberate strategy pivot **post-Phase-4
at the earliest**, scoped in its own decision doc — not smuggled in by loosening
the honesty constraints. Recorded here so it is not silently reopened.

---

## Refined north star (Alankrit, 2026-07-06)

> Icarus must understand a codebase **from the code itself** — regardless of
> whether descriptive PRs, issues, or docs exist. If nothing is written down, it
> reads the code and understands it well enough to answer **any** question,
> **regardless of framing, grammar, or spelling**. A JARVIS for every developer.

The load-bearing word is "any." Read naively it collides with cite-or-unknown.
Read correctly it *is* cite-or-unknown. That resolution is the governing
principle below, and it sits above every brick.

## Governing principle — the honesty boundary (over every brick)

"Answer any question" means **any phrasing of any answerable question** — never
"fabricate when the evidence isn't there." The boundary is deterministic:

- **What / how — derivable from the code.** With the code indexed and understood,
  Icarus should almost never abstain here. It reads the code and answers, citing
  the lines. Bricks A + C + S are what make this near-total. This is where the
  vision demands we get dramatically better.
- **Why / intent — sometimes never recorded.** You cannot derive "why Postgres
  over Mongo" from code if the reasoning was never written. Here the honest
  unknown **stays** — and it is the reason every *other* answer is trustworthy. A
  JARVIS that bluffs the "why" saves the developer nothing, because they'd have to
  re-verify everything.

So: *Icarus answers anything the code or the record can support, in any phrasing,
and is honest about the rest.* No brick in this plan weakens the abstention gate
to make thin retrieval look smarter — richer ingest and smarter retrieval feed the
gate more evidence; they never change what counts as a provable answer.

## Sequencing (probe first, then cheapest impact-per-brick)

Risk-first (playbook-planning): **Brick 0 is the probe** — it measures the very
thing the vision claims and is buildable *now* against the committed corpus, so it
reads RED before A/C and turns GREEN as they land. Nothing claims "understands
code" until Brick 0 says so.

```
Brick 0  Code-comprehension eval set   PROVES the vision · buildable now · RED baseline   ← probe
Brick A  Whole-codebase ingest         fixes 1,2,4 · unblocks D,Q,S · small
Brick B  PR/Issue coverage + bug       fixes 5                       · small
Brick C  Semantic retrieval            fixes 6,8 · lifts 7           · needs a dependency decision
Brick Q  Query-understanding layer     "any framing/grammar/spelling" · rides on C
Brick D  Line-select → explain         fixes 3 · after A+C
Brick S  Structural comprehension      the deep "reads the code" · LARGE · needs explicit go (deferred-gated)
Brick E  Richer "why" sources          lifts 7 · optional, after C
```

**Walking skeleton (earliest end-to-end proof):** after **0 + A + C**, a
messily-phrased *what/how* question returns a cited answer drawn from code alone,
and the eval board (Brick 0's set) reads green on comprehension with both honesty
gates at 100%. Everything after that milestone is deepening (Q, D, S, E), not new
promise.

Each brick is independently shippable and independently proven by the harness; one
brick in flight at a time.

---

## Brick 0 — Code-comprehension eval set (the probe; do this first)

**Goal:** a labelled question set that measures *understanding the code itself*,
asked in **deliberately messy phrasing**, so every later brick is proven red→green
instead of asserted.

**Why:** `phase1_questions.json` is "why"-heavy (6 PR-intent questions). It cannot
prove Icarus comprehends code, and it cannot prove robustness to bad grammar/
spelling. Per playbook-planning this is the *fatal-assumption probe* — and it is
buildable **now** against the committed `simonw/llm` corpus, which already has
`*.py` chunks, so it reads RED on today's BM25 + why-tuned pipeline and turns
GREEN as A/C/Q land.

**Success criterion (binary, externally checkable):**
- A new labelled file (e.g. `evals/comprehension_questions.json`) with **≥ 12**
  *what/how* questions grounded in `simonw/llm` code, each carrying a gold
  citation (`code:path#Lstart-Lend`) and a `reference_answer` for the judge.
- **Each question has a messy-phrasing variant** (typos + broken grammar) that must
  resolve to the *same* gold citation — this is the objective test for remark
  "any framing/grammar/spelling."
- At least 2 **honest-unknown** *why* questions whose intent is genuinely
  unrecorded, to keep the abstention gate honest on this set too.
- The eval board runs this set (`evals/run.py` extended or a sibling target),
  both honesty gates fire correctly, and comprehension/robustness read RED on the
  current pipeline (the baseline we will beat).

**Tasks (red→green):**
- **0.1** Author the set (human + Claude); a schema/loader test proves every
  answerable Q has a gold `code:` citation + reference answer, every unknown has
  none, and every Q has a messy variant. Mirror `test_reference_answers.py`.
- **0.2** Wire it into the grader/board as a distinct set (do **not** touch the
  frozen `phase1_questions.json`); record the RED baseline numbers in the doc.

**Definition of done:** the comprehension board runs, gates hold, and it reads RED —
a measured gap, not a vibe. This number is the acceptance test for A/C/Q/S.

**Execution log — Task 0.1 (done, branch `brick-0-comprehension-eval`, commit `dfb38a0`):**
`evals/comprehension_questions.json` (15 Qs: 13 answerable, 2 unanswerable) +
`evals/test_comprehension_questions.py` landed, spec-verified independently
(citations checked against the real corpus, 6/13 reference answers spot-checked
against actual source text, messy variants confirmed non-trivial, scope boundary
confirmed — `phase1_questions.json`/`grader.py`/`run.py` untouched). Two decisions
recorded here for **Task 0.2** to pick up, so they aren't lost between sessions:
- **Schema deviation (intentional, not a bug):** the new file uses a flat
  `"citations": ["code:llm/models.py", ...]` field, **not** `phase1_questions.json`'s
  `"gold_citations": [{"source", "ref", "why", "also_in_docs"}, ...]` shape read by
  `grader.gold_refs()`. This was the simplest schema that satisfied Task 0.1's own
  test spec, but it means **Task 0.2's grader/board wiring must either add a second
  parsing branch for the flat-string shape or reshape the JSON to match
  `gold_citations`** — decide explicitly at the start of 0.2, don't let it surprise
  you mid-task.
- **Granularity deviation (flagged by the final whole-brick review, not caught
  earlier):** this Brick 0 section's own success criterion (above) specifies gold
  citations as `code:path#Lstart-Lend`. What Task 0.1 actually delivered is
  whole-file citations (`code:llm/models.py`, no line range) — because the
  committed corpus only *has* whole-file `code:` chunks today (line-window
  chunking doesn't exist until Brick A). This is internally consistent (every
  test passes, both gates hold) but means **the retrieval_recall/citation_correctness
  baseline below is measured at whole-file granularity.** Once Brick A lands
  line-ranged refs, these two numbers are not directly comparable before/after —
  re-baseline (or note the granularity change explicitly) when A lands.
- **Known limitation:** question `c14` (why `Fragment.id()` uses `sha256`) is the
  weaker of the two honest-unknown cases — a nearby issue (`issue:617`) discusses
  `sha256` as precedent from a *different* feature, without stating a rationale for
  `Fragment.id()` itself. Still a legitimate abstention, but the more contestable
  one if this set is later used to stress-test the honesty gate against a
  plausible-sounding-but-unrecorded rationale.
- **Code-quality review verdict: ready to merge, no Critical/Important issues.**
  Two Minor, non-blocking test-rigor notes for whoever next touches this file: (a)
  `test_every_question_has_a_genuinely_messy_variant` only asserts `!=`, not a
  minimum divergence — a future question with a 1-character messy variant would
  still pass; (b) no test guards against duplicate/malformed refs inside a single
  question's `citations` list. Cheap to add if this set grows past ~15 rows;
  not worth a review round-trip at the current scale.

**Task 0.2 — corrected scope, verified against the real code before dispatch:**
1. **`evals/run.py` already has `--questions PATH` (default `phase1_questions.json`)**
   — no CLI change needed. `python3 -m evals.run --questions
   evals/comprehension_questions.json --pipeline gated` already runs any
   compatible question file today.
2. **The only real gap:** `evals/grader.py:18-20`'s `gold_refs()` reads
   `question.get("gold_citations", [])` (list of `{"source","ref",...}` dicts).
   `comprehension_questions.json`'s answerable questions use a flat `"citations":
   ["source:ref", ...]` list instead (confirmed: unanswerable questions already
   correctly use the existing `correct_behavior`/`notes` convention — the
   deviation is narrowly scoped to just this one field on answerable questions).
   Left as-is, `gold_refs()` silently returns `[]` for every comprehension
   question, making `retrieval_recall`/`citation_correctness` read a **false**
   0% (a data-shape bug, not a genuine capability signal) — the two real gates
   (groundedness, abstention recall) are unaffected since they don't use
   `gold_refs()`. **Fix:** `gold_refs()` gains a fallback — if `"citations"` is
   present, return it as-is (already `"source:ref"`-shaped); else fall back to
   the existing `gold_citations` dict-list logic. Two-line, backward-compatible,
   doesn't touch `phase1_questions.json`'s behavior at all.
3. **Real keys are available in this environment** (`.env` has `GROQ_API_KEY` +
   `GEMINI_API_KEY`) — Task 0.2 runs the actual `gated` pipeline for a genuine
   baseline, not a stub. Run once, not concurrently with anything else (free-tier
   quota).

**Honest limits:** authored on one repo (`simonw/llm`); it measures *our* pipeline,
not ground-truth "understanding" in the abstract. Only 2 unanswerable questions —
`abstention_recall` (gate) is quantized to {0%, 50%, 100%} and `abstention_precision`
(quality dial) is a small-sample estimate; grow the unanswerable set before treating
either number as a tuning target.

**Execution log — Task 0.2:**

`evals/run.py` already had a `--questions PATH` flag (default `phase1_questions.json`),
so no CLI change was needed. The one real gap was `evals/grader.py`'s `gold_refs()`,
which only read the `gold_citations` dict-list shape used by `phase1_questions.json`
and silently returned `[]` for `comprehension_questions.json`'s flat `citations:
["source:ref", ...]` field — which would have made `retrieval_recall_at_k` and
`citation_correctness` read a false, meaningless 0% for every question. Fixed with
a two-line fallback: `gold_refs()` now returns `question["citations"]` as-is when
present, otherwise falls back to the existing dict-list logic unchanged.
`evals/test_grader.py` gained two tests proving both shapes: the existing
`gold_citations` dict-list still normalizes correctly (regression), and the new flat
`citations` list normalizes as-is. Full offline suite (`python3 -m unittest discover
-t . -s evals`) stayed green: 125 tests, 12 skipped (live-network tests), 0 failures.

Ran the real gated pipeline once (`python3 -m evals.run --questions
evals/comprehension_questions.json --pipeline gated`, Groq writer) against the 15
comprehension questions (13 answerable, 2 unanswerable) on the committed
`simonw/llm` corpus. Both honesty gates held at 100% (groundedness, abstention
recall) — no bluff, no ungrounded citation. The measured RED baseline: retrieval
recall@k **53.8%**, citation correctness **30.8%**, answer correctness **30.8%**,
abstention precision **20.0%**. Status: `RED -- gates hold, quality below target`.
This is the concrete gap Bricks A/C/Q/S exist to close.

**Reconciled:** this branch had diverged from `main` (which had picked up two
doc-only commits recording Task 0.1's review verdict and Task 0.2's design
decisions, not yet present here) — merged `main` into this branch after Task 0.2
landed; both execution logs above now live together on `brick-0-comprehension-eval`.

**Code-quality review verdict: ready to merge, no Critical/Important issues.**
Two Minor, dormant (not live-data-affecting) test gaps for whoever next touches
`gold_refs()` or adds a third question-file schema: (a) no test for a question
carrying both `citations` and `gold_citations` (current precedence: `citations`
wins, untested); (b) no explicit test for a question with neither key (falls
back to `[]`, matching old behavior, but not asserted directly). Cheap to add
alongside the next schema change, not worth a round-trip now.

**Brick 0 status: DONE.** Both tasks (0.1, 0.2) implemented, independently
spec-reviewed and code-quality-reviewed, both verdicts "ready to merge." The
measured RED baseline above is the acceptance bar Bricks A/C/Q/S must beat.

---

## Brick A — Whole-codebase ingest (all languages, all directories)

**Goal:** `evals.ingest` chunks *every* source/text file in the repo, not just
`*.py`/`*.md` under one dir — so retrieval has the whole codebase to cite.

**Why:** remarks 1, 2, 4. Today a Go/TS/Rust/config repo yields PRs + issues but
almost no code evidence.

**Design decisions (lock before coding):**
1. **What counts as ingestable.** Extension allowlist of text/source types
   (`.py .js .ts .tsx .go .rs .java .rb .c .h .cpp .swift .kt .php .cs .scala .sh
   .yaml .yml .toml .cfg .ini .sql .md .rst .txt` — finalize the list). Skip
   binaries by extension **and** by a null-byte sniff. Keep the existing
   `_MAX_FILE_BYTES` / `_MAX_TOTAL_BYTES` caps — they are the OOM guard for a huge
   repo and must not be removed.
2. **Skip noise.** Ignore `.git`, `node_modules`, `vendor`, `dist`, `build`,
   `.venv`, lockfiles, minified assets. A small deny-list of dirs/globs.
3. **`--code-dir` becomes optional.** Default = whole repo root (walk everything);
   `--code-dir` still narrows the subtree when passed. No-arg `simonw/llm` run must
   stay byte-reproducible — so keep its default `code_dir="llm"` for the pinned
   corpus path, but make the general path walk the root.

   **Clarified before A3 (resolves a real conflict, checked against the actual
   committed corpus):** "byte-reproducible" here means the no-arg run still
   targets the **same repo/commit/code_dir scope** (`simonw/llm` @ `94769b8`,
   subtree `llm/`) — matching the precedent already established in Brick 7's plan
   ("re-ingesting is never bit-identical... this brick does not regenerate
   [the committed corpus]"). It does **not** mean the new classify/chunk logic
   must reproduce today's exact chunk boundaries. Checked: **8 of the 18 code
   chunks in the committed corpus already exceed 300 lines** (`llm/cli.py` is
   4166 lines), so applying Task A2's chunker for real would split them
   differently than today's whole-file chunks — that's fine and expected, it is
   NOT a regression. What must never happen: this task (or any test in it)
   actually running `python3 -m evals.ingest` for real / overwriting
   `evals/corpus/chunks.jsonl` or `evals/corpus/meta.json`. All new-path testing
   is via monkeypatched network calls into a temp output dir, exactly like the
   existing `evals/test_ingest_repo.py` pattern — never touching the real
   committed files. `--code-dir`'s DEFAULT VALUE resolution (not the chunking
   logic) is what stays scoped: `None` sentinel → resolves to `"llm"` only when
   `repo == REPO` and no override was given; otherwise resolves to `"."` (walk
   the whole clone root).
4. **Citation source tag.** Keep `code:` for source, `doc:` for prose (`.md/.rst/
   .txt`); add `config:` for config-ish files so citations read honestly. One-line
   `_FILE_SOURCES`-style mapping extension → source.
5. **Chunking.** Large files must be split (a 3k-line file as one chunk is useless
   for retrieval *and* blows the writer's context). Add size-bounded chunking
   (by lines, with overlap) — this is also a prerequisite for Brick D. This is the
   one non-trivial sub-task; give it its own red test.

**Branch note (found during A1, decided by Alankrit):** an unmerged prior branch
`feat/ingest-markdown` (commit `15373ca`) had already added a narrower `*.py`+`*.md`
→ `code`/`doc` glob (`_FILE_SOURCES`, `_collect_files`) plus matching `doc:` link
support in `demo/links.py`/`index.html` — but it was never merged into `main`
before Brick 0/A branched off. Since A1's classifier already generalizes `.md` →
`doc` as a strict superset (plus far more languages, deny-lists, binary-sniffing),
**Brick A supersedes `feat/ingest-markdown` entirely** — do not merge it in; A3/A4
rebuild the doc-linking behavior more generally. `feat/ingest-markdown` can be
deleted once Brick A lands.

**Tasks (red→green):**
- **A1 — extension/deny-list classifier (pure, offline).** `test_ingest_files.py`:
  a fixture tree with `.py .go .yaml`, a binary, a `node_modules/` file, an
  oversized file → assert only the intended files are selected with the right
  source tag. Then implement the classifier in `ingest.py`.
- **A2 — line-window chunking (pure, offline).** Test: a long file splits into N
  overlapping windows with stable `code:path#Lstart-Lend` refs; a short file → one
  chunk. Implement. **`ref` format carries line ranges** (needed by links + Brick D).
- **A3 — wire into `_collect_files`/`fetch_code`.** Extend `test_ingest_args.py` /
  `test_ingest_repo.py` (network monkeypatched) so whole-repo walk + caps + skip
  rules hold and counts come back per source.
- **A4 — links.** Update `demo/links.py` (`ref_to_url`) so a `code:path#L10-L40`
  ref deep-links to the right lines on GitHub at the pinned commit; extend
  `demo/test_links.py`.

  **Scope clarified before dispatch:** today `ref_to_url` returns `None` for
  `doc:`/`config:` sources entirely (never implemented — the unmerged, superseded
  `feat/ingest-markdown` branch had added `doc:` support, but that branch is not
  merged in, per the A1 decision). Now that A3 landed real `doc:`/`config:`
  ingestion, leaving them unlinked would mean whole-repo ingest produces citations
  that render as dead plain text — a real regression, not a neutral gap. `doc:`
  and `config:` use the exact same GitHub blob URL as `code:` (`blob/{commit}/
  {rest}`), so A4's scope now includes routing all three through the same
  line-range-aware blob-URL logic; `pr:`/`issue:` stay untouched. Visual chip
  styling for `doc:`/`config:` in `demo/index.html` is explicitly deferred (not
  required for correctness, purely a color-coding nicety) — out of scope for A4.
- **A5 — skippable live smoke.** Extend `test_ingest_smoke.py` to ingest a tiny
  **non-Python** public repo behind `RUN_INGEST_SMOKE=1` and assert non-`.py`
  chunks appear.

**Definition of done:** ingesting a mixed-language public repo produces `code:` /
`doc:` / `config:` chunks across the whole tree; caps + skip-lists hold; citation
links point at the right file and lines; no-arg `simonw/llm` corpus unchanged;
offline suite green; **no new dependency.**

**Honest limits:** still public repos only on free writers; no language-aware
parsing (line-window chunks, not AST/symbols) — that is a later brick if Brick C
plateaus; the eval board still only measures `simonw/llm`.

**Execution log — Brick A (done, branch `brick-a-whole-codebase-ingest`):**
All five tasks (A1 file classifier, A2 line-window chunking, A3 wiring into
`fetch_code`, A4 line-ranged multi-source citation links, A5 live smoke test)
landed, each independently spec-reviewed and code-quality-reviewed with
"ready to merge" verdicts, plus follow-up hardening applied per task (a
`relative_to` fallback removed in A1, a `stride`/stray-`#` guard added in A2,
an unguarded `OSError` on file reads fixed in A3, a stale docstring + missing
test fixed in A4). **A5 genuinely proved end-to-end multi-language ingest live**
against a real, tiny non-Python repo (`sindresorhus/is-online`): 10 chunks (7
code, 2 doc, 1 config) — independently reproduced by two different reviewer
subagents making the real network call themselves, not just trusting the
implementer's report.

**Gap flagged by A5's code-quality review, resolved by the final whole-brick
review:** no test chained a REAL non-Python ingest (A5) through `ref_to_url`
(A4). The final review independently traced the whole `classify_file` →
`chunk_text` → `fetch_code` → `ref_to_url` pipeline by hand and found no
mismatch, but concluded the gap was real against Brick A's own stated
Definition of Done ("citation links point at the right file and lines") and
cheap enough to close outright rather than defer — reusing A5's own
already-captured live refs, no new network call needed. Closed as a small
follow-up to A5.

**Two Minor findings recorded for later, not blocking:**
- **`.json` is absent from `_EXTENSION_SOURCES`**, so `package.json`/
  `tsconfig.json`/`.eslintrc.json` are silently dropped from ingest — a
  conspicuous gap for a "whole codebase, all languages" brick, since these are
  extremely common in JS/TS repos (confirmed: `sindresorhus/is-online`'s own
  `package.json` isn't counted in A5's live 10-chunk result). Consistent with
  the plan's "finalize the list" framing, but worth an explicit decision in a
  follow-up rather than staying an implicit omission.
- **`ingest_repo`'s `code_dir="llm"` parameter default is now dead/misleading**
  (`evals/ingest.py`) — both real callers always pass `code_dir` explicitly
  now, so a future direct caller omitting it would silently only walk `llm/`
  even for an unrelated repo, quietly contradicting "whole repo by default."
  Not urgent (nothing in the codebase hits this today); consider tightening
  when next touching this function.

---

## Brick B — PR/Issue coverage (and the "dropped title" report)

**Goal:** ingest **all** issues and **open + merged** PRs, not just merged PRs and
their linked issues. Confirm or refute the title report first.

**Why:** remark 5. Coverage gap: a standalone issue (never linked from a merged PR)
is invisible today, which *looks* like "titles not picked up."

**B0 result (repro'd, 2026-07-07):** Alankrit's tester feedback traced to
`benawad/vsinder` issue `#253` ("Android app not displaying new matches and
messages," state OPEN). Ran the real `ingest_repo` against this repo into a
scratch dir (never touched the committed corpus): `{"pr": 26, "issue": 12,
"code": 0}`. Grepped the output — **issue #253 is completely absent**; only 12
low-numbered issues (5–166) were captured, all with clean, correct titles
(e.g. "Rust as a flair", "Age calculation is a month off"). This confirms the
diagnosis exactly: it's a **coverage gap**, not a title bug — `fetch_issues`
only ever sees issues linked from a *merged* PR, and #253 is open/unresolved,
so it's never even attempted. Title-inclusion itself (`{title}\n\n{body}`) is
proven correct for every issue that does get fetched. **B1 (fetch all issues
via `gh issue list`) is confirmed as the right fix — proceed.**

**Tasks (red→green):**
- **B0 — repro (human + Claude).** Get the tester's repo + the specific issue that
  "lost its title." Re-ingest, grep `chunks.jsonl`. If the title is present → it
  was a coverage miss (proceed). If genuinely absent → fix the real bug in
  `fetch_issues` first. **Do not write the coverage code before this is known.**
- **B1 — `gh issue list` pass (network fn, thin).** Add an issue-list fetch (all
  issues up to a limit, states open+closed) alongside the linked-issue set; dedupe
  by number. Keep the linked-issue logic (cheap "why" signal). Unit-test the
  dedupe/merge as a pure function over stub JSON.

  **Done — `ISSUE_LIMIT=500` + `fetch_all_issue_ids`, plain set union with the
  existing linked-issue set (no wrapper needed). Ready to merge, no
  Critical/Important-blocking issues; `fetch_prs` confirmed byte-identical.
  Two non-blocking test-coverage gaps recorded for a fast-follow (not this
  brick): no test asserts the literal `gh issue list --state all --limit 500`
  CLI args reach the subprocess call (a future accidental edit dropping
  `--state all` would silently reintroduce the #253 gap, uncaught); no
  integration test for the zero-issues-in-repo case flowing through
  `ingest_repo` (the pure algebra is tested, the end-to-end path isn't).**
- **B2 — include open PRs.** `pr list --state all` (or `open` + `merged`), guarded
  by the same `PR_LIMIT`. Pure-test the number collection.
- **B3 — counts + meta.** Extend `ingest_repo` counts and `meta.json`; update
  tests.

**Definition of done:** a repo's standalone issues and open PRs appear in the
corpus with titles; dedupe verified; no-arg `simonw/llm` corpus untouched (its
counts are frozen — this brick changes the *general* path, and if it would alter
the pinned corpus, gate the new breadth behind the same "default repo keeps its
frozen behavior" rule Brick 7 established).

**Honest limits:** issue/PR *comments* still deferred (noise/volume); `PR_LIMIT`
still caps very large repos.

---

## Brick C — Semantic retrieval (context, not keywords)

**Goal:** retrieve by meaning, not term overlap, so "why does auth fail on token
refresh" finds the relevant code/PR even when it shares no keywords.

**Why:** remarks 6, 8; lifts 7. BM25 can't match paraphrases or concepts.

**⚠️ This brick needs a decision from Alankrit before any code — it likely adds a
dependency, which CLAUDE.md forbids without asking.** Two routes:

- **C-route-1 — hosted embeddings via the provider abstraction (recommended).**
  Add an `EmbeddingProvider` next to the writer/judge providers (Gemini/Cohere/
  OpenAI embeddings). Fits "rent the commodity, own the pipeline," stays close to
  stdlib, no heavy local model. **Trust boundary:** embedding text = sending it to
  the provider → **public repos only on free embeddings**, and **private repos must
  route through the private-safe provider + trust interlock** exactly like the
  writer does today (`evals/trust.py`). This route inherits the existing isolation
  proofs.
- **C-route-2 — local open embeddings (`sentence-transformers`).** Matches the
  CLAUDE.md stack line ("local open embeddings") and keeps text on-box, but adds a
  real dependency + model download + CPU cost. Heavier for the demo/Render image.

**Recommendation:** C-route-1 first (fastest to prove, reuses the trust interlock),
keep C-route-2 as the private/on-box option later. **Get Alankrit's sign-off on the
dependency/route before building.**

**Tasks (red→green), route-1 shape:**
- **C1 — `EmbeddingProvider` abstraction** with a `StaticEmbeddingProvider` test
  double (deterministic vectors); no-key error path; 429 backoff — mirror
  `evals/provider.py` + `test_provider.py`.
- **C2 — `SemanticRetriever`** (cosine over cached chunk vectors). Pure test with
  the static provider: a paraphrased query ranks the right chunk above a
  keyword-only match. Precompute + cache vectors at ingest (persist next to
  `chunks.jsonl`); the demo loads them.
- **C3 — hybrid rank (optional but recommended).** Blend BM25 + semantic
  (reciprocal-rank fusion). Prove recall@k rises on the labelled set **without
  dropping either honesty gate** — the red→green retrieval eval already exists
  (`test_retrieval_eval.py`); extend it.
- **C4 — gate untouched.** Explicitly assert the honesty gate + abstention recall
  stay 100% with semantic retrieval on (`grader`/`gate` tests). Retrieval getting
  smarter must never let a bluff through.

**Definition of done:** recall@k on `phase1_questions.json` beats BM25 with both
gates at 100%; private repos still only reach the private-safe embedder via the
interlock; the egress invariants test extended to cover the embedder.

**Honest limits:** embeddings improve *recall*, not truthfulness — the
deterministic gate is still the only thing standing between retrieval and a claim.

---

## Brick Q — Query-understanding layer (any framing, grammar, spelling)

**Goal:** the *same* answer whether the developer types "how does auth refresh
work" or "how duz teh authh refersh wrk lol". Robustness to phrasing, grammar, and
spelling — a first-class capability, not a side effect.

**Why:** the vision's "regardless of framing, grammar, or spelling." BM25 breaks on
a misspelled term (no token match); embeddings absorb most paraphrase/synonymy but
not arbitrary typos.

**Design (locked order):** embeddings (Brick C) do the heavy lifting for paraphrase
and synonyms, so **Q rides on C**. On top, a thin normalization step: lowercase,
spell-tolerant tokenization, and — where a writer call is already being made — let
the LLM restate the question before retrieval. No new heavyweight dependency;
prefer stdlib fuzzy matching over a spellcheck library unless a probe shows it's
needed.

**Success criterion (binary):** every messy-phrasing variant in **Brick 0** returns
the same gold citation as its clean twin, at the same k, with both gates at 100%.
That's the objective, pre-committed test.

**Tasks (red→green):**
- **Q1** Pure query-normalizer (fuzzy tokenize + optional LLM restate behind the
  provider abstraction); unit-tested on typo pairs.
- **Q2** Wire ahead of the retriever; extend the Brick 0 board to assert
  clean-variant parity. Turn Brick 0's robustness metric GREEN.

**Definition of done:** Brick 0's messy variants match their clean twins; gates
untouched.

**Honest limits:** extreme gibberish or ambiguous questions still legitimately get
"can you clarify / no evidence" — robustness is not mind-reading.

---

## Brick S — Structural comprehension (reads the code like a developer)

**Goal:** understand code *structurally* — what calls what, what a function depends
on, how data flows — so Icarus answers "how does X work across the system," not
just "here's the chunk that mentions X." This is the deep "reads and understands
the code" the vision is really about.

**Why:** the tail of remarks 1/4/7 and the north star. Line-window chunks (Brick A)
+ embeddings (Brick C) get us *semantic* retrieval; they do not get us a call
graph. Real comprehension of an undocumented legacy repo needs structure.

**⚠️ Gated — needs Alankrit's explicit go.** CLAUDE.md lists "deep structural code
understanding / dependency tracing" under **Do not build yet (post-Phase-4)**. This
brick is written so it's *ready*, not so it's started. It is also the **largest**
brick and almost certainly adds a parsing dependency (e.g. tree-sitter / language
servers) — which needs sign-off.

**Probe first (cheap, before committing):** on `simonw/llm` (Python), build a
call-graph for *one* module with stdlib `ast` only, and measure whether adding
"callers/callees as retrieval neighbors" moves Brick 0's harder *how-across-system*
questions. Stdlib `ast` is Python-only; multi-language structure is what would need
tree-sitter — decide based on the probe.

**Success criterion (binary):** the *structural* subset of Brick 0 (how-does-X-flow
questions) beats the Brick A+C baseline on recall@k, gates still 100%.

**Definition of done / limits:** deferred-gated. Even built, it stays retrieval +
reasoning + cite-or-unknown — never autonomous action on code (remark 9 stays
closed).

---

## Brick D — Select a line → explain it

**Goal:** in the app, select a file+line range and ask "what does this do / why is
it here" → a cited answer grounded in that code plus the PRs/issues/docs that
touch it. Honest unknown when the *why* was never written.

**Why:** remark 3. High-signal demo moment; depends on A (line-addressable chunks)
and benefits from C (semantic neighbors).

**Tasks (red→green):**
- **D1 — brain endpoint.** `POST /explain {repo, path, start, end}` → resolve the
  chunk(s) covering those lines (A2 refs), retrieve neighbors (semantic + the PRs/
  issues that reference the file), run the same cite-or-abstain writer → gate →
  `Result`. New handler test in `demo/test_server.py`; **reuses the gate — no new
  honesty path.**
- **D2 — payload/links** for the explain shape (`demo/payload.py`,
  `demo/test_payload.py`).
- **D3 — app surface** (`mac/`): a line-selection → explain call in the overlay/
  shell, rendering the cited answer or the honest unknown. IcarusKit client method
  + test; SwiftUI wiring.

**Definition of done:** selecting real lines returns a cited explanation or an
honest unknown, proven end-to-end (brain test + one live guard); no new gate.

**Honest limits:** explanation quality rides on A+C; without language-aware parsing
the "neighbors" are retrieval-based, not call-graph-based (deep structural
understanding stays post-Phase-4 per CLAUDE.md).

---

## Brick E — Richer "why" sources (optional, after C)

**Goal:** answer more "why did this fail / why is it this way" by adding
commit-message + `git blame` provenance for a line, so even repos thin on PRs have
*some* recorded rationale.

**Why:** remark 7 and the tail of remark 1. Commit messages are the most universal
"why" signal in legacy repos.

**Sketch (not yet task-broken — scope after C lands):** ingest commit messages as a
`commit:` source; on explain, map a line → its introducing commit via blame. Still
retrieval + cite-or-unknown; still no structural analysis. **Prove with a red eval
before building.**

---

## Cross-cutting invariants (true for every brick)
- Prove the gap with a **failing eval first**; never weaken an eval or a gate to
  pass (CLAUDE.md / WORKFLOWS.md).
- The **deterministic honesty gate is untouched** by all of this — richer ingest
  and smarter retrieval feed it more/better evidence; they never change what counts
  as a provable answer vs. an honest unknown.
- **Public repos → free providers; private repos → private-safe provider via the
  trust interlock.** Any new provider (embeddings) inherits this, with the egress
  test extended.
- **No new dependency without Alankrit's explicit sign-off** (Brick C is the one
  that needs it — decide the route first).
- Regenerate `general_index.md` + `detailed_index.md` after each brick's structural
  changes.

## Not doing (deferred, with reopen-triggers)
- **Icarus writes/modifies real code (remark 9).** Closed. *Reopen trigger:* a
  deliberate strategy pivot in its own decision doc, post-Phase-4 — never by
  loosening the honesty gate.
- **Structural comprehension / dependency tracing (Brick S).** Ready, not started.
  *Reopen trigger:* Alankrit's explicit go **and** the Brick S probe showing
  call-graph neighbors move Brick 0's structural questions.
- **Multi-language structural parsing (tree-sitter et al.).** *Reopen trigger:*
  the stdlib-`ast` probe proves value on Python first.
- **Private repos on new providers (embeddings).** Allowed only through the
  existing trust interlock; *reopen trigger for free embeddings on private code:*
  never.
- **Issue/PR comment ingestion, incremental sync.** *Reopen trigger:* a repo where
  the answer provably lives in comments and Bricks A/B/C miss it.

## Re-planning checkpoints
- After **Brick 0**: record the RED baseline. If comprehension is already high on
  the current pipeline, re-scope A/C (unlikely, but the probe decides — not a
  guess).
- After **each brick**: run both boards (`phase1` + comprehension). A broken gate
  halts everything. A brick that overran its session gets split, not pushed.
- Before **Brick C**: the dependency/route decision is made and written here first.
- Before **Brick S**: the probe result is written here; no go without it.

## Recommended first move
Alankrit chose "just write the plan," so nothing is built yet. When you are ready,
**start Brick 0** — the code-comprehension eval set. Per playbook-planning it is the
probe that de-risks the whole vision: buildable now against the committed corpus,
it turns "Icarus understands code" from a claim into a measured RED number that
Bricks A/C/Q/S then drive to GREEN. Brick A is the first *build-the-brain* step
right after it.
