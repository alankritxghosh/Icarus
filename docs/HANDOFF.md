# Icarus — Session Handoff (2026-07-09, D5 live-testing session)

Read this first next session. It supersedes the prior handoff (2026-07-08 →
2026-07-09, "Brick D D0-D4 done, D5 pending") entirely. That session's D5 was
picked up tonight and went sideways in an instructive way: what started as
"load the extension and click a line" turned into finding and fixing two real
production bugs, deploying to Render for the first time all session, and
landing at a **currently-broken live state that is the very next thing to
diagnose.** Don't re-derive any of this — it's all below.

---

## 0. TL;DR — where things stand right now

- **Brick D (D0-D4) is merged to `main`**, not just built on a branch —
  merged early, explicitly at Alankrit's call, **skipping the two-independent-
  reviewer pass every other brick this cycle got.** That review is still owed
  before this is considered done. §1.
- **Two more fixes landed on `main` tonight, also unreviewed**: a real port-
  binding bug in the demo server (§2), and a hardcoded-URL bug in the
  extension (§3). Same review debt applies to both.
- **The live Render service (`https://icarus-brain.onrender.com`) is up but
  effectively unusable right now** — sign-in works, but everything else
  (`/status`, `/connect`, `/ask`, `/explain`) is refusing with "still starting
  up." This has been true for well over 10 minutes as of the end of this
  session. **This is the #1 thing to check first next session** — see §4.
- **D5's actual goal (prove a real line-select → cited-answer round-trip
  through the loaded extension) was NOT reached.** We got as far as a
  successful GitHub sign-in through the extension; the moment we tried to
  actually use it, it broke. Nobody has seen `/explain` answer through the
  real extension yet.
- `main` and `origin/main` are in sync (both at `4b7a4df`) — everything
  described below is already pushed.

---

## 1. Brick D merge — done, but review debt is real

Merged `brick-d-explain-line` → `main` at commit `aecbda1` (`--no-ff`), full
297/158/29-test suite green beforehand on both the branch and post-merge.
**Why merged early, ahead of D5 passing:** Alankrit chose to deploy to Render
to test the extension's real OAuth flow against the exact URL already
registered as the GitHub OAuth App's callback (see §3.2's dead end below for
why that mattered), and Render auto-deploys `main` — merging was the fast
path to get Brick D's `/explain` endpoint live without a manual Render
branch-switch. This was flagged explicitly before doing it (see this
session's transcript) and Alankrit confirmed: **merge now, review-and-
formalize once D5 fully passes.** D5 has not fully passed yet (§0), so this
review is still outstanding — don't treat Brick D as done-done.

## 2. Real bug found + fixed: Render deploy never opened a port

**Symptom:** pushed `main` (which now included Brick C/Q, freshly caught up
after being found 35 commits stale on `origin/main` — see §3.1) to Render.
The build succeeded, the fastembed model downloaded fine, and then... nothing.
Render's port-scan timed out after 5 minutes with "no open ports detected,"
and the deploy failed. Full log is in this session's transcript if needed.

**Root cause, confirmed by reading the code, not guessed:**
`demo/library.py`'s `_build_retriever` synchronously embeds the ENTIRE
default corpus (243 chunks: 18 code + 141 PR + 84 issue) via `fastembed`
whenever no on-disk `vectors.json` cache exists. That cache is git-ignored by
design, and Render's disk is documented (in `render.yaml`'s own comments) as
wiped on every deploy/restart/idle-sleep — so **every fresh Render deploy
must cold-embed the whole corpus from scratch, with no way to skip it.** That
call happens inside `LibraryRegistry.__init__`, which `demo/server.py`'s
`serve()` was calling BEFORE constructing `ThreadingHTTPServer` — i.e. before
the port could ever bind. **This is very likely the first time Brick C has
ever actually been deployed to Render** — the previously-live service
predated Brick C by 35 commits, so it never had to do this.

**Fix (commit `e89801b`):** `demo/server.py` now has `_LazyRegistry`, which
builds the real `LibraryRegistry` on a background thread so `serve()` binds
the port immediately. Registry-dependent routes (`/status`, `/ask`,
`/explain`, `/connect`, `/disconnect`) return a clean `503 {"error": "starting
up, try again shortly"}` while warming, instead of hanging. `/health`
deliberately returns `200 {"ok": true, "state": "starting"}` during warmup
(not 503) so Render's own health check doesn't flap/restart-loop the
container during normal startup. New tests: `LazyRegistryTests` (the state
machine, using a `threading.Event`-gated fake builder — deterministic, no
real embedding needed) and `RegistryWarmupHttpTests` (the HTTP-level 503/200
wiring), both in `demo/test_server.py`. Full suite green after the fix (295
evals + 158 demo + 29 extension JS tests).

**Verified the fix itself works:** redeployed, and this time the port bound
immediately — `/health` responded within the same request cycle instead of
timing out, confirmed via direct `curl` against the live URL right after the
build finished. **What's NOT verified: whether the background corpus embed
ever actually finishes on Render's free tier.** See §4 — this is the open
thread.

## 3. Real bug found + fixed: extension pointed at localhost

**Symptom:** "Sign-in failed: TypeError: Failed to fetch," then after fixing
the code, still the same error even after "reloading" the extension.

**Root cause 1 — hardcoded URL:** `extension/background.js` and
`extension/content.js` both had `BRAIN_URL = "http://127.0.0.1:8000"`
hardcoded (a known, commented TODO — "configurable once the brain is hosted,
post-demo per CLAUDE.md"). Once we stopped the local dev server in favor of
testing against the deployed Render service, every fetch from the extension
started failing with connection-refused. **Fix (commit `4b7a4df`):** pointed
both files' `BRAIN_URL` at `https://icarus-brain.onrender.com`, added it to
`manifest.json`'s `host_permissions` (kept the `127.0.0.1:8000` permission
too, for future local dev). This is still a hardcoded swap, not real
configurability — that remains explicitly deferred post-demo.

**Root cause 2 — stale extension load:** even after that fix landed, Alankrit
kept seeing the same error. Diagnosed by having him open the service worker's
DevTools (`chrome://extensions` → the card → "service worker" → Inspect) and
check the actual loaded source: it still showed the OLD `127.0.0.1:8000`
constant, and the Network tab showed `net::ERR_CONNECTION_REFUSED` in ~8ms
(the signature of hitting a dead loopback port, not a real remote host).
**Why:** the extension had originally been loaded (per this session's own
earlier instructions, before Brick D was merged) from the WORKTREE's copy —
`.worktrees/brick-d-explain-line/extension` — a physically different
directory from `main`'s own `extension/` folder at the repo root, which is
where all the fixes were actually being made. No amount of reloading a
worktree-sourced extension would ever pick up edits made to `main`'s files.
**Fix:** removed the extension, re-loaded unpacked from
`/Users/alankritghosh/JARVIS /jarvis_engineering/extension` (repo root, not
the worktree). This is a real footgun worth remembering: **the worktree
directory (`.worktrees/brick-d-explain-line/`) is now stale/irrelevant** for
extension testing since Brick D lives on `main` now — don't point Chrome at
it again. (The worktree itself hasn't been cleaned up yet — still exists on
disk with its own venv/.env, per the usual per-brick worktree convention, but
its `extension/` copy specifically should not be reloaded into Chrome again.)

### 3.1 Side-quest: `origin/main` was 35 commits stale

While chasing the OAuth callback-URL problem (§3.2), discovered `origin/main`
was sitting at `301720c` — 35 commits behind local `main`, missing Brick C
(semantic retrieval) and Brick Q (query understanding) **entirely**. The live
Render service was, until tonight, running pre-Brick-C code. Pushed local
`main` to origin (fast-forward, no rewrite) to fix this — unrelated to Brick
D, just something we tripped over. If anyone else is depending on that
service, they now have BM25+typo-tolerant retrieval where they didn't before.

### 3.2 Side-quest: the GitHub OAuth App callback dead end

Before deciding to deploy to Render, we tried three other paths, in order,
each hitting a real wall:
1. Local server, default config → extension's `chrome-extension://` origin
   was rejected by the server's own CSRF/Origin guard (403 "forbidden").
   **Not a real bug** — `render.yaml` already opens this guard
   (`ICARUS_ALLOWED_HOSTS=*`) in production; it's a local-dev-only artifact.
   Restarted the local server with `ICARUS_ALLOWED_HOSTS=* 
   ICARUS_REQUIRE_GITHUB_AUTH=1` to mirror production, which fixed it.
2. That got past the Origin guard but hit GitHub itself: "The redirect_uri is
   not associated with this application" — the registered GitHub OAuth App's
   callback URL is `https://icarus-brain.onrender.com/auth/github/callback`
   only (see `docs/DISTRIBUTION.md`), not `http://127.0.0.1:8000/...`. GitHub
   OAuth Apps only accept redirect URIs you've explicitly registered.
3. Proposed adding a second, local-only callback URL to the same OAuth App
   (GitHub supports multiple). **Alankrit explicitly declined** — wanted the
   production app's registration left untouched. That's what led to "deploy
   to the real Render URL instead," which is the path documented above.

If local extension testing is ever needed again without deploying, the clean
option (never executed) is a throwaway second GitHub OAuth App registered
with `http://127.0.0.1:8000/auth/github/callback`, used only for that.

---

## 4. THE OPEN THREAD — start here next session

**"I signed in but I am unable to use Icarus for anything."** This was never
diagnosed before the session ended. Best working theory, from what we know:

Every push to `main` tonight (`aecbda1`, then `e89801b`, then `4b7a4df`) is
`autoDeploy: true` on Render, so each one triggered its OWN fresh deploy —
and per §2, **every fresh deploy wipes the disk and has to cold-embed the
corpus again from zero.** As of the last check this session (well after the
final push), `curl https://icarus-brain.onrender.com/health` was STILL
returning `{"ok": true, "state": "starting"}`, and `/status` was still `503`.
That's a long time for embedding 243 short chunks to still be "starting" —
long enough that it's worth treating as its own possible problem, not just
"still warming up, be patient." Sign-in works because `/auth/github/begin`
and `/auth/github/redeem` never touch the registry at all (§2's fix
deliberately decoupled them) — but literally everything else needs a ready
registry, which is why Alankrit could sign in and then do nothing else.

**Next session, in order:**
1. `curl https://icarus-brain.onrender.com/health` — if it now shows real
   `repo`/`commit` fields instead of `"state": "starting"`, the embed finished
   on its own and this was just slow, not stuck; retry the real D5 walkthrough
   (`/connect` to `simonw/llm` via the extension, select lines in
   `llm/errors.py`, click Ask Icarus).
2. If it's STILL `"starting"`, check the Render dashboard's Logs tab for the
   `icarus-brain` service — look for a Python exception, an OOM kill, or
   genuine forward progress (any log line at all after the fastembed model
   download completes). The background thread's exceptions are NOT currently
   logged anywhere (`_LazyRegistry._build` catches and stores the exception
   silently, only re-raising it on the next `library_for`/`disconnect` call —
   if nothing has called those since the error, it could be sitting caught
   and invisible). **This might be worth fixing**: have `_LazyRegistry._build`
   at least `print(..., file=sys.stderr)` the exception immediately when it
   happens, so a stuck/failed embed shows up in Render's logs without needing
   an incoming request to surface it.
3. If it's a genuine slow-CPU problem (not stuck, just very slow), that's a
   real product question for Render's free tier: if every cold start / wake-
   from-15-min-idle-sleep means several-plus minutes of "nothing works,"
   that's not viable for a real demo. Options to weigh: bake a precomputed
   `vectors.json` into the Docker image at build time (so the container never
   starts from a truly cold cache), upgrade off the free tier, or accept the
   degraded window as a known limitation for now.
4. Once `/explain` is actually reachable, D5's real goal is still untested:
   sign in → connect `simonw/llm` → select lines on
   `https://github.com/simonw/llm/blob/94769b8.../llm/errors.py` → click Ask
   Icarus → confirm a real response renders in the overlay. Note: per the
   deferred anchor-labeling issue below, the DEFAULT (no free-text question)
   explain click will likely show "No one wrote this down" even when the
   pipeline is fully healthy — that's expected today, not a new bug.
5. Once D5 truly passes, Brick D + the two fixes in §2/§3 all still need the
   two-independent-reviewer pass that was skipped tonight.

---

## 5. Deferred, not forgotten

**The `/explain` anchor-labeling gap** (found live-testing D5, before any of
the above): the default explain question ("What does this code do, and why
is it here?") reliably abstains even on trivial, clearly-documented code,
because the shared writer prompt (`evals/synth.py`'s `build_prompt`) has no
way to mark which evidence chunk is "this code" the user selected — it's a
flat, undifferentiated list. Confirmed live (not guessed): `llm/errors.py`
lines 1-3 abstained 3/3 tries, `llm/hookspecs.py` too, and the SAME evidence
answers fine through `/ask` when the question names the class explicitly
instead of saying "this." The extension never sends a free-text question, so
every real click hits this path. **Alankrit's call:** proceed with D5 as-is
tonight (D5's job is proving the transport mechanics, not writer quality);
fix separately. **Spawned as background task `task_6ab94816`** ("Fix
explain's anchor-labeling gap in shared prompt") — Alankrit started it in a
separate session mid-way through tonight's session; its outcome was never
reported back before this handoff was written. **Check its status next
session** — it may already be done, in progress, or need resuming.

---

## 6. Carried forward unchanged from the prior handoff

Still true, not re-verified tonight, not re-explained here — see the prior
handoff's git history (`git log -p -- docs/HANDOFF.md`) for full detail if
needed:
- **Brick E** (richer "why" sources — commit-message/git-blame provenance):
  sketched only, not task-broken. E1/E2 tracked, neither started.
- **Brick S** (structural comprehension): deliberately deferred-gated per
  CLAUDE.md's "do not build yet" list. Needs Alankrit's explicit, separate
  go-ahead before any code — not a "just continue the list" item.
- **Remark 9** (Icarus writing/modifying real code): permanently off the
  table, a closed decision, not "not started."
- **Billing/private-repo writer**: private repos currently use the free
  model (not a genuinely billed/no-training tier despite
  `GEMINI_PAID_API_KEY`'s name) — acceptable pre-revenue, but the existing
  UI's "paid writer — 0 trained on your code" badge is still not true and
  must be revisited before any real external customer's private code
  connects. (The extension's own badge already avoids this claim — see
  `extension/render.js`'s guarded test.)

---

## 7. Commands

```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"

# Full offline suite on main (now includes Brick D + tonight's two fixes)
.venv/bin/python -m unittest discover -t . -s evals   # 295 tests, 13 skipped
.venv/bin/python -m unittest discover -t . -s demo    # 158 tests, 2 skipped
node --test extension/*.test.js                       # 29 tests

# Live service (check warmup state first -- see §4)
curl https://icarus-brain.onrender.com/health
curl https://icarus-brain.onrender.com/status

# Local dev server, matching production's posture (needed for extension testing)
ICARUS_ALLOWED_HOSTS=* ICARUS_REQUIRE_GITHUB_AUTH=1 .venv/bin/python -m demo.server

# Load the extension in Chrome -- REPO ROOT, not the worktree (see §3):
#   chrome://extensions -> Load unpacked ->
#   /Users/alankritghosh/JARVIS /jarvis_engineering/extension

# The Brick D worktree still exists on disk but its extension/ copy is stale
# for testing purposes now that Brick D is merged to main (see §3). Safe to
# remove once the review debt in §0/§1 is settled and nothing else needs it:
#   git worktree remove .worktrees/brick-d-explain-line
#   git branch -d brick-d-explain-line   # already merged, safe
```
