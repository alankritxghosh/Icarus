# GitHub Auth + Full Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: `superpowers:executing-plans` (or subagent-driven once
> the rate limit resets). Red→green where logic is testable; manual/visual checks for UI and
> live OAuth. The honesty gate stays in the Python brain, untouched. Commit trailer per
> [CLAUDE.md](../../CLAUDE.md). Branch: `mac-app`.

**Goal:** Launch the app → **Sign in with GitHub** (real OAuth Device Flow, token in Keychain)
→ pick/enter a **public** `owner/repo` → the brain ingests it → ask a question → cited answer
or honest unknown. The full typed workflow, gated behind real auth.

**App shape (decided 2026-06-30):** a **hybrid** — a real **onboarding window** (Dock-visible
app) is the first screen: *Welcome → Sign in with GitHub → connect a repo → done*; the
**menu-bar + ⌘⇧I overlay** stays for actually asking. **GitHub is the login** — no separate
Icarus account/backend. This is a small, deliberate extension of the overlay-first vision
(onboarding/settings get a window; Q&A stays an overlay), the standard pattern for this app
category (Wispr/Raycast). Auth UI therefore lives in the window (revised G3), not the overlay.

**Architecture:** Auth is **app-side** (device flow + Keychain). Repo ingest **reuses the
brain's existing endpoints** — `POST /connect` (start indexing a repo) and `GET /status`
(poll until ready), already built in `demo/server.py`. So the brain needs **no change** for
public repos; the app orchestrates auth → connect → status → ask. The GitHub token is used
for identity + listing the user's repos + API rate limits; public repos clone anonymously, so
the token does not gate ingest yet (it will when private repos are un-shelved).

**Tech Stack:** Swift (URLSession async for GitHub's device-flow + API endpoints), Security
framework (Keychain), `IcarusKit` for testable auth logic, XCTest. No new SwiftPM dependency.

> ⚠️ **Scope guard (hard constraint):** PUBLIC repos only. Private repos stay blocked until the
> paid/private-model decision — free models may train on inputs. The auth plumbing is built so
> private is a later additive step (add the `repo` scope + a zero-retention model), not a
> rewrite. See [docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md](../decisions/2026-06-30-unified-cloud-per-tenant-isolation.md).

## The one non-negotiable, restated
The app still renders the brain's verdict verbatim. Auth changes *who's signed in and which
repo is loaded* — it never touches the cite-or-unknown gate.

## Credential handling (a credential is a responsibility)
- The GitHub access token is stored ONLY in the macOS **Keychain**, never in a file, never
  logged, never committed.
- Device flow uses a **client ID only** (no client secret — it's a public client). The client
  ID is not a secret but is per-install: read from env `ICARUS_GH_CLIENT_ID` (or a gitignored
  config), never hardcoded to a committed value.
- Request the **minimum scope**: `read:user` (identity + list public repos). Do NOT request
  `repo` (that's private-repo write/read — out of scope and constraint-breaking now).

---

## Status legend
`[x]` done · `[ ]` todo · `[~]` blocked on a prerequisite

## Where we are
- A1–A3 done: menu-bar agent, hotkey + overlay, and the wire to the brain (`/ask`). Committed
  on `mac-app` (`d388335`, `ad0c9b8`, `fed52fd`, `56fc137`).
- Brain already exposes `POST /connect {repo}`, `GET /status`, `POST /ask`, `GET /health`.

---

## Prerequisite G0 — Register a GitHub OAuth App (USER ACTION, blocks live auth)

**Why:** device flow needs a Client ID from an OAuth App with device flow enabled. Only you
(the account/org owner) can create it.

**Steps (Alankrit):**
1. GitHub → Settings → Developer settings → **OAuth Apps** → **New OAuth App**.
2. Name: `Icarus (dev)`. Homepage URL: anything (e.g. `https://example.com`). Authorization
   callback URL: `http://localhost` (device flow doesn't use it, but the field is required).
3. Create, then on the app's page **check "Enable Device Flow"** and Save.
4. Copy the **Client ID** (looks like `Ov23li...`). There is **no secret** needed for device flow.
5. Give me the Client ID, or set it yourself: `export ICARUS_GH_CLIENT_ID=Ov23li…` before
   launching the app.

**Gate:** G3's live sign-in can't run without this. G1/G2 (logic + tests) can be built first.

---

# BRICK G1 — Device-flow auth logic in IcarusKit (TDD)

**Outcome:** a `GitHubDeviceAuth` in `IcarusKit` that (a) requests a device code, (b) parses
the user code + verification URI, (c) polls for the access token, handling
`authorization_pending` / `slow_down` / `expired_token` / `access_denied`. Pure logic +
response parsing is unit-tested with canned JSON; the live HTTP calls are thin.

**Files:** Create `mac/Icarus/Sources/IcarusKit/GitHubAuth.swift`; tests in
`mac/Icarus/Tests/IcarusKitTests/GitHubAuthTests.swift`.

**TDD steps:**
1. Write failing tests: decode a device-code response (`device_code`, `user_code`,
   `verification_uri`, `interval`, `expires_in`); and a poll-result parser mapping GitHub's
   responses to a `PollOutcome` enum (`.pending`, `.slowDown`, `.token(String)`, `.denied`,
   `.expired`). Run → red.
2. Implement the `Codable` structs + a pure `parsePoll(json:) -> PollOutcome` function. Run → green.
3. Add the async methods (`requestDeviceCode`, `pollForToken`) over `URLSession` to
   `https://github.com/login/device/code` and `…/login/oauth/access_token` (Header
   `Accept: application/json`). These wrap the tested pure parsers.

**Verify:** `swift test` green; `swift build` clean.

---

# BRICK G2 — Token storage in the Keychain

**Outcome:** a `TokenStore` protocol (`save/load/delete`) with a real `KeychainTokenStore`
(Security framework, generic password item, service `ai.icarus.github`) and an in-memory
double for tests.

**Files:** `mac/Icarus/Sources/IcarusKit/TokenStore.swift` (protocol + in-memory double);
`mac/Icarus/Sources/Icarus/KeychainTokenStore.swift` (real impl); tests for the in-memory double.

**Notes:** Keychain itself isn't unit-tested headlessly (needs a keychain/entitlement) — test
the protocol contract via the in-memory double; the Keychain impl is verified in G5. Never log
the token.

**Verify:** `swift test` green; `swift build` clean.

---

# BRICK G3 — "Connect GitHub" UI + sign-in/out

**Outcome:** an `AuthController`/`AuthModel` (@MainActor @Observable) driving the device-flow
UX: a "Connect GitHub" affordance → show the `user_code`, open `verification_uri` in the
browser, poll, land in a **signed-in** state (show the GitHub login). Sign-out clears the
Keychain token. On launch, if a token exists, start signed-in.

**Files:** `mac/Icarus/Sources/Icarus/AuthModel.swift`; UI in `OverlayView.swift` (or a small
`ConnectView.swift`); wire into `OverlayController`.

**Verify (live, needs G0 Client ID):** click Connect → code shown → approve on github.com →
app shows signed-in. Token persists across relaunch. Manual/visual.

---

# BRICK G4 — Pick/enter a repo, ingest, gate asking

**Outcome:** when signed in, the user enters (or picks from a list of their public repos via
`GET /user/repos` with the token) an `owner/repo`; the app calls the brain `POST /connect`,
polls `GET /status` until `ready`, shows progress, then enables the ask box. Asking is disabled
until a repo is connected.

**Files:** extend `BrainClient` (in IcarusKit) with `connect(repo:)` and `status()` mirroring
`demo/server.py`; a `GitHubAPI.listRepos(token:)`; UI for repo entry/selection + status; wire
in `OverlayController`/`AskModel`.

**Verify:** with the brain running, connect a small public repo (e.g. `simonw/json-flatten`),
watch status reach ready. Unit-test the `/status` + repos decode; live-check the flow.

---

# BRICK G5 — Full workflow end-to-end

**Outcome:** launch → Sign in with GitHub → connect a public repo → ingest → ask → cited
answer / honest unknown, all in the app.

**Verify:** run the real brain (`python3 -m demo.server` with ROTATED keys) — or the keyless
stub for the wire — and walk the whole path on camera-worthy repos. This is the
"entire app workflow" milestone.

---

## Risks & honest notes
- **Live auth blocked on G0** (your OAuth App + Client ID). G1/G2 build without it.
- **Real-LLM answers need provider keys** (rotate the exposed ones first). The keyless stub
  proves the wire; the brain proves the answers.
- **Private repos remain blocked** on the paid/private-model decision — do not add `repo` scope.
- **Token = credential:** Keychain only, never logged/committed; minimum scope.
- Device-flow polling must honor `interval` and `slow_down` or GitHub rate-limits the poll.

## Out of scope
- Private repos / `repo` scope (constraint-gated).
- GitHub App (vs OAuth App) installation flow, org-level fine-grained perms.
- Voice (A4/A5) — resumes after this workflow.
- Signing/notarization/distribution.
