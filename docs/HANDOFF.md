# Icarus — Session Handoff (2026-07-08 → 2026-07-09)

Read this first next session. It supersedes the prior handoff (2026-07-07 →
2026-07-08) entirely — that session's open item (the Gemini-quota-blocked
Brick C proof) is resolved and its whole storyline is now historical (§6). This
handoff covers everything since: Brick C landing free/local, its demo-wiring
follow-up, Brick Q, a billing decision, and Brick D through D4.

**The plan doc is still the source of truth for brick-by-brick detail:**
`docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md`. This handoff
is the orientation layer + routing map on top of it — read the linked sections
before starting any pending work, don't rely on this doc's summaries alone.

**Important asymmetry to know before you go looking:** Bricks C, its demo-wiring
follow-up, and Q are **merged to `main`** — their plan-doc status write-ups are
in `main`'s copy of the plan doc. **Brick D (D0–D4) is NOT merged** — it lives
on branch/worktree `brick-d-explain-line`, and *that branch's copy* of the plan
doc has the D0–D4 status sections. `main`'s copy of the plan doc stops at
Brick D's original (pre-work) task list — if you only look at `main`, you will
NOT see the D0–D4 findings. See §2 for how to get to them.

---

## 0. TL;DR — where things stand

**On `main`, merged, done:**
- Brick C — semantic retrieval, **local + free** (pivoted off the original
  hosted-Gemini plan after it hit an unfixable free-tier quota wall). §1.
- Brick C's demo-wiring follow-up — the product actually uses semantic
  retrieval now, not just the eval harness. §1.
- Brick Q — query-understanding layer (typo/grammar robustness) + a
  third-party grep-baseline comparison. §1.
- A billing/private-repo decision, recorded and closed (not re-litigate). §1.4.

**Built, tested, live-verified where possible, NOT merged:**
- Brick D, tasks D0 through D4 (of D0–D5) — a GitHub browser extension that
  lets you select a line of code on github.com and ask Icarus what it does or
  why, for a repo you've already connected. Branch/worktree
  `brick-d-explain-line`. §2.
- **D5 (the final live guard) is the one open item, and it needs you
  specifically** — I cannot load a real Chrome extension myself (confirmed by
  trying: `chrome://extensions` is barred from remote automation). §2.5.

**Not started:**
- Brick E — richer "why" sources (commit-message/git-blame provenance).
  Sketched, not task-broken. §3.1.
- Brick S — structural comprehension (AST/call-graph). Deliberately
  deferred-gated; needs your explicit go before any code. §3.2.

**Push status:** `main` is **34 commits ahead of `origin/main`**, unpushed (as
of this handoff). Brick D's 5 commits are on the separate unmerged branch, not
counted in that 34.

---

## 1. What's merged to `main` — brief; full detail is in the plan doc

Route: `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md`,
sections `## Brick C`, `## Brick Q` (search those headers — `main`'s copy has
the complete story for both, unlike Brick D).

### 1.1 Brick C — semantic retrieval, local + free (merge commit `8c3273e`)
The original plan called for hosted Gemini embeddings. That hit a **daily
per-project quota wall** that no key-swapping could fix (quota is scoped to the
Google Cloud project, not the key). At Alankrit's explicit call ("remove any
dependency on billing, do this free of cost"), the route was reopened and
rebuilt on **`fastembed`** — a local, offline ONNX embedding model
(`BAAI/bge-small-en-v1.5`), zero API key, zero quota, zero egress. Runs
server-side in the brain, so retrieval quality never depends on which laptop a
user has. On Brick 0's comprehension board: hybrid (BM25 + semantic) beats BM25
on clean phrasing (69.2% vs 53.8%) and roughly doubles it on messy phrasing
(61.5% vs 30.8%), both honesty gates 100%. Two independent adversarial
reviewers reproduced every number before merge; one real bug (a filename
tokenization mismatch that silently corrupted queries) was found and fixed
mid-build.

**The one new dependency:** `fastembed`, in `requirements.txt`. Run everything
from a venv:
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

### 1.2 Brick C's demo-wiring follow-up (merge commit `22a19ba`)
Brick C alone only proved semantic retrieval in the *eval harness* —
`demo/library.py` (the actual serving pipeline) was still lexical-only. This
follow-up wires `HybridRetriever` into the real demo, with a process-shared
embedder singleton (the model loads once, not per-request) and an on-disk
vector cache (`evals/vector_cache.py`) so a server restart doesn't re-embed the
whole corpus. Two independent reviews; a flaky test was found, traced to real
test-isolation gaps (not the underlying code), and fixed — suite is now
deterministic.

### 1.3 Brick Q — query understanding + a third-party comparison (merge commit `5a93d3f`)
A stdlib-only (no new dependency) fuzzy typo/spelling normalizer,
`evals/query_normalize.py`, wired ahead of retrieval via `NormalizingRetriever`
— the writer still sees the user's real, unmangled question; only the search
query gets corrected. Real measured lift: clean recall@5 69.2%→76.9%, messy
61.5%→69.2%. Also adds `evals/baseline_retriever.py`'s `GrepBaselineRetriever`
— a fair, deliberately dumb, dependency-free "what would a developer get by
just grepping the repo" yardstick — proving Icarus's retrieval is a real,
measurable improvement over that (clean +30.7pp, messy +15.4pp). Two full
rounds of independent review; one real bug (a tokenizer mismatch — the *same
class* of bug as Brick C's) and two genuine test-honesty gaps were found and
fixed, each self-verified by injecting the flagged failure and watching the
test catch it before reverting.

### 1.4 Billing / private-repo writer — decided, closed
Investigated to ground truth: the Gemini billing account is on the free tier,
no prepayment set up, across all projects — so `GEMINI_PAID_API_KEY`, despite
its name, is not actually on a genuinely billed/no-training tier right now.
**Alankrit's explicit decision:** private repos may use the free model for
now (pre-revenue demo stage) — do not build a paid-tier gate, do not disable
private repos. **The one thing this creates an obligation for:** the existing
app/demo UI's "private · paid writer — 0 trained on your code" badge is
currently **false** and must not be shown to a real user as a guarantee.
**Hard reopen-trigger:** before any real external customer's private code is
connected, this must be revisited (genuine billing + truthful labeling). Full
finding was in the prior handoff's §2a — compressed here since it's now a
closed, recorded decision, not open work. If you need the full investigation
trail (AI Studio screenshots, the exact quota numbers), it's in this file's
git history (`git log -p -- docs/HANDOFF.md`) around 2026-07-08.

**Live suite counts on `main` right now (verify yourself, don't trust this
number without re-running):**
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # once
.venv/bin/python -m unittest discover -t . -s evals   # expect 275 tests, 13 skipped
.venv/bin/python -m unittest discover -t . -s demo    # expect 136 tests, 2 skipped
```

---

## 2. Brick D — explain a line on GitHub (D0–D4 done, D5 pending — needs you)

**Branch/worktree:** `.worktrees/brick-d-explain-line`, 5 commits ahead of the
`main` it branched from (`c741ca7`, `0c32901`, `a043aba`, `d92b57a`, `bf003d8`).
**Not merged.** To resume:
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering/.worktrees/brick-d-explain-line"
# venv + .env already set up in this worktree from this session; if fresh:
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp "/Users/alankritghosh/JARVIS /jarvis_engineering/.env" .env
```

**Route to the FULL detail (this branch's copy, not `main`'s):**
`docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md` on this
branch — search for `D0 status`, `D1 status`, `D3 status`, `D4 status` (each
is a dated, detailed status block appended under the `## Brick D` section,
around lines 1072–1330 on this branch as of this handoff). Read those before
touching any of this code — they record real bugs found/fixed and *why*
specific design choices were made, not just what shipped.

### What it does
On github.com, in a repo you've already connected to Icarus, select a line (or
range) with GitHub's own click+shift-click gesture, click the "Ask Icarus"
button that appears, and get a cited answer or an honest "no one wrote this
down" — rendered as an overlay right there on the GitHub page.

### D0 — probe (done)
Live-tested GitHub's actual DOM (not assumed): blob-view line selection sets
`location.hash` to `#L5`/`#L1-L4` deterministically via click+shift-click
(drag-selection does NOT work — a real finding, not a guess). PR-diff view is
a structurally different, semantically ambiguous DOM — explicitly scoped out
of v1.

### D1/D2 — the brain endpoint (done)
`POST /explain {repo, path, start, end[, question]}` in `demo/server.py`,
`evals/corpus.chunk_covers_lines()` for resolving evidence by location instead
of a text search, `GatedPipeline.explain()` in `evals/pipeline.py` funneling
through the *same* honesty gate `.answer()` uses (no new honesty path). **A
real bug was found and fixed via live testing**: the first version searched
for supporting evidence using the code's own text even when you supplied a
real question, causing it to wrongly abstain on things `/ask` answers
confidently. D2 (payload shape) needed zero new code — `/ask`'s existing
`build_payload`/`ref_to_url` already fit `/explain`'s response exactly.

### D3 — the extension + a new OAuth mode (built, partially live-verified)
`extension/` — Manifest V3, Chrome, no build step, no npm dependency
(`node --test`, Node's own built-in runner, mirrors the Python side's
stdlib-only ethos). Also: **discovered mid-build that the plan's D3 task text
assumed a bearer token already exists to send — it doesn't**, since a browser
extension is a separate auth context from the web demo's login. Fixed by
extending `demo/github_oauth.py` with a third `extension` OAuth mode
(`chrome.identity.launchWebAuthFlow` support), with a strict open-redirect
guard (`_CHROMIUMAPP_REDIRECT`) so this can't be abused to hijack a login
elsewhere. Live-verified: injected the real extension code into the real,
live `simonw/llm` GitHub page and drove it with real clicks — correct parsing,
correct trigger behavior, and (important) correctly **dormant** on a repo
that isn't connected, even with a valid selection.

### D4 — the answer overlay (built, live-verified, two real bugs found+fixed)
`extension/render.js` + `content.js` extensions — a real state machine
(trigger → loading → answer/unknown/error/signed-out), styled to match the
web demo's voice, with a working close button. **Two real bugs found by live
testing that 45 passing unit tests did not catch:**
1. The "Ask Icarus" trigger button's stylesheet was only injected when a
   panel was shown — so the very first trigger a user ever saw on a fresh
   page load was completely unstyled (confirmed live: `zIndex: "auto"`, not
   the declared max value).
2. An inline `position: relative` (meant to anchor the close button) silently
   overrode the panel's `position: fixed` — the whole panel rendered off
   the left edge of the viewport (`left: -24px`, confirmed via
   `getBoundingClientRect()`), not anchored to the bottom-right corner at all.

Both fixed and re-verified live against real captured `/explain` responses
(both the cited-answer and honest-unknown states render correctly, fully
legible, correctly positioned).

**One deliberate, recorded divergence from the existing web demo:** the demo's
`index.html` badge claims "private · paid writer — 0 trained on your code" —
which §1.4 above records as **not currently true**. The extension's badge was
built to say only the verifiable fact ("private repo" / "public repo"),
dropping the paid/training claim, with a unit test guarding against silently
reintroducing the stronger claim later.

### D5 — the one thing left, and it needs you specifically
**What's unverified:** I loaded the real code into a live GitHub tab and
proved the parsing/DOM/rendering logic works — but I cannot verify
`chrome.storage`, the real `chrome.identity` sign-in flow, or a real
extension's `fetch`-with-bearer-token call, because those only exist inside an
**actually loaded, packaged Chrome extension**, and `chrome://extensions` is a
page remote browser automation is deliberately barred from navigating to
(confirmed by trying — it came back as an error page). I also confirmed *why*
this matters: a plain page script fetching the local server hits a CORS error
(`TypeError: Failed to fetch`) — exactly the restriction a real extension's
`host_permissions` exists to bypass, which a page-script injection can't fake.

**What D5 needs from you, concretely:**
1. Start the demo server: `GROQ_API_KEY=… GEMINI_API_KEY=… python3 -m demo.server`
   (or whatever keys are in `.env`) from the `brick-d-explain-line` worktree.
2. Open Chrome → `chrome://extensions` → enable **Developer mode** (top right)
   → **Load unpacked** → select the `extension/` directory in that worktree.
3. Click the extension's toolbar icon → **Sign in with GitHub** (this
   exercises the new `extension` OAuth mode for real).
4. In the demo (web UI at `http://127.0.0.1:8000`, or via `/connect`), connect
   `simonw/llm` (the committed corpus's repo).
5. Visit `https://github.com/simonw/llm/blob/94769b8b076cde9392059d76bd766453cf900180/llm/errors.py`,
   select lines 1–3 with click+shift-click, click "Ask Icarus," confirm the
   overlay shows a real cited answer.
6. Report back what happened — errors from the extension's service-worker
   console (`chrome://extensions` → the extension's card → "service worker"
   → Inspect) are the most useful thing to paste if anything breaks.

Once D5 passes, the plan calls for the same whole-brick review process used
for every other brick this session (two independent adversarial reviewers,
one on correctness/security, one on test-honesty) before merging.

---

## 3. Not started

Full detail in `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md`
— read the linked section before starting either of these.

### 3.1 Brick E — richer "why" sources
Route: that plan doc, `## Brick E — Richer "why" sources` (line ~1088 on
`main`'s copy; search the header, don't trust the line number as this file
keeps growing). **Only a sketch right now, not task-broken**: "ingest commit
messages as a `commit:` source; on explain, map a line → its introducing
commit via `git blame`. Still retrieval + cite-or-unknown; still no structural
analysis. Prove with a red eval before building" is the entire spec as
written. Two tasks were pre-created this session to track picking this up:
**E1** (scope it into concrete tasks + write the red eval proving the current
gap, per this project's own probe-first convention) and **E2** (build to
green, review, merge) — neither started.

### 3.2 Brick S — structural comprehension (deferred-gated, needs your go)
Route: that plan doc, `## Brick S — Structural comprehension` (line ~966 on
`main`'s copy). The deep "traces what calls what" capability — the closest
thing to how a senior engineer actually reads a codebase, and by far the
largest, most dependency-heavy brick (almost certainly needs a real code-
parsing library). **CLAUDE.md explicitly lists this under "do not build yet
(post-Phase-4)."** Do not start any code here without Alankrit's explicit,
separate go-ahead — this is not a "continue the list" item like E is. The plan
calls for a cheap stdlib-`ast` probe first if/when it's greenlit, to prove the
approach before committing to the real build.

### 3.3 Remark 9 — permanently off the table
Icarus writing/modifying real code. Alankrit's explicit, recorded decision.
Do not build this or suggest it — reopening would need its own deliberate
strategy-pivot decision doc, post-Phase-4 at the earliest. Not "not started,"
**closed**.

---

## 4. Process note — what to keep doing

Every brick this session (C, its demo-wiring follow-up, Q, and D0–D4) was
built the same way, and it's worth continuing exactly this way for E/D5/S:
1. **Probe the riskiest unknown first**, live where possible, before writing
   real code (D0's GitHub DOM probe; the model2vec→fastembed model-quality
   probe for Brick C).
2. **TDD**: failing test first, then the minimum code to pass.
3. **Live-verify beyond unit tests wherever feasible** — this is what actually
   caught every real bug this session (the neighbor-search bug in D1, both
   styling bugs in D4, the tokenizer-mismatch bugs in both C and Q). Unit
   tests alone did not catch any of them.
4. **One worktree per brick** (`.worktrees/<branch-name>`), never work
   directly on `main` (this was violated once, briefly, this session — caught
   and reverted before any damage — see git history around the D0 probe if
   curious).
5. **Two independent adversarial reviewers before merge** — one on
   correctness/security (re-derive claims, re-run tests, don't trust the
   implementer's report), one specifically on test-honesty (could this test
   pass while the claim is false? — verified by literally injecting the
   flagged mutation and watching the test catch it, every time this session).
6. **Record real findings honestly in the plan doc as you go**, including
   ones that complicate the story (e.g. Brick Q's grep comparison found the
   gap was *larger* on clean phrasing than messy — the opposite of the
   initial hypothesis — and that got corrected in the doc, not hidden).
7. **Merge via `--no-ff`** (a visible, revertible merge commit per brick), then
   remove the worktree + delete the branch, then update this handoff.

---

## 5. Commands

```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"

# One-time setup (the demo/eval suite's one dependency)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# Full offline suite on main
.venv/bin/python -m unittest discover -t . -s evals   # 275 tests, 13 skipped
.venv/bin/python -m unittest discover -t . -s demo    # 136 tests, 2 skipped

# The web demo (needs a free writer key)
GROQ_API_KEY=… GEMINI_API_KEY=… .venv/bin/python -m demo.server
# -> http://127.0.0.1:8000

# Brick D's worktree (unmerged) — extension + its own JS tests
cd .worktrees/brick-d-explain-line
node --test extension/*.test.js   # 29 tests (13 lib.js + 16 render.js)
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m unittest discover -t . -s evals   # 295 tests, 13 skipped
.venv/bin/python -m unittest discover -t . -s demo    # 155 tests, 2 skipped
```

---

## 6. Historical: the Gemini quota saga (resolved, kept only for context)

The prior handoff's entire §1–§3 were about a Brick C live proof blocked on a
Gemini free-tier daily quota wall, with a scheduled retry task waiting for a
UTC-day reset. **That whole path was abandoned**, not resolved by waiting —
Brick C shipped instead via local, free, offline embeddings (§1.1 above). The
scheduled task `retry-brick-c-live-embedding-proof` is disabled and marked
obsolete (verify: `mcp__scheduled-tasks__list_scheduled_tasks` should show
`enabled: false`). No action needed on it; this section exists only so a
future reader doesn't waste time reconstructing a dead end from git history.
