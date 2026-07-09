# Icarus — Session Handoff (2026-07-09 → 2026-07-10, private repos fixed)

Read this first next session. It supersedes the prior handoff ("D5 live-testing
session -- live service is stuck") entirely. That session ended with the brain
stuck cold-embedding forever on every boot. Tonight fixed that, then found and
fixed a second, more important problem underneath it: **private repos --
the actual product -- were not usable at all** on the current hosting tier.
Both are fixed and verified live. Don't re-derive any of this — it's below.

---

## 0. TL;DR — where things stand right now

- **The brain boots warm.** `/health`/`/status` on the default `simonw/llm`
  corpus come up `"ready"` in milliseconds, not stuck `"starting"` — fixed by
  baking the embedding model + vector cache into the Docker image at build
  time. Verified live, repeatedly, all night. §1.
- **Private repos are usable.** This was the real fire tonight: a connect to
  Alankrit's own `alankritxghosh/Icarus` repo ran a newly-added 15-minute
  embed timeout to completion on Render's free tier without embedding even
  10% of the corpus — confirmed root cause is Render's CPU (0.1 vCPU,
  verified against their pricing page), not a bug. Fixed with a two-stage
  connect: a fast, lexical-only pipeline publishes "ready" in seconds
  (verified live: `connect received` → success in well under a minute on the
  real repo, real infra), and a full semantic pipeline upgrades it silently
  in the background. §3.
- **`/ask` is proven live, including the honesty gate.** Alankrit ran five
  test questions against the connected `alankritxghosh/Icarus` repo tonight
  — all passed, including a deliberate "what's Icarus's pricing model?"
  probe that correctly triggered an honest "I don't know" instead of an
  invented answer. This is the first live proof this session that `/ask`
  actually works post-fixes — nobody had tested it end to end before this.
  §4.
- **The Hugging Face Spaces migration is scoped, not started.** Still the
  right long-term fix (2 vCPU / 16GB free vs Render's 0.1 CPU / 512MB) but
  private repos no longer need it to be usable tonight. Plan:
  `docs/plans/2026-07-10-hugging-face-spaces-migration.md`. §5.
- **D5's actual goal — the extension walkthrough — is still unverified.**
  Select lines on GitHub → click Ask Icarus → a real cited answer in the
  overlay has never been completed successfully, tonight or in any prior
  session. Not touched tonight; still the biggest untested surface. §6.
- **The Mac app's timeout fix is source-only, not rebuilt.** The app on
  Alankrit's machine still has the old 180s connect deadline. Matters much
  less now that connects land in seconds, but isn't actually verified in the
  running app. §6.
- `main` and `origin/main` are in sync at `3a6053b` — everything below is
  already pushed and live on Render.

---

## 1. Fix: the brain was stuck cold-embedding on every boot

**Symptom (start of tonight):** `/health` returned `{"ok": true, "state":
"starting"}` and `/status` was `503` for 10+ minutes after every deploy.

**Root cause, confirmed by reading the code:** `demo/library.py`'s
`_build_retriever` synchronously embeds the entire default corpus (243
chunks) via `fastembed` whenever no on-disk `vectors.json` cache exists —
true on every fresh Render deploy, since the cache is git-ignored and
Render's disk is wiped on every deploy/restart/idle-sleep.

**Fix (`b948376`):** `demo/warm_cache.py` (new) bakes the fastembed model
download AND the default corpus's `vectors.json` into the Docker image at
`docker build` time (`Dockerfile`'s new `RUN python -m demo.warm_cache`
step), so the container boots warm instead of cold. Verified with a real
local `docker build` + `docker run`: `/status` returned `"ready"` in **0.05
seconds**. Measured the actual speedup too: cold-embedding 243 chunks took
7.8s on my machine vs 0.04s from the baked cache — 197x. On Render's slower
CPU the gap was much larger in practice (this is what was causing the
10+ minute stuck-boot symptom).

---

## 2. Fix: connect had no timeout and no visibility

Before touching the "private repos don't work" problem, tonight first closed
an observability gap that made every subsequent diagnosis take far longer
than it should have:

**`2294de4`** — `evals/retriever.py`'s `SemanticRetriever` gained an optional
`timeout` (raises `TimeoutError` past it) and `on_progress(done, total)`
param; `demo/library.py` wires a 900s bound + progress logging into the real
embed path. Before this, a slow embed just hung forever with zero signal —
proven live tonight (a connect ran 35+ minutes with no way to tell if it was
almost done or truly stuck).

**`d9f9327`** — added a log line the instant `/connect` is accepted
(`demo/server.py`). Before this, the server's default request logging is
deliberately suppressed, so a connect request left literally no trace until
(if ever) it reached the embed loop's own progress logging. This is what
made it possible to prove, live, that a click had genuinely reached the
server vs. a stale browser tab silently polling a server that had since
redeployed out from under it (this happened at least twice tonight — every
push triggers a fresh Render deploy, which resets in-flight connects).

Client-side, `demo/index.html` and
`mac/Icarus/Sources/Icarus/ConnectModel.swift` both had their poll windows
bumped from 150s/180s to 900s to match the server's bound, and the web page
now says so honestly if it times out instead of leaving "indexing…" up
forever (a real bug found live — the old code just silently stopped
polling).

**This whole layer is now largely superseded by §3** — the 900s timeout and
progress logging still exist and still matter for the background semantic
upgrade, but they're no longer the thing standing between a user and a
working connect.

---

## 3. THE REAL FIX: private repos are usable (two-stage connect)

**What actually happened:** with §1 and §2 live, Alankrit tried connecting
his own `alankritxghosh/Icarus` repo (216 chunks: 144 code, 68 doc, 4
config, 0 PR/issue). It ran the full 900s embed timeout **to completion,
with zero progress log lines ever appearing** (the progress log fires every
~10%, i.e. every ~21 chunks) — meaning it embedded fewer than 21 chunks in
15 minutes. Locally, the same repo embeds in 22.7s. That's roughly a **400x**
slowdown, and it's not a fluke: Render's free tier is confirmed at **0.1
CPU** (a literal tenth of a core) via their own pricing page. **Private
repos were not usable on this infra, full stop** — no amount of more
patient timeouts or better logging fixes that; the CPU genuinely isn't fast
enough to embed a real repo interactively.

**A wrong idea, ruled out before shipping it:** the first hypothesis was
that `evals/retriever.py`'s per-chunk `provider.embed()` loop (one call per
chunk) was the bottleneck and batching all chunks into a single call would
help. Benchmarked directly against the real repo: batching was **~10x
SLOWER** (261s vs 22.3s), not faster. Good thing this was measured before
being "fixed" — would have made things worse.

**The actual fix (`fae482c`):** `Library.connect_sync` now connects in two
stages instead of one:
- **STAGE 1** builds a lexical-only (BM25) pipeline and publishes it as
  `"ready"` immediately — pure Python string processing, no CPU-bound ONNX
  inference at all, so it's fast regardless of how throttled the host's CPU
  is. This is not a stub or a fake mode — lexical-only is the same
  real fallback retrieval mode already used whenever the embedder is
  unavailable at all.
- **STAGE 2** then builds the full hybrid (lexical + semantic) pipeline in
  the background and swaps it in once the embed finishes. A slow host or an
  outright timeout there is explicitly **not a connect failure** anymore —
  the repo is already answerable via stage 1 — so stage 2 exceptions are
  logged to stderr and swallowed, never undoing a working connection. The
  swap only applies if the caller hasn't switched to a different repo in the
  meantime (a real race — two different repos' `connect_sync` calls can
  genuinely run concurrently on separate background threads — guarded under
  the lock and covered by a dedicated test).

`_build_retriever`, `_default_build_pipeline`,
`_default_build_private_pipeline`, and `LibraryRegistry._build` all gained a
`fast=False` param threaded through; the private-repo trust interlock
(`assert_safe_for_private`) is completely unaffected either way — `fast`
only changes which *retriever* gets built, never which *writer*.

**Verified, not assumed, at every level:**
- Full test suite: 298 evals + 163 demo, all green (3 new/replaced tests in
  `demo/test_library.py` covering stage order, a stage-2 timeout not undoing
  stage 1, and the repo-switch race).
- Live against the real embedder, real repo (not test doubles): status
  flipped to `"ready"` with a genuine, searchable `LexicalRetriever` at
  **4.4s**; upgraded to a real `HybridRetriever` at ~30s once the embed
  finished — both confirmed by inspecting the actual retriever object type
  at each point.
- Live on Render itself, the actual infra that failed: `connect received`
  logged, and Alankrit confirmed the connect succeeded well within a minute
  — on the exact repo that previously ran 15 minutes to a hard failure.

**Known, honest tradeoff:** for a window after a fresh connect (unmeasured
on Render specifically — could be anywhere from seconds to the full 900s
bound depending on how throttled the CPU really is for that request), search
is keyword-based, not meaning-based. There's currently no client-visible
signal that this upgrade is in progress or has completed — `/status`'s JSON
shape wasn't changed, deliberately, to avoid touching any client code
tonight. A paraphrased question that shares no keywords with the relevant
code could underperform during that window. Not fixed tonight; a reasonable
follow-up if it turns out to matter in practice.

---

## 4. Verified live: `/ask` actually works, including the honesty gate

Nobody — not this session, not any prior one per the last handoff — had
actually tested `/ask` returning a real cited answer since any of tonight's
fixes landed. I structurally couldn't test this myself (requires Alankrit's
own GitHub bearer token). Alankrit ran five questions against the connected
`alankritxghosh/Icarus` repo:

1. Why one unified cloud instead of self-hosting (tests grounded "why",
   should cite `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md`)
2. How the two-stage connect avoids blocking on slow embedding (self-
   referential — tonight's own fix, should cite `demo/library.py`)
3. Whether Icarus trains on or retains a customer's code (privacy claim)
4. What happens when no grounded citation exists (self-referential — the
   honesty gate explaining itself)
5. Icarus's pricing model — **deliberately unanswerable**, nothing in the
   repo documents pricing (pre-revenue, pre-build per CLAUDE.md)

**All five passed**, including #5 triggering an honest "I don't know"
instead of an invented answer. That's the single most load-bearing proof
point of the whole product (CLAUDE.md's one non-negotiable: "it cannot
bluff") and it held up live, tonight, on real infra.

---

## 5. Scoped, not started: the Hugging Face Spaces migration

`docs/plans/2026-07-10-hugging-face-spaces-migration.md` — the verified case
for moving off Render entirely: HF Spaces' free Docker tier is 2 vCPU/16GB
vs Render's confirmed 0.1 CPU/512MB, a 20x CPU difference for the same $0.
Every real touchpoint enumerated by `grep`, not guessed (Dockerfile non-root
user requirement, 3 hardcoded Render URLs in `extension/`, the GitHub OAuth
callback needing a second registered URL, docs). Ordered as 5 tasks,
smallest-loop-first.

**Why this is no longer urgent:** §3's fix means private repos work on
Render right now. This migration is still the right move for real semantic-
search speed and headroom (§3's stage-2 upgrade could still be meaningfully
faster on better CPU), but it's a quality/speed improvement now, not a
blocker. Pick it up when there's a clear head and no time pressure — not a
crisis fix.

---

## 6. Open gaps — the real ones, not busywork

**D5's actual goal has never been verified, at all, ever.** Select lines on
a GitHub blob page → click "Ask Icarus" in the extension → a real cited
answer renders in the overlay. This has not happened successfully in this
session or (per the prior handoff) any session before it. Tonight was spent
on infra reliability, not this. **This is the single biggest untested
surface going into next session** if the extension is part of the demo
plan. Start here.

**The Mac app's timeout fix is source-only.** `ConnectModel.swift`'s 900s
deadline (was 180s) needs `mac/Icarus/scripts/bundle.sh` + a relaunch to
take effect in the app Alankrit actually runs. Matters less now (connects
land in seconds via stage 1) but hasn't been verified in the compiled app.

**No visibility into stage-2 (semantic upgrade) SUCCESS**, only failure —
`demo/library.py`'s stage-2 `except Exception` logs to stderr, but a
successful upgrade is silent. Fine for tonight; worth a one-line success log
if this needs debugging again.

**Two-independent-reviewer pass still owed.** Carried debt from Brick D's
early merge (`aecbda1`, explicitly flagged and approved by Alankrit at the
time — "review once D5 fully passes"). D5 still hasn't fully passed (see
above), so this review is still outstanding, and now covers a lot more
surface (all of tonight's fixes too).

**Render CLI/API access was set up tonight** for live log diagnosis (device-
auth login, `render whoami` confirms `Alankrit Ghosh`). The API key is
cached locally at `/tmp/.render_api_key` — a scratch, machine-local,
never-committed file, not durable across sessions/machines. If log access is
needed again, re-run `render login` (device-flow, opens a browser) rather
than assuming that file still exists.

---

## 7. Carried forward unchanged from prior handoffs

Still true, not re-verified tonight:
- **Brick E** (richer "why" — commit-message/git-blame provenance): sketched
  only, not task-broken.
- **Brick S** (structural comprehension): deliberately deferred-gated per
  CLAUDE.md's "do not build yet" list. Needs Alankrit's explicit go-ahead.
- **Remark 9** (Icarus writing/modifying real code): permanently off the
  table, a closed decision.
- **Voice**: Phase 3, deliberately deferred by the project's own stated
  build order (CLAUDE.md) — not an oversight, a sequencing decision. If any
  demo plan assumes voice interaction, that was never scheduled for this
  stage.
- **Billing/private-repo writer**: private repos use `GEMINI_PAID_API_KEY`
  (a dedicated key, gated by the trust interlock) but this is not yet
  confirmed as a genuinely billed/no-training tier in practice — acceptable
  pre-revenue, revisit before any real external customer's private code
  connects.

---

## 8. Commands

```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"

# Full offline suite on main (298 evals + 163 demo, all green as of 3a6053b)
.venv/bin/python -m unittest discover -t . -s evals
.venv/bin/python -m unittest discover -t . -s demo
node --test extension/*.test.js

# Live service
curl https://icarus-brain.onrender.com/health
curl https://icarus-brain.onrender.com/status

# Render CLI (device-auth login persists locally; re-login if it's expired)
render login
render whoami

# Local dev server, matching production's posture (needed for extension testing)
ICARUS_ALLOWED_HOSTS=* ICARUS_REQUIRE_GITHUB_AUTH=1 .venv/bin/python -m demo.server

# Load the extension in Chrome -- REPO ROOT, not any worktree:
#   chrome://extensions -> Load unpacked ->
#   /Users/alankritghosh/JARVIS /jarvis_engineering/extension
```
