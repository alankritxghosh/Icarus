# Icarus — Session Handoff (2026-07-04)

Read this first next session. It captures the current state, how to run it, what's
done vs. not, and the gotchas. Pair with `CLAUDE.md`, `AGENTS.md`,
`general_index.md`, the `docs/decisions/` records, and the memory index.

---

## 1. TL;DR — where we are
The **brain is done + proven**, the macOS app is a **full windowed shell**, and —
new this session — **Icarus is now shippable to other people without an Apple
Developer ID**: the brain runs in the **cloud (Render)** and the app ships as a
**downloadable `.dmg`**. The end-to-end sign-in → cited-answer flow **works live**.

> Recipient downloads `Icarus.dmg` → drags to /Applications → one-time Gatekeeper
> "Open Anyway" → **Sign in with GitHub** (real web OAuth, now against the hosted
> brain) → **connect a public repo** → **⌘⇧I** to type or hold **Right Option (⌥)**
> to speak → a **cited answer** (clickable GitHub receipts, spoken aloud) or the
> honest **"No one wrote this down."** Login persists (Keychain); **Sign out** switches accounts.

**Hosted brain:** `https://icarus-brain.onrender.com` (Render free tier, Docker,
GitHub-bearer-gated). **Repo is now on GitHub:** `alankritxghosh/Icarus` (**private**,
`origin`), `main` pushed. The full runbook is **`docs/DISTRIBUTION.md`**.

## 2. What works today
- **Brain** (`evals/` + `demo/`): ingest a public repo → BM25 retrieval →
  cite-or-abstain prompt → free hosted writer → **deterministic honesty gate** →
  cited answer or honest unknown. Eval board GREEN on the free stack.
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
  repo is on GitHub (`alankritxghosh/Icarus`, private); `main` is pushed.

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
- **Public repos only, free hosted models** (Groq writer + Gemini judge). Private
  repos blocked on the paid/private-model decision.
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

**To run it HOSTED / build the shareable DMG** (the whole point of this session)
see **`docs/DISTRIBUTION.md`**: deploy to Render, set env vars, point the GitHub
OAuth callback at the Render URL, then
`ICARUS_BRAIN_URL=https://icarus-brain.onrender.com ./scripts/package_dmg.sh` →
`mac/Icarus/Icarus.dmg`. Local dev still uses the loopback `.env` + `bundle.sh`.

Tests: `cd mac/Icarus && swift test` (**35**). Brain:
`python3 -m unittest discover -t . -s evals` and `... -s demo` (**85 + 70**).

## 6. Secrets & credentials
- **Where they live now:** for the hosted brain, secrets are set in the **Render
  dashboard** as env vars (`render.yaml` marks them `sync:false`, never committed):
  `GROQ_API_KEY`, `GEMINI_API_KEY`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`,
  `GH_TOKEN`, `ICARUS_PUBLIC_URL`. Local dev still reads a gitignored `.env`.
- **GitHub client secret: rotated this session** (the rotation-mismatch was what
  broke sign-in — see §10). The Render value now matches the OAuth app whose
  **Client ID is `Ov23liVZXvv6V5vX2x1Y`** (Client ID is public; the secret is not).
- **Still verify:** if the **Groq/Gemini keys** exposed in an earlier transcript
  were not yet rotated, do so and update Render. `.env` is gitignored + the
  pre-commit hook blocks staged secrets, so nothing secret is in git.

## 7. What is NOT done (next work)

> **TOP PRIORITY — Private-repo support (for the PMF beta).** The goal: let
> engineers connect their **own private repos** and get cited answers, so we can
> test product-market fit. Decisions already made: keep it **hosted/cloud**
> (centrally operated, not local per-engineer), with **per-user isolation** (the
> current shared instance holds only one active repo and pools code — unsafe for
> private repos), and a **paid, no-training LLM writer** (billing-enabled Gemini —
> the free tier may train on inputs; verify the paid-tier terms before onboarding
> real code). The only external egress of private code is the writer prompt
> (retrieval is local BM25, no judge in the serve path). Not started — a detailed
> approach was scoped but deliberately deferred. Prereqs the owner must do: enable
> a **paid Gemini API key** and **upgrade Render off the free tier**.

1. **Notarization / Developer-ID signing.** The app is ad-hoc signed. This is the
   biggest gap: it (a) makes the Keychain "sign in once" seamless (no repeated
   prompts) and (b) lets the app open on someone else's Mac. Enrollment has lead
   time — start it before any investor touches the binary.
2. **Rotate any remaining exposed keys** (see §6) — the GitHub client secret is
   done; confirm Groq/Gemini.
3. **Harden the hosted brain if it goes beyond a controlled demo:** no rate-limiting
   today (auth is the only lever — don't post the URL publicly); the free instance
   sleeps; repo-switching ingests arbitrary public repos on the server (prompt-
   injection surface, disclosed). The OAuth CSRF state is in-memory (see §10).
4. **Bundle real fonts** (Geist + JetBrains Mono) — UI uses SF stand-ins.
5. **Persist the connected repo** across launches (login persists; the repo does
   not — you reconnect each launch). Also survives a Render restart poorly (in-memory).
6. **Record the demo** (A6; script in `docs/plans/2026-06-28-brick-6-recordable-demo.md`).
7. **Multi-repo, non-GitHub sources, stale-decision detection** — post-v1 roadmap,
   gated/deferred. (Private repos moved up to TOP PRIORITY above.)

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
- **Render injects `$PORT`** (observed `10000`) and expects `0.0.0.0`; the Dockerfile
  sets `HOST=0.0.0.0` and `serve()` reads `$PORT`. `ICARUS_ALLOWED_HOSTS=*` opens the
  Host guard so the Render hostname + health check pass.
- **A code-only Dock icon shows a blank tile until launch.** `applicationIconImage`
  set at runtime doesn't help Finder/DMG/pre-launch Dock — the bundle needs a static
  `AppIcon.icns` + `CFBundleIconFile`. `bundle.sh` now bakes it from `IconArt` via the
  `--render-iconset` path (`IconExport.swift`), so don't re-introduce a runtime-only icon.

## 11. Key files
- Brain: `evals/*.py`, `demo/*.py` (incl. `demo/github_oauth.py`, `demo/auth.py`).
- App: `mac/Icarus/` (SwiftPM) — see §3.
- Security: `.githooks/`, `.github/workflows/security.yml`, `scripts/`.
- Docs: `docs/plans/`, `docs/decisions/`, `docs/EVALUATION.md`.

## 12. Git state
**`main`** is pushed to a **GitHub remote: `origin` → `alankritxghosh/Icarus`
(private)** — the repo is no longer local-only (Render deploys from it), and
**local == remote** as of this handoff. Latest commits (newest first): `daf1cba`
bake a static app icon (no more blank Dock tile), `165154f` HANDOFF refresh,
`8d891ab` log the real GitHub-callback failure reason, `6024581` host the brain on
Render + package a shareable DMG, `25ed8f0` HANDOFF refresh, `b94687f` best-quality
answer voice, `6e9e072`/`4ef199e` web GitHub login (app/brain). `.env` and `.codex/`
are untracked (leave them); `Icarus.app`/`Icarus.dmg` are gitignored build
artifacts. The old `mac-app` branch still exists locally (same history line).
