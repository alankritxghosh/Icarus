# Migrate the brain from Render to Hugging Face Spaces

**STATUS: confirmed as next session's #1 priority (Alankrit, explicit).**
Not "someday" — semantic retrieval is currently NOT WORKING on Render, at
all, confirmed live (see below). Start at Task 1.

**Goal:** Move the hosted brain (`demo/server.py`) off Render's free tier
onto a Hugging Face Spaces free Docker Space, so semantic (context-aware)
retrieval actually completes and Icarus is genuinely context-aware, not
running on keyword search as a permanent fallback.

**Why now (verified TWICE — the original diagnosis, then confirmed again
after a later fix, both live, not assumed):**

| | Render free | HF Spaces free (cpu-basic) |
|---|---|---|
| CPU | **0.1 CPU** (a tenth of a core) | **2 full vCPU** |
| RAM | 512 MB | 16 GB |
| Idle sleep | 15 min | 48 h |
| Disk | ephemeral | ephemeral (same posture) |

Original incident: a private-repo connect to `alankritxghosh/Icarus` (216
chunks) ran a 900s embed timeout to completion without finishing — the
progress log (fires every ~10%, ~21 chunks) never printed once. Local
timing for the same repo was ~27s total (4.4s ingest + 22.7s embed). That's
roughly a **400x** slowdown on Render's CPU, consistent with 0.1 CPU being
the real ceiling, not a code bug.

**That connect-blocking problem was then fixed separately** (a two-stage
connect: fast lexical-only pipeline first, semantic upgrade in the
background — see `docs/HANDOFF.md` §3) — so repos connect fast now
regardless of this migration. But checking the SAME real connect's
background semantic upgrade against Render's logs afterward showed it had
run its own full 900s bound and failed: `semantic upgrade failed for
'alankritxghosh/Icarus' (TimeoutError); staying on lexical-only search`.
**Confirmed, not theoretical: on Render, semantic retrieval does not
complete for a real repo.** HF Spaces' free tier gives 20x more CPU and 32x
more RAM for the same $0 — this is the single highest-leverage fix
available, and it's an infra change, not another code patch.

**Scope:** Get the SAME server (`demo/server.py`, unchanged brain logic)
running on HF Spaces instead of Render. No product changes. Render stays
configured (`render.yaml` untouched) so this is reversible — don't delete
anything Render-specific until the HF Space is proven live.

---

## What actually needs to change (every touchpoint, found by grep tonight — not guessed)

**Dockerfile — one real change (non-root user), everything else works as-is:**
- HF Docker Spaces run the container as **UID 1000**, not root. Needs a
  `RUN useradd -m -u 1000 user` + `USER user` switch, inserted **after** the
  `apt-get install` (git/gh) step (those need root) and **before** `COPY`/pip
  install (per HF's own guidance — avoids permission errors).
- **No secret-handling code change needed.** Verified directly against HF's
  docs (not the vaguer search-result summary, which conflated buildtime vs
  runtime): the `/run/secrets/NAME` file-mount trick is **buildtime only**
  (for `RUN --mount=type=secret` steps). At **runtime**, secrets are injected
  as plain env vars — exactly what `os.environ.get(...)` already does
  everywhere in this codebase (`evals/provider.py`, `demo/server.py`, etc.).
  Our `RUN python -m demo.warm_cache` build step needs no secret at all (the
  fastembed model download is unauthenticated), so this doesn't even touch
  the build step.
- Port: HF expects the container to listen on whatever `app_port` declares in
  the Space's README (see below). `demo/server.py` already reads `$PORT` from
  env (`server.py:446`, added for Render) — so no server code change, just
  set `PORT` to match whatever `app_port` you pick (7860 is HF's Gradio-era
  default, but literally any port works since `app_port` is explicit).

**New file required — `README.md` YAML front-matter** (HF-specific, doesn't
exist today): a Docker Space needs its README's top YAML block to declare
`sdk: docker` and `app_port: <port>`. This is a Hugging Face platform
requirement, not a code file — a few lines, added once.

**Config that moves from `render.yaml` to the Space's Settings UI** (no new
code — same env vars, different place to set them): `ICARUS_ALLOWED_HOSTS`,
`ICARUS_REQUIRE_GITHUB_AUTH`, `ICARUS_PUBLIC_URL`, `GROQ_API_KEY`,
`GEMINI_API_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`,
`GEMINI_PAID_API_KEY`, `GH_TOKEN`, `ICARUS_STORAGE_ROOT`. `render.yaml`
documents exactly what each one is for — copy the *values*, not the file.

**Hardcoded Render URL — 3 files** (found via `grep -rn "onrender.com"`):
- `extension/manifest.json` — `host_permissions` entry
- `extension/background.js` — `BRAIN_URL` constant
- `extension/content.js` — `BRAIN_URL` constant

Same class of edit as the earlier Render URL swap this session — point all
three at the new `https://<username>-<space-name>.hf.space` URL. Keep the
`127.0.0.1:8000` permission/fallback for local dev, same as today.

**Mac app — no source change needed.** `ICARUS_BRAIN_URL` is resolved from
the bundle's Info.plist, stamped at *packaging* time by
`mac/Icarus/scripts/package_dmg.sh` (`BrainEndpoint.swift` reads it, falls
back to `127.0.0.1:8000` for dev). Next time the app is packaged, pass the HF
Space URL as the stamp value — a build parameter, not a code edit.

**GitHub OAuth App — an external, account-level change, not code.** The
registered callback URL is currently
`https://icarus-brain.onrender.com/auth/github/callback`
(`docs/DISTRIBUTION.md`). GitHub OAuth Apps support multiple registered
callback URLs — **add** the new
`https://<username>-<space-name>.hf.space/auth/github/callback` rather than
replacing, so Render keeps working during the transition. This needs
Alankrit to do it directly in GitHub's OAuth App settings (same reason we
didn't add a localhost callback earlier tonight — don't touch the app's
registration without him explicitly present).

**Docs to update once the Space is live and proven:** `docs/DISTRIBUTION.md`
(the whole hosting runbook is Render-specific today), `docs/HANDOFF.md`,
`general_index.md`'s `render.yaml`/`Dockerfile` entries. Don't touch these
until the migration is actually verified working — a doc describing a broken
setup is worse than an outdated one.

---

## Task 1: Create the Space and get a bare `/health` responding

**Why first:** Prove the platform mechanics (build, boot, port, non-root
user) work before wiring any secrets or OAuth — smallest possible loop to
find a surprise.

**Steps:**
1. Create a new Space at huggingface.co/new-space, SDK = Docker, hardware =
   free (cpu-basic).
2. Add the README YAML front-matter (`sdk: docker`, `app_port: 8000` to match
   `demo/server.py`'s default, or pick 7860 and set `PORT=7860` as a Space
   variable — either works, just keep them consistent).
3. Add the non-root `USER` block to `Dockerfile`, positioned after the
   `apt-get install` step, before `COPY`/`pip install` (see HF's own example
   in their Docker Spaces doc for the exact `useradd`/`chown` pattern —
   linked below).
4. Push this repo (or a mirror/subset — decide in Task 1 whether the Space
   tracks the same repo or a slimmed copy) to the Space's git remote.
5. Verify: `curl https://<space-url>/health` returns `{"ok": true, ...}` with
   real repo/commit fields, not stuck warming — this alone should already be
   fast (baked cache still applies, same as the Render fix).

**Definition of done for this task:** `/health` and `/status` both healthy
from a bare Space, no auth/secrets wired yet.

## Task 2: Wire secrets + GitHub OAuth, prove sign-in works

**Steps:**
1. Add all the env vars listed above via the Space's Settings → Variables
   and repository secrets tab (secrets for keys/tokens, plain variables for
   `ICARUS_ALLOWED_HOSTS` etc. — HF's UI distinguishes the two, doesn't
   matter functionally at runtime per the verified doc above).
2. Add the Space's callback URL to the GitHub OAuth App (Alankrit does this
   step directly).
3. Verify: sign in via the web demo at the Space's URL, confirm a session
   redeems successfully.

## Task 3: Prove the actual thing this migration is FOR

**Steps:**
1. Connect a fresh, non-default, non-trivial repo (reuse
   `alankritxghosh/Icarus` — the same repo that timed out on Render tonight)
   and time it end to end.
2. Compare against tonight's numbers: Render never finished in 900s embedding
   216 chunks; local (fast machine) was 27s total. HF Spaces' 2 vCPU should
   land somewhere between those, hopefully close to local. **Write down the
   actual number** — this is the number that decides whether the migration
   was worth it, not a guess.

**Definition of done:** a fresh repo connect completes well inside a few
minutes, with real progress visible in the (much shorter) embedding log.

## Task 4: Point the clients at the new brain — including a REAL app rebuild

**This is the actual finish line for the session, not a formality.**
Alankrit's explicit end goal: a rebuilt, running app reflecting everything
— not source changes sitting uncompiled. Don't stop at "the code is
correct"; stop at "the app was rebuilt and launched."

**Steps:**
1. Swap the 3 hardcoded `onrender.com` references in `extension/` to the
   Space's URL (mirror the earlier Render URL swap's exact diff shape).
2. Update `extension/manifest.json`'s `host_permissions`.
3. Run `node --test extension/*.test.js` — should be unaffected (these tests
   don't assert on the URL constant, but confirm before assuming).
4. Rebuild the Mac app for real: `mac/Icarus/scripts/package_dmg.sh`
   (or `bundle.sh` for a dev build), stamping `ICARUS_BRAIN_URL` to the new
   HF Space URL. This is ALSO the first time the 900s connect-timeout fix
   (`ConnectModel.swift`, landed source-only the prior session — see
   `docs/HANDOFF.md` §2) actually ships in a running app. Two fixes,
   one rebuild — don't rebuild twice.
5. **Actually launch the rebuilt app and use it** — connect a real repo,
   ask a real question, confirm the retriever genuinely upgrades to
   semantic (same verification method as Task 3). A successful build is
   not the same as a working app.

## Task 5: Update docs, decide Render's fate

**Steps:**
1. Update `docs/DISTRIBUTION.md`, `docs/HANDOFF.md`, and the two
   `general_index.md` lines for `Dockerfile`/`render.yaml` to reflect
   reality (which platform is live, which is kept as a fallback or retired).
2. **Decision needed from Alankrit, don't guess:** keep `render.yaml` +
   the Render service around as a documented fallback (costs nothing extra
   on the free tier, but is another thing to keep in sync), or retire it
   once HF Spaces is proven stable. Either is defensible — this is a decision
   point, not a task to silently resolve.

---

## Open questions to resolve during Task 1 (verify live, don't assume)

- **Custom domain on the free tier:** not confirmed either way from HF's
  docs during tonight's research. Not required for a working migration (the
  default `*.hf.space` URL works fine functionally) — only matters if a
  cleaner public URL is wanted later.
- **Whether the Space should track this exact repo** (public GitHub repo →
  HF Space git remote, similar to Render's GitHub-integration deploy) or a
  separate slimmed mirror. Render's model was "point Render at the GitHub
  repo, auto-deploy on push." HF Spaces are themselves git repos — the
  cleanest mirror of today's workflow is likely `git push` (or a mirror
  remote) from this repo to the Space repo, but confirm HF's exact
  auto-deploy-on-push behavior during Task 1 rather than assuming it matches
  Render's.
- **`gh`/`git` subprocess behavior as a non-root UID-1000 user** — should be
  identical to Render (no root requirement for git/gh operation), but this
  is exactly the kind of assumption that should get a real smoke test
  (`RUN_INGEST_SMOKE=1` style live check) in Task 1, not just an assertion
  in this doc.

---

## Definition of done

- HF Space live, `/health` + `/status` healthy.
- Sign-in works end to end.
- **The actual bar, not just "connect completes fast":** a fresh,
  non-default repo connect (same test repo as the original incident,
  `alankritxghosh/Icarus`) reaches a genuine `HybridRetriever` — the
  semantic upgrade actually succeeds, not just the lexical-only fallback.
  Verify by inspecting the real retriever type, same method used to verify
  the connect fix itself (`docs/HANDOFF.md` §3) — a fast "ready" status
  alone proves nothing about semantic search working.
- Extension + Mac app point at the new URL.
- Docs describe what's actually live, not what used to be true.
- Render fallback question explicitly decided, not left ambiguous.

---

## Sources (verified tonight, not recalled from training data)

- [Render Pricing 2026: Free Tier, RAM Limits & Alternatives](https://www.srvrlss.io/provider/render/) — 0.1 CPU / 512MB confirmed.
- [Spaces Overview · Hugging Face](https://huggingface.co/docs/hub/en/spaces-overview) — 2 vCPU / 16GB / 50GB ephemeral confirmed.
- [Docker Spaces · Hugging Face](https://huggingface.co/docs/hub/spaces-sdks-docker) — fetched directly (not just search snippet): runtime secrets are plain env vars, non-root UID 1000 requirement, `app_port` config, ephemeral-disk-unless-Storage-Bucket behavior, README YAML block requirement.
