# Icarus final-user canary runbook

This is the release gate for a limited production rollout. Canary users receive
the real product; limiting the cohort limits blast radius, not quality.

No step here authorizes a push, deployment, release, OAuth change, credential
rotation, purchase, or user-data mutation. Those actions happen only after the
operator explicitly authorizes them. Record exact commands and observed output
in the release handoff; never turn an intended check into a claimed result.

## Launch-scope decision recorded 2026-08-30

Alankrit explicitly dropped paid-Gemini verification and Apple Developer ID /
notarization as near-term launch blockers. This is a scope reduction, not an
engineering proof.

Consequences:

- do not claim paid-provider no-training, ZDR, cryptographic operator blindness,
  enterprise private-code readiness, or notarized/frictionless macOS install
  unless those facts are later observed;
- keep the existing provider-key posture honest in product copy and support
  docs;
- keep the canary, rate-limit, credential hygiene, log hygiene, repository
  entitlement and cite-or-unknown checks in force; and
- treat unsigned/unnotarized Mac installation as accepted launch friction that
  must be shown clearly in the download instructions video.

## Current production control-plane findings (read-only audit, rechecked 2026-08-30)

These are observed blockers, not hypothetical checklist items:

- the resource group inherits two subscription-level `Owner` assignments;
- the Container Apps environment sends application logs to Log Analytics, but
  the app has no diagnostic setting and the resource group has no activity-log
  alert;
- the storage account permits the public network, has no private endpoint and
  reports a `TLS1_0` minimum; file-share soft delete is now enabled for 7 days;
- the live app still exposes legacy `GROQ_API_KEY`; `GEMINI_API_KEY` remains
  the serving writer by explicit launch decision, and none of the new explicit
  global capacity settings are deployed yet; the prepared deployment pipeline
  removes/adds the appropriate values, but has not run;
- the resource group has no deletion/read-only lock;
- the current Mac DMG has no stapled Apple notarization ticket and is rejected
  by the final-user verifier.
- GitLab currently has only `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, and
  `AZURE_TENANT_ID`; the new protected file variable
  `AZURE_CLIENT_CERTIFICATE_FILE` is not provisioned, so deploy now fails closed
  instead of falling back to a password in argv.

Do not alter the running production account in place merely to clear a
checkbox. Build the isolated canary with the intended network, RBAC, retention,
alerting and recovery controls, prove it, then choose a deliberate migration.

## Isolated canary foundation (provisioned 2026-08-30)

`infra/launch_canary.bicep` reproducibly provisioned `icarus-canary-rg` in
Central India. The observed post-deployment state is:

- Storage and Key Vault public network access disabled with default-deny rules;
- approved Azure Files and Key Vault private endpoints plus private DNS links;
- Storage minimum TLS 1.2 and Azure Files soft delete retained for 14 days;
- a VNet-integrated Container Apps environment writing to Log Analytics;
- a dedicated user-assigned identity with only `Key Vault Secrets User` on the
  canary vault; and
- a `CanNotDelete` resource-group lock.

The foundation deliberately contains no Container App, secret values, alert
recipient or customer data. Do not mark the canary operational until the exact
candidate image, managed-identity ACR pull, Key Vault references, diagnostic
settings, action group/activity alert and HTTP acceptance matrix are deployed
and observed. Secret insertion needs a private-network-capable path; never
temporarily expose the vault or place a secret in command arguments to bypass
that requirement.

## Isolated canary app layer (prepared, not deployed)

`infra/launch_canary_app.bicep` now defines the post-foundation app layer. A
placeholder what-if on 2026-08-30 planned only four creates inside
`icarus-canary-rg`: the canary Container App, the app diagnostic setting, the
incident action group and the resource-group activity alert. Existing
foundation resources were ignored, and no production resource was in scope.

The module deliberately accepts Key Vault secret URLs, not secret values. It
configures:

- the canary app as one warm replica using a full non-`latest` candidate image,
  preferably an ACR digest;
- managed-identity-only ACR pull configuration;
- required launch env values and no legacy serving credential names;
- `GEMINI_API_KEY`, `GH_TOKEN` and `GITHUB_CLIENT_SECRET` as Key
  Vault-backed secret references;
- optional `POSTHOG_PROJECT_TOKEN` and `ICARUS_ANALYTICS_SALT` only when their
  Key Vault URLs are supplied;
- the Azure Files environment storage as volume `cache` mounted at `/data`;
- workspace-backed `AllMetrics` diagnostics; and
- an enabled action group plus resource-group activity alert for the incident
  email.

Before granting ACR pull or deploying this module, run the local no-mutation
input preflight. It requires a full ACR digest image and validates only shapes;
it prints fixed PASS/FAIL labels, never the values:

```bash
ICARUS_CANARY_ACR_LOGIN_SERVER=<registry>.azurecr.io \
ICARUS_CANARY_CANDIDATE_IMAGE=<registry>.azurecr.io/icarus-brain@sha256:<digest> \
ICARUS_CANARY_GITHUB_CLIENT_ID=<public-oauth-client-id> \
ICARUS_CANARY_INCIDENT_EMAIL=<incident-email> \
ICARUS_CANARY_KV_GEMINI_API_KEY_URL=https://<vault>.vault.azure.net/secrets/gemini-api-key \
ICARUS_CANARY_KV_GH_TOKEN_URL=https://<vault>.vault.azure.net/secrets/gh-token \
ICARUS_CANARY_KV_GITHUB_CLIENT_SECRET_URL=https://<vault>.vault.azure.net/secrets/github-client-secret \
python3 scripts/canary_app_preflight.py
```

Then grant the canary managed identity `AcrPull` on the exact registry resource
id, and record the observed assignment id. Keep this as an explicit
authorization step because the registry is outside the canary resource group:

```bash
CANARY_IDENTITY_PRINCIPAL_ID=$(az identity show \
  -g icarus-canary-rg -n icarus-canary-identity \
  --query principalId -o tsv --only-show-errors)
ACR_ID=$(az acr show -g <acr-rg> -n <acr-name> \
  --query id -o tsv --only-show-errors)
az role assignment create \
  --assignee-object-id "$CANARY_IDENTITY_PRINCIPAL_ID" \
  --assignee-principal-type ServicePrincipal \
  --role AcrPull \
  --scope "$ACR_ID" \
  --only-show-errors
```

Do not run the app-layer deployment with placeholder values. The real deploy
still needs the incident contact, the exact candidate image tag or digest, the
canary GitHub OAuth client id, and private Key Vault secret URLs populated

## Thin production canary fallback (executed 2026-08-30)

After the isolated canary Key Vault correctly rejected local secret population
with `ForbiddenByConnection`, Alankrit explicitly accepted a thinner fallback:
upgrade the existing production Container App to the exact candidate image and
launch runtime allowlist, then run live smoke checks there. This proves serving
health for the candidate artifact, not isolated canary hardening.

Observed live artifact:

- app: `icarus-brain` in `icarus-rg`;
- revision: `icarus-brain--0000074`;
- image: `caec8849f1f0acr.azurecr.io/icarus-brain@sha256:580bbf863690804e3128456bd0f4dbca3e8fad778f5afde8c65423fdc864c6b3`;
- scale: one warm replica, max one replica;
- launch env: `GEMINI_API_KEY` and global capacity limits present;
- removed launch-forbidden env: `GROQ_API_KEY`, `GEMINI_PAID_API_KEY`.

Observed HTTP smoke:

- `/health` returned 200;
- `/ready` returned 200 with `github_auth_required`, `github_oauth`,
  `public_ingest_credential`, `registry_ready`, `storage_writable` and
  `writer_key`;
- unauthenticated `/context`, `/connect`, `/map` and `/agent-mode/context`
  returned 401;
- unauthenticated `/ask` returned cited demo answers only under the intentional
  `ICARUS_PUBLIC_DEMO=1` default-repo path;
- authenticated `/status`, `/map`, `/connect` and `/ask` returned 200/202;
- the authenticated canary repo remained in background indexing phase
  `Building smart search…` with no observed error after the initial smoke.

Observed log smoke: sampled Container App logs showed startup, a content-free
connect line, one transient GitHub retry and issue/PR cap notices. The sample
did not contain tokens, questions, answers or retrieved evidence content.

Observed hardening gap: `scripts/canary_control_plane.py` remains red against
the existing production app for the known thin-route reasons: no managed
identity, registry pull not managed-identity-only, runtime secrets not
Key-Vault-backed, storage not private/default-deny/TLS-checked by the harness,
no resource-group delete lock, no enabled activity-log alert destination and no
workspace-backed metric diagnostic setting. Do not cite the thin fallback as
proof that the isolated canary passed.
through a private-network-capable path.

## What the canary must prove

The same immutable brain image and Mac build intended for production must prove:

1. cite-or-unknown survives the release;
2. one GitHub identity cannot read another repository;
3. entitled collaborators can use the same repository memory without pooling
   it with another repository;
4. caller credentials remain request-scoped and absent from disk, argv and logs;
5. corpora and decision records survive a revision while process-local agent
   sessions expire cleanly;
6. global and per-identity limits bound spend and return actionable retry data;
7. provider, GitHub and storage failures remain honest failures;
8. install, update, deletion, monitoring and rollback work outside a developer
   checkout.

## Non-negotiable truth boundary

- Icarus runs in a unified Azure service. Private repositories are logically
  isolated by repository plus a GitHub entitlement check on every read. They
  currently share one Azure Files account and encryption boundary; there are
  not separate encryption keys per customer.
- Infrastructure administrators can technically access runtime storage and
  secrets. Do not claim cryptographic operator blindness. The current promise
  is least-privilege, exceptional access with an auditable operational reason;
  that control still needs to be configured and evidenced before launch.
- Paid Gemini API terms say paid prompts and responses are not used to improve
  Google's products. They may still be logged for limited abuse monitoring.
  Do not claim zero data retention unless the production project has approved
  ZDR. Sources verified 2026-08-29:
  https://ai.google.dev/gemini-api/terms and
  https://ai.google.dev/gemini-api/docs/zdr .
- Icarus deliberately retains indexed corpora, confirmed decisions and bounded
  ledgers until deletion. That durable memory is the product, not a leak.
- Product analytics are counts-only unless a caller explicitly sends
  `X-Icarus-Share-Content: 1`. Never enable or simulate consent centrally.

## Canary topology

Production currently has one Azure Container App. A valid canary requires a
second app with all of the following isolated from production:

- hostname and OAuth callback;
- Azure Files share/storage root;
- app secrets and dedicated public-ingest GitHub machine credential;
- PostHog project, or analytics disabled;
- deployment environment and revision history;
- Mac build stamped with the canary brain URL and a non-production update feed.

Do not point a canary build at production storage. Do not rebuild between
canary and promotion: promote the exact brain image digest and exact signed DMG
that passed.

## Release identity

Write these values before running any gate:

| Artifact | Required immutable identity |
|---|---|
| Source | full Git commit SHA from a clean launch branch |
| Brain | ACR image digest, not `latest` |
| Mac app | version, build number, signing authority and Team ID |
| DMG | byte count and SHA-256 |
| Extension | byte count and SHA-256 |
| Update | appcast EdDSA signature and exact enclosure URL |

Any change to one value invalidates the canary result for that artifact.

## Configuration allowlist

The canary and production runtime may receive only the values they use:

- `GEMINI_API_KEY` via an Azure secret reference;
- `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` for OAuth;
- `GH_TOKEN` from a dedicated public-ingest machine identity;
- `ICARUS_ANALYTICS_SALT` and `POSTHOG_PROJECT_TOKEN` when counts analytics are
  enabled;
- host/auth/storage flags and the explicit capacity values below.

`GROQ_API_KEY` and `GEMINI_PAID_API_KEY` must be absent from the launch
runtime. By explicit 2026-08-30 decision, the existing `GEMINI_API_KEY` is the
serving writer key for this launch. Secret values must never be printed, placed
in argv, copied into the repository, or included in the canary record.

Current conservative process limits:

| Boundary | Default |
|---|---:|
| asks per identity | 30/minute |
| connects per identity | 5/10 minutes |
| refreshes per identity | 2/hour |
| investigations per identity | 3/minute |
| anonymous demo asks | 300/hour globally |
| all asks/onboarding/explain | 120/minute globally |
| all investigations/context | 12/minute globally |
| all repository connects | 30/10 minutes globally |
| simultaneous writer requests | 8 |
| simultaneous repository ingests | 2 |

Before launch, compare those values with the production Gemini quota and the
maximum acceptable hourly spend. A code default is not evidence that an
account-level quota or budget alert exists.

## Gate 1 — clean candidate

- [ ] Candidate is based on current `main`, not a dirty experiment checkout.
- [ ] Agent Mode changes and current `main` are reconciled deliberately.
- [ ] Secret scan is clean.
- [ ] Python evals and demo suites pass; skips are named.
- [ ] Swift build/tests and extension tests pass.
- [ ] The eval board remains green, or every pre-existing non-honesty failure is
      named without weakening it.
- [ ] `git diff --check`, release-manifest selftest/check, and index check pass.
- [ ] No placeholder, test double or ad-hoc artifact is called production.

## Gate 2 — provider and credentials

- [ ] The Gemini key's Cloud Project visibly shows an active paid plan.
- [ ] Gemini API developer logging is disabled; no dataset or feedback sharing
      is enabled.
- [ ] ZDR approval state is recorded as approved or not approved. Marketing and
      privacy copy match the observed state.
- [ ] The GitHub server token belongs to a dedicated machine identity and its
      scopes/access are recorded.
- [ ] Storage enforces TLS 1.2+, has a deliberate private-network or equivalent
      documented access boundary, and file-share recovery retention is enabled
      and restored in a drill.
- [ ] Runtime/deploy roles are least-privilege; subscription Owner is not the
      normal operating identity. Privileged changes are auditable and alerted.
- [ ] GitLab deploy authentication uses the protected certificate file variable;
      no password, bearer, GitHub token or provider key appears in process argv.
- [ ] Azure runtime env contains no legacy provider credential.
- [ ] Logs contain no bearer-token shapes, repository names, file paths,
      command arguments, provider exception text, questions, answers or
      evidence; only operation/status and exception categories are retained.
- [ ] PostHog receives only allowlisted count metadata in a default request.

## Gate 3 — adversarial tenant matrix

Use two real GitHub identities and four disposable repositories:

- public repository `P`;
- private repository readable only by A, `A-private`;
- private repository readable only by B, `B-private`;
- private repository shared by A and B, `shared`.

Run the repeatable HTTP matrix with tokens and repository slugs supplied only
through the environment (never argv):

```bash
ICARUS_CANARY_BASE=https://<canary-host> \
ICARUS_CANARY_TOKEN_A=<token-a> ICARUS_CANARY_TOKEN_B=<token-b> \
ICARUS_CANARY_REPO_PUBLIC=<owner/public> \
ICARUS_CANARY_REPO_A_PRIVATE=<owner/a-private> \
ICARUS_CANARY_REPO_B_PRIVATE=<owner/b-private> \
ICARUS_CANARY_REPO_SHARED=<owner/shared> \
ICARUS_CANARY_ACK=I-authorized-this-canary-run \
python3 scripts/canary_acceptance.py
```

The harness prints only fixed labels, never tokens, slugs, questions, answers,
evidence or response bodies. It proves health/readiness, anonymous denial,
public access, both one-sided private denials, shared access, repo-scoped agent
grant isolation, disconnect isolation, and cite-or-unknown shape. Revocation,
and a live per-identity 429 with a positive `Retry-After`. Revocation, restart
persistence, process-wide capacity exhaustion and log/control-plane inspection
remain separate gates below because they require deliberate external state
changes, higher-cost load, or operator access.

Pass every case at the HTTP boundary and in the Mac app:

| Case | Expected result |
|---|---|
| A connects and asks `A-private` | cited answer or honest unknown |
| B reads while A's active corpus is `A-private` | `403`; no evidence or metadata |
| B connects `B-private`; A reads it | `403`; no evidence or metadata |
| A and B connect `shared` | both authorized; one repo memory |
| A disconnects from `shared` | A's personal state removed; shared corpus remains for B |
| revoked collaborator reads `shared` | next read fails closed after GitHub check |
| anonymous caller asks private state | `401`/`403`; never demo downgrade |
| agent grant for repo X calls repo Y | `403` |

Inspect response bodies, headers, analytics payloads and service logs. Analytics
must contain neither raw GitHub identity nor repository slug; without the
analytics salt, identity must collapse to anonymous and the repository field
must be absent. A status code alone is insufficient if confidential metadata or
excerpts leak.

## Gate 4 — persistence, limits and failures

- [ ] Preflight and postflight show Azure environment storage `icaruscache`
      mounted as volume `cache` at `/data`.
- [ ] Connect a disposable repo and confirm a decision; deploy/restart the
      canary revision; verify corpus and decision survive.
- [ ] Verify the old process-local agent session is rejected and a newly minted
      repo-scoped session works.
- [ ] Exhaust each per-identity and process-wide limit. Every rejection occurs
      before billed work and carries `Retry-After`.
- [ ] Exceed simultaneous writer capacity. The extra request receives retryable
      `503`; admitted requests finish and release capacity, including after a
      provider exception.
- [ ] Exhaust the global connect-start budget and exceed ingest concurrency.
      Excess work is rejected before clone/ingest, and both successful and
      failed background jobs release their slot.
- [ ] Invalid/missing provider credential returns an honest `503`, never an
      invented answer or stack trace.
- [ ] Provider 429 retries honor Retry-After but stop inside the bounded
      90-second total backoff budget, leaving headroom below Azure ingress
      timeout and releasing the writer slot on failure.
- [ ] GitHub timeout/403, failed ingest, full storage and failed deletion each
      remain explicit failures.
- [ ] Run a bounded soak at the intended launch concurrency and record p50/p95,
      error rate, 429/503 counts and provider usage. Do not infer quota safety
      from unit tests.

## Gate 5 — observability and rollback

Run the read-only control-plane acceptance check and retain its fixed-label
output with the canary evidence:

```bash
python3 scripts/canary_control_plane.py \
  --resource-group <canary-rg> --app <canary-app> \
  --environment <canary-environment> --storage-account <canary-storage>
```

It queries metadata without `--show-secrets` and performs no mutation. It fails
unless the runtime uses an immutable image, one warm replica, exact capacity
values, managed-identity Key Vault references, managed-identity-only registry
pulls and no legacy provider variables; `/data` is a real environment storage
mount; Log Analytics, diagnostics and an actionable
activity alert exist; and storage has TLS 1.2, denied public networking, an
approved private endpoint, at least seven days of file soft delete and a
`CanNotDelete` lock.

Required content-free signals:

- request count by route/status/surface;
- answer latency and provider availability;
- 429, capacity 503, auth 401/403 and ingest/delete failures;
- active revision, storage mount state and disk use;
- provider usage/quota and Azure cost alerts;
- synthetic sign-in, public connect, cited answer and honest-unknown journeys.

Alerts need an owner and destination. `/health` proves only process liveness and
default-corpus provenance; it is not readiness for auth, storage or the writer.

Before canary, record the previous healthy revision and image digest. Rehearse
rolling the canary back to it, then repeat health, persistence and one real ask.
Rollback never deletes the Azure Files share and never rebuilds an image tag.

## Gate 6 — final-user distribution

- [ ] App uses a stable Apple Developer ID signature, hardened runtime,
      notarization and stapling; verify on a clean macOS user account.
- [ ] Sparkle public key and feed are stamped; appcast signature verifies.
- [ ] `scripts/prepare_release.py` accepts the notarized DMG and signed appcast;
      its resulting four-file diff is reviewed before any upload or deployment.
- [ ] `release.json`, appcast, website links, redirects, DMG and extension agree
      on version, URL, bytes and SHA-256.
- [ ] Fresh install, GitHub sign-in, private scope upgrade, Claude Agent Mode
      install/repair, update and uninstall/delete instructions are exercised.
- [ ] Domain HTTPS, privacy policy, terms, support contact and incident contact
      are live before public promotion.

If Apple notarization is unavailable, the Mac artifact is not a frictionless
final-user release. Launch the web experience or label the download accurately;
do not hide the Gatekeeper workaround inside instructions.

## Promotion and abort rules

Promote only after every applicable checkbox has observed evidence. Start with
2–5 final users, then widen deliberately while watching the signals above.
Release preparation is local and reversible; GitHub upload, site deployment and
public release promotion remain separate authorized actions.

Abort or roll back immediately on:

- any cross-user evidence, repository name, decision or analytics-content leak;
- any private request routed through an unverified/unpaid provider;
- missing persistent mount or failed deletion presented as success;
- cite-or-unknown regression or fabricated/unresolvable citation;
- unexplained provider-cost spike, sustained capacity failure or secrets in logs;
- installer/update signature mismatch.

Creative assets may be recorded once the exact release candidate passes the
offline gates. Public product claims may be finalized only after the live
canary gates they describe have passed.
