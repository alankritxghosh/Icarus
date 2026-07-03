# Icarus — Session Handoff (2026-07-03)

Read this first next session. It captures the current state, how to run it, what's
done vs. not, and the gotchas. Pair with `CLAUDE.md`, `AGENTS.md`,
`general_index.md`, the `docs/decisions/` records, and the memory index.

---

## 1. TL;DR — where we are
The **brain is done + proven**, there's a **web demo**, the repo is **security-
hardened** with a per-commit gate, and the **native macOS app** (branch
**`mac-app`**) is now a **full windowed shell** you sign into like Google:

> Launch Icarus → the **shell window** opens → **Sign in with GitHub** (real web
> OAuth in a sheet — no code-pasting) → **connect a public repo** → press **⌘⇧I**
> anywhere and **type** a question — **or hold Right Option (⌥) and speak it** →
> a **cited answer** (clickable GitHub receipts, spoken aloud) or the honest
> **"No one wrote this down."** Login persists (Keychain); **Sign out** switches
> accounts.

The whole session's work is now **merged into `main`** (fast-forward); `mac-app`
still points at the same commit. There is **no git remote** — the repo is local only.

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
- **Security** (this session): per-commit secrets gate (`.githooks/pre-commit`,
  block on secret / warn on failing tests) + CI (`.github/workflows/security.yml`).

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
3. GitHub redirects to the brain's **loopback callback**
   `http://127.0.0.1:8000/auth/github/callback`; the brain **exchanges the code
   using the client SECRET** (held only in its env) and **302s to
   `icarus://auth?session=…`** so the sheet closes.
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

Tests: `cd mac/Icarus && swift test` (30). Brain:
`python3 -m unittest discover -t . -s evals` and `... -s demo` (85 + 67).

## 6. Secrets & credentials — ROTATE BEFORE SHARING
- `.env` now holds the **Groq + Gemini keys AND the GitHub client secret**, and all
  of them were pasted into this session's chat transcript. **Rotate all before
  sharing the app or transcript.** `.env` is gitignored + the pre-commit hook blocks
  a staged secret, so nothing is in git — the exposure is the transcript.
- The GitHub **Client ID** (`Ov23liVZXvv6V5vX2x1Y`) is public; the **secret** is not.

## 7. What is NOT done (next work)
1. **Notarization / Developer-ID signing.** The app is ad-hoc signed. This is the
   biggest gap: it (a) makes the Keychain "sign in once" seamless (no repeated
   prompts) and (b) lets the app open on someone else's Mac. Enrollment has lead
   time — start it before any investor touches the binary.
2. **Rotate the exposed keys** (see §6) — the one real security to-do.
3. **Push to a git remote** if you want `main` off this machine (none is
   configured; `.env` stays local/gitignored). The merge to `main` itself is DONE.
4. **Bundle real fonts** (Geist + JetBrains Mono) — UI uses SF stand-ins.
5. **Persist the connected repo** across launches (login persists; the repo does
   not — you reconnect each launch).
6. **Record the demo** (A6; script in `docs/plans/2026-06-28-brick-6-recordable-demo.md`).
7. **Private repos, multi-repo, non-GitHub sources, stale-decision detection** —
   post-v1 roadmap, gated/deferred.

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

## 11. Key files
- Brain: `evals/*.py`, `demo/*.py` (incl. `demo/github_oauth.py`, `demo/auth.py`).
- App: `mac/Icarus/` (SwiftPM) — see §3.
- Security: `.githooks/`, `.github/workflows/security.yml`, `scripts/`.
- Docs: `docs/plans/`, `docs/decisions/`, `docs/EVALUATION.md`.

## 12. Git state
**`main`** and **`mac-app`** both point at the same commit — the session was
**merged into `main` via fast-forward**. **No git remote is configured (local only)**;
nothing is pushed. Latest commits (newest first): `b94687f` best-quality answer
voice, `691ca6f` HANDOFF refresh, `93252aa` Keychain persist + Sign out, `a1ddc35`
sign-in crash fix, `6e9e072` web GitHub login (app), `4ef199e` web login (brain),
`dc4fc26` shell as primary window, `490eba2` chromeless title bar, `f4f536a` app
shell, `2a4e3df` per-commit secrets gate, `5b60db4` brain security hardening. `.env`
and `.codex/` are untracked (leave them).
