# Icarus engineering handoff and Gemini delegation note — 2026-08-30

This note records the state left by the current launch-engineering session and the decision logic for using Gemini alongside Codex. It is a working handoff, not canonical product truth. Durable product decisions should still be copied into the proper vault/doc home when settled.

## Current launch-engineering state

The launch canary now has a verified foundation and an app-layer deployment plan, but it has not been deployed with real production secrets in this session.

Completed and observed:

- Installed Bicep locally.
- Provisioned the isolated Azure canary foundation in `icarus-canary-rg`.
- Added `infra/launch_canary_app.bicep` for the canary app layer.
- Added `scripts/canary_app_preflight.py` for local, non-mutating validation of deployment inputs.
- Added `evals/test_canary_app_preflight.py` for digest-only image and secret-shape checks.
- Tightened `scripts/canary_control_plane.py` so diagnostics and activity alerting are required rather than optional.
- Updated `evals/test_canary_control_plane.py`.
- Updated `docs/LAUNCH_CANARY.md`, `general_index.md`, and `detailed_index.md`.
- Wrote session learnings into the Obsidian vault: `Work Queue.md` and `Learning.md`.

Verification observed:

- Focused canary tests: `evals.test_canary_app_preflight`, `evals.test_canary_control_plane`, and `evals.test_canary_acceptance` passed, 12/12.
- Canary app preflight with valid dummy inputs passed and printed only fixed labels, not supplied secret material.
- Naked canary app preflight failed closed on missing inputs.
- `az bicep build --file infra/launch_canary_app.bicep` passed.
- Azure group validation for `launch_canary_app.bicep` succeeded with dummy values.
- Azure what-if showed only four creates in `icarus-canary-rg`: container app, diagnostic setting, action group, and activity alert.
- Demo suite passed: 722 tests, 2 skips.
- Swift suite passed: 300 tests.
- Extension tests passed: 55 tests.
- Website lint/build passed.
- `python3 scripts/check_detailed_index.py` passed: 53/53.
- `bash scripts/scan_secrets.sh` passed clean.
- `git diff --check` passed clean.
- After Alankrit dropped the paid-Gemini blocker, serving was aligned to
  explicit `gemini-launch` backed by `GEMINI_API_KEY`; focused provider/server/
  canary tests passed, the live demo smoke answered through the existing key,
  and Azure group validation for the renamed canary app parameter succeeded.
- `az acr build` from a minimal 36 MB context pushed
  `caec8849f1f0acr.azurecr.io/icarus-brain:9f16b7e51362-canary` with digest
  `sha256:580bbf863690804e3128456bd0f4dbca3e8fad778f5afde8c65423fdc864c6b3`.
- Canary identity `AcrPull` was granted on ACR `caec8849f1f0acr`; observed role
  assignment id `29110ac2-766b-4b8c-92db-3edd2a24704f`.
- Canary Key Vault `icarus-canary-qn5fxmrfsg` rejects local data-plane access
  with `ForbiddenByConnection`, which preserves the private-link boundary but
  blocks secret population from this host.
- By Alankrit's explicit fallback decision, the existing production app was
  upgraded as a thin canary to revision `icarus-brain--0000074`, running
  `caec8849f1f0acr.azurecr.io/icarus-brain@sha256:580bbf863690804e3128456bd0f4dbca3e8fad778f5afde8c65423fdc864c6b3`.
- Production readback showed the latest and ready revisions match, min/max
  replicas are 1/1, `GEMINI_API_KEY` and global capacity env vars are present,
  and `GROQ_API_KEY`/`GEMINI_PAID_API_KEY` are absent.
- Thin HTTP smoke passed: `/health` and `/ready` return 200; unauthenticated
  `/context`, `/connect`, `/map` and `/agent-mode/context` return 401;
  unauthenticated `/ask` returns cited demo answers only under
  `ICARUS_PUBLIC_DEMO=1`; authenticated `/status`, `/map`, `/connect` and
  `/ask` return 200/202.
- Background indexing for the authenticated canary repo is still in phase
  `Building smart search…` with no observed error; serving is green, indexing
  completion is not yet observed.
- Sampled production logs showed startup, a content-free connect line, one
  transient GitHub retry and issue/PR cap notices; no token, question, answer or
  retrieved evidence content appeared in the sampled tail.
- The control-plane checker remains red against the existing production app on
  managed identity, Key Vault-backed secrets, private storage networking/TLS,
  delete lock, alert destination and metric diagnostics. This is the known cost
  of the thin route, not a passed isolated canary.
- After the next hardening pass, production has system-assigned managed
  identity, managed-identity ACR pull, storage minimum TLS 1.2, a resource-group
  `CanNotDelete` lock, `Microsoft.Insights` registered and Container App
  `AllMetrics` diagnostics routed to Log Analytics. The checker now has 9
  remaining failures: Key Vault-backed runtime secrets, production storage
  private/default-deny networking, and a real activity-alert destination.
- Tiny public and private GitHub canary repos were created and smoked. Public
  canary settled, returned two cited answers and one honest unknown. Private
  canary denied anonymous connect, did not leak the private phrase to anonymous
  `/ask`, settled for the authenticated caller, returned one cited private
  answer and one honest unknown. Post-smoke logs stayed content-free.
- The launch freeze/evidence packet now lives at
  `outputs/2026-08-30-icarus-launch-evidence-freeze.md`.
- Gemini 3 Pro Preview was invoked once in read-only plan mode with a compact
  four-file/facts prompt for the freeze/evidence/stop-drift review. It produced
  no findings within the bounded low-credit window, so the run was interrupted
  and the freeze packet was written from Codex-observed command results.

Known not-green item:

- Full Python eval discovery still has one known failure: `evals.test_description_recall.DescriptionRecallBoard.test_intent_phrasing_reaches_the_evidence`.
- This appears to be the preserved r03/r04 intent phrasing miss around `issue:841`, not a new canary/security/privacy regression.
- Do not hide this by weakening the eval or by making a rushed “semantic” tweak without a proper red/green decision.

## What remains before final users

The next smallest engineering bricks are:

1. Align launch claims with the provider decision.
   - Alankrit explicitly dropped paid-Gemini verification as a near-term blocker on 2026-08-30.
   - That means launch copy must not claim paid-provider no-training, ZDR, enterprise private-code readiness, or any privacy guarantee stronger than the observed implementation.
   - Runtime now uses an explicit `gemini-launch` provider backed by `GEMINI_API_KEY`.

2. Populate the canary Key Vault through a private-network-capable path.
   - This host cannot do it; Key Vault rejects the connection because public network access is disabled.
   - Required missing operator inputs: a GitHub server token (`GH_TOKEN`) and incident email. `.env` has Gemini and OAuth client/secret only.

3. Deploy `infra/launch_canary_app.bicep` with real canary-only settings.
   - Keep customer/user data out of the canary unless the trust boundary is explicitly verified.
   - Candidate image is already built and `AcrPull` is already granted.

4. Run canary acceptance against the isolated live app.
   - Verify health, diagnostics, alerting, privacy/no-secret-output, auth behavior, and rate-limit behavior.

4a. If staying on the thin production route tonight, wait for background
    indexing to settle on the authenticated smoke repo or intentionally choose a
    smaller disposable repo; then rerun `/status`, `/ask`, `/ready` and a fresh
    log tail. Do not claim isolated-hardening proof from this path.

5. Decide the known full-eval failure.
   - Either fix it properly with a red/green evidence path, or explicitly mark it as not launch-blocking with the reason captured in the vault.

6. Package/release checks.
   - Re-run release safety, distribution verification, macOS packaging, website build, and secret scans after the final artifact is assembled.

## Why the current canary shape is intentionally narrow

The core logic is separation of authority:

- The canary resource group owns only canary runtime resources.
- Existing shared infra such as ACR remains outside that template.
- The candidate image must be immutable so we know exactly what is under test.
- Secret values are supplied through Key Vault secret URLs and should not be printed, committed, or embedded.
- Diagnostics and alerts are required because a launch canary without observability gives false confidence.

## Gemini 3.1 Pro Preview research snapshot

Current official source picture:

- Google’s changelog says `gemini-3-pro-preview` was shut down on 2026-03-09 and now points to `gemini-3.1-pro-preview`.
- The current model code is `gemini-3.1-pro-preview`; there is also `gemini-3.1-pro-preview-customtools` for workflows that rely heavily on custom tools or shell/file tools.
- The model supports text, image, video, audio, and PDF inputs, with text output.
- The published context window is 1,048,576 input tokens with up to 65,536 output tokens.
- Supported capabilities include function calling, structured outputs, code execution, search grounding, URL context, caching, and thinking.
- Google positions it for complex reasoning, agentic workflows, advanced coding, long-context repo/file analysis, multimodal analysis, and algorithmic development.
- Google’s developer guidance recommends keeping temperature at the default 1.0 for Gemini 3-family models; lowering temperature can degrade complex reasoning or cause looping.
- Google AI Developer API pricing currently marks free-tier data as used to improve products, while paid tier is marked not used to improve products. That matters for Icarus.

Sources:

- Google AI changelog: https://ai.google.dev/gemini-api/docs/changelog
- Gemini 3.1 Pro Preview docs: https://ai.google.dev/gemini-api/docs/models/gemini-3.1-pro-preview
- Gemini 3 developer guide: https://ai.google.dev/gemini-api/docs/gemini-3
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Gemini API terms: https://ai.google.dev/gemini-api/terms
- Gemini Enterprise model page: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/gemini/3-1-pro
- Gemini Enterprise Agent Platform pricing: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing

## How to use Gemini in this repo without breaking trust

Use Gemini for read-only, bounded, non-secret work unless and until a stronger provider posture is verified later.

Good Gemini tasks:

- Long-context repo surveys over non-secret checked-in source.
- Independent review of docs for contradictions.
- Test-plan generation from known requirements.
- Release checklist critique.
- Website/product copy critique where no credentials/customer data are present.
- Finding likely missing cases in tests, with Codex making the final patch.
- Summarizing large public docs or public API docs.

Do not use Gemini yet for:

- Customer private repositories.
- Real canary secret URLs if they disclose tenant/provider details.
- `.env`, local credentials, tokens, logs with secrets, or private user data.
- Final claims that something is secure, deployed, passing, or production-ready without Codex/local verification.
- Autonomous edits in yolo mode.

Recommended CLI pattern:

```bash
gemini --model gemini-3.1-pro-preview-customtools --approval-mode plan --prompt "Read only. Do not edit files. Review docs/LAUNCH_CANARY.md and infra/launch_canary_app.bicep for launch-blocking gaps. Do not print secrets. Return concise findings with file paths."
```

If the task is pure writing or strategy, use:

```bash
gemini --model gemini-3.1-pro-preview --approval-mode plan --prompt "Review this launch positioning for clarity and risk. Do not edit files. Return the top five improvements."
```

## Division of labor

Codex should own:

- Repository mutation.
- Test execution and final verification.
- Privacy/security gating.
- Azure/canary commands that mutate cloud state.
- Release readiness calls.
- Any statement that something is done, shipped, or safe.

Gemini should assist with:

- Wide-context critique.
- Alternative test ideas.
- Copy/positioning review.
- “What am I missing?” passes over checked-in docs.
- Non-mutating second opinions on launch checklists.

The operational rule is simple: Gemini can widen attention; Codex closes the loop.

## Immediate next move

Alankrit has decided to stick with the existing Gemini setup for now. Therefore, restrict Gemini delegation to public or non-sensitive checked-in repo material and keep it away from secrets, private customer data and final launch-readiness authority.

Then run one pilot delegation:

```bash
gemini --model gemini-3.1-pro-preview-customtools --approval-mode plan --prompt "Read only. Review the canary launch path in docs/LAUNCH_CANARY.md, scripts/canary_app_preflight.py, scripts/canary_control_plane.py, infra/launch_canary_app.bicep, and evals/test_canary_app_preflight.py. Do not edit files. Do not print secrets. Return: launch blockers, non-blocking risks, and one smallest next step."
```

Codex should then verify every Gemini finding against source/tests before acting.

## If Codex is out of usage: task list for Gemini

Give Gemini only read-only review tasks under the existing provider posture. Do not ask it to deploy, mutate Azure, edit files, read `.env`, inspect local credentials, ingest private customer data, or decide that the product is launch-ready.

Priority 1: canary deployment review

- Review `docs/LAUNCH_CANARY.md`, `infra/launch_canary.bicep`, `infra/launch_canary_app.bicep`, `scripts/canary_app_preflight.py`, `scripts/canary_control_plane.py`, `scripts/canary_acceptance.py`, and the corresponding `evals/test_canary_*.py` files.
- Output launch blockers, non-blocking risks, and any missing verification that can be added locally without secrets.
- Do not recommend weakening the canary, relaxing digest-only images, exposing Key Vault publicly, removing diagnostics, or skipping acceptance tests.

Priority 2: final-user privacy/security review

- Review `docs/VISION.md`, `docs/ARCHITECTURE.md`, `docs/DISTRIBUTION.md`, `docs/LAUNCH_CANARY.md`, `demo/server.py`, `demo/ratelimit.py`, `demo/payload.py`, `demo/posthog_capture.py`, `demo/library.py`, `evals/trust.py`, and `evals/test_egress_invariants.py`.
- Check whether docs, code, and tests agree on the actual privacy boundary: logical repository isolation, paid-provider terms, no training claim for paid Gemini, no ZDR unless approved, and no cryptographic operator blindness claim.
- Flag any overclaim in docs or launch copy.

Priority 3: release/package readiness review

- Review `scripts/prepare_release.py`, `scripts/check_release.py`, `mac/Icarus/scripts/package_dmg.sh`, `mac/Icarus/scripts/verify_distribution.sh`, `docs/DISTRIBUTION.md`, `release.json`, `web/public/install.sh`, and `web/public/appcast.xml`.
- Find ways the release metadata, DMG notarization, Sparkle appcast, install script, or website download path could drift.
- Do not tell Gemini to notarize, upload, publish, tag, push, or modify Apple/GitHub accounts.

Priority 4: Agent Mode UX/intent capture review

- Review `docs/decisions/2026-08-29-claude-agent-mode-capture-loop.md`, `demo/decision_ledger.py`, `demo/memory_writer.py`, `demo/mcp_server.py`, `mac/Icarus/Sources/Icarus/Shell/AgentModeInboxView.swift`, `mac/Icarus/Sources/Icarus/Shell/DecisionInboxModel.swift`, and Agent Mode tests.
- Check whether the current implementation matches the updated product vision: low-friction multiple choice, Yes/No where appropriate, Other option available, no paragraph-writing burden, and no unconfirmed memory entering future sessions.
- Suggest only small testable improvements; do not propose broad product rewrites.

Priority 5: launch copy fact-check

- Review website/product copy only after engineering facts are settled.
- Flag claims that imply unsupported guarantees: “zero retention,” “cryptographic isolation,” “fully autonomous,” “reads everything automatically,” “production ready” without canary proof, or “works for all repos” without scoped evidence.
- Suggest clearer language for creatives/vibe coders without weakening the honesty boundary.

## Deep prompt to give Gemini

Use this prompt as-is under the existing Gemini setup. Keep the review to checked-in repository files and do not include secret values, local logs, customer repos, private `.env` content, or cloud resource identifiers that are not already committed.

```text
You are helping with Icarus, a privacy-first engineering memory product. You are a read-only reviewer, not the implementer.

Repository root: /Users/alankritghosh/JARVIS /jarvis_engineering

Hard rules:
- Do not edit files.
- Do not run deploys, pushes, tags, releases, package uploads, Azure mutations, GitHub mutations, account changes, or destructive commands.
- Do not read `.env`, shell history, credential files, private logs, customer repositories, or uncommitted binary artifacts.
- Do not print or request secrets, tokens, OAuth secrets, Key Vault secret values, or private repository contents.
- Treat the existing Gemini setup as the launch constraint. Do not claim paid-provider no-training, ZDR, or enterprise private-code readiness unless those facts are later observed.
- Do not claim anything is done, shipped, secure, deployed, passing, or launch-ready unless you can cite the exact checked command/result already recorded in docs or test output.
- Prefer finding small, local, testable gaps over proposing large architecture rewrites.

Product truth to preserve:
- Icarus must cite retrieved evidence or honestly abstain.
- It must not invent citations or answer from unsupported model memory.
- Private repositories are logically isolated by repository identity and GitHub entitlement checks; do not describe this as cryptographic per-tenant isolation.
- Do not make paid-provider, no-training or zero-retention claims under the current launch decision.
- Agent Mode should reduce user cognitive load: multiple choice, Yes/No where appropriate, and an Other option. It should not require users to write paragraphs to confirm intent.
- Unconfirmed, rejected, pending, or Not sure decisions must not enter future-session memory.

Read these files first:
1. AGENTS.md
2. CODEX.md
3. docs/VISION.md
4. docs/LAUNCH_CANARY.md
5. outputs/2026-08-30-icarus-engineering-handoff-gemini-delegation.md

Then review these areas:

Canary:
- infra/launch_canary.bicep
- infra/launch_canary_app.bicep
- scripts/canary_app_preflight.py
- scripts/canary_control_plane.py
- scripts/canary_acceptance.py
- evals/test_canary_acceptance.py
- evals/test_canary_app_preflight.py
- evals/test_canary_control_plane.py

Provider/privacy:
- evals/provider.py
- evals/trust.py
- evals/test_provider.py
- evals/test_egress_invariants.py
- demo/server.py
- demo/ratelimit.py
- demo/payload.py
- demo/posthog_capture.py
- docs/DISTRIBUTION.md
- docs/ARCHITECTURE.md

Release/distribution:
- scripts/prepare_release.py
- scripts/check_release.py
- mac/Icarus/scripts/package_dmg.sh
- mac/Icarus/scripts/verify_distribution.sh
- release.json
- web/public/install.sh
- web/public/appcast.xml

Agent Mode:
- docs/decisions/2026-08-29-claude-agent-mode-capture-loop.md
- demo/decision_ledger.py
- demo/memory_writer.py
- demo/mcp_server.py
- mac/Icarus/Sources/Icarus/Shell/AgentModeInboxView.swift
- mac/Icarus/Sources/Icarus/Shell/DecisionInboxModel.swift
- demo/test_decision_ledger.py
- demo/test_memory_writer.py
- demo/test_mcp_server.py
- mac/Icarus/Tests/IcarusAppTests/DecisionInboxModelTests.swift

Return exactly this structure:

1. Launch blockers
   - Bullet each blocker.
   - For each: cite file path(s), why it blocks final users, and the smallest safe local fix or verification.
   - If the blocker requires external credentials or account mutation, say so clearly and do not invent a result.

2. Non-blocking risks
   - Bullet each risk.
   - Include why it can wait, or what would make it blocking.

3. Suspected overclaims
   - Quote or paraphrase the risky claim briefly.
   - Cite file path.
   - Explain the safer wording.

4. Missing local tests
   - Name the exact behavior that should be pinned.
   - Suggest the smallest likely test file.
   - Do not write the test.

5. Agent Mode UX alignment
   - Does the current design support multiple choice / Yes-No / Other / Not sure?
   - Does it avoid paragraph-writing burden?
   - Does it prevent unconfirmed memory from entering future sessions?
   - Cite evidence or say unknown.

6. One smallest next step for Codex
   - Pick exactly one next action that is local, testable, and does not need secrets.
   - Explain why it has the highest launch-readiness leverage.
```

Recommended command:

```bash
gemini --model gemini-3.1-pro-preview-customtools --approval-mode plan --prompt "$(cat /tmp/icarus-gemini-review-prompt.txt)"
```

If the CLI has trouble with spaces in the repository path, run the command from inside the repository root and remove the absolute root line from the prompt.
