# Icarus — General Index

A fast map of every tracked file in the repo with a 1–2 line description.
Grouped by directory. Regenerate this after any structural change (adding,
removing, or renaming files). For class/function-level detail see
`detailed_index.md`.

## Repo root
- `CLAUDE.md` — standing orders for anyone (human or AI) building Icarus:
  engineering principles, hard constraints, codebase map, and the commands.
- `AGENTS.md` — the same standing orders addressed to non-Claude coding agents
  (Codex etc.); mirrors CLAUDE.md's rules.
- `README.md` — the pitch and one-paragraph overview of Icarus plus its honesty
  promise.
- `general_index.md` — this file: every tracked file + a short description.
- `detailed_index.md` — every class/function in the `evals/` package + its
  description, drawn from real docstrings/signatures.
- `.gitignore` — ignored paths (secrets/`.env`, caches, build artifacts); the
  committed `.env.example` is explicitly un-ignored.
- `.env.example` — committed template (NO real keys) to copy to a gitignored
  `.env`; the brain/eval harness load it on startup for provider keys.

## Security automation (per-commit + CI)
- `scripts/scan_secrets.sh` — deterministic secrets scan; `--staged` (pre-commit)
  or tracked-files (CI) mode. Exits non-zero on a provider-token or secret-shaped
  hit so it can block a commit/build.
- `scripts/install_hooks.sh` — one-time wire of `core.hooksPath` → `.githooks`.
- `.githooks/pre-commit` — commit gate: a staged secret hard-blocks; failing
  tests only warn (never block).
- `.github/workflows/security.yml` — CI backstop on push/PR: secrets scan +
  Python suites (evals, demo) + Swift build/test.

## docs/
- `docs/VISION.md` — product vision: the conversational engineering brain, what
  it answers, and the v1 scope (GitHub + Mac voice app + private cloud).
- `docs/ARCHITECTURE.md` — plain-language map of how Icarus is built (the Mac app
  is the face; the cloud is the brain).
- `docs/STRATEGY.md` — build & product strategy: sell the typed brain first, rent
  the commodities, own the moat. Includes the decided stack.
- `docs/COMPETITIVE.md` — competitive landscape: how comparable products were
  built, what to steal, what to avoid.
- `docs/BUILD_ORDER.md` — the phase-by-phase build order; never build the talker
  before the brain.
- `docs/PHASE_1_PLAN.md` — the concrete Phase 1 build: cited answer or honest
  unknown about one GitHub repo, proven by the harness.
- `docs/EVALUATION.md` — how Icarus proves it isn't bluffing; the gates and
  quality dials, plus the disclosed prompt-injection limitation.
- `docs/METRICS.md` — the numbers that tell us we're winning, grouped by what
  they protect (honesty first, then retrieval, experience, trust).
- `docs/WORKFLOWS.md` — the rules of the road for every change (red → green,
  never weaken the eval, scoped edits, report results).
- `docs/DESIGN_VISION.md` — the "Honest Brutalism" design language for the app.
- `docs/UI_UX_BRIEF.md` — UI/UX brief and intent behind the app surfaces.
- `docs/HANDOFF.md` — session handoff: current state, how to run it, what's done
  vs. not, and the gotchas.

## docs/decisions/
- `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md` — the hosting
  model: one unified cloud we operate with per-tenant data isolation.
- `docs/decisions/2026-06-30-organizational-memory-positioning.md` — positioning
  (Icarus is organizational memory; explanation is the wedge) + roadmap.

## docs/plans/
- `docs/plans/2026-06-28-phase-1.md` — the Phase 1 plan.
- `docs/plans/2026-06-28-brick-2-gate-and-writer.md` — gate + writer brick.
- `docs/plans/2026-06-28-brick-3-embeddings.md` — embeddings brick.
- `docs/plans/2026-06-28-brick-4-answer-grading.md` — answer-grading brick.
- `docs/plans/2026-06-28-brick-5-web-demo.md` — web demo brick.
- `docs/plans/2026-06-28-brick-6-recordable-demo.md` — recordable-demo brick.
- `docs/plans/2026-06-28-brick-7-any-repo-ingest.md` — any-repo ingest brick.
- `docs/plans/2026-06-28-brick-8-9-private-repos.md` — private-repos bricks.
- `docs/plans/2026-06-29-free-hosted-providers.md` — free hosted providers (Groq/
  Gemini) plan.
- `docs/plans/2026-06-29-in-app-repo-switcher.md` — in-app repo switcher plan.
- `docs/plans/2026-06-30-github-auth-workflow.md` — GitHub device-flow auth plan.
- `docs/plans/2026-06-30-macos-app.md` — the macOS app plan (A0–A6).
- `docs/plans/2026-07-02-security-hardening.md` — the security-audit fix plan
  (server threading, auth, ingest limits, key hygiene, per-commit gate).
- `docs/plans/2026-07-02-full-app-shell.md` — the full windowed app-shell plan
  (five surfaces, all wired to real data, no fabricated values).

## evals/ (the Phase 1 eval harness — Python stdlib only)
- `evals/__init__.py` — package docstring: the harness is the product's
  conscience (cited-answer correctness + honest abstention).
- `evals/corpus.py` — the `Chunk` dataclass and `load_chunks` (read the committed
  corpus, one evidence unit per line with a citation ref).
- `evals/ingest.py` — one-time corpus generator from a public repo (PRs, linked
  issues, Python source) → `corpus/chunks.jsonl` + `meta.json`. Subprocess
  timeouts, per-file/total size caps, and a `code_dir` path-traversal guard.
  Needs `gh` + `git`.
- `evals/corpus_meta.py` — `write_meta`/`load_meta` for the self-describing corpus
  provenance the demo reads for citation links.
- `evals/retriever.py` — `LexicalRetriever`, a stdlib BM25 keyword retriever, plus
  a `tokenize` helper.
- `evals/provider.py` — the `Provider` abstraction for the rented writer/judge:
  `GroqProvider`, `GeminiProvider` (key in the `x-goog-api-key` header, not the
  URL), `OpenRouterProvider`, `StaticProvider`; `make_provider` factory + 429
  backoff. Stdlib `urllib`; keys from env.
- `evals/env_file.py` — `load_env_file`: stdlib loader that reads a gitignored
  `.env` into `os.environ` without overriding real env vars.
- `evals/synth.py` — `build_prompt`, the strict cite-or-abstain prompt (also tells
  the writer to treat evidence as data, not instructions).
- `evals/gate.py` — the deterministic honesty gate: emits an answer ONLY if it
  parses, claims "answer", has prose, and cites ≥1 retrieved ref; else "unknown".
- `evals/judge.py` — the answer-correctness judge (quality dial, NOT a gate):
  `build_judge_prompt`, `parse_verdict` (fails safe to "incorrect"), `Judge`.
- `evals/pipeline.py` — the `Result`/`Pipeline` contract, plus `StubPipeline`,
  `RetrievalPipeline`, and `GatedPipeline` (retrieve → writer → gate → Result).
- `evals/grader.py` — deterministic grading against the labelled set: the two
  honesty gates + quality dials; optional `judge` fills answer_correctness.
- `evals/run.py` — CLI that runs the eval board and prints it (loads `.env`
  first); exits non-zero only when a gate breaks. `--pipeline/--writer/--judge`.
- `evals/test_corpus.py` — `load_chunks` parses JSONL into `Chunk`s (tolerates
  blank lines).
- `evals/test_corpus_meta.py` — `write_meta`/`load_meta` round-trip; missing meta
  returns None.
- `evals/test_ingest_args.py` — ingest CLI defaults/overrides, commit resolution,
  and `_safe_code_dir` path-traversal rejection.
- `evals/test_ingest_repo.py` — `ingest_repo` writes chunks + meta and returns
  counts (network fetches monkeypatched; offline).
- `evals/test_ingest_smoke.py` — skippable live ingest of a tiny public repo
  (`RUN_INGEST_SMOKE=1`).
- `evals/test_env_file.py` — the `.env` loader: parses KEY=VALUE, doesn't override
  real env, tolerates comments/quotes/export, no-ops on a missing file.
- `evals/test_retriever.py` — tokenization + BM25 ranking, truncation, zero-score
  dropping, deterministic tie-breaking.
- `evals/test_pipeline.py` — `RetrievalPipeline` populates `retrieved` yet still
  abstains.
- `evals/test_provider.py` — `StaticProvider` queuing, no-key errors, the retry
  budget, and the Gemini key going in the header not the URL.
- `evals/test_synth.py` — the prompt includes question/refs/text, offers the
  unknown path, truncates long chunks.
- `evals/test_gate.py` — the gate passes grounded answers and fails safe to
  abstention on everything ambiguous.
- `evals/test_gated_pipeline.py` — `GatedPipeline` end to end with a
  `StaticProvider` (answer, abstention, forced-unknown bluff).
- `evals/test_grader.py` — the harness conscience: gates hold for an honest
  abstainer/oracle and fire for a bluffer.
- `evals/test_retrieval_eval.py` — end-to-end red→green: retrieval recall@k rises
  without dropping a gate (skips without the corpus).
- `evals/test_gated_eval.py` — real-model proof: citation correctness > 0 with
  both gates 100% (skips without a key/corpus).
- `evals/test_reference_answers.py` — every answerable question has a
  `reference_answer`, every unanswerable one has none.
- `evals/test_judge_prompt.py` — `build_judge_prompt` includes question/reference/
  candidate and truncates long candidates.
- `evals/test_judge.py` — `parse_verdict` + `Judge` over a `StaticProvider`.
- `evals/test_answer_correctness.py` — `grade(..., judge=…)` scores answer
  correctness and leaves the gates untouched; PENDING without a judge.
- `evals/test_answer_correctness_eval.py` — real-model proof: answer correctness
  > 0 while both gates stay 100% (skips without a key/corpus).
- `evals/test_free_hosted_eval.py` — real-model proof on the free hosted stack
  (Groq writer + Gemini judge).

## evals/ data files
- `evals/phase1_questions.json` — the verified labelled question set (pinned to
  `simonw/llm` @ `94769b8`): labels, gold citations, notes, reference answers.
- `evals/corpus/chunks.jsonl` — the committed corpus (one JSON object per line).
- `evals/corpus/meta.json` — provenance for the committed corpus.

## demo/ (the Phase 1 web face — stdlib only, packaging over the gated brain)
- `demo/__init__.py` — package docstring: the minimal local face over the gated
  brain; imports `evals/`, changes no brain code.
- `demo/links.py` — `ref_to_url`, mapping a `source:ref` citation to its GitHub
  URL; unknown/malformed → None.
- `demo/payload.py` — `build_payload`, turning a `Result` into the page JSON.
- `demo/library.py` — `Library`: the active-repo state + live `GatedPipeline`;
  `connect_sync` reuses a cache or ingests once, single-flight and thread-safe,
  serving a generic error on failure (never the raw command line).
- `demo/auth.py` — bearer-token auth for the brain: `bearer_token`,
  `GitHubTokenVerifier` (validates against GitHub `/user`, cached, fail-safe),
  and `StaticTokenVerifier` (test double). Enforced only in the auth mode.
- `demo/server.py` — stdlib `http.server` over a `Library`: `make_handler`
  (loopback Host/Origin guard, 64KB body cap, optional GitHub bearer on
  `/ask`+`/connect`), `resolve_provenance`, `serve` (ThreadingHTTPServer, loads
  `.env`). `GET /`,`/health`,`/status`; `POST /ask`,`/connect`.
- `demo/index.html` — the single-page UI: question box, cited-answer card, the
  honest-unknown hero, and an `owner/repo` connect control; vanilla `fetch`.
- `demo/test_links.py` — `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — `build_payload` for answer and honest-unknown shapes.
- `demo/test_auth.py` — the bearer helpers: `bearer_token` parsing and the GitHub
  verifier's cache + network-error fail-safe (offline).
- `demo/test_library.py` — the `Library`: default repo, cache-hit vs. ingest,
  single-flight concurrent connect, and generic (non-leaking) ingest errors.
- `demo/test_server.py` — routing against a stub library, plus the Origin guard
  (403), body cap (413), bearer-auth gate (401), concurrency, and index.html
  smoke checks (real hooks present, no fabricated data).
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline; skips
  without a key or the corpus.

## mac/ (the macOS app — SwiftPM, SwiftUI + AppKit)
- `mac/.gitignore` — ignores SwiftPM build artifacts and the assembled `.app`.
- `mac/Icarus/Package.swift` — SwiftPM manifest: `IcarusKit` (testable logic) +
  `Icarus` (the app), dependency on KeyboardShortcuts.
- `mac/Icarus/Package.resolved` — pinned dependency versions.
- `mac/Icarus/Icarus-Info.plist` — bundle Info.plist (mic + speech usage strings)
  assembled into `Icarus.app` for TCC.
- `mac/Icarus/scripts/bundle.sh` — wraps the SwiftPM binary into an ad-hoc-signed
  `Icarus.app` (required for microphone access).

### mac/Icarus/Sources/IcarusKit (UI-free, unit-tested)
- `Models.swift` — the brain's JSON contract: `Verdict`, `Citation`,
  `AskResponse`, `RepoStatus`, and `IndexCounts` (real `/status` counts).
- `BrainClient.swift` — the HTTP client to the brain (`/ask`,`/connect`,`/status`);
  attaches an `Authorization: Bearer` from a shared token; injectable URLSession.
- `GitHubAuth.swift` — OAuth Device Flow: device-code request + the pure
  `parsePoll` outcome parser (fails safe, never fakes a token).
- `TokenStore.swift` — the token-store protocol + an in-memory test double.
- `SpeechRecognizer.swift` — streaming speech-to-text protocol + a stub.
- `VoiceModel.swift` — `@Observable` push-to-talk orchestrator: live
  `partialTranscript`, silence → empty → not emitted.
- `AskHistory.swift` — the real in-session ask record (most-recent-first,
  `unknowns` filter, `citedRate` nil until the first ask); powers the shell.
- `ShellNav.swift` — `ShellSurface`, the five sidebar surfaces + their titles.

### mac/Icarus/Sources/Icarus (the executable app)
- `IcarusApp.swift` — `@main`; no window, delegates to `AppDelegate`.
- `AppDelegate.swift` — app wiring: activation policy, menu-bar item, hotkey,
  push-to-talk, shared models (auth/connect/voice/history/status), and the
  primary shell window (setup is folded into its Home gate).
- `OverlayController.swift` — owns the ⌘⇧I ask overlay + ask/voice/speak wiring;
  records each ask into the shared `AskHistory`.
- `FloatingPanel.swift` — a translucent, non-activating, chromeless `NSPanel` that
  floats above other apps (hidden transparent title bar).
- `OverlayView.swift` — the overlay UI: question, cited answer, honest unknown.
- `AskModel.swift` / `AuthModel.swift` / `ConnectModel.swift` — `@Observable`
  state for asking, GitHub auth, and repo connect (shared via `AppDelegate`).
- `KeychainTokenStore.swift` — stores the GitHub token in the login Keychain
  (`WhenUnlocked`); the real `TokenStore`.
- `IconArt.swift` — the Signal Spine app icon + menu-bar glyph in Core Graphics.
- `Theme.swift` — the "Quiet Native Memory v2" tokens + shared views
  (`MonoLabel`, `CitationChip`, `PrimaryButton`, `FlowLayout`).
- `AppleSpeechRecognizer.swift` — on-device `SFSpeechRecognizer` + `AVAudioEngine`
  (audio never leaves the Mac; fails rather than using Apple's servers).
- `PushToTalkMonitor.swift` — hold Right Option (⌥) to talk via a global
  `.flagsChanged` monitor.
- `Speaker.swift` — `AVSpeechSynthesizer`; speaks the answer and the honest
  unknown, with barge-in.

### mac/Icarus/Sources/Icarus/Shell (the full app shell — the primary window)
- `ShellView.swift` — sidebar + content router across the five surfaces (passes
  auth/connect through to Home for its setup gate).
- `SidebarView.swift` — brand mark, nav rows, and the real connected-repo footer
  (the real macOS traffic-lights float over its top; no decorative dupes).
- `HomeView.swift` — until a repo is connected, the `SetupView` gate; once ready,
  the dashboard: hero (real ⌥ trigger), metrics (real `/status` counts + session
  cited-rate), recent asks, and the proof drawer — all real/honest data.
- `SetupView.swift` — the in-shell setup gate (Sign in with GitHub → connect a
  public repo), driving the shared `AuthModel`/`ConnectModel`. Replaces the old
  separate onboarding window.
- `ShellSurfaces.swift` — Decision history, Unknowns, Privacy boundary (true
  claims), and Ask-by-voice surfaces, with honest empty states.
- `ShellComponents.swift` — shared shell views (`MarkView`, `NavRow`,
  `VerdictPill`, `HistoryRow`, `ShellCard`).
- `StatusModel.swift` — polls `/status` for the real repo + index counts.
- `MainWindowController.swift` — hosts the shell as the primary window with a
  chromeless (transparent, full-size-content) title bar.

### mac/Icarus/Tests/IcarusKitTests
- `GitHubAuthTests.swift` — device-code decode + `parsePoll` outcomes (fail-safe).
- `ModelsTests.swift` — decoding the brain's JSON, including real `IndexCounts`.
- `TokenStoreTests.swift` — the in-memory token store's save/load/delete.
- `VoiceModelTests.swift` — push-to-talk states; silence → no question.
- `AskHistoryTests.swift` — record order, unknowns filter, cited-rate (nil first).
- `BrainClientTests.swift` — the bearer token is sent when present, omitted when
  absent (URLProtocol stub).
- `ShellNavTests.swift` — the five surfaces' order, titles, and stable ids.

## .claude/agents/ and .codex/agents/
- `.claude/agents/opus-architect.md` — the opus-architect agent (principal
  architect / adversarial reviewer).
- `.claude/agents/sonnet-test-writer.md` — the sonnet-test-writer agent
  (adversarial test writer / bounded implementer).
- `.codex/agents/opus-architect.toml` / `.codex/agents/sonnet-test-writer.toml` —
  the same two agents defined for the Codex tooling.
