# Icarus — Session Handoff (2026-07-06)

Read this first next session. It captures the current state, how to run it, what's
done vs. not, and the gotchas. Pair with `CLAUDE.md`, `AGENTS.md`,
`general_index.md`, the `docs/decisions/` records, and the memory index.

---

## 1. TL;DR — where we are
The **brain is done + proven**, the macOS app is a **full windowed shell**, Icarus
is **shippable without an Apple Developer ID** (cloud brain + downloadable `.dmg`),
and **private-repo support is fully merged, deployed, and proven live end-to-end**:
a signed-in engineer can connect their **own private GitHub repo** and get cited
answers from a **paid, no-training-verified writer**, with proven **per-user
isolation** and a **deterministic trust interlock** that makes it impossible in
code for private text to reach a free-tier model. This was proven with **real
credentials against a real private repo**, not just self-skipping test scaffolding.

> Recipient downloads `Icarus.dmg` → drags to /Applications → one-time Gatekeeper
> "Open Anyway" → **Sign in with GitHub** (real web OAuth, against the hosted
> brain, **`repo`-scoped**) → **connect a public or private repo** → **⌘⇧I** to
> type or hold **Right Option (⌥)** to speak → a **cited answer** (clickable
> GitHub receipts, spoken aloud) or the honest **"No one wrote this down."**
> Login persists (Keychain); **Sign out** switches accounts.

**Hosted brain:** `https://icarus-brain.onrender.com` (Render free tier, Docker,
GitHub-bearer-gated, private-repo support live). **Repo on GitHub:**
`alankritxghosh/Icarus` (**private**, `origin`), `main` pushed and matches local.
The full runbook is **`docs/DISTRIBUTION.md`**.

**Only two real things left on the private-repo effort, both in §7 — everything
else about it is done:**
1. Record the written no-training policy link for the paid Gemini key (your job,
   not code — billing is confirmed enabled, the written terms link isn't).
2. **Rotate the Gemini paid key and the GitHub PAT used to prove the live tests
   this session** — they were typed directly into this chat session's transcript,
   which isn't the intended home for live credentials, even though they were
   never written to disk or printed back by the assistant. Do this before the
   next session if you haven't already.

**Update (later on 2026-07-06): Brick G is now built** — the Mac app has the
private-repo surface (trust-tier badge, disconnect, repo persistence across
launches, and the client-side lost-connection banner). App-only; zero brain
changes; plan + details in `docs/plans/2026-07-06-brick-g-private-repo-ui.md`.
48 Swift tests pass (up from 35). Not yet committed as of this note.

## 2. What happened this session (private repos: built, merged, deployed, proven)
Built task-by-task via subagent-driven development (fresh implementer + spec
review + code-quality review per task, looping on real findings) against the
16-task plan (`docs/plans/2026-07-04-private-repos-implementation.md`, Bricks
A–F). All 16 landed, several needing real fix rounds (most notably two rounds
closing a race/downgrade bug in the per-user registry's LRU eviction). A final
**holistic** review of the whole branch — not per-task — re-verified everything
at the composed level and returned a clean "ready to merge."

**What it does, end to end:** a signed-in user (GitHub OAuth, `repo`-scoped)
connects their own private repo → the brain verifies **with the caller's own
token** that they can actually read it (`evals/github_access.py`) → clones it
leak-safe (`evals/ingest.py`'s `token=`, via subprocess **env**, never argv/URL)
→ answers **only** through a paid, billing-confirmed writer
(`evals.provider.PaidGeminiProvider`) → gated by a **deterministic trust
interlock** (`evals/trust.py`'s `assert_safe_for_private`) that refuses any
provider not explicitly flagged `private_safe = True` — never inferred from a key
string. Every user's active repo, corpus, and pipeline are isolated per GitHub
identity (`demo/registry.py`'s `LibraryRegistry`), proven at the real HTTP
boundary and **mutation-tested** (`demo/test_isolation.py` — a reviewer broke
isolation two different ways and confirmed the suite catches both). A companion
suite (`evals/test_egress_invariants.py`) proves private text reaches the writer
and nothing else. `POST /disconnect` deletes a user's own data. `/ask`+`/connect`
are per-identity rate-limited (`demo/ratelimit.py`).

**The one thing every task was checked against, re-verified independently by
SHA-256 (not just `git diff`): `evals/gate.py` — the deterministic cite-or-abstain
honesty gate — is byte-for-byte unchanged across the entire effort.**

**After merging** (`a237ab2` → `95aeda6` fast-forward), this session also:
- **Pushed to `origin` and deployed to Render** with `GEMINI_PAID_API_KEY` set —
  confirmed live (`GET /status` on the hosted brain returns the new `"private"`
  field).
- **Ran both live proofs for real**, not just self-skip-checked:
  - `evals.test_paid_writer_eval` — hit a real, transient Google "high demand"
    503 on the old `gemini-2.5-flash-lite` default. Verified `gemini-3.1-flash-lite`
    is a real, stable model id via the live `/v1beta/models` list before bumping
    the default (`evals/provider.py`, commit `7510c4b` — a single shared default,
    so this also bumped the free writer and the judge). Board: gates 100%,
    citation correctness 100%, answer correctness 100%.
  - `evals.test_private_ingest_live` — run against Icarus's own private repo.
    Found and fixed a genuine, pre-existing bug along the way: `evals/ingest.py`'s
    `fetch_code` compared an unresolved temp-dir path against an already-resolved
    one; on macOS `/var` symlinks to `/private/var`, so any real clone with a
    nested directory raised `ValueError` — invisible until now because every
    offline test mocks `subprocess.run`, and this was the first genuine
    end-to-end clone into a real temp dir. Fixed in `ab305b3` (resolve the clone
    root once; `simonw/llm`'s committed corpus ref format is unaffected). All 3
    sub-tests then passed for real: access check, authenticated clone, a
    paid-writer answer holding the honesty gate, and the interlock genuinely
    refusing a real free provider.
- **Closed the two remaining test-coverage gaps** the final review flagged
  (neither was a bug — both proven already-correct, just untested):
  `demo/test_library.py::test_interlock_refusal_inside_connect_sync_leaves_state_untouched`
  (the interlock raising *inside* `connect_sync`, not just via a direct call,
  leaves the previously-connected repo/pipeline/private-flag completely
  untouched) and `demo/test_registry.py`'s two `..._resume_never_calls_ingest`
  tests (LRU eviction-resume — public and private — is provably always a cache
  hit, pinning why it's safe to sit outside the rate limiter's reach).

## 3. What works today
- **Brain** (`evals/` + `demo/`): ingest a public repo → BM25 retrieval →
  cite-or-abstain prompt → free hosted writer → **deterministic honesty gate** →
  cited answer or honest unknown. Eval board GREEN on the free stack.
- **Private repos:** the same brain, gated per user, proven end-to-end live — see §2.
- **Web demo** (`demo/server.py`): `ThreadingHTTPServer` over the brain. `GET /`,
  `/health`, `/status`, `/auth/github/callback`; `POST /ask`, `/connect`,
  `/disconnect`, `/auth/github/begin`, `/auth/github/redeem`. Loopback Host/Origin
  guard, 64 KB body cap, optional GitHub bearer gate, per-identity rate limits,
  loads `.env` on start.
- **Typed web staging link** (`demo/index.html`, branch `feat/web-staging-link`):
  the hosted brain now doubles as a **browser** try-it surface — engineers sign
  in with GitHub in the page (web-mode OAuth: `/auth/github/begin {"mode":"web"}`
  → callback returns to `/?session=` → redeem → token in **sessionStorage** →
  `Authorization: Bearer` on `/ask`+`/connect`+`/status`), connect their own
  public or private repo, and see a public/private writer badge. No DMG needed.
  Typed only (no voice/overlay — those are native-only, and browser voice would
  break the on-device-audio promise). **Same infra/bill/no-training caveats as
  the DMG — a link is easier to pass around, so don't post it publicly, and close
  the paid-key no-training-policy checkbox before real private code.** The Mac-app
  OAuth flow (`icarus://`) is unchanged. Deploying this needs a Render redeploy
  (it's a brain change). See `docs/plans/2026-07-06-web-staging-link.md`.
- **macOS app** (`mac/Icarus/`, SwiftPM): the **primary windowed shell** (five
  surfaces) + ⌘⇧I overlay + hold-⌥ voice. **Web GitHub login**, **Keychain-
  persisted** session, **Sign out**, **voice in/out**, packaged as a signed
  `.app`. **48 Swift unit tests pass.** Brick G (private-repo UI) is built:
  private/public trust-tier badge, Disconnect-repo control, repo persistence
  across launches, and an explicit lost-connection banner when the server drops
  the session (restart / LRU eviction) — with one-click Reconnect (the app holds
  the caller's bearer, so it CAN legitimately re-connect a private repo the
  server-side registry couldn't resume).
- **Security**: per-commit secrets gate (`.githooks/pre-commit`,
  block on secret / warn on failing tests) + CI (`.github/workflows/security.yml`).
- **Cloud deployment:** `Dockerfile` + `render.yaml` + `.dockerignore` deploy the
  brain to Render. `demo/server.py` binds from `$HOST`/`$PORT`, has a
  configurable Host guard (`ICARUS_ALLOWED_HOSTS`; `*` = cloud, trust TLS proxy +
  rely on the bearer gate), and builds the OAuth callback from
  `ICARUS_PUBLIC_URL`. Auth is **mandatory** in the cloud
  (`ICARUS_REQUIRE_GITHUB_AUTH=1`). Live at `icarus-brain.onrender.com`.
- **Distribution:** `mac/Icarus/scripts/package_dmg.sh` builds a shareable
  `Icarus.dmg` — ad-hoc signed, stamps the hosted brain URL into the bundle,
  drag-to-Applications + a `READ ME FIRST.txt`. The app resolves its brain from
  the bundle's `ICARUS_BRAIN_URL` (`IcarusKit/BrainEndpoint.swift` +
  `Icarus/AppConfig.swift`); dev builds fall back to `127.0.0.1:8000`.
- **Static app icon:** baked into the bundle (`IconExport.swift` +
  `bundle.sh --render-iconset`), so Finder/DMG/Dock never show a blank tile.
- **End-to-end proven, twice over:** the hosted sign-in → cited-answer flow for
  public repos, and now the full private-repo path (§2) — both work live, not
  just in tests.

## 4. The macOS app — architecture & files
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

**GitHub login (web OAuth):**
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
back is `AVSpeechSynthesizer` in `Speaker.swift`, which picks the **best-quality
installed English voice** (premium > enhanced > default, preferring en-US) and never
a novelty voice. For a natural sound, download a **Premium** voice: System Settings →
Accessibility → Spoken Content → System Voice → **Manage Voices** → an English
"(Premium)" voice — the app then uses it automatically (relaunch to pick it up). No
premium voice installed = falls back to the standard en-US voice.

## 5. Constraints & decisions (the operating rules)
- **Public repos: free hosted models** (Groq writer + Gemini judge, now on
  `gemini-3.1-flash-lite`). **Private repos: only the paid, billing-confirmed
  `PaidGeminiProvider`** — the free/paid split is enforced in code by the
  deterministic trust interlock (`evals/trust.py`), not by convention.
- **Positioning:** Icarus is **organizational memory**; explanation is the wedge.
- The non-negotiable: **cite-or-unknown, deterministic, never bluff** — preserved,
  byte-for-byte, through the entire private-repo effort (§2).
- **GitHub login needs a client secret** (GitHub requires it even with PKCE), so
  the exchange runs on the **brain**, never the app. Loopback callback per GitHub's
  native-app guidance.

## 6. How to run it (exact)
Keys + the GitHub OAuth app live in a **gitignored `.env`** at the repo root (copy
`.env.example`). It holds `GROQ_API_KEY`, `GEMINI_API_KEY`, `GITHUB_CLIENT_ID`,
`GITHUB_CLIENT_SECRET`, and now **`GEMINI_PAID_API_KEY`** (currently the same
underlying key as `GEMINI_API_KEY`, with billing enabled — see §7). The GitHub
OAuth App's **Authorization callback URL** must be
`http://127.0.0.1:8000/auth/github/callback`.

**Start the brain** (reads `.env`, no inline keys needed):
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"
python3 -m demo.server          # prints "web login on" when GitHub creds are set
```
**Build + launch the app** (the bundle is required for the mic; `open` is fine —
the brain builds the authorize URL, the app needs no GitHub client id):
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering/mac/Icarus"
./scripts/bundle.sh && open ./Icarus.app
```
In the app: **Sign in with GitHub** → authorize in the sheet → connect
**`simonw/llm`** → **⌘⇧I** → ask. Known cited question: *"Why did llm implement the
OpenAI Responses API as a new model class instead of modifying the existing chat
completions class?"* → cites `pr:1435`.

**To run it HOSTED / build the shareable DMG** see **`docs/DISTRIBUTION.md`**:
deploy to Render, set env vars, point the GitHub OAuth callback at the Render URL,
then `ICARUS_BRAIN_URL=https://icarus-brain.onrender.com ./scripts/package_dmg.sh`
→ `mac/Icarus/Icarus.dmg`. Local dev still uses the loopback `.env` + `bundle.sh`.

**To connect a private repo:** sign in (or sign out/in again if your token
predates the `repo`-scope widening, §9), `POST /connect` with your own repo — the
brain verifies you can read it, clones it with your token (never logged, never on
disk after the process exits), and routes you to the paid writer. `POST
/disconnect` deletes your data. `GET /status` shows `private: true/false`. **No
app-side UI for this yet** — it's a raw HTTP call today (curl/Postman/the demo
page), not a Mac app button (§7, Brick G).

**Tests:** `cd mac/Icarus && swift test` (**35**). Brain:
`python3 -m unittest discover -t . -s evals` (**118, 12 self-skip**) and
`... -s demo` (**120, 2 self-skip**) — up from 85+70 before the private-repo
effort began. Live proofs (skip without keys, both **actually run this session
with real credentials, both GREEN** — see §2):
```bash
GEMINI_PAID_API_KEY=… python3 -m unittest evals.test_paid_writer_eval
RUN_PRIVATE_INGEST=1 ICARUS_TEST_PRIVATE_REPO=owner/repo GITHUB_TOKEN=… \
  GEMINI_PAID_API_KEY=… python3 -m unittest evals.test_private_ingest_live
```
Note on `GITHUB_TOKEN`: if it's a GitHub **fine-grained PAT**, it must have the
target repo explicitly selected in its own Repository access settings when
created — a repo you own but didn't select still 404s (indistinguishable from
"doesn't exist," which is the correct fail-safe behavior, not a bug).

## 7. What is NOT done (next work)

**Private-repo effort — only two items left, neither is code:**
1. **Record the written no-training policy link** for the paid Gemini key.
   Billing is confirmed enabled, but the actual policy-link verification is
   still an open checkbox in
   `docs/plans/2026-07-04-private-repos-per-user-isolation.md`. Close this
   before onboarding real private code from other people (not just your own).
2. **Rotate the credentials used to prove the live tests this session** — a
   Gemini paid key and a GitHub fine-grained PAT were typed directly into the
   chat transcript to run the live proofs (§2). Neither was written to disk or
   echoed back by the assistant, but a chat transcript isn't the designated
   home for live secrets. Regenerate both if you haven't already.

**Brick G — DONE (2026-07-06, same-day update to this handoff):** built per
`docs/plans/2026-07-06-brick-g-private-repo-ui.md`, TDD, app-only. The
`RepoStatus` model decodes `private`, `BrainClient` has `disconnect()`, a new
`IcarusKit/SavedConnection.swift` persists the last connection + implements the
pure `isLost` downgrade check, and the shell shows the trust-tier badge, the
Disconnect control, and the lost-connection banner (the previously-flagged
"no explicit signal" gap — solved client-side: the app remembers what it
connected and flags a ready-on-a-different-repo status, with one-click
Reconnect using the caller's own bearer). Remaining for Brick G: a live
end-to-end run with a real signed-in user + private repo (needs your
credentials; unit + contract-level checks are green).

**Older, smaller items (predate this session, still open):**
1. **Notarization / Developer-ID signing.** The app is ad-hoc signed. This is the
   biggest gap: it (a) makes the Keychain "sign in once" seamless (no repeated
   prompts) and (b) lets the app open on someone else's Mac. Enrollment has lead
   time — start it before any investor touches the binary.
2. **Confirm Groq/Gemini keys are rotated** if an even earlier transcript than
   this session ever exposed them (the GitHub client secret rotation from a
   prior session is already done — see §8).
3. **Harden the hosted brain if it goes beyond a controlled demo:** `/ask` and
   `/connect` now have per-identity rate limits (`demo/ratelimit.py`), but auth
   is still the only ban/throttle lever otherwise — don't post the URL publicly.
   The free instance sleeps; repo-switching ingests arbitrary public repos on
   the server (prompt-injection surface, disclosed). The OAuth CSRF state is
   in-memory (§9).
4. **Bundle real fonts** (Geist + JetBrains Mono) — UI uses SF stand-ins.
5. ~~Persist the connected repo across launches~~ — **done in Brick G**
   (`SavedConnection` + auto-resume at launch when signed in; a Render restart
   now surfaces the explicit lost-connection banner instead of a silent revert).
6. **Record the demo** (script in `docs/plans/2026-06-28-brick-6-recordable-demo.md`).
7. **Multi-repo, non-GitHub sources, stale-decision detection** — post-v1
   roadmap, gated/deferred.

## 8. Security posture
- Brain: loopback Host/Origin guard, 64 KB body cap, GitHub bearer gate on
  `/ask`+`/connect`+`/disconnect`, per-identity rate limits, ingest subprocess
  timeouts + size caps + path-traversal guard, generic (non-leaking) ingest
  errors, provider keys in headers not URLs, the deterministic trust interlock
  gating every private-repo answer.
- Prompt-injection via ingested content is **disclosed** (see `docs/EVALUATION.md`);
  the gate proves provenance, not faithfulness — connect only vetted repos on stage.
- Per-commit: `.githooks/pre-commit` (secret hard-blocks; failing tests warn),
  installed via `scripts/install_hooks.sh` (`core.hooksPath` → `.githooks`).
- CI backstop: `.github/workflows/security.yml` (scan + Python suites + Swift).
- Fix plans: `docs/plans/2026-07-02-security-hardening.md` (server hardening),
  `docs/plans/2026-07-04-private-repos-per-user-isolation.md` +
  `docs/plans/2026-07-04-private-repos-implementation.md` (private-repo trust
  model, fully built).

## 9. Gotchas
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
  code.
- **The GitHub auth sheet / SecurityAgent / Keychain prompts are separate system
  processes** — invisible to computer-use screenshots (compositor filters non-
  allowlisted apps). Their absence in a screenshot ≠ they didn't appear.
- **Restart the brain to pick up `.env` changes** (it loads `.env` once at start).
  Restarting also resets the brain's active repo to the default; reconnect in the app.
- **`/status` returns `counts` as an object** (`{pr,issue,code}`), and now also
  `private: true/false`.
- **`swift test`** must be run, not `unittest discover` for Python without `-t .`
  (relative imports need the repo root as top-level).
- **`incorrect_client_credentials` on sign-in = the Render `GITHUB_CLIENT_SECRET`
  doesn't match the OAuth app** whose Client ID the brain sends
  (`Ov23liVZXvv6V5vX2x1Y`). The brain logs the real reason to stderr — look in
  **Render → Logs** for `github callback failed: <reason>`. `/auth/github/begin`
  succeeds even with a wrong secret (only needs it non-empty), so a working
  authorize URL doesn't prove the secret.
- **OAuth CSRF `state`/sessions are in-memory.** Any Render redeploy (every
  env-var save triggers one) or the free-tier ~15-min idle sleep **wipes them
  mid-sign-in** → "expired." Don't change Render settings while signing in;
  retry once warm.
- **Pushing `.github/workflows/*` needs the `workflow` token scope.** `gh`'s
  default OAuth token lacks it; `gh auth refresh -h github.com -s workflow` fixes it.
- **Ad-hoc Keychain prompt is a one-time "Always Allow," not a bug.** Run Icarus
  from **/Applications** (not the DMG/Downloads — App Translocation randomizes the
  path each launch so "Always Allow" can't stick) and clear quarantine
  (`xattr -dr com.apple.quarantine /Applications/Icarus.app`). Every rebuild
  changes the cdhash → one re-prompt. Only notarization removes it entirely.
- **The GitHub OAuth scope widened `read:user` → `repo`** so a signed-in user's
  own token can read their private repos. Anyone who signed in **before** this
  change is holding a stale `read:user`-scoped token — private-repo connect
  fails for them until they **sign out and sign back in**. There is **no
  server-side token migration**; this is a real, one-time, user-visible step.
- **Render injects `$PORT`** (observed `10000`) and expects `0.0.0.0`; the
  Dockerfile sets `HOST=0.0.0.0` and `serve()` reads `$PORT`.
  `ICARUS_ALLOWED_HOSTS=*` opens the Host guard so the Render hostname + health
  check pass.
- **A code-only Dock icon shows a blank tile until launch.** The bundle needs a
  static `AppIcon.icns` + `CFBundleIconFile` — `bundle.sh` already bakes this;
  don't reintroduce a runtime-only icon.
- **A GitHub fine-grained PAT 404s on a repo you own but never selected** when
  creating the token — Repository access must explicitly include that repo (or
  be "All repositories"). This 404 is indistinguishable from "repo doesn't
  exist," which is the correct fail-safe behavior of `evals/github_access.py`'s
  access check, not a bug to work around in code.
- **On macOS, `/var` is a symlink to `/private/var`.** Any code that clones into
  a `tempfile.TemporaryDirectory()` and later resolves paths within it (e.g. for
  `Path.relative_to()`) must resolve BOTH sides consistently, or comparisons
  silently fail on real runs even though every mocked-`subprocess.run` test
  passes. Fixed once in `evals/ingest.py` (`ab305b3`) — watch for the same
  pattern anywhere else that walks a real clone.

## 10. Plans & decisions (docs/)
- `docs/plans/2026-07-04-private-repos-per-user-isolation.md` — the private-repo
  scoping doc (per-user isolation, trust interlock, decisions). One open
  checkbox: the written no-training policy link (§7).
- `docs/plans/2026-07-04-private-repos-implementation.md` — the executable
  16-task plan, all done. Brick G (app) is outlined there but not yet turned
  into its own detailed plan.
- `docs/plans/2026-07-02-full-app-shell.md` — the windowed shell (Home gate +
  five surfaces, all real data).
- `docs/plans/2026-07-02-security-hardening.md` — the security-audit fixes.
- `docs/plans/2026-07-03-web-github-login.md` — the web login (brain exchange +
  ASWebAuthenticationSession).
- `docs/plans/2026-06-30-macos-app.md`, `docs/plans/2026-06-30-github-auth-workflow.md`
  — earlier app/auth plans (device flow now superseded by web login).
- `docs/decisions/` — hosting model + org-memory positioning. `docs/DESIGN_VISION.md`
  / `docs/UI_UX_BRIEF.md` — design intent (Figma file `SbmCti2rnsog2rwrzzCWm0`,
  frame `5:2` "Quiet Native Memory v2").

## 11. Key files
- Brain: `evals/*.py`, `demo/*.py`. Private-repo pieces:
  `demo/registry.py` (per-user isolation), `demo/ratelimit.py`, `evals/trust.py`,
  `evals/github_access.py`, `evals/provider.py`'s `PaidGeminiProvider` (model
  default now `gemini-3.1-flash-lite`), `evals/ingest.py`'s leak-safe `token=`
  support (and its macOS-symlink fix, `ab305b3`). Proof suites:
  `demo/test_isolation.py`, `evals/test_egress_invariants.py`,
  `evals/test_paid_writer_eval.py`, `evals/test_private_ingest_live.py`. Full
  map: `general_index.md`/`detailed_index.md`.
- App: `mac/Icarus/` (SwiftPM) — see §4. **No private-repo UI yet** — Brick G is next.
- Security: `.githooks/`, `.github/workflows/security.yml`, `scripts/`.
- Docs: `docs/plans/`, `docs/decisions/`, `docs/EVALUATION.md`.

## 12. Git state
**`main` == `origin/main`**, both pushed and current as of this handoff. Merged
`feat/private-repos` into `main` via fast-forward (`a237ab2` → `95aeda6`, no
merge commit, clean history), then landed several more commits directly on
`main`: the model bump to Gemini 3.1 (`7510c4b`), the macOS-symlink ingest fix
(`ab305b3`), the two pinning tests (`3def661`), and a few HANDOFF refreshes in
between. All pushed.

The `feat/private-repos` branch still exists locally (only its worktree at
`.claude/worktrees/private-repos` was removed, since it's fully merged) — safe
to `git branch -d feat/private-repos` whenever convenient, or leave it as a
historical marker. `.env` and `.codex/` are untracked (leave them);
`Icarus.app`/`Icarus.dmg` are gitignored build artifacts. The old `mac-app`
branch still exists locally (same history line, unrelated to this work).
