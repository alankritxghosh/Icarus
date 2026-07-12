# Distributing Icarus (no Apple Developer ID)

How to put a working Icarus in someone else's hands without paying Apple. Two
parts, in order: **host the brain** (so any recipient can reach it), then **build
and share the app** (ad-hoc signed, past Gatekeeper by hand).

This is a **controlled-demo posture**, not a hardened public service. Read the
tradeoffs at the bottom before sharing widely.

**Hosting history:** Render (free tier) was the original host; its 0.1 CPU
free tier could never finish embedding a real repo (docs/HANDOFF.md), so the
brain moved to **Azure Container Apps** on 2026-07-11/12. The Render service
(`icarus-brain`, `srv-d94153cvikkc73ba8ckg`) is now **suspended**, not
deleted — `render.yaml`/`Dockerfile` still work unchanged on Render if it's
ever resumed, but it is not the live host.

---

## Part 1 — Host the brain on Azure Container Apps (free tier)

The brain is pure Python stdlib; the container adds `git` + `gh` only so the app's
"connect any public repo" switch can ingest on the server. Files: `Dockerfile`,
`.dockerignore` (repo root). Needs the `az` CLI (`brew install azure-cli`) and an
Azure account with billing enabled (a card on file, even to stay in the free
consumption grant — same as every real-CPU cloud).

### 1a. One-time account setup
```bash
az login                                        # browser-based sign-in
az provider register --namespace Microsoft.App
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.ContainerRegistry
az group create --name icarus-rg --location centralindia   # pick a region near you
```
`az containerapp` is a built-in command group in recent `az` versions — the
`containerapp` extension install can fail on newer Python (a wheel-compat
issue, not a real blocker); if it does, core `az containerapp` commands still
work without it.

### 1b. Build locally and push (new subscriptions can't use ACR Tasks' remote build)
A **brand-new** Azure subscription is blocked from ACR Tasks (`TasksOperationsNotAllowed`,
a real, documented restriction on new accounts) — build with local Docker instead:
```bash
az containerapp up --name icarus-brain --resource-group icarus-rg \
  --location centralindia --source . --ingress external --target-port 8000 \
  --env-vars 'ICARUS_ALLOWED_HOSTS=*' 'ICARUS_SYNC_CONNECT=1'
# ^ this WILL fail at the ACR Tasks build step on a new subscription -- it still
#   creates the registry + environment first, which is what you need. Then:

ACR=<the acr name printed above, e.g. caec8849f1f0acr>
az acr credential show --name "$ACR" --query "passwords[0].value" -o tsv \
  | docker login "$ACR.azurecr.io" --username "$ACR" --password-stdin
docker build --platform linux/amd64 -t "$ACR.azurecr.io/icarus-brain:latest" .
docker push "$ACR.azurecr.io/icarus-brain:latest"

az containerapp create --name icarus-brain --resource-group icarus-rg \
  --environment icarus-brain-env --image "$ACR.azurecr.io/icarus-brain:latest" \
  --registry-server "$ACR.azurecr.io" --registry-username "$ACR" \
  --registry-password "$(az acr credential show --name $ACR --query 'passwords[0].value' -o tsv)" \
  --ingress external --target-port 8000 --min-replicas 1 --max-replicas 3 \
  --cpu 1.0 --memory 2.0Gi \
  --env-vars 'ICARUS_ALLOWED_HOSTS=*' 'ICARUS_SYNC_CONNECT=1'
```
`--platform linux/amd64` matters on an Apple Silicon Mac — Azure's default node
pool is x86.

**`--min-replicas 1`, not `0`, is a deliberate decision — do not "optimize" this
back to 0.** `0` was tried first (genuinely free) but live-verified to cause a
real ~24-second cold start on the first request after ~5 min idle (measured via
`az containerapp replica list` showing zero replicas, then timing a request:
24.15s). A client-side retry (`BrainClient.swift`) was shipped to absorb a
*transient* blip, but 24s is far longer than that retry's delay ever covers —
so real users hit hard "can't reach Icarus's brain" failures. `min-replicas 1`
costs real money (~$24/month once the free grant is used — see below) but
eliminates the cold start entirely, which matters once real people are testing
the app. Covered for now by Azure's $200/30-day free-account credit; that
credit expires 2026-08-10 regardless of remaining balance and the subscription
gets **disabled** at that point unless upgraded to Pay-As-You-Go first — a
real deadline, not urgent yet, but don't let it lapse silently.

**`ICARUS_SYNC_CONNECT=1` is required on Azure/Cloud Run-style platforms.**
Request-scoped-CPU hosts only reliably give a container CPU while a request is
being processed — a background thread's embed work after the response returns
isn't guaranteed resourced. This flag makes `/connect` block on the real embed
and return its final status directly (200, not 202) instead of backgrounding
it. See `demo/server.py`'s `sync_connect` docstring. Verified live: a genuine
cold embed of a 219-chunk private repo completed in **1.2s** on Azure's CPU
(vs never-finishing on Render's 0.1 CPU) — confirmed as real semantic
retrieval, not a lexical fallback, via a conceptual query with zero keyword
overlap returning the correct evidence.

### 1c. Wire secrets + GitHub OAuth
```bash
az containerapp secret set --name icarus-brain --resource-group icarus-rg --secrets \
  groq-key="$GROQ_API_KEY" gemini-key="$GEMINI_API_KEY" \
  gemini-paid-key="$GEMINI_PAID_API_KEY" gh-token="$(gh auth token)" \
  github-client-secret="$GITHUB_CLIENT_SECRET"

FQDN=$(az containerapp show --name icarus-brain --resource-group icarus-rg \
  --query "properties.configuration.ingress.fqdn" -o tsv)

az containerapp update --name icarus-brain --resource-group icarus-rg --set-env-vars \
  'ICARUS_ALLOWED_HOSTS=*' 'ICARUS_SYNC_CONNECT=1' 'ICARUS_REQUIRE_GITHUB_AUTH=1' \
  "ICARUS_PUBLIC_URL=https://$FQDN" \
  "GITHUB_CLIENT_ID=$GITHUB_CLIENT_ID" 'GITHUB_CLIENT_SECRET=secretref:github-client-secret' \
  'GROQ_API_KEY=secretref:groq-key' 'GEMINI_API_KEY=secretref:gemini-key' \
  'GEMINI_PAID_API_KEY=secretref:gemini-paid-key' 'GH_TOKEN=secretref:gh-token'
```
Then in GitHub → Settings → Developer settings → OAuth Apps → your app, set the
**Authorization callback URL** to `https://$FQDN/auth/github/callback` — an
OAuth **App** (not a GitHub **App**) allows exactly **one** registered
callback, so this *replaces* whatever was there (e.g. Render's), it doesn't
add alongside it.

**Azure has no automatic spend cap** (unlike some other clouds' softer
guardrails) — set a budget alert in Cost Management immediately after account
setup.

### 1d. Verify the brain is live
```bash
curl "https://$FQDN/health"
# {"ok": true, "repo": "simonw/llm", "commit": "..."}
```
Boots warm immediately (the fastembed model + default corpus's embeddings are
baked into the image at build time, same as every host) — no cold-embed wait.

---

## Part 2 — Build and share the app

### 2a. Build the DMG, stamped with your brain URL
```bash
cd mac/Icarus
ICARUS_BRAIN_URL="https://$FQDN" ./scripts/package_dmg.sh
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
- **Always warm, not free.** `min-replicas 1` keeps a replica running always
  (no cold start), at ~$24/month once the free grant is used up — see the
  note above. Covered by the $200/30-day account credit for now.
- **Repo-switching ingests on your server** on the user's input. Prompt-injection
  via ingested content is disclosed in `docs/EVALUATION.md`; the honesty gate
  proves provenance, not faithfulness. Prefer vetted repos for demos.
- **Ad-hoc signature, not notarized.** The app opens on other Macs only via the
  manual Gatekeeper step above, and rebuilding changes the signature (re-prompts
  the Keychain). Notarization (needs the $99/yr Developer ID) removes both.

## Rotate the keys
The Groq/Gemini keys and the GitHub client secret were exposed in an earlier chat
transcript (see `docs/HANDOFF.md` §6). Rotate them when you set the Azure
Container App's secrets — same sitting.
