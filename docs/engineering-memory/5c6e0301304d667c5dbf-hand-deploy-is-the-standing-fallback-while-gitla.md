<!-- icarus-agent-mode-decision:v1 id=5c6e0301304d667c5dbfb175fa2a1bbba5eeb0d7477a7298d82fc80f46c7cb2c -->

# Hand-deploy is the standing fallback while GitLab CI is out of compute minutes: the brain via `az acr build` + `az containerapp update`, and the Mac app via package_dmg + Sparkle `sign_update` + `gh release` + `vercel --prod`.

> Human-confirmed decision proposal. This is not merged project truth.

## Decision

Hand-deploy is the standing fallback while GitLab CI is out of compute minutes: the brain via `az acr build` + `az containerapp update`, and the Mac app via package_dmg + Sparkle `sign_update` + `gh release` + `vercel --prod`.

## Confirmed rationale

On 2026-08-31 every GitLab pipeline failed instantly with `ci_quota_exceeded` (no runner, deploy job unplayable), which had been true for ~10 hours before the launch push. Both deploys are fully hand-operable and were proven end to end this session (brain rev 0000076; app 0.1.10 live via Sparkle). ACR Tasks works despite an older note saying it was disabled, so no local Docker is needed. This unblocks launch without waiting on a billing action, and the full runbook plus the `scripts/deploy_site.sh`-is-broken landmine (Vercel project Root Directory = web breaks `cd web && vercel`) are recorded in the deploys memory.

## Alternatives considered

- Restore GitLab CI minutes (buy compute or wait for monthly reset) and deploy through the pipeline
- Leave deploys blocked until CI is restored

## Affected paths

- `.gitlab-ci.yml`
- `scripts/deploy_site.sh`
- `mac/Icarus/scripts/package_dmg.sh`

---

Proposed through Icarus Agent Mode. GitHub review and merge history are authoritative.
