# Distributing Icarus (no Apple Developer ID)

How to put a working Icarus in someone else's hands without paying Apple. Two
parts, in order: **host the brain** (so any recipient can reach it), then **build
and share the app** (ad-hoc signed, past Gatekeeper by hand).

This is a **controlled-demo posture**, not a hardened public service. Read the
tradeoffs at the bottom before sharing widely.

---

## Part 1 — Host the brain on Render (free tier)

The brain is pure Python stdlib; the container adds `git` + `gh` only so the app's
"connect any public repo" switch can ingest on the server. Files: `Dockerfile`,
`render.yaml`, `.dockerignore` (repo root).

### 1a. Put the source on GitHub
Render deploys from a Git repo. From the repo root:
```bash
git init            # if not already a repo (this one already is)
gh repo create icarus --private --source=. --remote=origin --push
```
`.env` is gitignored and the pre-commit hook blocks staged secrets, so no keys go
up. Verify with `git status` before pushing that `.env` is untracked.

### 1b. Create the Render service
1. Render dashboard → **New → Blueprint** → pick the `icarus` repo. It reads
   `render.yaml` and proposes one **free** web service, `icarus-brain`, Docker.
2. Set the secret env vars (they are `sync: false`, so Render prompts for them):
   - `GROQ_API_KEY`, `GEMINI_API_KEY` — the writer/judge keys.
   - `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — your GitHub OAuth app.
   - `GH_TOKEN` — a GitHub token so the container's `gh` can fetch PRs/issues when
     a user switches repos. A fine-grained token with public-repo read is enough.
   - `GEMINI_PAID_API_KEY` — a **billing-enabled** Gemini key; the private-repo
     writer. Never satisfied by the free `GEMINI_API_KEY` (the trust interlock
     only trusts this dedicated env var — see
     `docs/plans/2026-07-04-private-repos-per-user-isolation.md`).
   - `ICARUS_PUBLIC_URL` — **the service's own https URL**, e.g.
     `https://icarus-brain.onrender.com`. You get this after the first deploy;
     set it, then redeploy. It must match the OAuth callback in step 1c.
   - (already in `render.yaml`, no action) `ICARUS_ALLOWED_HOSTS=*`,
     `ICARUS_REQUIRE_GITHUB_AUTH=1`, and `ICARUS_STORAGE_ROOT` (per-user corpora;
     Render's free-tier disk is ephemeral, so this is a cache, not durable storage).
3. Deploy. Health check is `GET /health`.

### 1c. Point the GitHub OAuth app at the hosted callback
In GitHub → Settings → Developer settings → OAuth Apps → your app, set the
**Authorization callback URL** to:
```
https://icarus-brain.onrender.com/auth/github/callback
```
(Use your real Render URL.) This must equal `ICARUS_PUBLIC_URL` + `/auth/github/callback`.

### 1d. Verify the brain is live
```bash
curl https://icarus-brain.onrender.com/health
# {"ok": true, "repo": "simonw/llm", "commit": "..."}
```
The first request after ~15 min idle wakes the free instance (~30–60s) — expected.

---

## Part 2 — Build and share the app

### 2a. Build the DMG, stamped with your brain URL
```bash
cd mac/Icarus
ICARUS_BRAIN_URL=https://icarus-brain.onrender.com ./scripts/package_dmg.sh
# -> mac/Icarus/Icarus.dmg
```
The script does a release build, ad-hoc signs, stamps `ICARUS_BRAIN_URL` into the
bundle's Info.plist (so the app talks to your cloud brain — dev builds without the
env var stay on `127.0.0.1:8000`), re-signs, and produces `Icarus.dmg` with a
drag-to-Applications layout and a `READ ME FIRST.txt`.

### 2b. Share it
Send `Icarus.dmg` (AirDrop, a file host, etc.). Tell recipients to read
`READ ME FIRST.txt`. Because it isn't notarized, each recipient takes a one-time
Gatekeeper step:

- Open **System Settings → Privacy & Security**, scroll down, click **Open Anyway**
  next to the Icarus message, confirm. (On older macOS: right-click Icarus → Open.)
- If that button doesn't appear:
  `xattr -dr com.apple.quarantine /Applications/Icarus.app`, then open normally.

There is **no way to remove this first-open step without notarization** — it is the
price of not paying Apple. It happens once per recipient.

Then: **Sign in with GitHub** → connect a public repo (e.g. `simonw/llm`) →
**⌘⇧I** to type, or hold **Right Option (⌥)** to speak.

**One-time re-sign-in for private repos.** The GitHub OAuth scope widened from
`read:user` to `repo` so a signed-in user's own token can read their private
repos. Anyone who signed in **before** this deploy is holding a stale
`read:user`-scoped token — private-repo connect will fail for them until they
**sign out and sign back in once** to pick up the new scope. There is no
server-side token migration; this is a real, user-visible one-time step.

---

## Tradeoffs you accepted (know these before sharing widely)

- **Your quota, their questions.** Every ask spends your free Groq/Gemini quota
  (capped; free tiers may train on inputs — that's why it's **public repos only**).
- **No rate-limiting.** The stdlib server has none. This is safe only because
  `/ask` and `/connect` require a real GitHub identity (`ICARUS_REQUIRE_GITHUB_AUTH`),
  which is your throttle/ban lever. Don't hand the URL to the open internet.
- **Free instance sleeps** after ~15 min idle → a slow first request.
- **Repo-switching ingests on your server** on the user's input. Prompt-injection
  via ingested content is disclosed in `docs/EVALUATION.md`; the honesty gate
  proves provenance, not faithfulness. Prefer vetted repos for demos.
- **Ad-hoc signature, not notarized.** The app opens on other Macs only via the
  manual Gatekeeper step above, and rebuilding changes the signature (re-prompts
  the Keychain). Notarization (needs the $99/yr Developer ID) removes both.

## Rotate the keys
The Groq/Gemini keys and the GitHub client secret were exposed in an earlier chat
transcript (see `docs/HANDOFF.md` §6). Rotate them when you set the Render env vars
— same sitting.
