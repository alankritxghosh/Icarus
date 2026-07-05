# Icarus — Session Handoff (2026-07-05)

Read this first next session. It captures the current state, how to run it, what's
done vs. not, and the gotchas. Pair with `CLAUDE.md`, `AGENTS.md`,
`general_index.md`, the `docs/decisions/` records, and the memory index.

---

## 1. TL;DR — where we are
The **brain is done + proven**, the macOS app is a **full windowed shell**, Icarus
is **shippable without an Apple Developer ID** (cloud brain + downloadable `.dmg`),
and — **new this session** — **private-repo support just merged into `main`**: a
signed-in engineer can connect their **own private GitHub repo** and get cited
answers from a **paid, no-training-verified writer**, with proven **per-user
isolation** and a **deterministic trust interlock** that makes it impossible in
code for private text to reach a free-tier model.

> Recipient downloads `Icarus.dmg` → drags to /Applications → one-time Gatekeeper
> "Open Anyway" → **Sign in with GitHub** (real web OAuth, now against the hosted
> brain, **`repo`-scoped** — widened this session) → **connect a public or (new)
> private repo** → **⌘⇧I** to type or hold **Right Option (⌥)** to speak → a
> **cited answer** (clickable GitHub receipts, spoken aloud) or the honest **"No
> one wrote this down."** Login persists (Keychain); **Sign out** switches accounts.

**Hosted brain:** `https://icarus-brain.onrender.com` (Render free tier, Docker,
GitHub-bearer-gated). **Repo is now on GitHub:** `alankritxghosh/Icarus` (**private**,
`origin`). The full runbook is **`docs/DISTRIBUTION.md`**.

**This session's headline: the 16-task private-repo plan
(`docs/plans/2026-07-04-private-repos-implementation.md`) is fully built, reviewed,
merged to `main`, pushed to `origin`, and deployed live on Render with
`GEMINI_PAID_API_KEY` set — brain-side. Not yet: a Mac-app surface (Brick G), or
anyone actually running the two live proofs for real. See §1a and §7.**

## 1a. This session: private repos, merged (read this if you're picking up next)
Built task-by-task via subagent-driven development (fresh implementer + spec review
+ code-quality review per task, looping on real findings) against
`docs/plans/2026-07-04-private-repos-implementation.md` (16 tasks, Bricks A–F).
All 16 landed, each independently spec- and quality-reviewed (several needed real
fix rounds — most notably two rounds closing a race/downgrade bug in the per-user
registry's LRU eviction, and a docstring caught overclaiming a compliance fact that
wasn't actually true yet). A final **holistic** review of the whole branch (not
per-task) re-verified everything at the composed level and returned a clean
**"ready to merge."** Merged to `main` via fast-forward (`a237ab2` → `95aeda6`,
34 files, +2490/-207) on 2026-07-05.

**What it does, end to end:** a signed-in user (GitHub OAuth, now `repo`-scoped)
connects their own private repo → the brain verifies **with the caller's own
token** that they can actually read it (`evals/github_access.py`) → clones it
leak-safe (`evals/ingest.py`'s `token=`, via subprocess **env**, never argv/URL) →
answers **only** through a paid, billing-confirmed writer
(`evals.provider.PaidGeminiProvider`) → gated by a **deterministic trust
interlock** (`evals/trust.py`'s `assert_safe_for_private`) that refuses any
provider not explicitly flagged `private_safe = True` — never inferred from a key
string. Every user's active repo, corpus, and pipeline are isolated per GitHub
identity (`demo/registry.py`'s `LibraryRegistry`), proven at the real HTTP
boundary and **mutation-tested** (`demo/test_isolation.py` — the reviewer broke
isolation two different ways and confirmed the suite catches both). A companion
suite (`evals/test_egress_invariants.py`) proves private text reaches the writer
and nothing else. `POST /disconnect` deletes a user's own data. `/ask`+`/connect`
are now per-identity rate-limited (`demo/ratelimit.py`).

**The one thing every task was checked against, and the final review re-verified
independently (SHA-256, not just `git diff`): `evals/gate.py` — the deterministic
cite-or-abstain honesty gate — is byte-for-byte unchanged across the entire
effort.** Nothing about this work touched or weakened it.

**Non-negotiable before real private repos flow through this in production:**
set `GEMINI_PAID_API_KEY` (Task 0's billing is confirmed enabled, but the written
no-training policy link is still an open checkbox — see §7) and
`ICARUS_STORAGE_ROOT` on Render, then redeploy. See §7 for the full open list —
nothing was silently dropped; every gap found during review is written down there.

## 2. What works today
- **Brain** (`evals/` + `demo/`): ingest a public repo → BM25 retrieval →
  cite-or-abstain prompt → free hosted writer → **deterministic honesty gate** →
  cited answer or honest unknown. Eval board GREEN on the free stack.
- **Private repos (new this session):** the same brain, gated per user — see §1a.
- **Web demo** (`demo/server.py`): `ThreadingHTTPServer` over the brain. `GET /`,
  `/health`, `/status`, `/auth/github/callback`; `POST /ask`, `/connect`,
  `/auth/github/begin`, `/auth/github/redeem`. Loopback Host/Origin guard, 64 KB
  body cap, optional GitHub bearer gate, loads `.env` on start.
- **macOS app** (`mac/Icarus/`, SwiftPM): the **primary windowed shell** (five
  surfaces) + ⌘⇧I overlay + hold-⌥ voice. **Web GitHub login**, **Keychain-
  persisted** session, **Sign out**, **voice in/out**, packaged as a signed
  `.app`. **30 Swift unit tests pass.**
- **Security**: per-commit secrets gate (`.githooks/pre-commit`,
  block on secret / warn on failing tests) + CI (`.github/workflows/security.yml`).
- **Cloud deployment (new this session):** `Dockerfile` + `render.yaml` +
  `.dockerignore` deploy the brain to Render. `demo/server.py` now binds from
  `$HOST`/`$PORT`, has a configurable Host guard (`ICARUS_ALLOWED_HOSTS`; `*` =
  cloud, trust TLS proxy + rely on the bearer gate), and builds the OAuth callback
  from `ICARUS_PUBLIC_URL`. Auth is **mandatory** in the cloud
  (`ICARUS_REQUIRE_GITHUB_AUTH=1`). Live at `icarus-brain.onrender.com`.
- **Distribution (new this session):** `mac/Icarus/scripts/package_dmg.sh` builds
  a shareable `Icarus.dmg` — ad-hoc signed, stamps the hosted brain URL into the
  bundle, drag-to-Applications + a `READ ME FIRST.txt`. The app resolves its brain
  from the bundle's `ICARUS_BRAIN_URL` (`IcarusKit/BrainEndpoint.swift` +
  `Icarus/AppConfig.swift`); dev builds fall back to `127.0.0.1:8000`.
- **Static app icon (new this session):** the app previously only set its Dock icon
  at runtime, so Finder/DMG/Dock showed a blank tile until launch. `IconExport.swift`
  now renders the same `IconArt` art headlessly (`Icarus --render-iconset`),
  `bundle.sh` bakes it into `Resources/AppIcon.icns`, and the Info.plist declares
  `CFBundleIconFile` — so the icon shows everywhere, before first launch.
- **End-to-end proven:** the hosted sign-in → cited-answer flow **works live** (the
  final blocker was a `GITHUB_CLIENT_SECRET` mismatch on Render, since fixed). The
  repo is on GitHub (`alankritxghosh/Icarus`, private); **`main` is currently
  27 commits ahead of `origin/main` and not yet pushed** — see §12.

## 3. The macOS app — architecture & files
**Shape (current):** the **shell is the primary window** — no separate onboarding
window. Its **Home** surface is a **setup gate**: signed-out → "Sign in with
GitHub"; signed-in-but-not-connected → "connect a repo"; ready → the dashboard.
The **menu-bar `☉` glyph** opens the shell and the **⌘⇧I overlay** is for asking.
GitHub is the login; there is no Icarus account backend. The app is a **thin
client** — it renders the brain's verdict verbatim and never re-implements the
honesty gate.

**Build system:** **Swift Package Manager**, two targets:
- `IcarusKit` (testable, UI-free): `Models.swift` (Ask/Citation/Verdict/RepoStatus/
  `IndexCounts`), `BrainClient.swift` (`/ask`,`/connect`,`/status`,`/auth/github/
  begin`,`/auth/github/redeem`; injectable URLSession; sends the bearer),
  `WebAuth.swift` (`WebAuthenticating` protocol + `parseCallbackSession`),
  `TokenStore.swift` (protocol + in-memory double), `SpeechRecognizer.swift`,
  `VoiceModel.swift`, `AskHistory.swift` (real in-session ask record), `ShellNav.swift`
  (the five `ShellSurface`s).
- `Icarus` (the app): `IcarusApp.swift` (@main), `AppDelegate.swift` (activation
  policy, menu bar, hotkey, push-to-talk, shared models, **primary shell window**),
  `AppleWebAuth.swift` (**real `ASWebAuthenticationSession`** sheet),
  `KeychainTokenStore.swift` (**the real, persistent `TokenStore`**),
  `AuthModel.swift`/`AskModel.swift`/`ConnectModel.swift`, `OverlayController.swift`
  + `FloatingPanel.swift` + `OverlayView.swift` (the ⌘⇧I overlay), `IconArt.swift`,
  `Theme.swift` (v2 tokens + shared views), `AppleSpeechRecognizer.swift`,
  `PushToTalkMonitor.swift`, `Speaker.swift`, and **`Shell/`**: `ShellView.swift`
  (router), `SidebarView.swift` (nav + repo footer + **Sign out**), `HomeView.swift`
  (gate → dashboard), `SetupView.swift` (in-shell sign-in/connect), `ShellSurfaces.swift`
  (Decision history / Unknowns / Privacy boundary / Ask-by-voice), `ShellComponents.swift`,
  `StatusModel.swift` (polls `/status`), `MainWindowController.swift` (chromeless
  title bar).
- Dependency: **KeyboardShortcuts** only (⌘⇧I). Voice-in is Apple's built-in
  **Speech** framework (on-device). Packaging: `scripts/bundle.sh` → signed
  `Icarus.app` (mic TCC needs the bundle + Info.plist usage strings + a signature).

**GitHub login (web OAuth — replaced device flow):**
1. App `POST /auth/github/begin` → brain returns the GitHub authorize URL (CSRF
   `state` minted server-side).
2. `ASWebAuthenticationSession` opens GitHub's login in a sheet
   (`callbackURLScheme: "icarus"`, **ephemeral** so Sign out → pick another account).
3. GitHub redirects to the brain's callback — **the hosted URL for a shipped build**
   (`https://icarus-brain.onrender.com/auth/github/callback`, from `ICARUS_PUBLIC_URL`)
   or the loopback callback in local dev. The brain **exchanges the code using the
   client SECRET** (held only in its env) and **302s to `icarus://auth?session=…`**
   so the sheet closes. The GitHub OAuth app's callback URL must match this exactly.
4. App `POST /auth/github/redeem {session}` → the token; it's stored in the
   **login Keychain** (`KeychainTokenStore`, `WhenUnlocked`) so **sign-in persists
   across launches**, and sent as `Authorization: Bearer` on `/ask`+`/connect`.
   **Sign out** (sidebar) deletes it. The client secret is **never in the app**.

**Voice:** voice-in is real-time on-device Apple Speech (`requiresOnDeviceRecognition
= true`; fails rather than using Apple's servers), hold **Right Option (⌥)**. Speak-
back is `AVSpeechSynthesizer` in `Speaker.swift`, which now picks the **best-quality
installed English voice** (premium > enhanced > default, preferring en-US) and never
a novelty voice. For a natural sound, download a **Premium** voice: System Settings →
Accessibility → Spoken Content → System Voice → **Manage Voices** → an English
"(Premium)" voice — the app then uses it automatically (relaunch to pick it up). No
premium voice installed = falls back to the standard en-US voice.

## 4. Constraints & decisions (the operating rules)
- **Public repos: free hosted models** (Groq writer + Gemini judge), same as
  before. **Private repos (new): only the paid, billing-confirmed
  `PaidGeminiProvider`** — the free/paid split is enforced in code by the
  deterministic trust interlock (`evals/trust.py`), not by convention.
- **Positioning:** Icarus is **organizational memory**; explanation is the wedge.
- The non-negotiable: **cite-or-unknown, deterministic, never bluff** — preserved.
- **GitHub login needs a client secret** (GitHub requires it even with PKCE), so
  the exchange runs on the **brain**, never the app. Loopback callback per GitHub's
  native-app guidance.

## 5. How to run it (exact)
Keys + the GitHub OAuth app live in a **gitignored `.env`** at the repo root (copy
`.env.example`). It holds `GROQ_API_KEY`, `GEMINI_API_KEY`, `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET`. The GitHub OAuth App's **Authorization callback URL** must
be `http://127.0.0.1:8000/auth/github/callback`.

**Start the brain** (reads `.env`, no inline keys needed):
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"
python3 -m demo.server          # prints "web login on" when GitHub creds are set
```
**Build + launch the app** (the bundle is required for the mic; `open` is fine now
— the app no longer needs `ICARUS_GH_CLIENT_ID`, the brain builds the authorize URL):
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering/mac/Icarus"
./scripts/bundle.sh && open ./Icarus.app
```
In the app: **Sign in with GitHub** → authorize in the sheet → connect
**`simonw/llm`** → **⌘⇧I** → ask. Known cited question: *"Why did llm implement the
OpenAI Responses API as a new model class instead of modifying the existing chat
completions class?"* → cites `pr:1435`.

**To run it HOSTED / build the shareable DMG** see **`docs/DISTRIBUTION.md`**:
deploy to Render, set env vars, point the GitHub
OAuth callback at the Render URL, then
`ICARUS_BRAIN_URL=https://icarus-brain.onrender.com ./scripts/package_dmg.sh` →
`mac/Icarus/Icarus.dmg`. Local dev still uses the loopback `.env` + `bundle.sh`.

**To connect a private repo** (once `GEMINI_PAID_API_KEY` is set — see §6): sign in
(or sign out/in again if your token predates the `repo`-scope widening, §10),
`POST /connect` with your own repo — the brain verifies you can read it, clones it
with your token (never logged, never on disk after the process exits), and routes
you to the paid writer. `POST /disconnect` deletes your data. `GET /status` shows
`private: true/false`.

Tests: `cd mac/Icarus && swift test` (**35**). Brain:
`python3 -m unittest discover -t . -s evals` (**118, 12 self-skip**) and
`... -s demo` (**117, 2 self-skip**) — up from 85+70 before this session's
16-task private-repo effort. Live proofs (skip without keys):
`GEMINI_PAID_API_KEY=… python3 -m unittest evals.test_paid_writer_eval` (paid
writer holds both honesty gates at 100% on the public board) and
`RUN_PRIVATE_INGEST=1 ICARUS_TEST_PRIVATE_REPO=owner/repo GITHUB_TOKEN=…
GEMINI_PAID_API_KEY=… python3 -m unittest evals.test_private_ingest_live`
(real private clone + real paid answer + real interlock refusal — **nobody has
run this for real yet**, only proven to construct correctly and self-skip).

## 6. Secrets & credentials
- **Where they live now:** for the hosted brain, secrets are set in the **Render
  dashboard** as env vars (`render.yaml` marks them `sync:false`, never committed):
  `GROQ_API_KEY`, `GEMINI_API_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`,
  `GH_TOKEN`, `ICARUS_PUBLIC_URL`, and **new this session: `GEMINI_PAID_API_KEY`**
  (the private-repo writer — billing-enabled, per the project owner; placing a
  value here is the attestation it's billed, since code can't tell a free key
  string from a paid one) — **now set on Render, redeployed, confirmed live**
  (`GET /status` returns the new `"private"` field). `ICARUS_STORAGE_ROOT` is
  NOT a dashboard secret — it's a plain committed value (`/app/data`) directly in
  `render.yaml`, applied automatically on every deploy; nothing to set for it.
  Local dev still reads a gitignored `.env`.
- **GitHub client secret: rotated this session** (the rotation-mismatch was what
  broke sign-in — see §10). The Render value now matches the OAuth app whose
  **Client ID is `Ov23liVZXvv6V5vX2x1Y`** (Client ID is public; the secret is not).
- **Still verify:** if the **Groq/Gemini keys** exposed in an earlier transcript
  were not yet rotated, do so and update Render. `.env` is gitignored + the
  pre-commit hook blocks staged secrets, so nothing secret is in git.

## 7. What is NOT done (next work)

> **Private-repo support (brain side) — DONE and MERGED to `main` this session**
> (16-task plan, `docs/plans/2026-07-04-private-repos-implementation.md`;
> fast-forward merge `a237ab2` → `95aeda6`). Per-GitHub-identity `LibraryRegistry`
> isolation, a deterministic trust interlock (`evals/trust.py`) that refuses any
> non-`private_safe` provider, caller-scoped access checks + leak-safe
> token-authed ingest, a paid no-training writer (`PaidGeminiProvider`,
> `GEMINI_PAID_API_KEY`), per-identity rate limiting, and two mutation-tested
> proof suites (`demo/test_isolation.py`, `evals/test_egress_invariants.py`).
> **`main` is pushed to `origin` and Render is redeployed with `GEMINI_PAID_API_KEY`
> set** (`ICARUS_STORAGE_ROOT` was already committed with a value in `render.yaml`,
> so no dashboard entry was needed for it — confirmed live: `GET /status` on
> `https://icarus-brain.onrender.com` now returns the new `"private"` field).**
>
> **Still open, in priority order:**
> 1. ~~Push `main` to `origin`~~ **Done.**
> 2. ~~Set `GEMINI_PAID_API_KEY` on Render and redeploy~~ **Done — confirmed live.**
> 3. **Actually run the two live proofs with real credentials** (§5) —
>    `evals.test_paid_writer_eval` and `evals.test_private_ingest_live` are
>    built and self-skip cleanly, but **nobody has run either for real yet**.
>    Do this before telling anyone private repos are proven end-to-end, not just
>    "correctly constructed."
> 4. **Record the written no-training policy link** for the paid Gemini key —
>    billing is confirmed enabled, but the actual policy-link verification is
>    still an open checkbox in
>    `docs/plans/2026-07-04-private-repos-per-user-isolation.md`. Close this
>    before onboarding real private code from other people (not just your own).
> 5. **App-side private-repo UI (Brick G) is NOT built yet:** the app has no
>    "connect a private repo" affordance, no "disconnect / delete my data"
>    control, and no public-vs-private / which-writer indicator. Scoped as its
>    own brick in the implementation plan's Brick G outline.
> 6. **Private-connection-loss signal is a genuine, still-open product gap:**
>    if the `LibraryRegistry`'s LRU eviction can't safely resume a user's private
>    repo (it never holds the caller's token, so it can't re-ingest — see
>    `demo/registry.py`'s eviction/resume logic), it honestly falls back to "not
>    connected" rather than silently serving public-tier answers under the wrong
>    pretense. But the user currently sees **no explicit signal** that this
>    happened: `GET /status` just shows a normal-looking "ready" state pointing
>    at the public default repo. The Mac app's `RepoStatus` model
>    (`mac/Icarus/Sources/IcarusKit/Models.swift`) doesn't even have a `private`
>    field yet to detect this. Fold into Brick G scoping (item 5).
> 7. **Two small, non-blocking test gaps** flagged by the final whole-branch
>    review (both "safe by construction today," not live bugs, just untested
>    interactions): (a) no test exercises the trust interlock raising *inside*
>    `Library.connect_sync` specifically (only in isolation) — add one asserting
>    a refusal there leaves `_private`/`_pipeline` untouched; (b) the rate
>    limiter doesn't cover the LRU eviction-resume path (harmless today since
>    resume is always a cache-hit, no subprocess cost — but worth a pinning test
>    so a future change to `_default_build_private_pipeline` can't silently add
>    unthrottled cost there).

1. **Notarization / Developer-ID signing.** The app is ad-hoc signed. This is the
   biggest gap: it (a) makes the Keychain "sign in once" seamless (no repeated
   prompts) and (b) lets the app open on someone else's Mac. Enrollment has lead
   time — start it before any investor touches the binary.
2. **Rotate any remaining exposed keys** (see §6) — the GitHub client secret is
   done; confirm Groq/Gemini.
3. **Harden the hosted brain if it goes beyond a controlled demo:** `/ask` and
   `/connect` now have per-identity rate limits (`demo/ratelimit.py`, Task 15),
   but auth is still the only ban/throttle lever otherwise — don't post the URL
   publicly. The free instance sleeps; repo-switching ingests arbitrary public
   repos on the server (prompt-injection surface, disclosed). The OAuth CSRF
   state is in-memory (see §10).
4. **Bundle real fonts** (Geist + JetBrains Mono) — UI uses SF stand-ins.
5. **Persist the connected repo** across launches (login persists; the repo does
   not — you reconnect each launch). Also survives a Render restart poorly (in-memory).
6. **Record the demo** (A6; script in `docs/plans/2026-06-28-brick-6-recordable-demo.md`).
7. **Multi-repo, non-GitHub sources, stale-decision detection** — post-v1 roadmap,
   gated/deferred.

**DONE this session:** cloud deployment (Render), shareable DMG, the git remote
(`alankritxghosh/Icarus`, private), a baked static app icon, and a live end-to-end
sign-in → cited-answer flow — the app is now downloadable and works for real users.

## 8. Security posture (this session)
- Brain: loopback Host/Origin guard, 64 KB body cap, optional GitHub bearer gate
  on `/ask`+`/connect`, ingest subprocess timeouts + size caps + path-traversal
  guard, generic (non-leaking) ingest errors, Gemini key in a header not the URL.
- Prompt-injection via ingested content is **disclosed** (see `docs/EVALUATION.md`);
  the gate proves provenance, not faithfulness — connect only vetted repos on stage.
- Per-commit: `.githooks/pre-commit` (secret hard-blocks; failing tests warn),
  installed via `scripts/install_hooks.sh` (`core.hooksPath` → `.githooks`).
- CI backstop: `.github/workflows/security.yml` (scan + Python suites + Swift).
- The fix plan is `docs/plans/2026-07-02-security-hardening.md`.

## 9. Plans & decisions (docs/)
- `docs/plans/2026-07-02-full-app-shell.md` — the windowed shell (Home gate + five
  surfaces, all real data).
- `docs/plans/2026-07-02-security-hardening.md` — the security-audit fixes.
- `docs/plans/2026-07-03-web-github-login.md` — the web login (brain exchange +
  ASWebAuthenticationSession).
- `docs/plans/2026-06-30-macos-app.md`, `docs/plans/2026-06-30-github-auth-workflow.md`
  — earlier app/auth plans (device flow now superseded by web login).
- `docs/decisions/` — hosting model + org-memory positioning. `docs/DESIGN_VISION.md`
  / `docs/UI_UX_BRIEF.md` — design intent (Figma file `SbmCti2rnsog2rwrzzCWm0`,
  frame `5:2` "Quiet Native Memory v2").

## 10. Gotchas (learned this session)
- **Ad-hoc signing re-prompts the Keychain on every rebuild.** Each `swift build`
  changes the signature, so the first launch after a rebuild that reads an existing
  token shows a "Icarus wants to use your keychain" prompt — click **Always Allow**.
  A properly **notarized** build prompts once ever, then never. (A fresh/empty
  Keychain doesn't prompt; `security delete-generic-password -s ai.icarus.github`
  clears a stale token for a clean slate.)
- **`ASWebAuthenticationSession`'s completion handler fires on a background thread.**
  It must be `@Sendable`/non-isolated (not `@MainActor`) or the app **traps
  (EXC_BREAKPOINT)** on sign-in. Only hop to `@MainActor` to `start()` the session.
- **`open Icarus.app` launches the registered bundle, not `.build/debug/Icarus`.**
  Rebuild the bundle (`scripts/bundle.sh`) after code changes, or `open` runs stale
  code. A stale `Icarus.app` bundle bit us during verification.
- **The GitHub auth sheet / SecurityAgent / Keychain prompts are separate system
  processes** — invisible to computer-use screenshots (compositor filters non-
  allowlisted apps). Their absence in a screenshot ≠ they didn't appear.
- **Restart the brain to pick up `.env` changes** (it loads `.env` once at start).
  Restarting also resets the brain's active repo to the default; reconnect in the app.
- **`/status` returns `counts` as an object** (`{pr,issue,code}`) — decoded into
  `IndexCounts` for the metrics card.
- **`swift test`** must be run, not `unittest discover` for Python without `-t .`
  (relative imports need the repo root as top-level).

**Cloud / distribution gotchas (new this session):**
- **`incorrect_client_credentials` on sign-in = the Render `GITHUB_CLIENT_SECRET`
  doesn't match the OAuth app** whose Client ID the brain sends (`Ov23liVZXvv6V5vX2x1Y`).
  Classic rotate-one-side-not-the-other. The brain now logs the real reason to
  stderr — look in **Render → Logs** for `github callback failed: <reason>`
  (`server.py` `_github_callback`). `/auth/github/begin` succeeds even with a wrong
  secret (only needs it non-empty), so a working authorize URL doesn't prove the secret.
- **OAuth CSRF `state`/sessions are in-memory.** Any Render redeploy (every env-var
  save triggers one) or the free-tier ~15-min idle sleep **wipes them mid-sign-in**
  → "expired." Don't change Render settings while signing in; retry once warm.
- **Pushing `.github/workflows/*` needs the `workflow` token scope.** `gh`'s default
  OAuth token lacks it; `gh auth refresh -h github.com -s workflow` fixes it.
- **Ad-hoc Keychain prompt is a one-time "Always Allow," not a bug.** Run Icarus
  from **/Applications** (not the DMG/Downloads — App Translocation randomizes the
  path each launch so "Always Allow" can't stick) and clear quarantine
  (`xattr -dr com.apple.quarantine /Applications/Icarus.app`). Every rebuild changes
  the cdhash → one re-prompt. Only notarization removes it entirely.
- **The GitHub OAuth scope widened `read:user` → `repo`** (private-repo support,
  `demo/github_oauth.py`) so a signed-in user's own token can read their private
  repos. Anyone who signed in **before** this change is holding a stale
  `read:user`-scoped token — private-repo connect fails for them until they
  **sign out and sign back in** to pick up the new scope. There is **no
  server-side token migration**; this is a real, one-time, user-visible step
  (also called out in `docs/DISTRIBUTION.md`).
- **Render injects `$PORT`** (observed `10000`) and expects `0.0.0.0`; the Dockerfile
  sets `HOST=0.0.0.0` and `serve()` reads `$PORT`. `ICARUS_ALLOWED_HOSTS=*` opens the
  Host guard so the Render hostname + health check pass.
- **A code-only Dock icon shows a blank tile until launch.** `applicationIconImage`
  set at runtime doesn't help Finder/DMG/pre-launch Dock — the bundle needs a static
  `AppIcon.icns` + `CFBundleIconFile`. `bundle.sh` now bakes it from `IconArt` via the
  `--render-iconset` path (`IconExport.swift`), so don't re-introduce a runtime-only icon.

## 11. Key files
- Brain: `evals/*.py`, `demo/*.py` (incl. `demo/github_oauth.py`, `demo/auth.py`).
  **New this session (private repos):** `demo/registry.py` (per-user isolation),
  `demo/ratelimit.py`, `evals/trust.py`, `evals/github_access.py`, plus
  `evals/provider.py`'s `PaidGeminiProvider` and `evals/ingest.py`'s leak-safe
  `token=` support. Proof suites: `demo/test_isolation.py`,
  `evals/test_egress_invariants.py`. Full map: `general_index.md`/
  `detailed_index.md` (both regenerated this session).
- App: `mac/Icarus/` (SwiftPM) — see §3. **Not yet touched by the private-repo
  work** — Brick G (§7) is next.
- Security: `.githooks/`, `.github/workflows/security.yml`, `scripts/`.
- Docs: `docs/plans/`, `docs/decisions/`, `docs/EVALUATION.md`. Private-repo plans:
  `docs/plans/2026-07-04-private-repos-per-user-isolation.md` (scoping) +
  `docs/plans/2026-07-04-private-repos-implementation.md` (the executable
  16-task plan, all done).

## 12. Git state
**`main` == `origin/main`, both at `899be8f`** (this HANDOFF's own commit) —
pushed this session. This session merged `feat/private-repos` into `main` via
fast-forward (`a237ab2` → `95aeda6`, no merge commit, clean history), pushed it,
and confirmed the Render deploy picked it up live (§6/§7).

Latest commits (newest first): `899be8f` this HANDOFF refresh, `95aeda6` HANDOFF's
Task-0 gap + a Render storage-path fix, `dbe7b38` private-repo env/deploy/docs +
regenerated indexes, `e4d2bcb` per-identity rate limits, `0a0b03f`/`454e5cd`
egress-invariants proof suite, `1ebfd45` cross-user isolation proof suite,
`f9f70d3`/`aff26cb` the live private-repo proof (self-skipping), `7391277`/`0fce604`
the private connect path + an eviction-resume race/downgrade fix, working back
through all 16 tasks to `a237ab2` (the plan docs, and the branch point off the
previous session's HEAD).

The `feat/private-repos` branch still exists locally (only its worktree at
`.claude/worktrees/private-repos` was removed, since it's now fully merged) —
safe to `git branch -d feat/private-repos` whenever convenient, or leave it as a
historical marker. `.env` and `.codex/` are untracked (leave them);
`Icarus.app`/`Icarus.dmg` are gitignored build artifacts.
The old `mac-app` branch still exists locally (same history line, unrelated to
this session).
