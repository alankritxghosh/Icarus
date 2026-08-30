# Distributing Icarus (current Azure service; final-user gate)

How to put a working Icarus in someone else's hands. Two parts, in order:
**host the brain** (so any recipient can reach it), then **build and verify a
Developer ID-signed, notarized app**.

The cloud service supports public and private repositories behind caller-scoped
GitHub authorization. Self-signed builds remain useful for local development,
but they are not final-user artifacts and must not be published.

**Hosting history:** Render (free tier) was the original host; its 0.1 CPU
free tier could never finish embedding a real repo (docs/HANDOFF.md), so the
brain moved to **Azure Container Apps** on 2026-07-11/12. The Render service
(`icarus-brain`, `srv-d94153cvikkc73ba8ckg`) is now **suspended**, not
deleted. Its retired Blueprint was removed; Azure is the only shipping host.

---

## Part 1 — Host the brain on Azure Container Apps (free tier)

> **Redeploying an EXISTING brain? Do not follow this section — use the
> pipeline.** Everything below is FIRST-TIME setup (creating the registry, the
> container app, the secrets, the OAuth callback). Shipping a change to the
> already-running brain goes through `.gitlab-ci.yml` on the `gitlab` remote
> (`gitlab.com/icarus-group4/Icarus`):
>
> ```bash
> git push gitlab main          # runs secrets-scan + both suites + docker build
> glab ci trigger deploy -R icarus-group4/Icarus -b main
> ```
>
> `deploy` is a MANUAL gate on purpose — every redeploy mints a new revision
> and drops process-local sessions. Corpora, decision records and ledgers live
> on the `icaruscache` Azure Files mount at `/data` and survive revisions. The
> pipeline now checks that mount before and after updating; a missing mount is a
> hard failure, never an apparently healthy ephemeral deployment.
>
> Azure control-plane login uses a service-principal certificate supplied as a
> protected GitLab **file** variable (`AZURE_CLIENT_CERTIFICATE_FILE`). Do not
> replace it with `az login --password "$AZURE_CLIENT_SECRET"`: that places a
> reusable secret in process arguments. The ACR-only build credential is sent
> to `docker login` on stdin.
>
> The pipeline is not merely a convenience wrapper around the manual commands:
> it pins `--max-replicas 1` (queued jobs and short-lived agent sessions still
> live in ONE replica's memory) and **removes** `ICARUS_SYNC_CONNECT`, which made `/connect`
> block past Azure's fixed 240s ingress timeout — measured live on
> `astral-sh/uv`, 2026-08-10, where it never connected at all. A hand-run
> `az containerapp update` copied from the setup commands below will happily
> put that variable back and reintroduce the bug. Deploying by hand was done
> on 2026-08-11 out of not knowing the pipeline existed; that cost an Azure
> re-login, a Docker Desktop start, and very nearly that regression.

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
  --env-vars 'ICARUS_ALLOWED_HOSTS=*'
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
  --ingress external --target-port 8000 --min-replicas 1 --max-replicas 1 \
  --cpu 1.0 --memory 2.0Gi \
  --env-vars 'ICARUS_ALLOWED_HOSTS=*'
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

**Do not set `ICARUS_SYNC_CONNECT` on Azure.** A live `astral-sh/uv` connect
crossed Azure's fixed 240-second ingress timeout when this was enabled. The
shipping configuration keeps one replica warm and runs connect asynchronously;
`--max-replicas 1` keeps the job and the caller's process-local status/session
on the same replica. The corpus itself is durable on Azure Files.

Before serving users, provision the environment storage named `icaruscache`
(`icarusbraindata` / `icarus-cache`, ReadWrite), mount it into the app as volume
`cache` at `/data`, and set `ICARUS_STORAGE_ROOT=/data`. Never put the storage
account key in a shell argument or this repository. The deploy pipeline assumes
that infrastructure already exists and refuses to proceed when it does not.

### 1c. Wire secrets + GitHub OAuth
Create the three Azure Container Apps secrets (`gemini-api-key`, `gh-token`,
`github-client-secret`) through the Azure Portal or an approved secret-injection
workflow. Do not paste their values into a CLI argument, shell history, log, or
repository. Then wire only their references:

```bash
FQDN=$(az containerapp show --name icarus-brain --resource-group icarus-rg \
  --query "properties.configuration.ingress.fqdn" -o tsv)

az containerapp update --name icarus-brain --resource-group icarus-rg --set-env-vars \
  'ICARUS_ALLOWED_HOSTS=*' 'ICARUS_REQUIRE_GITHUB_AUTH=1' \
  'ICARUS_STORAGE_ROOT=/data' 'ICARUS_GLOBAL_ASKS_PER_MINUTE=120' \
  'ICARUS_GLOBAL_INVESTIGATIONS_PER_MINUTE=12' \
  'ICARUS_GLOBAL_CONNECTS_PER_10_MINUTES=30' \
  'ICARUS_MAX_CONCURRENT_WRITERS=8' 'ICARUS_MAX_CONCURRENT_INGESTS=2' \
  "ICARUS_PUBLIC_URL=https://$FQDN" \
  "GITHUB_CLIENT_ID=$GITHUB_CLIENT_ID" 'GITHUB_CLIENT_SECRET=secretref:github-client-secret' \
  'GEMINI_API_KEY=secretref:gemini-api-key' 'GH_TOKEN=secretref:gh-token'
```
The ambient `GH_TOKEN` must belong to a dedicated machine identity and
exist only to raise GitHub's rate limit for public-repository bulk ingestion.
Do not reuse a founder's broad personal token. Private-repository calls replace
the ambient credential per subprocess with the signed-in caller's request-time
token; that token is never persisted. `GROQ_API_KEY` and `GEMINI_PAID_API_KEY`
must not be injected into the launch runtime.
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

## Part 2 — Build, notarize, and verify the app

### 2a. One-time Apple setup

Create a **Developer ID Application** certificate in the Apple Developer
account and install it, including its private key, in the signing Mac's
Keychain. Store notarization credentials as a named `notarytool` Keychain
profile; never pass an Apple password or API private key on the command line.

### 2b. Build the DMG, stamped with your brain URL
```bash
cd mac/Icarus
ICARUS_BRAIN_URL="https://$FQDN" \
ICARUS_CODESIGN_IDENTITY="Developer ID Application: <legal name> (<team id>)" \
ICARUS_NOTARY_PROFILE="Icarus" \
ICARUS_REQUIRE_DEVELOPER_ID=1 \
ICARUS_REQUIRE_NOTARIZATION=1 \
./scripts/package_dmg.sh
# -> mac/Icarus/Icarus.dmg
```
The script release-builds with hardened runtime and timestamp, stamps the hosted
brain URL, submits the DMG to Apple's notary service, waits for acceptance, and
staples the ticket. A missing signing identity, rejected notarization, or absent
profile is a hard failure.

### 2c. Independently verify, then publish

```bash
./scripts/verify_distribution.sh ./Icarus.dmg
```

This independently checks the stapled ticket, Gatekeeper assessment, Developer
ID authority and Team ID, hardened runtime, trusted timestamp, strict nested
signatures, and absence of the debug entitlement. Only after this passes may the
artifact enter Gate 6 of `docs/LAUNCH_CANARY.md`. `site/release-dmg.sh` is
retired because it targets the old self-signed/Vercel-hosted asset path; the
current website reads `release.json` and downloads from the public GitHub
Release.

After Sparkle's Keychain-backed `generate_appcast` has produced the signed
single-item feed, prepare every committed release consumer in one local,
reversible step:

```bash
python3 scripts/prepare_release.py \
  --dmg mac/Icarus/Icarus.dmg \
  --extension /absolute/path/icarus-extension.zip \
  --signed-appcast /absolute/path/appcast.xml \
  --version X.Y.Z --build N \
  --assets-base https://github.com/alankritxghosh/Icarus-Website/releases/download/vX.Y.Z
```

The command reruns the independent distribution verifier, validates the signed
feed's version, build, URL, length and 64-byte Ed25519 signature, then updates
`release.json`, its website copy, `appcast.xml` and `install.sh` together. It
does not upload, commit, deploy or publish anything. Inspect the diff before the
separately authorized promotion.

Then: **Sign in with GitHub** → connect a public repo (e.g. `simonw/llm`) →
**⌘⇧I** to type, or hold **Right Option (⌥)** to speak.

**One-time re-sign-in for private repos.** The GitHub OAuth scope widened from
`read:user` to `repo` so a signed-in user's own token can read their private
repos. Anyone who signed in **before** this deploy is holding a stale
`read:user`-scoped token — private-repo connect will fail for them until they
**sign out and sign back in once** to pick up the new scope. There is no
server-side token migration; this is a real, user-visible one-time step.

---

## Part 3 — Give a user's coding agent access (MCP)

The Mac app IS the MCP server: `Icarus --mcp` speaks newline-delimited JSON-RPC
on stdio and serves the same three tools as `demo/mcp_server.py`. A user needs
no checkout, no Python (macOS ships none by default) and no separate package —
only the app they already installed, signed in, with a repository connected.

Tell them to add this to their agent's MCP configuration — `.mcp.json` for
Claude Code, `.cursor/mcp.json` for Cursor, the equivalent block for Codex:

```json
{
  "mcpServers": {
    "icarus": {
      "type": "stdio",
      "command": "/Applications/Icarus.app/Contents/MacOS/Icarus",
      "args": ["--mcp"]
    }
  }
}
```

No credential goes in that file, and none should ever be put there. The app
reads the user's GitHub token from their own login Keychain and exchanges it for
a short-lived, read-only, route-scoped Icarus session per run; the GitHub
credential never reaches the agent or the config.

**The first run shows a Keychain prompt, and it must be answered.** macOS asks
before letting a binary read a Keychain item it did not create, and a coding
agent launches this in the background where a prompt cannot be seen — the
server will simply sit there producing no output. Have the user run it once in
a terminal first:

```bash
/Applications/Icarus.app/Contents/MacOS/Icarus --mcp
```

Click **Always Allow**, then Ctrl-C. After that the agent can launch it silently.
(Observed during development: a freshly built, differently-signed copy of the
app blocks on exactly this, with empty stdout AND empty stderr — the same
symptom for `--agent-session`, which is how it was identified as a Keychain
prompt rather than a bug in the server.)

Two things worth telling a user up front:
- **One repository at a time.** A tool call names the repo it expects, and
  Icarus refuses if a different one is connected rather than answering about
  the wrong codebase. Switching repos happens in the app.
- **Restart the agent after upgrading Icarus**, since the client keeps the
  stdio process alive for the session.

The Python adapter (`demo/mcp_server.py`) remains the path for anyone working
from a checkout, and stays the SOURCE OF TRUTH for the tool contract: the
Swift copy is generated from it by `scripts/gen_mcp_tools.py`, and
`demo/test_mcp_tools_generated.py` fails if the two drift.

## Launch boundaries (know these before sharing widely)

- **Your quota, their questions.** Every ask spends the service's Gemini
  quota. Per-identity limits, process-wide ask/investigation ceilings, and a
  writer-concurrency cap bound model use. Global connect starts and concurrent
  ingests separately bound repository indexing; provider quotas and billing
  alerts remain additional required controls.
- **Always warm, not free.** `min-replicas 1` keeps a replica running always
  (no cold start), at ~$24/month once the free grant is used up — see the
  note above. Covered by the $200/30-day account credit for now.
- **Repo-switching ingests on your server** on the user's input. Prompt-injection
  via ingested content is disclosed in `docs/EVALUATION.md`; the honesty gate
  proves provenance, not faithfulness. Prefer vetted repos for demos.
- **Logical isolation, not operator blindness.** Repositories are isolated by
  authenticated caller access and separate repo storage, but infrastructure
  administrators can technically access storage and secrets. Do not claim
  cryptographic operator blindness or per-tenant encryption until built and
  independently verified.

## Rotate the keys
The Groq/Gemini keys and the GitHub client secret were exposed in an earlier chat
transcript (see `docs/HANDOFF.md` §6). Rotate them when you set the Azure
Container App's secrets — same sitting.
