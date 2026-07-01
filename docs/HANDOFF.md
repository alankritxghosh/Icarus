# Icarus — Session Handoff (2026-07-01)

Read this first next session. It captures the current state, how to run it, what's
done, what isn't, and the gotchas. Pair with `CLAUDE.md`, `AGENTS.md`,
`general_index.md`, the `docs/decisions/` records, and the memory index.

---

## 1. TL;DR — where we are
The **brain is done + proven**, there's a **web demo**, and this session built a
**working native macOS app** on branch **`mac-app`**:

> Launch Icarus → a real window opens → **Sign in with GitHub** (real OAuth device
> flow, token in Keychain) → connect a **public** repo (it ingests) → press **⌘⇧I**
> anywhere and **type** a question — **or hold Right Option (⌥) and speak it** →
> a **cited answer** (clickable GitHub receipt pills, spoken aloud) or the honest
> **"No one wrote this down."**

The typed loop was **verified live** (cited answer citing `pr:1435`, clicked through to
the real PR). The app has the **Signal Spine icon** (Dock + menu bar), is **restyled to
the Figma "Honest Brutalism v2"** language, and now has **voice**: real-time on-device
speech-to-text in (Apple Speech, hold ⌥) and speak-back out (AVSpeechSynthesizer). It's
packaged as a **signed `.app` bundle** (needed for the mic). Still **not merged to
`main`**. The live voice path (mic + Speech permission prompts) is verified by hand.

## 2. What works today
- **Brain** (`evals/` + `demo/`): ingest any public repo → BM25 retrieval →
  cite-or-abstain prompt → free hosted writer → **deterministic honesty gate** →
  cited answer or honest unknown. Eval board GREEN on the free stack.
- **Web demo** (`demo/server.py`): the browser face over the brain. `GET /health`,
  `GET /status`, `POST /ask`, `POST /connect` (in-app repo switch).
- **macOS app** (`mac/Icarus/`, SwiftPM): menu-bar agent + real onboarding window +
  hotkey overlay; GitHub sign-in; repo connect/ingest; cited-answer + honest-unknown
  rendering; app icon; Honest-Brutalism v2 styling; **voice-in (hold ⌥, real-time
  on-device Apple Speech) + voice-out (AVSpeechSynthesizer)**; packaged as a **signed
  `.app` bundle** via `scripts/bundle.sh`. **22 Swift unit tests pass.**

## 3. The macOS app — architecture & files
**Shape (decided):** hybrid — a real **onboarding window** (Dock-visible) for setup,
plus a **menu-bar `☉`-replacement glyph + ⌘⇧I overlay** for asking. **GitHub is the
login** (no Icarus account backend). The app is a **thin client**: it renders the
brain's verdict verbatim and never re-implements the honesty gate.

**Build system:** **Swift Package Manager** (not an Xcode project) so it builds
headlessly. Two targets:
- `IcarusKit` (testable, UI-free logic): `Models.swift` (AskResponse/Citation/Verdict/
  RepoStatus), `BrainClient.swift` (URLSession → `/ask`,`/connect`,`/status`),
  `GitHubAuth.swift` (device-flow request + poll parser), `TokenStore.swift`
  (protocol + in-memory double), `SpeechRecognizer.swift` (streaming STT protocol +
  stub), `VoiceModel.swift` (`@MainActor @Observable` push-to-talk orchestrator: live
  `partialTranscript`, silence → empty → not emitted).
- `Icarus` (executable app): `IcarusApp.swift` (@main, no window), `AppDelegate.swift`
  (`.regular` policy, status item, hotkey, push-to-talk monitor, owns shared models +
  windows), `OnboardingWindowController.swift`, `OnboardingView.swift`,
  `OverlayController.swift`, `FloatingPanel.swift` (NSPanel, auto-sizes to content),
  `OverlayView.swift`, `AskModel.swift` / `AuthModel.swift` / `ConnectModel.swift`
  (`@MainActor @Observable` state, shared via AppDelegate), `KeychainTokenStore.swift`,
  `IconArt.swift` (Signal Spine in Core Graphics), `Theme.swift` (v2 tokens),
  `AppleSpeechRecognizer.swift` (SFSpeechRecognizer on-device + AVAudioEngine, live
  partials), `PushToTalkMonitor.swift` (global `.flagsChanged`, right-Option keyCode 61),
  `Speaker.swift` (AVSpeechSynthesizer, speaks answer + honest unknown, barge-in).
- Dependency: **KeyboardShortcuts** only (SPM, pinned) for the ⌘⇧I hotkey (registered
  Carbon hotkey → **no Accessibility permission**). Voice-in uses Apple's built-in
  **Speech** framework — no third-party STT dependency, no model download.
- **Packaging:** `scripts/bundle.sh` wraps the SwiftPM binary into a signed `Icarus.app`
  (`Icarus-Info.plist` carries mic + speech usage strings). A bare Mach-O can't get mic
  TCC, so the bundle is required. `Icarus.app` is git-ignored.

**Voice (decided + built):** voice-in is **real-time on-device Apple Speech**
(`SFSpeechRecognizer`, `requiresOnDeviceRecognition = true` — audio never leaves the Mac;
fails rather than using Apple's servers). Trigger is **hold Right Option (⌥)** — a
single modifier key, so it uses a global `.flagsChanged` monitor (not KeyboardShortcuts)
and likely needs an **Input Monitoring** grant to fire from other apps. (An earlier
WhisperKit `large-v3` batch approach was replaced: on the 8 GB Mac batch decode took
minutes; Apple Speech streams live.)

**GitHub auth:** OAuth **Device Flow**, scope `read:user` only (public repos). Client
ID via env `ICARUS_GH_CLIENT_ID` (public, not a secret). Token stored **only in the
Keychain** (`KeychainTokenStore`), never logged/committed; restored on launch.

## 4. Constraints & decisions (the operating rules)
- **Public repos only, free hosted models** (Groq writer + Gemini judge). Private
  repos are **blocked** on the paid/private-model decision (free tiers may train on
  inputs). See `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md`.
- **Positioning (decided):** Icarus is **organizational memory**; explanation is the
  wedge. *"Git remembers what changed. Icarus remembers why."* Push (stale-decision
  detection) beats pull for usage frequency; **capture** is the moat. See
  `docs/decisions/2026-06-30-organizational-memory-positioning.md`.
- The non-negotiable: **cite-or-unknown, deterministic, never bluff** — preserved.

## 5. How to run it (exact)
The app talks to the brain at `http://127.0.0.1:8000`. **Start the brain first**, in
its own Terminal, with a provider key:
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"
GROQ_API_KEY=<key> GEMINI_API_KEY=<key> python3 -m demo.server
# wait for: Icarus demo on http://127.0.0.1:8000
```
Then build the **signed `.app` bundle** and launch it. The bundle is required for
microphone access (TCC needs the Info.plist mic usage string + a signature — a bare
`.build/release/Icarus` cannot get the mic). Run the *inner* binary directly so the
`ICARUS_GH_CLIENT_ID` env var is inherited (a plain `open Icarus.app` would not pass it),
while still getting the bundle's Info.plist + signature for TCC:
```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering/mac/Icarus"
./scripts/bundle.sh        # swift build -c release → Icarus.app (ad-hoc signed)
ICARUS_GH_CLIENT_ID=Ov23liVZXvv6V5vX2x1Y ./Icarus.app/Contents/MacOS/Icarus
```
In the app: **Sign in with GitHub** → approve the device code in the browser →
connect **`simonw/llm`** → **⌘⇧I** → ask. Known-answerable question (gives a cited
answer): *"Why did llm implement the OpenAI Responses API as a new model class
instead of modifying the existing chat completions class?"* → cites `pr:1435`.

Voice: **hold Right Option (⌥)** and speak — the transcript appears live and, on release,
runs the same ask path. Grant the mic + Speech prompts on first hold (and Input Monitoring
so ⌥ fires from other apps). The answer is spoken back.

Tests: `cd mac/Icarus && swift test` (22 pass). Brain evals:
`GROQ_API_KEY=… GEMINI_API_KEY=… python3 -m evals.run --pipeline gated`.

## 6. Secrets & credentials
- **ROTATE THE KEYS.** The **Gemini** and **Groq** API keys were pasted into this
  session's chat transcript. They are free-tier ($0 risk) but exposed — rotate before
  sharing the transcript / going public.
- The **GitHub OAuth Client ID** (`Ov23liVZXvv6V5vX2x1Y`) is **not** a secret (device
  flow public client). The OAuth App lives under Alankrit's GitHub account with
  "Enable Device Flow" on. No client secret exists (device flow doesn't need one).

## 7. What is NOT done (next work)
1. **A6 — record the demo** (script in `docs/plans/2026-06-28-brick-6-recordable-demo.md`).
   Voice (A4 in / A5 out) is **built** — the demo can now be driven by voice.
3. **Full app shell (U1 scope B, deferred).** We only **restyled the current two
   surfaces** to the Figma v2 look. The wireframe's full windowed app (sidebar nav:
   Home / Ask by voice / Decision history / Unknowns / Privacy boundary; hero card;
   metrics; recent-questions list; proof drawer) is **not built** — it's a large
   re-architecture and needs its own plan. Figma: file `SbmCti2rnsog2rwrzzCWm0`,
   direction frame `5:2` ("Quiet Native Memory v2 - clean").
4. **Bundle real fonts.** UI uses system sans + SF Mono as stand-ins for **Geist +
   JetBrains Mono**; bundle + register the real fonts for a pixel match.
5. **Merge `mac-app` → `main`** (or open a PR). Everything this session is on
   `mac-app`, unmerged.
6. **Productization gaps:** manual brain startup (Terminal) is not customer-acceptable
   → folds into the one-unified-cloud hosting work. There's now a signed `.app` bundle
   (ad-hoc), but **no Developer-ID signing / notarization** yet.
7. **Private repos, multi-repo, non-GitHub sources, stale-decision detection** — the
   roadmap beyond v1 (see the org-memory decision doc). All gated / deferred.

## 8. Task board snapshot
Done: brain/demo (prior) · A0 `/health` · A1 menu-bar skeleton · A2 hotkey+overlay ·
A3 wire-to-brain · G0–G5 GitHub auth + workflow (verified live) · U2 app icon · U1 UI
restyle (current surfaces) · **V0 signed `.app` bundle** · **A4 voice-in (real-time
on-device Apple Speech, hold ⌥)** · **A5 voice-out (AVSpeechSynthesizer)**. Pending:
**A6 record demo · U1 scope B (full shell) · Developer-ID signing/notarization**. Voice
built + unit-tested (22 pass); the live mic/Speech path is a manual check.

## 9. Plans & decisions (docs/)
- `docs/plans/2026-06-30-macos-app.md` — the macOS app plan (A0–A6), task-by-task.
- `docs/plans/2026-06-30-github-auth-workflow.md` — the GitHub auth + workflow plan (G0–G5).
- `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md` — hosting model.
- `docs/decisions/2026-06-30-organizational-memory-positioning.md` — positioning + roadmap.
- `docs/DESIGN_VISION.md` (Honest Brutalism), `docs/UI_UX_BRIEF.md` — design intent.

## 10. Gotchas (learned this session)
- **Full Xcode is required** for the app (not just CLT), and its **license must be
  accepted** (`sudo xcodebuild -license accept`) — after Xcode is active, even the
  Xcode-shimmed `git`/`swift` refuse to run until the licence is accepted.
- **Always rebuild `-c release` before relaunching** — a stale release binary once
  showed old UI (the debug build was current but the launched release binary wasn't).
- **Restarting the brain resets its active repo** to the default; reconnect the repo
  in the app window afterward. The app keeps pointing at `:8000`; no app relaunch needed.
- The brain **starts without keys** (ingest/`/connect`/`/status` need no LLM), but
  `/ask` needs a provider key.
- `/status` returns `counts` as an **object** (`{pr,issue,code}`) — the Swift model
  ignores it (was a real decode bug, fixed).
- **Figma MCP works** for this file (read design context/screenshots/metadata; tokens
  came from node `9:44`). `get_variable_defs` returned `{}` (no bound variables).
- `mac/Icarus/.build/` is git-ignored; only `.codex/` (Codex tooling, not ours) is
  untracked in the tree.

## 11. Key files
- Brain: `evals/*.py`, `demo/*.py` (+ `GET /health`).
- App: `mac/Icarus/` (SwiftPM) — see §3.
- Docs: `docs/plans/`, `docs/decisions/`, `docs/DESIGN_VISION.md`, `docs/UI_UX_BRIEF.md`.

## 12. Git state
Branch **`mac-app`** (unmerged). Latest commits (newest first): `7a963ab` restyle,
`907f268` app icon, `7413c72` dead-code removal, `27ea069`/`3343339` docs reconcile,
`7bc74e6` panel auto-size, `bb85353` status decode fix, `e55bdea` G4, `2709014`
onboarding window, `b7f2eca` G3, `eb11d38` G1+G2, `56fc137` A3, `fed52fd`/`ad0c9b8` A2,
`d388335` A1, `8ee5902` A0. Only `.codex/` is untracked (leave it or gitignore).
