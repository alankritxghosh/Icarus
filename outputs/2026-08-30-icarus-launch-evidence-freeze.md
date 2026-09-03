# Icarus launch evidence freeze — 2026-08-30

This file records the observed launch artifact and the evidence collected after
Alankrit approved the thin production canary route. It is a freeze packet, not a
claim that the hardened isolated canary has passed.

## Frozen artifact

- Production app: `icarus-brain`
- Resource group: `icarus-rg`
- Public URL:
  `https://icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io`
- Ready revision: `icarus-brain--0000074`
- Image:
  `caec8849f1f0acr.azurecr.io/icarus-brain@sha256:580bbf863690804e3128456bd0f4dbca3e8fad778f5afde8c65423fdc864c6b3`
- Scale observed after deploy: min replicas `1`, max replicas `1`
- Serving writer: explicit launch provider backed by `GEMINI_API_KEY`
- Removed legacy env from the live runtime: `GROQ_API_KEY`,
  `GEMINI_PAID_API_KEY`

Do not redeploy over this artifact for cosmetic or speculative work. If the app
is redeployed, repeat the health, readiness, public smoke, private smoke, log
tail and control-plane checks before using this document as launch evidence.

## Live HTTP evidence

Observed against the production URL after the digest deploy and after production
hardening:

- `GET /health` returned 200.
- `GET /ready` returned 200 with these checks true:
  `storage_writable`, `writer_key`, `public_ingest_credential`,
  `github_oauth`, `github_auth_required`, `registry_ready`.
- Unauthenticated protected-route checks:
  - `POST /connect` to the private canary repo returned 401.
  - `POST /ask` about the private canary phrase returned `unknown` and did not
    echo the private phrase.
- Public tiny canary:
  - repo: `alankritxghosh/icarus-launch-canary-public-20260830165534`
  - authenticated connect returned 202.
  - status settled to ready.
  - mascot question returned a cited answer containing `hummingbird`.
  - intent question returned a cited answer.
  - unsupported Kubernetes-region question returned `unknown` with no
    citations.
- Private tiny canary:
  - repo: `alankritxghosh/icarus-launch-canary-private-20260830165534`
  - authenticated connect returned 202.
  - status settled by the second poll with `private: true`.
  - private passphrase question returned a cited answer containing
    `moonlit-banyan`.
  - unsupported invoice question returned `unknown` with no citations.

## Log evidence

Sampled Container App logs after the private canary smoke showed only startup
and this content-free event shape:

- `connect received: private=True refresh=True (background)`

The sampled tail did not show the private repository name, private phrase,
GitHub token, user question, model answer or retrieved evidence content.

Earlier sampled logs showed one transient GitHub retry and issue/PR cap notices
from a large public canary attempt. That explained slow background indexing on
the large repo and was not repeated by the tiny canary smoke.

## Production hardening applied

These safe hardening steps were applied to the existing production app after
the thin canary deploy, and `/health` + `/ready` stayed green afterward:

- system-assigned managed identity enabled on the Container App;
- ACR pull switched to managed identity;
- production app identity granted `AcrPull` on the ACR;
- storage minimum TLS raised to `TLS1_2`;
- resource-group `CanNotDelete` lock added;
- `Microsoft.Insights` registered for the subscription;
- Container App `AllMetrics` diagnostic setting routed to Log Analytics.

The production control-plane checker improved from 14 failures to 9 failures.

## Remaining launch caveats

These are not fixed and must not be described as fixed:

- Runtime secrets are still platform-stored Container App secrets, not
  managed-identity Key Vault references.
- Production storage still does not have the isolated canary's private endpoint
  and default-deny network posture.
- The resource group still has no real activity-alert action group because no
  incident email has been provided.
- The hardened isolated canary app has not been deployed because the private
  canary Key Vault correctly rejected local data-plane access with
  `ForbiddenByConnection`.
- Full Python discovery is not a reliable launch-night gate on this machine:
  it hangs inside local ONNX/fastembed semantic embedding. Focused Python
  boards passed, but the broad discovery run was interrupted rather than
  relabelled green.
- Icarus's own history lookup could not provide repository context while
  writing this freeze file because the connected repository was one of the
  disposable canary repos, not `alankritghosh/jarvis-engineering`.

## Verification board

Green:

- `.venv/bin/python -m unittest discover -t . -s demo`:
  722 tests passed, 3 skipped.
- `node --test extension/*.test.js`:
  55 tests passed.
- `(cd mac/Icarus && swift build)`:
  passed.
- `(cd mac/Icarus && swift test)`:
  300 tests passed.
- `.venv/bin/python scripts/check_detailed_index.py`:
  53/53 modules documented and resolving.
- `bash scripts/scan_secrets.sh`:
  clean.
- `git diff --check`:
  clean.
- `.venv/bin/python -m unittest evals.test_prepare_release -v`:
  4 tests passed.
- `.venv/bin/python -m unittest evals.test_canary_acceptance
  evals.test_canary_app_preflight evals.test_canary_control_plane -v`:
  12 tests passed.

Not green / not completed:

- broad `.venv/bin/python -m unittest discover -t . -s evals` was interrupted
  after hanging inside local ONNX/fastembed semantic embedding;
- broad `.venv/bin/python -m unittest discover -t . -s demo` was separately
  observed to hang inside the same local embedding path when left running from
  an earlier invocation, even though the focused demo discovery passed.

## Go / no-go

Go for a tightly framed launch/demo if the public copy stays inside the
observed evidence:

- working hosted product;
- public demo answers;
- authenticated public-repo connect and cited answers;
- authenticated private-repo connect and cited answers on a disposable private
  repo;
- unauthenticated private access denied/unknown;
- no sensitive content in sampled logs;
- known hardening gaps still open.

No-go for any claim that the product is fully hardened, enterprise-private,
zero-retention, ZDR, isolated-canary-proven, notarized/frictionless on macOS, or
perfectly production-ready.

## Stop-engineering-drift rule

Until launch creative work is complete, only change engineering if one of these
is true:

1. `/health` or `/ready` fails on the frozen revision.
2. Public or private smoke can no longer reproduce the observed behavior.
3. Logs show token, repo-private content, question, answer or evidence leakage.
4. A launch page/download path points to the wrong artifact.
5. A genuine blocker is found and written down with exact reproduction steps.

Everything else should move to post-launch hardening.

## Gemini usage note

Gemini 3 Pro Preview was invoked once in read-only plan mode with a compact
four-file/facts prompt for steps 5-7. It did not return findings within the
bounded low-credit window, so the run was interrupted and this evidence file was
written from Codex-observed command results instead.
