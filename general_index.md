# Icarus — General Index

A fast map of every tracked file in the repo with a 1–2 line description.
Grouped by directory. Regenerate this after any structural change (adding,
removing, or renaming files). For class/function-level detail see
`detailed_index.md`.

## Repo root
- `CLAUDE.md` — Claude Code's project instructions and working context.
- `AGENTS.md` — canonical shared engineering constitution: collaboration rules,
  honesty/trust boundaries, codebase entry path, workflow, and verification.
- `CODEX.md` — thin Codex-specific adapter covering collaboration style, task
  startup, tool conventions, verification/reporting, and instruction drift.
- `README.md` — the pitch and one-paragraph overview of Icarus plus its honesty
  promise.
- `general_index.md` — this file: every tracked file + a short description.
- `detailed_index.md` — every class/function in the `evals/` package + its
  description, drawn from real docstrings/signatures.
- `.gitignore` — ignored paths (secrets/`.env`, caches, build artifacts); the
  committed `.env.example` is explicitly un-ignored.
- `.env.example` — committed template (NO real keys) to copy to a gitignored
  `.env`; separates the one serving credential from optional eval-provider keys.
- `requirements.txt` — the sole Python dependency: `fastembed` (local, free,
  offline semantic-retrieval embeddings; ONNX Runtime + tokenizers, no PyTorch). Lazily
  imported, so everything else runs pure-stdlib without it. Install into a venv.

## Coding-agent integration
- `.mcp.json` — Claude Code project registration for the read-only Icarus MCP
  server shipped inside the installed Mac app; no credential lives in project
  configuration.
- `.cursor/mcp.json` — Cursor IDE/CLI project registration for the same stdio
  adapter.
- `.codex/config.toml` — Codex project registration for the same stdio adapter,
  using the installed app binary rather than a checkout-specific virtualenv.

## Cloud deployment (host the brain on Azure Container Apps)
- `Dockerfile` — container for the brain: `python:3.12-slim` + `git`/`gh` (for
  repo-switch ingest), non-root UID 1000 (required by some hosts, harmless on
  others), `RUN python -m demo.warm_cache` bakes the fastembed model + default
  corpus's embeddings in at build time (boots warm on any host), runs
  `python -m demo.server`; binds `0.0.0.0`/`$PORT`. The image runs on Azure
  Container Apps (live) or a local Docker daemon.
- `.dockerignore` — keeps the image slim (only `evals/`+`demo/`+committed corpus;
  excludes local data/worktrees, tooling, clients, docs, `.git`, caches, `.env`).

## Security automation (per-commit + CI)
- `scripts/scan_secrets.sh` — deterministic secrets scan; `--staged` (pre-commit)
  or tracked-files (CI) mode. Exits non-zero on a provider-token or secret-shaped
  hit so it can block a commit/build.
- `scripts/install_hooks.sh` — one-time wire of `core.hooksPath` → `.githooks`.
- `scripts/private_flow_smoke.py` — manual, leak-safe live smoke of the brain's
  PRIVATE-repo HTTP path (/status→/connect→/ask→/disconnect) the Mac app drives;
  token from `GH_BEARER` env (never argv/logs), repo from `ICARUS_PRIVATE_REPO`.
- `scripts/agent_call_audit.py` — counts real `mcp__icarus__*` `tool_use` blocks
  in Claude Code's persisted session transcripts
  (`~/.claude/projects/<slug>/*.jsonl`), because an agent's SELF-REPORT of its
  own tool use has now disagreed with the harness metadata three times (once 6
  reported against 14 actual). The measurement half of the Agent Mode work: any
  claim that a change made agents consult Icarus more must come from this, not
  from asking the agent. Flags a session "directed" if a user message names
  Icarus, biased so the unprompted count under-claims. `--selftest` runs its
  own parser check with no transcripts needed.
- `.githooks/pre-commit` — commit gate: a staged secret hard-blocks; failing
  tests only warn (never block).
- `.github/workflows/security.yml` — CI backstop on push/PR: secrets scan +
  Python suites (evals, demo) + Swift build/test.

## CI/CD — the deploy pipeline (GitLab, NOT GitHub)
The repo has TWO remotes: `origin` (github.com/alankritxghosh/Icarus) and
`gitlab` (gitlab.com/icarus-group4/Icarus). **Deploys run on GitLab.** A
`.github/`-only look at this repo shows just the security workflow and reads
as "there is no deploy automation" — which is how a session on 2026-08-11
came to redeploy the brain by hand. Check `git remote -v` before concluding
anything about CI here.
- `.gitlab-ci.yml` — the deploy pipeline: `secrets-scan` + `tests` (both
  suites) → `build` (docker build + push to ACR; ACR Tasks is disabled on this
  registry, so the runner builds) → `deploy` (`az containerapp update`, then
  polls `/health` until the new revision actually serves) → `package-dmg` (Mac
  app + Sparkle on a SaaS macOS runner; manual, or automatic on an `alpha-*`
  tag; deliberately does NOT sign the appcast — that private EdDSA key stays
  in one login keychain). `deploy` is a MANUAL gate: every revision drops all
  connected sessions and wipes per-user corpora. Gated on `.image_sources`, so
  a docs-only commit cannot offer to deploy an image that was never built.
  Ship a change with `git push gitlab main` then
  `glab ci trigger deploy -R icarus-group4/Icarus -b main`.

## docs/
- `docs/VISION.md` — product vision: one honest organizational-memory brain for
  engineers and their coding agents, preserving the Mac/extension experience
  and the cite-or-unknown boundary.
- `docs/ARCHITECTURE.md` — plain-language map of how Icarus is built (human and
  agent faces over the same cloud brain), including the MCP trust boundary
  (public AND private repos since 2026-08-07; the exposure is transferred to
  whoever configures the client, not verified by Icarus).
- `docs/STRATEGY.md` — build & product strategy: sell the typed brain first, rent
  the commodities, own the moat. Includes the decided stack.
- `docs/COMPETITIVE.md` — competitive landscape: how comparable products were
  built, what to steal, what to avoid.
- `docs/BUILD_ORDER.md` — the phase-by-phase build order; never build the talker
  before the brain, with Phase 1B as the narrow read-only coding-agent face.
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
- `docs/DISTRIBUTION.md` — runbook to share Icarus without an Apple Developer ID:
  host the brain on Azure Container Apps (minimal serving secrets + OAuth
  callback), build the DMG, and pass Gatekeeper once; lists alpha tradeoffs.

## docs/decisions/
- `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md` — the hosting
  model: one unified cloud we operate with per-tenant data isolation.
- `docs/decisions/2026-06-30-organizational-memory-positioning.md` — positioning
  (Icarus is organizational memory; explanation is the wedge) + roadmap.
- `docs/decisions/2026-08-07-engineering-memory-records.md` — accepted first
  closed-loop record path: one human-triggered repository Markdown proposal,
  one branch, one GitHub pull request, never an automatic merge.

## docs/experiments/
Append-only records of measured runs — the evidence base for every Agent Mode
claim. A negative result is kept exactly like a positive one.
- `docs/experiments/PROTOCOL.md` — the rules every Agent Mode experiment
  follows, **one rule per failure that actually happened**, each naming the run
  it cost: tool use is read from transcripts and never from self-report; a task
  is valid only if the bug is proven present at the PINNED commit AND the
  mechanism is a genuine closed-unmerged PR (both checks mechanical, with the
  exact commands); the prediction is registered before launch; inconvenient
  results go in the result, not a footnote; `git remote -v` before any claim
  about repo state. Read before designing a run.
- `2026-08-10-agent-mode-exp-a-run1.md` — Experiment A run 1 (`astral-sh/uv`
  #20477): Icarus inverted a wrong prior (absolute paths were a regression
  inside a PR titled "Preserve absolute/relative paths", not a design choice)
  **and produced the one fabrication** across all four A tasks — a `..`-escaping
  rule that does not exist, over-generalised from two real sources, with every
  citation resolving so the gate passed it.
- `2026-08-10-agent-mode-exp-a-run2.md` — run 2 (#20917, workspace groups no
  longer additive): chosen to test whether run 1's fabrication recurs, with the
  issue naming no PR and labelled `enhancement` so "deliberate" was a live
  answer. Both claims accurate; corrected the prior again.
- `2026-08-10-agent-mode-exp-a-run3.md` — run 3 (#20981, `uv tool run` ignores
  the installed version): designed to test ABSTENTION via a `needs-decision`
  label, and the premise was wrong — Icarus answered, correctly, from a
  maintainer comment. The decisive outcome was "write nothing at all", the
  maintainer considering the behaviour intended.
- `2026-08-10-agent-mode-abstention-test.md` — the property runs 1–3 left
  untested, run against the committed board rather than a live repo: all gates
  100% on `gemini-paid`, so the fabrication was not an abstention failure.
- `2026-08-10-agent-mode-exp-c.md` — Experiment C, Claude Code in VS Code, the
  only run Alankrit drove by hand. Source of the 0-unprompted-calls-in-4-tasks
  result under a strong `CLAUDE.md` nudge, of the transcript-verification method
  (`~/.claude/projects/*.jsonl`), and of two honestly-logged task-selection
  misses that PROTOCOL §2 now prevents.
- `2026-08-10-agent-mode-exp-d.md` — Experiment D, paired within-task control
  vs. Icarus on `astral-sh/uv`, control frozen in writing first. Discloses what
  the design CANNOT measure: the Icarus arm is contaminated by having just read
  the code, so efficiency numbers are not available from it.
- `2026-08-10-agent-mode-exp-d-efficiency.md` — the efficiency half redone with
  two subagents that cannot see each other (control explicitly forbidden every
  `mcp__icarus__*` tool), on uv #20675 — the run where a control agent declared
  a live bug fixed because only the merge was visible.
- `2026-08-10-agent-mode-exp-d-directed.md` — D redone with DIRECTED rather than
  volunteered consultation, two clean clones. The registered prediction was
  wrong: control did better first-principles code reading and would still have
  shipped an 8th duplicate; one directed call surfaced all seven prior attempts
  and flipped the recommendation to "do not write this".
- `2026-08-10-quotation-vs-composition-negative-result.md` — **negative result,
  nothing shipped.** `evals/attribution.py` was built to label sentences by
  lexical overlap with cited chunks, measured against the real recorded cases,
  found ANTI-correlated with truth (a plausible fabrication is assembled from
  the evidence's own words and so scores higher than an honest paraphrase), and
  deleted. Why the per-claim WRITER self-report exists instead.
- `2026-08-10-rejected-attempt-false-positive-rate.md` — the relevance-noise
  measurement behind the tool description's "up to one in three": three runs,
  criterion registered before any hit was seen, and the third run (uv, 5.4× the
  closed-PR pool) contradicting the "no filter needed" conclusion the first two
  supported.
- `2026-08-11-fabrication-recheck-per-claim.md` — proves the shipped per-claim
  self-report does NOT flag the Experiment A fabrication class: the sentence
  reproduced and came back `quoted`, the trusted label. Also the first record of
  a claim resting entirely on a closed-unmerged PR.
- `2026-08-11-agent-mode-exp-c2-plan.md` — C2 registered BEFORE the run per
  PROTOCOL §3: the prediction (0–1 of 4, expected to fail), the four tasks with
  their §2 validation evidence, verbatim prompts fixed in advance, and what
  would make the run invalid.
- `2026-08-11-agent-mode-exp-c2-results.md` — the load-bearing measurement so
  far: rewriting the MCP tool description to trigger on observable events took
  unprompted calls from 0/11 to **4/4** with no nudge, refuting the registered
  prediction; plus the nine-PR tally showing "closed unmerged" meant "already
  done another way" eight times out of nine, and one invalid task whose §2a
  check was inferred from a version string instead of executed.

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
- `docs/plans/2026-07-04-private-repos-per-user-isolation.md` — the private-repo
  scoping doc (hosted, multi-user): per-user library registry, private-safe writer +
  trust interlock, caller-authorized leak-safe PAT ingest, isolation/egress proofs.
- `docs/plans/2026-07-04-private-repos-implementation.md` — the executable
  task-by-task TDD plan for the above: 16 tasks across Bricks A–F with exact code,
  tests, commands, and commits; Brick G (app) outlined.
- `docs/plans/2026-07-06-brick-g-private-repo-ui.md` — Brick G, built: the Mac
  app's private-repo surface (private flag, disconnect, repo persistence across
  launches, client-side lost-connection banner) — historical; the private flag
  was retired from the current public-repository alpha.
- `docs/plans/2026-07-06-tester-feedback-deeper-comprehension.md` — turns the nine
  tester remarks + the refined north star ("understand code from the code itself,
  answer any phrasing, JARVIS per developer") into a probe-first build order: Brick
  0 (code-comprehension eval set), A (whole-codebase ingest), B (PR/Issue coverage),
  C (semantic retrieval), Q (query-understanding: framing/grammar/spelling), D
  (line-select explain), S (structural comprehension, deferred-gated), E (richer
  "why"). Governed by the what/how-vs-why honesty boundary; remark 9 (writing code)
  stays off the table.
- `docs/plans/2026-07-10-hugging-face-spaces-migration.md` — plan to move the
  hosted brain off Render's free tier (0.1 CPU, verified the actual root cause
  of a live incident: a 216-chunk private-repo connect never finished inside a
  15-minute embed timeout) onto Hugging Face Spaces' free Docker tier (2 vCPU/
  16GB, verified). Enumerates every real touchpoint (Dockerfile non-root user,
  hardcoded Render URLs in extension/, GitHub OAuth callback, docs) found by
  grep, not guessed; task-ordered smallest-loop-first. Not started.
- `docs/plans/2026-08-08-investigation-engine.md` — the investigation engine:
  what the repo does today (read, not assumed), why one-shot retrieve→write→gate
  blocks multi-step investigation, and the seven-phase plan to add a bounded
  loop over five primitives (retrieve/inspect/trace/compare/verify) with an
  explicit state, deterministic confidence and stopping, and per-claim
  re-verification through the EXISTING gate. Phases 1+3 (`evals/entities.py`,
  `evals/investigation.py`) are built; 2 and 4–7 are not.
- `docs/plans/2026-08-07-engineering-memory-loop-extension-bridge.md` — executable
  red→green plan for Memory Gaps, reviewed memory records, removal of two shell
  sections, the Mac-native Chrome bridge, and the adversarial extension matrix.

## evals/ (the Phase 1 eval harness — Python stdlib only)
- `evals/__init__.py` — package docstring: the harness is the product's
  conscience (cited-answer correctness + honest abstention).
- `evals/corpus.py` — the `Chunk` dataclass, `load_chunks` (read the committed
  corpus, one evidence unit per line with a citation ref), and
  `chunk_covers_lines(chunk, path, start, end)` (Brick D: does a chunk cover a
  GitHub line selection? Handles both a windowed `#Lstart-Lend` ref and a
  whole-file ref with no suffix -- the committed corpus's actual shape).
- `evals/ingest.py` — corpus generator from a public **or private** repo (PRs,
  linked issues, source code) → `chunks.jsonl` + `meta.json`. Code chunking is
  NOT Python-only — `_EXTENSION_SOURCES` maps Python, JS/JSX/MJS/CJS, TS/TSX,
  Go, Rust, Java, Ruby, C/C++, **Objective-C/C++ (`.m`/`.mm`)**, Swift, Kotlin,
  PHP, C#, Scala, and Shell to "code" (`.md`/`.rst`/`.txt` → "doc",
  `.yaml`/`.yml`/`.toml`/`.cfg`/`.ini`/`.sql`/`.gradle`/`.podspec` → "config").
  `.json` is deliberately EXCLUDED (2026-07-17) — on a real React Native app it
  is dominated by Xcode asset catalogs and i18n locale bundles, which would skew
  BM25/IDF corpus-wide; allowlist the filename if `package.json` ever matters. Subprocess timeouts, per-file (512KB) + total-byte (100MB) + total-
  chunk (50k, bounds lexical stage-1 memory on a hostile many-short-lines repo)
  caps that log to stderr when they truncate, a `code_dir`
  path-traversal guard, and an optional caller `token` threaded leak-safe into
  `git`/`gh` subprocess **env** (`_git_env`/`_gh_env` — never argv, never the
  clone URL, never logged). Needs `gh` + `git`. `chunk_text`'s windowing is
  character- as well as line-aware (2026-07-17 fix): a single PHYSICAL line
  that alone exceeds the char budget (a machine-generated file with one huge
  object-literal line -- measured live up to ~250,000 chars) is truncated
  in place with a visible marker and a stderr log, rather than shipped whole
  -- found because the prior floor-of-one-line-of-progress guarantee only
  ever checked MULTI-line windows, never a single oversized line by itself.
  `_chunk_code` (T4) dispatches a CODE file to `ast_chunk`/`ts_chunk` behind
  `ICARUS_AST_CHUNKING` (env flag, default OFF -- the committed board and
  every existing corpus keep chunking unchanged unless deliberately turned
  on); `.py` → `ast_chunk`, the React Native language set → `ts_chunk`,
  everything else (doc/config sources, `.h`, Go/Rust/Ruby/...) stays on
  `chunk_text`. Both chunkers are imported lazily INSIDE the dispatcher, not
  at module level -- required, not stylistic: both import `chunk_text`/
  `_CHUNK_MAX_CHARS` FROM this module, so an eager top-level import would be
  circular. Verified end-to-end against a real cloned repo (wix/react-native-
  navigation's `ios/`): 1,624 real chunks, `.mm` files split from 1 whole-file
  chunk to per-method chunks (e.g. `RNNCommandsHandler.mm` 1→19), `.h` stayed
  on `chunk_text` unchanged.
  `fetch_pr_diff(repo, number)` live-fetches ONE pull request's actual
  before/after hunks as a `diff:<number>` chunk -- what the code BECAME, which
  nothing indexed records (a `pr:` chunk lists filenames with +/- counts; a
  `commit:` chunk holds only its message). Deliberately NOT indexed, for the
  same reason commits are not: thousands of diffs would dwarf every other kind
  of evidence and swamp BM25's IDF. An exact-identifier lookup, bounded to
  `_REF_DETAIL_MAX_CHARS` with a VISIBLE truncation marker, leak-safe token via
  `_gh_env`, fail-safe to None. `diff` is a known source in `gate.py` (its
  citations resolve like any other) and deliberately NOT a rationale source --
  a "why" resting only on a diff still abstains, since a diff never records why
  anyone chose it. `_pr_or_issue_text` also now records GitHub's own
  `closingIssuesReferences` as a `Linked issues: #N` line -- fetched since the
  beginning and thrown away until 2026-08-08, which left an issue linked only
  through GitHub's interface invisible; written in the shape the entity index's
  mention regex already reads, so nothing downstream needed changing, and a
  pull request closing nothing produces byte-identical text to before.
  `fetch_commit_detail(repo, sha)` live-fetches ONE commit (message, author,
  per-file diff) as a `commit:<full-sha>` chunk — commits are deliberately NOT
  indexed (a real repo has 10k-1M; they'd swamp the 50k cap and BM25's IDF), so
  a named SHA is resolved on demand exactly like `fetch_ref_detail`'s `#N`.
- `evals/ast_chunk.py` — `ast_chunk(text, ref_prefix)`: AST-aware code chunking,
  splitting Python at function/class boundaries (stdlib `ast`, NO new
  dependency) instead of `ingest.chunk_text`'s fixed 300-line windows. Exists
  because the embedder (`bge-small-en-v1.5`) truncates at 512 tokens while a
  real 300-line window measures p50 ~2,234 -- so semantic retrieval silently
  read ~the first quarter of every window. Same contract/ref format as
  `chunk_text`; falls back to it on non-Python, syntax errors, or a module with
  no top-level defs, so it can never do worse. Emits a scope header (imports +
  enclosing class) per chunk and keeps module/class-level constants as evidence.
  **Proven, NOT yet wired into `fetch_code`** -- see docs/HANDOFF.md.
- `evals/ts_chunk.py` — `ts_chunk(text, ref_prefix, ext)`: tree-sitter-backed
  AST chunking for the React Native language set (`.ts`/`.tsx`/`.js`/`.jsx`/
  `.mjs`/`.cjs` via the `tsx` grammar -- measured 96% fewer parse errors than
  `javascript` on real Flow-typed RN code; `.mm`/`.m`/`.java`/`.kt`).
  Same contract as `ast_chunk.ast_chunk`. Recursive definition walk +
  export/const-arrow unwrapping (measured: `export const Foo = () => {}`
  outnumbers `function Foo(){}` ~30:1 in real code) + a size-based safety
  valve (any emitted span over 2x `chunk_text`'s window, by LINE COUNT **or**
  CHAR COUNT, gets re-windowed via `chunk_text` itself, checked against the
  final emitted text including its scope header -- found live: a Jest
  `describe()` block, invisible to the definition scheme, produced a single
  ~950,000-char chunk without the line check; a 125-line file with one
  ~250,000-char generated line needed the char check too, since line count
  alone never trips on a pathologically long single line). `.h` deliberately
  unsupported (neither the `c` nor `objc` grammar parses real RN headers
  cleanly). Lazy tree-sitter import, ERROR-rate gate, falls back to
  `chunk_text` whenever untrustworthy. **Proven (27 tests, T1+T2 of
  docs/plans/2026-07-17-ast-chunking-all-languages.md; verified max chunk
  size across 17,657 real RN files is 19,991 chars), NOT yet wired into
  `fetch_code` and no per-language recall eval yet (T3/T4 pending).**
- `evals/index_facts.py` — `build_index_chunk(chunks)`: Icarus's OWN index as one
  citable evidence chunk (`index:overview`, source `index`), plus the shared
  `language_for(path)` extension→language table (`demo/repo_map.py` imports it,
  so a cited answer and the map can never disagree about a file's language).
  Exists because every other evidence chunk is something a PERSON wrote, which
  left a class of true statements Icarus could not make: nobody writes "this
  project is in TypeScript" in a doc — it is a property of the FILES. Found
  live 2026-08-06 on muxinc/media-chrome, where "what coding languages does the
  codebase contain" returned "No one wrote this down" while `/map` had already
  computed the answer and the tour had rendered it (the word "languages"
  lexically matched `docs/src/languages.ts`, an i18n file about HUMAN
  languages). Deliberately NOT a keyword router — the index is offered as
  ordinary evidence on every ask, so any phrasing retrieval routes to it can be
  answered and cited. Honesty boundary: the text states only measured counts and
  is pinned against gate.py's REAL `_RATIONALE_MARKERS` list, because an earlier
  draft ending "...they say nothing about intent" made a DISCLAIMER of intent
  register as a statement of one (substring `intent`), which would have let a
  "why was TypeScript chosen?" ground on a file listing. `index:` is not a
  rationale source and `demo/links.ref_to_url` gives it no URL.
- `evals/test_index_facts.py` — the chunk's contract: distinct FILES counted (not
  chunks), languages by file count, determinism under reordering, empty corpus
  yielding None rather than asserting zeroes, purity (`open`/`socket` patched to
  raise), and the two honesty guards (never trips `_states_reason`, never a
  rationale `_source`) checked against gate.py's real rules, not a hand-copy.
- `evals/test_index_evidence_wiring.py` — the chunk reaching the writer without
  disturbing anything measured: appended LAST so `retrieved[:k]` (and therefore
  every recall@k number in the repo) is byte-identical, real retrieval order
  otherwise untouched, a citation to it grounds, a "why" grounded only on it is
  still forced to unknown, `.explain(neighbors=False)` gets no index either (the
  onboarding README step's answer-from-this-location-alone guarantee), and an
  unresolvable location stays unknown rather than being answered with a
  repo-wide file listing.
- `evals/entities.py` — `build_entity_index(chunks, structure=None)`: the
  relationships between repository entities, DERIVED from chunks already in
  memory (pure, ~50ms over the 3,051-chunk committed corpus) — the third member
  of the `repo_map.py`/`structure.py` family and the traversal layer the
  investigation engine walks. Edges: `linked_issues`/`mentioned_by` (`#N` in a
  PR's own text, lookbehind-guarded so `owner/repo#372` is never a local link),
  `changed_files` (ingest's `Files changed (N):` line, anchored to a line start
  so a comment quoting it yields nothing), `commits` (the `(#400)` squash
  subject, FIRST line only — a body citing another PR is not membership),
  `subsequent_prs` (later-numbered PR touching a shared file: co-occurrence,
  never causation), and `dependents`/`dependencies` delegated to
  `demo.structure.build_structure` (passed IN — `demo` depends on `evals`, never
  the reverse). **Every edge names the indexed chunk whose literal text proves
  it**, and a dependency edge is matched to the importing file's own window that
  names the import — dropped rather than cited to lines that do not contain it.
  A relationship with a FILE targets its PATH, not a window: fanning across
  windows turned 30 real import edges into 56,056 emitted ones on the committed
  corpus, and picking one window would guess which part of the file the
  relationship concerns. `chunks_for(path)` expands it. Verified: 250 sampled
  real edges, 0 unverified. Disclosed ceilings in `limitations`.
- `evals/test_entities.py` — the index's contract, weighted toward what must NOT
  be emitted: foreign-repo `#N`, an unindexed number, a PR restating its own
  number, a commit body quoting a PR, a well-formed `Files changed` line quoted
  inside a comment (an earlier draft of this one was VACUOUS — `_FILE_ENTRY`
  rejected it before the anchor was reached, so it passed with the anchor
  removed), an import no indexed window shows, plus determinism, purity
  (`open`/`socket` patched to raise) and no score/rank field on any edge.
- `evals/investigation.py` — the investigation STATE and every rule a model must
  not make: `classify_support` (explicit/strong/weak/unsupported, computed from
  `gate._states_reason` and `gate._source` so it cannot drift from the honesty
  gate), `score_hypothesis` (only VERIFIED claims count; evidence both ways is
  reported as partial, never silently resolved), `Step` (id derived from the
  call itself, so duplicate detection is identity not similarity), `Budget`
  (hard ceilings that name which one stopped a run) and `Investigation`
  (subject/claims/evidence/contradictions/trail + `should_stop`, whose
  diminishing-returns rule is measured on whether new REFS appeared, never on a
  model saying it is satisfied). Holds refs, never chunk text. Per
  `docs/plans/2026-08-08-investigation-engine.md`; the full loop and probes are
  built and served by `/investigate`.
- `evals/probes.py` — the five investigation primitives as THIN adapters over
  what already exists: `retrieve` (the pipeline's own hybrid retriever — never a
  second ranking that could disagree with `/ask`), `inspect` (indexed chunk,
  else the live `fetch_ref_detail`/`fetch_commit_detail` fetchers `.answer()`
  already uses; a bare path reads that file's windows, bounded and reported),
  `trace` (evals/entities.py — evidence is the chunk PROVING the edge, targets
  come back as `discovered` and are deliberately NOT read, so discovery stays
  cheap and wide while reading stays expensive and narrow), `compare` (real
  per-file diffs via a live commit fetch on the commits a PR carries; falls back
  to the indexed message, and honestly finds nothing when a repo records no
  commit→PR link) and `verified_citations` / `verify` (evals/gate.py verbatim —
  the reader retains only the gate's canonical refs, never a raw model list).
  `run_round` runs independent probes on a
  thread pool (all I/O bound) and returns results in STEP order; a failing probe
  is a step that found nothing and says so, never an exception into the loop.
- `evals/test_probes.py` — 33 offline tests: retrieval delegated not
  reimplemented, a live fetch deciding the KIND (`pr:6952` returning
  `issue:6952`), the caller's token reaching the fetch, trace discovering
  without reading, compare refusing a non-PR and disclosing its commit bound,
  and `verify` proven to be the real gate (self-disclaiming prose refused
  despite a perfectly resolving citation).
- `evals/context_package.py` — `build_context_package`: Experiment B's `icarus.context(task)` (docs/HANDOFF.md's Agent Mode entry). Pure reshaping of ALREADY-gated outputs into structured pre-implementation context -- NO new retrieval, NO new model call, NO new honesty logic. `architecture`/`dependencies` come straight from `demo/structure.build_structure` (pure, deterministic); `decisions`/`unknowns`/`citations` come from an ordinary `evals/investigator.py` run through the SAME gate `/ask` and `/investigate` use; `risks` are pull requests already tried and refused for related work (`evals/attempts.rejected_attempts`, computed over EVERYTHING the investigation gathered, not just what the final answer cited); `constraints` are disclosed limits on the context itself (budget exhaustion, unanalysed languages, unresolved imports), never invented engineering constraints about the target codebase. Deliberately DROPS `symbols` from the original brief's schema -- nothing extracts symbol-level information cheaply and honestly today, and a permanently-empty field would be worse than a documented omission.
- `evals/test_context_package.py` — 18 tests weighted toward what must NOT leak in: a WEAK claim (code alone) is not a `decision`, an unverified claim is not a `decision`, a gathered-but-uncited rejected PR still appears as a `risk`, `citations` (from the gated result) stays narrower than `prs`/`issues` (everything gathered), and `symbols` never appears as a key.
- `evals/investigator.py` — the loop: subject bound deterministically from the
  question's own refs (reusing `pipeline`'s regexes, so "PR 400" means the same
  thing here as in `/ask`), fixed opening seeds, then adaptive rounds of
  probe → read → verify → classify → score → stop. A model is consulted at
  exactly three points (plan, read, synthesize) and every step it proposes is
  validated against a closed vocabulary AND that primitive's exact argument
  schema (`_STEP_SCHEMA`) — an unknown primitive, an argument belonging to a
  different primitive, an unknown edge, an invented ref, or a non-positive /
  boolean / absurd `k` is DROPPED, never coerced into something runnable. `k` is
  additionally clamped to `probes.MAX_RETRIEVE_K` in the probe itself, since
  seeds reach it without passing the validator.
  `_clip_to_budget` drops the lowest-ranked WHOLE pieces of a round's evidence before any of it
  enters state, `texts` or a prompt (never sliced — half a chunk is text nobody
  wrote) and the clip is disclosed as an unknown rather than applied silently.
  `conclude` writes the answer from verified findings and returns an ordinary
  `Result`, so every existing renderer works unchanged; it faces the FULL gate
  with the real question, so nothing reaches a reader having passed a weaker
  check than `/ask` applies.
- `evals/test_investigator.py` — 34 offline tests with a scripted provider,
  weighted toward what a model must not be able to do: run a primitive outside
  the vocabulary, smuggle an argument through, cite evidence nobody retrieved
  (isolated per layer — gate and classifier each proven to refuse alone), score
  its own confidence, declare its own hypothesis true, or outlast the budget.
  Plus the live-found stop bug: a run that ended after one round calling an
  untested hypothesis "decided".
- `evals/investigation_grader.py` — grading an INVESTIGATION, not just an
  answer. Four gates, each a different way of lying: **groundedness** (the
  answer's citations were retrieved), **claim_groundedness** (every PUBLISHED
  finding cites evidence the investigation actually holds — a finding is shown
  as a receipt, and one citing something nobody gathered is a receipt for
  nothing), **explicit_cites_rationale** (no finding labelled `explicit` unless a
  chunk it cites is a rationale-bearing source whose text records a reason —
  RECOMPUTED from the evidence text via `gate._states_reason`/`_source`, never
  read off the label. Scope is deliberately narrow: it proves the CLASS matches
  the evidence, NOT that the recorded reason is the reason for that finding.
  Marker matching cannot tell "changed because logging was noisy" apart from a
  finding about scalability citing it; arbitrary semantic entailment stays
  writer-reliant per AGENTS.md, and the published wording says only what was
  cited), and **abstention_recall**. Quality dials: citation correctness, hop recall (did it
  reach evidence several relationships away?), abstention precision, step
  efficiency, duplicate steps. Takes a `run(question)` callable rather than a
  pipeline, so the harness's own conscience can be tested offline.
- `evals/investigation_questions.json` — 8 hand-verified questions over the
  committed `simonw/llm` corpus. Every gold ref was read in `chunks.jsonl`
  before it was written down. The multi-hop case (`pr:1525` → `issue:1523` →
  `code:llm/embeddings_migrations.py` → `pr:1572`) is real distributed evidence;
  the four unanswerable ones are reused verbatim from `phase1_questions.json`,
  since a proven-unrecorded question beats inventing one and hoping.
- `evals/test_pr_diff.py` — `fetch_pr_diff` offline (stubbed subprocess): real
  hunks, the token never reaching argv, a huge diff truncated WITH a marker, an
  empty diff returning None rather than an empty chunk, every failure mode
  failing safe; plus the `diff:` source's contract — it resolves through the
  gate, links to the pull request's files view, and is NOT recorded rationale
  (a "why" grounded only on a diff abstains). Also the `Linked issues:` line:
  it makes the entity index see an exact link, and a pull request closing
  nothing is byte-identical to before.
- `evals/test_investigation_grader.py` — the harness's conscience, always run,
  no model or corpus: each gate tested twice, once against an honest
  investigator and once against a bluffer built to break exactly that gate —
  including the dangerous one (a real citation, a real finding, and a strength
  the evidence does not earn, which groundedness passes happily).
- `evals/test_investigation_eval.py` — the LIVE board (self-skips without
  `GEMINI_PAID_API_KEY`/fastembed/corpus) plus always-run regression tests that
  `/ask` is untouched and every gold ref still exists. Measured 2026-08-08 on
  the real pipeline: **all four gates 100%**, citation correctness 75%, hop
  recall 87.5%, abstention precision 80%, mean 6 steps, 0 duplicates.
- `evals/test_investigation.py` — the state's contract: one source cited twice
  is not corroboration, code alone is never explicit, a citation to unretrieved
  evidence may only LOWER support, an unverified claim cannot support a
  hypothesis, budget exhaustion outranks looking finished, and the gate-alignment
  pins that keep confidence speaking the honesty gate's language.
- `evals/corpus_meta.py` — `write_meta`/`load_meta` for the self-describing corpus
  provenance the demo reads for citation links. `write_meta` also stamps a
  `"chunking"` field (`"chunk_text"` or `"ast"`, default `"chunk_text"` so
  existing callers don't need updating) -- T6 of docs/plans/2026-07-17-ast-
  chunking-all-languages.md, read by `demo/library.py`'s staleness check so a
  corpus chunked by a scheme that's since changed gets refreshed on its next
  connect instead of silently staying stale forever.
- `evals/retriever.py` — `LexicalRetriever` (stdlib BM25 keyword retriever) plus
  a `tokenize` helper, `SemanticRetriever` (cosine similarity over an
  `EmbeddingProvider`'s vectors; optional `vectors=` param + `.vectors` property
  to supply/persist precomputed chunk embeddings), `HybridRetriever` (RRF
  fusion of BM25 + semantic), and `NormalizingRetriever` (Brick Q: wraps any
  retriever, running `query_normalize.normalize_query` on the query before
  delegating -- "wire ahead of the retriever") -- all share the
  `.search(query, k) -> List[str]` contract, drop-in for each other.
- `evals/query_normalize.py` — Brick Q's query-understanding layer:
  `build_vocabulary(chunks)` (reuses `retriever.tokenize()` exactly),
  `normalize_query(text, vocabulary, cutoff=0.8)`, a stdlib-only (`difflib`)
  fuzzy spelling corrector toward real corpus terms -- never an external
  dictionary, and `COMMON_SHORT_WORDS` (shared with `baseline_retriever.py`).
  Retrieval-only preprocessing; the writer/user still see the original
  question text.
- `evals/baseline_retriever.py` — `GrepBaselineRetriever`: the third-party
  comparison yardstick -- what a developer gets by grepping the repo today,
  with none of Icarus's ranking/semantics. Deliberately dumb (keyword-presence
  OR-match, no term-frequency weighting, no typo tolerance), pure Python (no
  subprocess call to a real grep/rg binary, so it's reproducible without
  ripgrep installed). Same `.search(query, k)` contract, drops into `grade()`
  for an apples-to-apples comparison; not a shipped retrieval technique.
- `evals/vector_cache.py` — `load_vectors`/`save_vectors`: the on-disk embedding
  cache (JSON sidecar tagged by model name) so the demo doesn't re-embed a corpus
  on every start. Pure optimization, fail-safe: any miss/model-change/corpus-
  change/corrupt file returns None → re-embed. Cache (`vectors.json`) is derived,
  gitignored, never committed.
- `evals/provider.py` — the `Provider` abstraction for the rented writer/judge:
  `GroqProvider`, `GeminiProvider` (key in the `x-goog-api-key` header, not the
  URL), `OpenRouterProvider`, `StaticProvider`, and `PaidGeminiProvider` (a
  billing-enabled, `private_safe=True` Gemini on its own `GEMINI_PAID_API_KEY`);
  `make_provider` factory + 429 backoff. Stdlib `urllib`; keys from env. Also the
  `EmbeddingProvider` family for semantic retrieval: `StaticEmbeddingProvider`
  (test double) and **`LocalEmbeddingProvider`** (the decided FREE route: local
  ONNX transformer via `fastembed` (bge-small-en-v1.5), `private_safe=True`, no
  key/network/quota, lazily imported); `make_embedding_provider` factory. (The
  hosted `GeminiEmbeddingProvider`/`PaidGeminiEmbeddingProvider` were removed
  2026-07-18 — nothing selected them once serving standardized on the local
  embedder.)
- `evals/trust.py` — the deterministic trust interlock: `assert_safe_for_private`
  raises `PrivateDataError` unless a provider declares `private_safe=True`
  (never inferred from a key string) — private code's only gate to a writer.
- `evals/github_access.py` — `repo_info`: the caller-scoped permission check
  (`GET /repos/{owner}/{repo}` as the caller's own token); 200 → `{"private":
  bool}`, anything else (403/404/network/malformed) → `None` (fail-safe refuse).
  Plus the two staleness probes behind `demo/freshness.py`: `head_commit`
  (default-branch HEAD sha) and `commits_between` (GitHub's own `ahead_by` for
  `base...head`, asked only once the shas are known to differ, so the common
  up-to-date case costs one request not two). Both fail safe to `None` meaning
  UNKNOWN, and both allow a missing token — unlike `repo_info`, they read
  public state, and refusing without one would make freshness permanently
  unavailable on the web surface, whose login narrowed to `read:user`.
- `evals/env_file.py` — `load_env_file`: stdlib loader that reads a gitignored
  `.env` into `os.environ` without overriding real env vars.
- `evals/synth.py` — (2026-08-10) `per_claim=` asks the writer to additionally
  report, per sentence, which refs that sentence restates (`_PER_CLAIM_RULE`,
  reusing `_READ_RULES`' `{text, citations}` shape rather than a second claim
  schema). Default False leaves the prompt BYTE-IDENTICAL, the same guarantee
  `selection`/`audience` carry. Built because detecting quotation-vs-composition
  AFTER the fact provably fails — a plausible fabrication is assembled from the
  evidence's own words and so scores HIGHER on lexical overlap than an honest
  paraphrase (measured; see docs/experiments/2026-08-10-quotation-vs-composition-
  negative-result.md). `build_prompt`, the strict cite-or-abstain prompt (also tells
  the writer to treat evidence as data, not instructions). Truncates prose chunks
  to `_MAX_CHUNK_CHARS` (1500) but CODE chunks to `_MAX_CODE_CHUNK_CHARS` (10000)
  so a 300-line code window stays visible to the writer instead of ~40 lines.
  `selection=` (2026-08-06) marks the refs the caller resolved BY LOCATION — a
  user's line selection — so the writer answers about the code they pointed at
  rather than a neighbour that merely ranked well. Marker text and instruction
  are appended only when a selected ref actually survived into the chunks shown;
  an empty/None/unmatched selection leaves the prompt BYTE-IDENTICAL, which is
  what keeps `/ask` and every number on the eval board untouched (`.answer()`
  sets `anchored` too, so the two are deliberately NOT merged).
- `evals/gate.py` — (2026-08-10) also `attribute_claims`: validates the writer's per-sentence self-report (`synth.build_prompt(per_claim=True)`) against what was retrieved, labelling each claim `quoted` (one retrieved ref), `composed` (two or more) or `unsupported`. ADVISORY -- never called by `gate()`, never touches a verdict; it reuses `_resolve`, so a claim citation is held to the same standard as an answer citation and an unretrieved ref is dropped, which can only move a claim toward `unsupported`. A self-report is evidence, not proof: a writer that merged can still report one ref. The deterministic honesty gate: emits an answer ONLY if it
  parses, claims "answer", has prose, and cites ≥1 retrieved ref; else "unknown".
  Citation matching is tolerant-but-safe (`_parse_ref`/`_resolve`): it grounds a
  citation the writer reformatted — dropped `code:` prefix, display brackets, or
  narrowed a chunk's `#L1-L300` window to the specific `#L21` line — when paths
  match AND the cited lines are CONTAINED in the retrieved window, but still forces
  unknown on an unretrieved path, an out-of-window line, or a MALFORMED range
  (line 0/negative, end<start), so groundedness holds. It also applies the (b)
  rationale guard: when given the question + evidence, a "why" question whose
  grounded evidence records no reason (a bare code constant, not pr/issue/doc or
  rationale prose) is forced to "unknown" — catching the why→what dodge.
  And the (c) entity-presence guard (added 2026-07-18): a question naming a
  DISTINCTIVE code identifier (snake_case / camelCase / long non-acronym
  ALL-CAPS, reduced to its leaf symbol) that appears NOWHERE in the evidence the
  writer saw is forced to "unknown" — catching a fabricated symbol grounded to
  adjacent real code (found live: Redis has no `HYPERVECTOR` type, but its real
  vector-set code let the writer answer as if it did). Fail-safe, evidence-gated,
  off for `.explain()`; single Title-case words are deliberately not flagged.
  A named source prefix must equal the retrieved ref's source (`code:1489` never
  grounds to `pr:1489`); only a bare-body citation gets the prefix-drop tolerance.
- `evals/judge.py` — the answer-correctness judge (quality dial, NOT a gate):
  `build_judge_prompt`, `parse_verdict` (fails safe to "incorrect"), `Judge`.
- `evals/pipeline.py` — the `Result`/`Pipeline` contract, plus `StubPipeline`,
  `RetrievalPipeline`, and `GatedPipeline` (retrieve → writer → gate → Result;
  `.answer()` and Brick D's `.explain(path, start, end, question=None)` --
  location-resolved evidence instead of a `.search()` query -- both funnel
  through the shared `_answer_from` writer→gate core, so `.explain()` opens no
  new honesty path). `.explain()`'s neighbor search uses the caller's
  `question` when given (proven live to reproduce `.answer()`'s exact top-k
  for the same question), else the anchor chunk's own text. `Result.anchored`
  (2026-07-28) carries the refs resolved by EXACT LOOKUP -- because the
  question named them ("PR 6952") or, in `.explain()`, because the user
  selected those lines -- split out from the ones search merely suggested.
  Always a prefix of `retrieved`, set on the abstention path too. Display
  only: it is carried alongside the honesty decision, never into it.
  `Pipeline.indexed_chunks()` (base: `[]`, so a corpus-less pipeline says so
  rather than raising; `GatedPipeline`: every chunk it holds) lets a caller
  DESCRIBE the corpus instead of querying it -- read-only, outside the honesty
  path, and what `demo/repo_map.py` is built on.
- `evals/grader.py` — deterministic grading against the labelled set: the two
  honesty gates + quality dials; optional `judge` fills answer_correctness.
- `evals/onboarding_probe.py` — measures how often a guided onboarding tour
  would have to abstain, BEFORE any tour UI exists. Seven fixed writer-backed
  steps (purpose, stack, architecture, decisions, conventions, debt, recent --
  the deterministic map/entry-point steps are excluded on purpose, since they
  cannot abstain and would flatter the result) asked over ten real public repos
  through the REAL serving path (`demo.library.Library`), with
  `background_upgrade=False` so every question is asked AFTER the semantic
  index is installed -- asking inside the lexical-only window would measure the
  wrong thing. Corpora cache under `--storage`, so a re-run is minutes not an
  hour. Deliberately NOT a unittest: needs network, `gh`, a paid writer key and
  ~1 hour. **First run (2026-07-29): 46/70 answered, 24/70 abstained, every
  abstention `writer_abstained` (the gate never fired). `purpose` 2/10 and
  `architecture` 2/10 were the worst steps; `stack` and `recent` 10/10. 93% of
  all citations came from history (58 commit + 17 pr + 14 issue) against 2 doc
  and 1 code** -- the evidence base for the history-versus-source ranking work.
- `evals/run.py` — CLI that runs the eval board and prints it (loads `.env`
  first); exits non-zero only when a gate breaks. `--pipeline/--writer/--judge`.
- `evals/test_corpus.py` — `load_chunks` parses JSONL into `Chunk`s (tolerates
  blank lines); `chunk_covers_lines` across windowed/whole-file/malformed refs,
  path mismatches, and non-file-addressable (pr/issue) sources.
- `evals/test_ast_chunk.py` — `ast_chunk`'s unit contract (stdlib-only,
  always-run): per-function/class splitting, chunk_text-identical ref/shape,
  scope headers, a big class splitting per method while its docstring +
  class-level attributes survive under the CLASS's ref (never leaking into the
  module preamble's whole-file ref), module constants preserved, chunks
  dramatically smaller than a line window, and the fallbacks (non-Python,
  syntax error, no-defs module, null bytes) returning `chunk_text` verbatim.
- `evals/test_ast_chunking_eval.py` — AST chunking's live board proof
  (self-skips without fastembed/corpus): same-run, never-hardcoded comparison
  against `chunk_text`, holding PR/issue chunks and source text identical and
  varying ONLY the code chunker. Proves the mechanism (median line-window
  EXCEEDS the 512-token embed budget; AST chunks fit) and the payoff (strictly
  better semantic recall@5), plus a guard that lexical recall never regresses.
  Scores FILE-LEVEL recall on purpose -- `grader.grade`'s exact-ref
  recall would score AST 0 against whole-file gold citations for reasons
  unrelated to quality.
- `evals/test_ts_chunk.py` — `ts_chunk`'s unit contract, self-skips without
  tree-sitter-language-pack: per-language fixtures for TS/TSX (const-arrow
  functions, small vs. large classes), Flow-typed `.js` (parses via `tsx`,
  not `javascript`), ObjC (`.mm` method nesting), Java, Kotlin (name-field
  fallback regression guard -- proven by reverting the fix and watching the
  test fail), the size-based safety valve (Jest `describe()` block, a giant
  single function, and a few-line/huge-single-line file each proven red→green
  by disabling the relevant check), and the chunk_text fallbacks (unsupported
  `.h`, garbage input, no definitions, missing tree-sitter).
- `evals/test_ts_chunking_eval.py` — T3's live per-language proof: for each of
  TSX/Kotlin/ObjC/Java, same-run file-level recall@5 (semantic) comparing
  `ts_chunk` against `chunk_text`'s window-300 baseline over the committed
  real fixture corpora (`evals/fixtures/ts_chunk_eval/`), plus the mechanism
  proof (median token length under the 512-token embed budget per language).
  Gold files are deliberately 400-550+ real lines -- an earlier draft using
  short (~250-line) targets found both chunkers hit 100% identically, since a
  file that short never triggers the truncation this brick fixes. Measured:
  tsx 66.7%→100%, java 33.3%→66.7% (the one java miss is a real, disclosed
  semantic-competition case -- other real Fab-named files outrank the one
  method that merely references Fab -- not a chunking defect), kotlin/objc
  tied at 100% (no regression, ceiling effect at this corpus scale). Self-skips
  only on missing fastembed/tree-sitter -- the fixture corpus is committed.
- `evals/ts_chunk_eval_questions.json` — T3's 12 hand-verified questions (3 per
  language), each checked against the real fixture source in full before its
  reference_answer was written; questions target content positioned LATE in
  each gold file, which is what actually exercises the truncation difference.
- `evals/fixtures/ts_chunk_eval/` — real, MIT-licensed source files (~70/lang,
  java capped at 47, its directory's whole bounded pool) from wix/react-
  native-navigation, facebook/react-native, and bluesky-social/social-app,
  committed verbatim for T3's deterministic, no-network eval -- see
  `MANIFEST.md` for exact commit provenance and file-selection rationale.
- `evals/test_corpus_meta.py` — `write_meta`/`load_meta` round-trip; missing meta
  returns None; the "chunking" field round-trips and defaults to "chunk_text"
  for callers that omit it (T6).
- `evals/test_ingest_args.py` — ingest CLI defaults/overrides, commit resolution,
  and `_safe_code_dir` path-traversal rejection.
- `evals/test_ingest_chunking.py` — `chunk_text`'s pure line-window contract:
  short-file/exact-boundary/single-line/empty-text whole-chunk cases, the
  overlap/coverage/uniqueness invariants of a multi-window split, a dense-but-
  short file splitting by char budget, and (2026-07-17) a single PHYSICAL
  line that alone exceeds the char budget being truncated in place with a
  visible marker rather than shipped whole -- reproduces a live bug (a
  machine-generated file with one ~250,000-char line became one oversized
  chunk) and proves refs stay unique post-truncation (load-bearing:
  `SemanticRetriever` keys embeddings by `chunk.ref`) and GitHub-linkable.
- `evals/test_ingest_repo.py` — `ingest_repo` writes chunks + meta and returns
  counts (network fetches monkeypatched; offline); meta.json's "chunking"
  field reflects the flag (T6). Also T4's wiring tests: `_chunk_code`'s
  dispatch decision in isolation (mock.patch on ast_chunk/ts_chunk -- default
  OFF never calls either; every truthy env-var spelling routes `.py`→ast_chunk
  and the RN language set→ts_chunk; `.h` and other languages stay on
  chunk_text even with the flag on), plus the same wiring exercised through
  the real `fetch_code` walk (doc/config sources never reach the dispatcher;
  the flag-off path matches plain chunk_text byte-for-byte, protecting the
  committed board's reproducibility).
- `evals/test_commit_lookup.py` — a named commit SHA is an exact-identifier
  LOOKUP, not a search: proves `GatedPipeline`'s live commit anchor fetches the
  SHA and grounds a citation, fails safe to honest-unknown when the fetch
  returns None, never fires on hex-shaped English ("defaced"), stays a no-op
  with no fetcher wired (the offline eval board), and that the gate's (b)
  rationale guard accepts a commit message as recorded rationale.
- `evals/test_ingest_smoke.py` — skippable live ingest of a tiny public repo
  (`RUN_INGEST_SMOKE=1`).
- `evals/test_env_file.py` — the `.env` loader: parses KEY=VALUE, doesn't override
  real env, tolerates comments/quotes/export, no-ops on a missing file.
- `evals/test_retriever.py` — tokenization + BM25 ranking, truncation, zero-score
  dropping, deterministic tie-breaking; plus `SemanticRetriever`/`_cosine` tests,
  including the core proof that cosine similarity finds a paraphrased chunk with
  zero keyword overlap where BM25 provably returns nothing.
- `evals/test_pipeline.py` — `RetrievalPipeline` populates `retrieved` yet still
  abstains.
- `evals/test_provider.py` — `StaticProvider` queuing, no-key errors, the retry
  budget, and the Gemini key going in the header not the URL; `private_safe`
  flags per provider and `PaidGeminiProvider`'s dedicated key env.
- `evals/test_trust.py` — the trust interlock refuses every free provider and an
  undeclared one, and passes the private-safe/static providers.
- `evals/test_github_access.py` — `repo_info` across 200 (public/private),
  sends the caller's token as Bearer, and refuses on 404/network error/garbage
  body/missing `private` field/no token (never calls out without one).
- `evals/test_synth.py` — the prompt includes question/refs/text, offers the
  unknown path, truncates long chunks.
- `evals/attempts.py` — `rejected_attempts(evidence)`: the pull requests among
  retrieved evidence that were CLOSED WITHOUT MERGING. **A merged PR leaves a
  commit; a refused one leaves nothing**, so `git log`, `git blame` and the
  working tree are structurally blind to it -- measured twice as the decisive
  fact an agent could not otherwise reach (docs/experiments/2026-08-10-agent-
  mode-exp-d*.md): once where a control agent was about to write a patch two
  people had already had rejected, once where it declared a live bug fixed
  because only the merge was visible. Deterministic, derived from the header
  line `evals/ingest._pr_or_issue_text` already writes, so it cannot be bluffed
  and needs no ingest change, no model and no extra fetch. A closed ISSUE is
  deliberately NOT an attempt (544 of them vs 129 closed PRs in the committed
  corpus would bury the signal). Reports WHAT was refused, never WHY -- the
  reason lives in review comments, and asserting one is the composed rationale
  these experiments caught twice.
- `evals/test_attempts.py` — 11 tests weighted toward what must NOT be
  reported: a MERGED PR, an OPEN one, a closed ISSUE, a non-PR ref, a body
  merely containing the word (anchored to the header start), plus determinism,
  hostile input, and a guard that reads the REAL committed corpus so the parser
  cannot drift from what ingest actually writes.
- `evals/test_claim_selfreport.py` — the writer's per-sentence self-report (18
  tests, stdlib only): the prompt is BYTE-IDENTICAL with `per_claim=False` (the
  guarantee that lets this ship without re-baselining the board), a claim citing
  one retrieved ref is `quoted` and two is `composed`, a ref nobody retrieved is
  DROPPED rather than trusted (so a self-report can only move a claim toward
  `unsupported`), one source cited twice is not corroboration, malformed input
  never raises, and the verdict is provably identical with the flag on or off.
- `evals/test_gate.py` — the gate passes grounded answers and fails safe to
  abstention on everything ambiguous.
- `evals/test_grader.py` — the harness conscience: gates hold for an honest
  abstainer/oracle and fire for a bluffer.
- `evals/test_gated_pipeline.py` — `GatedPipeline` end to end with a
  `StaticProvider` (answer, abstention, forced-unknown bluff).
- `evals/test_gated_explain.py` — Brick D's `.explain()`: anchor resolution
  (windowed + whole-file chunks), semantic neighbors, honest unknown with no
  coverage, the shared honesty gate (grounded answer / forced-unknown bluff /
  writer abstention -- proves no new honesty path), the default vs. caller-
  supplied question, question-preferred-over-anchor-text neighbor search (the
  real bug this brick found+fixed: an earlier version always searched on the
  anchor's own code text even with a real question, live-verified to find
  measurably worse neighbors than /ask), and a regression guard that
  `.answer()`'s behavior is byte-identical after the `_answer_from` refactor.
- `evals/test_vector_cache.py` — the embedding cache round-trips and fails safe
  to None (re-embed) on every mismatch/corruption; the `SemanticRetriever`
  `vectors=` param skips chunk embedding yet still embeds the query live.
- `evals/test_gated_semantic.py` — the honesty-gate proof for the SEMANTIC/HYBRID
  retrieval path (Brick C): a `GatedPipeline` + real writer over
  `SemanticRetriever`/`HybridRetriever` evidence emits a grounded answer but
  forces an ungrounded citation to abstention. Deterministic
  `StaticEmbeddingProvider` (offline, always-on), so it proves the gate is
  retriever-agnostic without needing fastembed.
- `evals/test_query_normalize.py` — Brick Q's `normalize_query`/
  `build_vocabulary`: corrects real typos, leaves correct/unmatched/common-short
  words alone, deterministic (incl. a genuine-scoring-tie case, not a vacuous
  no-tie fixture), and `TokenizerLockstepTests` -- an always-run guard proving
  `query_normalize`'s word-splitter stays byte-identical to
  `retriever.tokenize()` (catches the exact filename-corruption bug class this
  brick fixed, without needing fastembed). Stdlib only, always runs.
- `evals/test_baseline_retriever.py` — `GrepBaselineRetriever`'s unit tests:
  keyword OR-matching, count-based ranking (no term-frequency weighting, unlike
  BM25 -- proven by a chunk repeating a keyword 50x NOT outranking one
  mentioning it once), case-insensitivity, common-word skipping, determinism.
- `evals/test_grep_comparison_eval.py` — the third-party comparison proof:
  Icarus's retrieval (hybrid + normalized) beats the grep baseline on the
  comprehension board, both phrasings, same-run recall@5, gates 100%
  throughout. Self-skips without fastembed/the corpus/comprehension set.
- `evals/test_query_normalization_eval.py` — Brick Q's live board proof: wrapping
  hybrid retrieval with `NormalizingRetriever` never regresses recall on either
  phrasing and closes messy-phrasing recall@5 up to the clean baseline in
  aggregate (same-run boards, gates 100% throughout). Self-skips without
  fastembed/the corpus/comprehension set.
- `evals/test_code_answering_gap.py` — regression guard for the two code-answering
  gaps found+fixed 2026-07-13: the gate grounds a code citation the writer
  reformatted (dropped `code:` prefix / display brackets / narrowed a chunk's
  `#L1-L300` window to the specific `#L21` line it used) yet still forces unknown
  on an unretrieved path or an out-of-window line; and `build_prompt` shows code
  past the old 1500-char cap so a mid-window answer isn't truncated out. Started
  as a RED failing eval (red→green, deterministic, no live model).
- `evals/test_explain_selection_eval.py` — live proof (self-skips without paid
  key/fastembed/corpus) that a LINE SELECTION is answered about the selected
  lines. Red→green 2026-08-06 against the real serving pipeline: selecting
  `logging_client()` (`llm/utils.py#L149-L153`) and clicking "Ask Icarus" with
  no typed question returned an honest-looking `unknown`, while the SAME
  pipeline asked only the "what" half answered correctly — the shipped default
  question was compound ("...and why is it here?") and the writer's
  answer-everything-or-unknown contract let an unrecorded why drag the
  answerable what down with it. Worse, asking why the selected code was chosen
  produced a confident, correctly-cited explanation of an unrelated Pydantic
  v1/v2 decision: **every citation resolved, so the honesty gate passed it** —
  groundedness proves a citation is real, never that the answer is about the
  code the user pointed at. Third test is the honesty guard that must stay red
  if the fix ever buys helpfulness with a bluff (an unrecorded why must still
  abstain).
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
- `evals/test_paid_writer_eval.py` — real-model proof: the paid Gemini writer
  holds both honesty gates at 100% with citation correctness > 0 on the public
  board (self-skips without `GEMINI_PAID_API_KEY`).
- `evals/test_private_ingest_live.py` — live end-to-end private-repo proof: the
  access gate, an authed clone, a paid-writer answer, and the free-provider
  interlock refusal, all against a real repo (self-skips without
  `RUN_PRIVATE_INGEST=1` + a real repo/token/paid key).
- `evals/test_egress_invariants.py` — proves, offline with a spy provider, that
  private text reaches only a genuinely private-safe provider, an unsafe one
  raises before any prompt is sent, the serve path never imports the judge, and
  the per-user private tree is git-ignored.

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
- `demo/payload.py` — (2026-08-10) also `build_context_payload`: wraps `evals.context_package`'s output with the same self-identifying `repo`/`commit`/`indexing` fields every payload carries. Deliberately NOT built on `build_payload` -- a context package has no single verdict (it can hold decisions AND risks AND unknowns at once), so forcing it through the answer/unknown shape would invent a field that means nothing here. `build_payload` emits `claims` when the caller set `per_claim`:
  the writer's per-sentence self-report, each entry `{text, citations, label}`
  with label `quoted`/`composed`/`unsupported`. ABSENT unless present, so every
  existing client is byte-identical. `build_payload`, turning a `Result` into self-identifying
  repo/commit JSON. Human callers keep citation-only evidence; read-only agent
  callers can explicitly request bounded retrieved evidence even on an honest
  unknown. Carries `anchored` beside `searched` so a renderer can distinguish
  what the question named from what search suggested.
- `demo/mcp_server.py` — (2026-08-10) a third tool, `get_task_context` (Experiment B): structured pre-implementation context rather than a conversational answer, over `POST /context`. Costs several model calls like an investigation, so its description tells the agent when to reach for it over the cheaper `get_change_context`. Both existing tools send `per_claim: true`
  unconditionally (not a tool argument — no caller here would want it off), and
  the tool description tells the agent to verify `composed` sentences. Dependency-free stdio MCP adapter over `/status`,
  `/ask`, and `/explain`: two read-only tools, explicit repo mismatch refusal,
  and evidence-rich unknowns. Serves PUBLIC AND PRIVATE repositories since
  2026-08-07 — the prior fail-closed private check was removed deliberately
  (`docs/decisions/2026-08-07-mcp-private-repository-access.md`): Icarus cannot
  verify a calling MCP client's model-provider posture, so that exposure is
  transferred to whoever configures the client rather than refused on their
  behalf. It obtains a ten-minute credential from the installed Mac app when
  no development override is present, keeps it only in memory, owns no
  retrieval or answering logic, and its evidence-opt-in asks do not pollute the
  human documentation-demand ledger.
- `demo/agent_sessions.py` — bounded, thread-safe in-memory store for opaque
  coding-agent sessions. Grants carry only verified identity, active public
  repo, and expiry—never the GitHub credential.
- `demo/repo_map.py` — `build_map(chunks, status)`: the repository map served
  by `GET /map` — what Icarus INDEXED, said before anyone asks a question. Pure
  (the in-memory corpus + a status snapshot in, dict out): no model call, no
  network, no filesystem, and no re-read of `chunks.jsonl` (chunks come from
  `GatedPipeline.indexed_chunks()`, already in memory, so a 50k-chunk repo
  costs nothing per request). Takes CHUNKS rather than refs only because
  entry-point detection must read a manifest's text; every other field needs
  just the ref. Reports distinct indexed file count, files grouped by
  language and by top-level directory, indexed documentation (+ an explicit
  `readme: null` when none was indexed), chunk counts per source, lexical/
  semantic readiness, truncation, `indexed_entry_points`
  (`demo/entry_points.py`) and `indexed_structure` (`demo/structure.py` — the
  import-derived arrangement). **Every field is named `indexed_*` on
  purpose**: a corpus-derived map describes what Icarus READ, never what
  EXISTS in the repository, so it publishes no total-file count and no
  excluded-file count/list. The ingest deny-lists are reported as
  `exclusion_rules` — rules that were APPLIED, derived from `evals/ingest.py`'s
  own constants so they can't drift — never as observed excluded files, since
  `classify_file` records nothing about what it skips. A future
  ingestion-manifest brick can add genuinely observed discovered/eligible/
  excluded/failed counts.
- `demo/onboarding.py` — the tour now opens with TWO writer-free steps:
  `overview` (the map) and `structure` (kind `"structure"`, served from
  `/map`'s `indexed_structure`). The structure step is deliberately NOT the
  writer-backed `architecture` step measurement cut at 2/10 — it asks no
  writer, so it cannot abstain and cannot bluff; `architecture` stays cut and
  stays measured by the probe. An older Mac app decodes an unknown step kind to
  `.unsupported` and skips it, so this ships without a DMG.
  `demo/onboarding.py` — the guided onboarding tour: `STEPS` (the five steps
  measurement proved reliable), `plan(status)` (the ordered tour -- pure and
  instant, no writer, no retrieval) and `answer_step(pipeline, status, step_id,
  token)` (one step, returning a `Result` untouched). Deliberately NOT a
  workflow engine and holds NO per-user state: the plan is a constant and each
  step is fetched on its own, so "interrupt with a question and come back" needs
  no session and nothing can be lost by resuming. Every step is an ordinary
  gated ask -- same retrieval, writer and honesty gate -- because a claim Icarus
  VOLUNTEERS earns less scepticism from a reader than one they asked for, so it
  needs more proof, not less. **Which steps ship is a measurement**
  (`evals/onboarding_probe.py`, 2026-07-29 over ten real repos): purpose 10/10,
  stack 10/10, recent 10/10, conventions 9/10, decisions 8/10 shipped; debt
  5/10 and architecture 2/10 CUT. `purpose` addresses the README by path
  (resolved via `demo/repo_map.py`) through `.explain()` instead of searching
  for it -- 2/10 -> 10/10 -- falling back to an ordinary ask when no README was
  indexed; its honest cost is that `.explain()` runs with the gate's (b)
  why->what guard off. The tour is the single source of the step WORDING, which
  the probe imports, so the measured numbers can never drift away from the
  shipped questions.
- `demo/test_onboarding.py` — the tour's contract, written before the
  implementation: only the measured-reliable steps ship and the cut ones are
  absent, the tour opens with the deterministic overview (solid during the
  lexical-only window, when the writer-backed steps are measurably worst),
  `purpose` addresses the indexed README and degrades to an ordinary ask
  without one, every other step is a plain `.answer()` carrying the caller's
  token, an abstention is passed through untouched, an unknown step raises
  rather than being guessed, and the drift guards (probe and product share one
  question definition; the probe still measures the cut steps so we learn if
  they become viable).
- `demo/entry_points.py` — `detect_entry_points(chunks)`: "where do I start
  reading?", answered by explicit RULES only, never by a score. Five rules:
  `pyproject-console-script` (a `[project.scripts]` entry in a whole-file
  `pyproject.toml`, resolved to an indexed module incl. src-layout, via stdlib
  `tomllib` — no new dependency), `python-main-guard`, `go-main-function`
  (needs BOTH `package main` and `func main(`, tracked per path so the two can
  sit in different windows), `rust-main-file`, `conventional-filename`. Every
  result carries `{rule, evidence_ref, detail}` — the indexed chunk that proves
  it, citable like any other Icarus claim — and a rule may only name a file
  that is IN the corpus, so anything it points at can also be shown. Rules on
  one file group into one entry, so a count of entry points is a count of
  FILES. No rule fires → empty list, never a guess. Two rules earned by running
  it over this repo, not by unit tests: **test files are excluded from every
  rule** (`if __name__ == "__main__": unittest.main()` is boilerplate in all
  60+ test files here, so the guard rule returned 70 "entry points" and buried
  the four that matter), and the guard is matched **anchored to a line start**,
  not as a substring — this module matched ITSELF, since it holds the guard as
  a string literal (same class as `evals/pipeline.py`'s "a hex-shaped English
  word is not a commit SHA"). Two disclosed gaps: `package.json` is never
  indexed (`.json` is excluded corpus-wide), so JS/TS falls back to
  conventional filenames; and `setup.py`'s `entry_points=` is executable
  Python, not data, so it is deliberately not parsed.
- `demo/test_entry_points.py` — entry-point detection's contract, written
  before the implementation: each rule firing on a positive case with the right
  evidence ref, a console script pointing at an UNINDEXED module yielding
  nothing, a PR body quoting `func main()` never becoming a file, an ordinary
  library repo yielding an empty list, no score/rank field on any output,
  unparseable and windowed-partial manifests staying silent, several rules on
  one file grouping into one entry, a windowed file named once, determinism
  under reversed input, the test-file and quoted-guard exclusions (both
  red→green from real-repo findings), and purity (signature takes only
  `chunks`; `builtins.open`/`socket.socket` patched to raise).
- `demo/structure.py` — `build_structure(chunks)`: how the code is ARRANGED,
  read off its own import statements. Answers the question measurement found
  hardest (`architecture`, 2/10 on the ten-repo probe) and that anchoring to a
  README provably could not fix — a README says what a project is FOR, not how
  its code is laid out, and in most repos the arrangement is written down
  nowhere but the code. Pure (chunks in, dict out), deterministic, no writer,
  so it holds during the lexical-only window and cannot bluff. Emits
  `file_edges` (Python/JS — imports there name a FILE), `package_edges` (Go —
  an import names a package DIRECTORY), directory-level `components` each
  carrying the indexed refs proving its edges, `most_depended_on_files`,
  `unresolved_import_count` and `unanalysed_languages`. **Every resolver is
  language-specific on purpose:** a first generic pass invented a `pkg -> demo`
  edge across 566 files of lazygit (Go's `.../pkg/config` bare-name-matched
  `demo/config.yml`), indistinguishable from the true edges beside it. Two
  further fabrications were caught by sampling emitted edges against real
  source, not by unit tests — resolving a Go package to one of its files meant
  taking the alphabetically-first and stating it as fact (18.1% of sampled
  edges wrong; cobra's `active_help.go`, glow's `config_cmd.go`), fixed by
  splitting package edges from file edges. Final measurement: 8/10 repos yield
  structure, **199 sampled edges, 0 unverified**; the 2 misses are honest
  (shellcheck is Haskell and unindexed, mdBook is Rust and says so). 72ms over
  a 14,675-chunk corpus, so it stays per-request like the rest of the map.
- `demo/test_structure.py` — structure's contract, written before the
  implementation and weighted toward what must NOT be emitted: the
  fabrication-guard suite (bare-name match, unindexed target, cross-language
  resolution, self-dependency, an import quoted in a PR body, a Go package
  import never becoming a file-level edge), per-language resolution for
  Python/JS/Go incl. src-layout, relative and root-package cases, components as
  directories rather than top-level buckets (top-level collapses lazygit's
  1,591 edges to 2), determinism under reordered input, no score/rank field,
  and purity (`builtins.open`/`socket.socket` patched to raise). One guard here
  was found to be VACUOUS and rewritten — its decoy was a `.yml` file rejected
  by the language filter before the rule under test was reached, so it passed
  with the bug deliberately reintroduced.
- `demo/test_repo_map.py` — the map's contract, written before the
  implementation: every named file is an indexed ref (the map's version of
  groundedness), counts are deterministic and order-independent, a distinct
  FILE is counted once however many chunks it made, a missing README is
  reported as `readme: null` rather than omitted or invented, truncation is
  surfaced in both a flag and words, an UNtruncated corpus is never called
  complete, the exclusion rules are strings derived from ingest's constants
  with no excluded-file count or list published, language totals always equal
  `indexed_file_count`, and `build_map` takes no provider and opens no file or
  socket (proven by patching `builtins.open`/`socket.socket`).
- `demo/ledger.py` — `Ledger`: the append-only per-repo ask record (question,
  verdict, citations, timestamp — deliberately NOT the answer body and NOT who
  asked). One JSONL file per repo, stored OUTSIDE the corpus dir because ingest
  republishes with `os.replace()` and would destroy it. Read via `GET /ledger`
  (`?gaps=1&resolved=1` for server-owned open/proposed/resolved Memory Gaps).
  One Unicode-casefold identity and opaque repo-scoped gap ID are used for
  listing, proposing, and resolution. Exact-text gaps resolve only after a
  later cited answer; entity-absent/unclear unknowns are visible but not
  actionable.
- `demo/memory_writer.py` — `GitHubMemoryWriter`: caller-scoped, stdlib-only
  bounded, idempotent write for one actionable gap. Verifies push permission;
  uses the opaque gap ID to deterministically create or recover one branch, one
  retrospective Markdown record under `docs/engineering-memory/`, and one pull
  request; never merges or overwrites.
- `demo/test_memory_writer.py` — offline GitHub request-shape, permission,
  validation, deterministic replay, lost-response recovery, and partial-failure
  tests for the bounded writer.
- `demo/freshness.py` — `FreshnessChecker`: does the connected index still
  match the repository? A corpus is frozen at the commit it was ingested and
  nothing said so — this repo's own index sat NINE commits behind HEAD while
  answering with full confidence. Reports `up_to_date` / `behind_by` /
  `head_commit` / `checked_at` on `/status`. **`up_to_date` is three-valued
  and every failure path lands on `None`**: telling someone their index is
  current because the check failed is the same class of failure as a bluffed
  citation. One deliberate exception the other way — if HEAD is readable and
  DIFFERS but the compare call then fails, `up_to_date` stays `False` and only
  the count is unknown, since "it differs" is a fact we actually hold.
  TTL-cached per `(repo, indexed_commit)` because `/status` is polled
  continuously and GitHub's API is not; keying on the commit means a refresh
  invalidates instantly, and `checked_at` reports when the check ACTUALLY ran,
  not now. A failed check is retried rather than pinned for the TTL. The
  caller's token is used per request and never cached. `/status` adds a
  `pinned` flag beside it: the committed demo corpus is frozen ON PURPOSE
  (`connect_sync` exempts it — it is the reproducible eval board), so it is
  permanently behind upstream (68 commits, measured live). The true numbers
  stay; `pinned` is what stops a deliberate decision reading as neglect and
  a client offering a refresh that is forbidden by design.
- `demo/test_freshness.py` — freshness's contract, weighted toward the
  never-claim-fresh property: every unknown path, the differs-but-count-unknown
  case, TTL hit/expiry, per-repo and per-commit cache separation, a failed
  check being retried, `checked_at` reporting the real check time on a cached
  read, and the token never reaching the cache.
- `demo/visits.py` — `VisitStore`: what Icarus remembers about a RETURNING
  user — exactly four facts and no fifth (user identity, repository identity,
  last-seen commit, last-visit timestamp), per
  `docs/decisions/2026-07-30-returning-user-state.md`. **`demo/ledger.py`
  records questions against the REPO with no identity; this records identity
  with no questions, and the two must never be joined** — that separation is
  the entire safety property and is why this is a new store rather than a
  user-id column on the ledger. `record()` takes no question/answer/verdict
  parameter at all: a signature that cannot accept one is a stronger guarantee
  than a policy saying we won't pass one. A visit OVERWRITES rather than
  appends, because a list of timestamps is an activity log however innocuous
  each row looks. Stored inside the caller's own storage dir — the exact tree
  `LibraryRegistry.disconnect` deletes, so "deletable, and actually deleted"
  needs no second mechanism (test-pinned in `demo/test_registry.py`). Atomic
  write via `os.replace`; never raises into a request.
- `demo/test_visits.py` — the store's contract, weighted toward what must NOT
  be stored: exactly the four approved fields reach disk, `record`'s signature
  rejects question/answer/verdict/citation/count, no visit count or streak is
  derived, cross-user invisibility, hostile user id and repo name refused,
  survives a new process, and a corrupt file reads as "first visit" rather
  than raising.
- `demo/investigations.py` — `ConversationStore`: what one caller's
  investigation remembers between turns, so "why did **it** change?" resolves.
  Keyed on (identity, repo) — the repo is part of the KEY, not a field checked
  afterwards, so a subject cannot survive a repo switch or leak between users.
  Keyed on (identity, repo, **corpus-content fingerprint**) with a request counter: a
  `/connect refresh` republishes the corpus, so findings verified against the
  old index cannot be carried into an answer about the new one, and every
  request advances the counter so an older overlapping investigation cannot
  finish late and overwrite a newer one (compare-and-set
  under the store's own lock; no lock is held across a model call).
  In-memory, TTL'd (20 min) and LRU-capped: losing a conversation on restart is
  the CORRECT failure, since a stale investigation resumed against a moved index
  would answer about a repository that has since changed. Carries subject,
  objective, indexed verified findings **with the support class they were measured
  with**, hypotheses and steps — never evidence TEXT, because the corpus can be
  refreshed underneath a live conversation. Plus `refers_back`, the deterministic
  deictic check ("it", "that change", "afterwards") gating subject inheritance —
  never a model, because a wrongly inherited subject produces a confident, fully
  cited answer about the wrong change and groundedness cannot detect it (the
  2026-08-06 selection-drift finding).
- `demo/test_investigations.py` — the store's contract: only verified findings
  carried, support classes carried not recomputed, evidence text never stored,
  cross-identity and cross-repo invisibility, expiry/renewal/eviction, and
  `refers_back` refusing a word that merely CONTAINS a referring word ("commit"
  contains "it") — which would otherwise inherit a subject on almost any
  question.
- `demo/test_investigate_endpoint.py` — POST /investigate at the HTTP boundary:
  the four-turn conversation holding one subject, a follow-up COMPOUNDING on
  earlier findings rather than restarting (its writer stamps each finding with a
  turn number — an earlier draft emitted identical text every turn and passed
  whether or not anything was carried), a question naming its own subject
  rebinding, an unrelated question inheriting nothing, `fresh: true`, one
  caller's subject never reaching another, and the shared /ask rate limit.
- `demo/library.py` — (2026-08-10) `status_snapshot()` also reports
  `connecting_to`: the repo an in-flight connect is working toward, or None.
  `_repo` cannot answer that -- it is only reassigned at the stage-1 publish,
  AFTER the whole ingest. `Library`: one active repo's state + pipeline. `snapshot()`
  returns a frozen `_CorpusSnapshot` (pipeline, provider, repo, commit,
  content fingerprint, indexing state) read under the SAME lock the pipeline swap takes, so one request
  cannot be torn across a concurrent `/connect refresh` — answering from one
  index while returning citation URLs and conversation provenance from another.
  Its `corpus_id` is `(repo, commit, generation)`: a commit SHA alone is NOT a
  corpus identity, because ingest includes mutable pull-request and issue
  discussion and a same-SHA refresh republishes different evidence. Builds a
  `HybridRetriever` (BM25 + local semantic) via `_build_retriever`, wrapped in a
  `NormalizingRetriever` (Brick Q query normalization, wired into serving
  2026-07-18) so messy/typo'd query phrasing is corrected toward real corpus
  terms before retrieval; backed by a
  process-shared `_shared_embedder` (the fastembed model loads ONCE; falls back
  to lexical-only if fastembed is unavailable) and the `evals/vector_cache`
  on-disk cache so restarts/reconnects don't re-embed. `connect_sync`
  reuses a cache or ingests once, single-flight and thread-safe, serving a
  generic error on failure. The one writer is constructed through the trust
  interlock (`evals/trust.py`); the public alpha has no dormant private-connect
  branch in `Library`. T6: `connect_sync` also refreshes an already-cached
  corpus whose `meta.json` "chunking" scheme has since changed
  (`Library._corpus_is_stale`) -- but never for the committed default repo
  (exempt), and never for a private repo with no token available (the
  tokenless eviction-replay resume in `registry.py`, which must never fail or
  silently downgrade to the public default). `_resolve` itself deliberately
  stays pure availability ("does a corpus exist"), never staleness -- see the
  plan doc's "What T6 found" for why that separation is load-bearing.
- `demo/registry.py` — `LibraryRegistry`: one isolated `Library` per GitHub
  identity under `<storage_root>/<user_id>/…`; the shared public default is
  built once and reused read-only. LRU-bounded (`max_live`); an evicted user's
  library rebuilds from its on-disk cache and the registry replays their last
  connect so eviction never silently reverts them to the demo repo. `disconnect`
  deletes a user's storage + forgets their last-connected repo and surfaces any
  deletion failure other than an already-absent directory.
- `demo/ratelimit.py` — `RateLimiter`: per-key sliding-window limiter (stdlib,
  thread-safe, injectable clock) bounding how often an identity can hit `/ask`
  (bills the writer) or `/connect` (shells out to git/gh).
- `demo/auth.py` — bearer-token auth that resolves *identity*, not just
  validity: `bearer_token`, `GitHubTokenVerifier` (returns the caller's stable
  GitHub user id via `/user`, cached, fail-safe to `None`), and
  `StaticTokenVerifier` (test double mapping tokens to ids). Enforced only in
  the auth mode.
- `demo/github_oauth.py` — server-side GitHub web-login flow: `authorize_url`
  (takes an explicit `scope`, defaulting to `repo`), `exchange_code`
  (uses the client SECRET, injectable opener), and `OAuthFlow` (single-use
  state/session, TTL). `begin(mode, redirect_target=None)` tags each login
  `app` (Mac app), `web` (browser), or Brick D's `extension` (a browser
  extension's `chrome.identity.launchWebAuthFlow`, which needs its own
  `redirect_target` -- validated by `_CHROMIUMAPP_REDIRECT` against
  `https://<32 a-p chars>.chromiumapp.org/` so a caller can never turn this
  into an open redirect to an arbitrary URL); `complete` returns `(session_id,
  mode, redirect_target)` so the callback knows where to send the user. The
  **requested scope is per-surface** (`_WEB_SCOPE`/`_NATIVE_SCOPE`, added
  2026-07-26): `web` asks for `read:user` (identity only -- the browser trial
  connects PUBLIC repos, which need no repo scope, so the consent screen a
  stranger meets first no longer demands read/write on all their private
  repositories), while `app`/`extension` keep `repo` because connecting a
  private repo is what they actually do. Only NEW logins narrow -- GitHub keeps
  the union of scopes already granted to an OAuth App. The
  secret lives only here, never in the app or extension.
- `demo/server.py` — (2026-08-10) `POST /context` (`_handle_context`, Experiment B): the exact `/investigate` engine (same investigate()/conclude() call, same honesty gate, same `investigate_limiter` budget -- an investigation spends several billed writer calls, same as /investigate) reshaped through `evals.context_package.build_context_package` plus `demo.structure.build_structure` for the dependency map. Deliberately STATELESS unlike /investigate: no conversation continuity, no `fresh` flag, no subject inheritance -- a caller asking what to know before doing X is not a follow-up about a prior "it". stdlib `http.server` over a `LibraryRegistry`: `make_handler`
  (loopback Host/Origin guard, 64KB body cap, per-request identity resolution,
  optional GitHub bearer on `/ask`+`/connect`+`/disconnect`, per-identity rate
  limits via `demo/ratelimit.py` — including a SEPARATE, much tighter
  `refresh_limiter` (2/hour) checked only once `refresh: true` is parsed, since
  an ordinary connect to a cached repo is a ~1s cache hit while a refresh is a
  283s re-ingest that republishes a corpus concurrent readers are using —
  web-login endpoints), `resolve_provenance`,
  `serve` (ThreadingHTTPServer, loads `.env`, builds the registry from
  `ICARUS_STORAGE_ROOT`). `GET /`,`/health`,`/status`,`/map` (the repository
  map — `demo/repo_map.py` over `indexed_refs()` + the status snapshot; guarded
  by the SAME entitlement check as `/ledger`, since a private repo's file paths
  are at least as sensitive as the answers drawn from them, and it never
  reaches the writer),`/onboarding` (the tour PLAN -- constant, no writer, no
  retrieval, same entitlement gate),`/auth/github/callback`;
  `POST /ask`,`/connect` (checks `evals.github_access.repo_info` with the
  caller's token and refuses private repos before ingest; `sync_connect`/`ICARUS_SYNC_CONNECT`
  makes it block on `connect_sync` and return its final status directly instead
  of backgrounding it and returning 202 -- needed on request-scoped-CPU hosts
  like Cloud Run/Azure Container Apps, where a background thread's embed work
  after the response returns isn't reliably resourced; `connect_sync` itself is
  unchanged, this only changes who waits for it),`/disconnect`,`/auth/github/begin`
  (reads a `mode`: `web` → callback returns to `/?session=`, `app` →
  `icarus://`, Brick D's `extension` → the caller-supplied, validated
  `redirect_target`; a bad/missing `redirect_target` for `extension` mode is a
  clean 400, not a crash),`/auth/github/redeem`. `POST /onboarding` (`_handle_onboarding`) -- `{"step": ...}` -> one cited
  tour step in the IDENTICAL `build_payload` shape as `/ask` plus `step`/`title`,
  so every client renders the tour with the renderer it already has; shares
  `/ask`'s billed-writer rate limit and entitlement check; an unknown step id
  (including one measurement CUT from the tour) is a clean 400, never a silently
  invented question; and it is deliberately NOT written to the ask ledger, since
  machine-generated steps fired once per connect per user would swamp the
  questions a team actually asked and invent documentation debt nobody was
  looking for. `POST /explain` (Brick D, `_handle_explain`)
  — `{repo, path, start, end[, question]}` for a GitHub line selection; shares
  `/ask`'s billed-writer rate limit; refuses (409) unless `repo` matches the
  caller's currently connected repo, never silently answering about or
  switching to a different one; calls `lib.current_pipeline().explain(...)`
  and reuses `build_payload` unchanged (identical response shape to `/ask`).
  `POST /memory-gaps/record` requires a verified GitHub caller, read
  entitlement, an exact actionable open gap, bounded human-authored fields,
  and its own rate limit before calling `GitHubMemoryWriter`; returns success
  only with an observed pull-request URL and preserves a partial recovery URL.
- `demo/index.html` — the single-page UI: question box, cited-answer card, the
  honest-unknown hero, an `owner/repo` connect control, and **browser GitHub
  sign-in** (web-mode OAuth → session redeemed for a token held in
  sessionStorage, sent as `Authorization: Bearer` on `/ask`+`/connect`+`/status`),
  a public-alpha badge, and vanilla
  `fetch`. This is the typed **web staging link** (no voice/overlay — native only).
- `demo/test_links.py` — `ref_to_url` across pr/issue/code and bad input.
- `demo/test_payload.py` — `build_payload` for answer and honest-unknown shapes.
- `demo/test_per_claim_endpoint.py` — `per_claim` at the HTTP/MCP boundary: the
  payload has NO `claims` key unless asked for (so every existing client is
  unchanged), claim citations carry URLs like any other ref, the rest of the
  payload is untouched, and BOTH MCP tools always request `per_claim` — plus a
  guard that the tool description actually tells the agent `composed` is the
  label to verify, since an unexplained label is inert.
- `demo/test_context_endpoint.py` — `POST /context` at the real HTTP boundary, reusing `test_investigate_endpoint`'s exact harness (same engine, so the same fixture proves both). Pins what's specific to the new shape: no `investigation`/`verdict`/`answer` wrapper keys, a gathered PR reported even outside any conversation, `citations` narrower than `prs` (gate-verified vs. everything gathered), and the SAME tight rate-limit category `/investigate` uses (not the cheap `/ask` budget).
- `demo/test_mcp_server.py` — MCP handshake/tool contracts, evidence-rich honest
  unknowns, explicit selection forwarding, repo mismatch refusal, and the
  2026-08-07 reversal: a private repository IS served
  (`test_private_repo_is_served_like_any_other`, so reinstating a block breaks a
  named test) while a mid-answer repo SWITCH still refuses. Also pins automatic
  app-issued session acquisition/reuse and explicit development overrides.
- `demo/test_agent_sessions.py` — opaque agent-grant issuance, identity/repo
  scope, expiry, and unknown-token refusal.
- `demo/test_auth.py` — the bearer helpers: `bearer_token` parsing, the verifier's
  token→id mapping, cache hit/expiry, and network-error fail-safe (offline).
- `demo/test_github_oauth.py` — the web-login flow: authorize-url building,
  offline token exchange, and the single-use
  state/session lifecycle. Brick D's `extension` mode: the redirect_target
  carried through `begin`→`complete`, and the open-redirect guard rejecting a
  missing/non-chromiumapp.org/malformed-id target. `LoginScopeByModeTests`
  pins the per-surface scope: `web` asks `read:user` and must NOT ask for
  `repo`, while `app`/`extension`/the default keep `repo` (the three
  non-web cases passed before the change, so the web one failing first was a
  real red, not a vacuous fixture).
- `demo/test_library.py` — the `Library`: default repo, cache-hit vs. ingest,
  single-flight concurrent connect, generic (non-leaking) ingest errors, and
  private connect (token/private routing, refusal without the paid writer,
  token never in status output). T6 staleness: `_resolve` stays availability-
  only regardless of a stale corpus (the registry's tokenless eviction-replay
  safety invariant -- proven by deliberately re-merging staleness into
  `_resolve` live and confirming the guard fails), `_corpus_is_stale`'s scheme
  comparison (including a pre-T6 corpus with no "chunking" field at all), and
  `connect_sync`'s real refresh behavior: a stale public repo refreshes
  automatically, a stale private repo refreshes when a token is present, a
  stale private repo WITHOUT a token is served as-is rather than attempting a
  doomed re-ingest, and the committed default repo is never touched
  regardless of the flag.
- `demo/test_registry.py` — the registry: per-user isolation, per-user storage
  paths, the shared default pipeline built once, hostile-id rejection, LRU
  eviction, and disconnect deleting only that user's storage.
- `demo/test_queued_connect.py` — the queued ingest: `/connect` answers 202
  immediately and the job is OBSERVABLE. `connecting_to` names the repo an
  in-flight connect is working toward (`repo` only changes at the stage-1
  publish, so for the whole slow part status showed the PREVIOUS repo -- a
  running job and no job were indistinguishable, measured live on
  astral-sh/uv 2026-08-10), is cleared after failure so it never points at a
  dead job, and is only cleared by the call that owns it. Plus the red->green
  guard that the queued path passes `background_upgrade` -- it was dropped,
  so a queued connect ran stage 2 INLINE while the sync path backgrounded it
  (proven by reverting the kwarg and watching the test fail).
- `demo/test_ratelimit.py` — the limiter: allows up to the limit, blocks past
  it, a different key is unaffected, and the window sliding restores access.
- `demo/test_ledger.py` — the ask ledger: record/read round-trip, per-repo
  separation, the unknowns-only filter, most-recent-first + limit, surviving a
  new process, an unknown repo reading empty rather than raising, concurrent
  writes all landing and staying parseable, a hostile repo name unable to
  escape the ledger root, and the guard that **who asked is never recorded**;
  plus shared casefold identity, opaque IDs, and open→proposed→resolved memory
  lifecycle.
- `demo/test_server.py` — routing against a stub registry, plus the Origin guard
  (403), body cap (413), bearer-auth gate (401), per-request identity, rate
  limiting (429), `/disconnect`, concurrency, and index.html smoke checks.
  `/explain` (Brick D): cited answer with a line-ranged citation URL, honest
  unknown for uncovered locations, optional-question pass-through, wrong-repo
  refusal (409, never reaches the pipeline), and input validation (missing
  fields, non-integer/non-positive/inverted start-end, blank path).
  `/memory-gaps/record`: opaque gap selection, actionable-only writes,
  persisted proposal state, retry reuse even after the write limit is spent,
  and recoverable partial failures.
- `demo/test_isolation.py` — cross-user isolation proven at the HTTP boundary: a
  real `LibraryRegistry` behind a real server with two authenticated identities
  — connect, storage, disconnect, and provenance all stay disjoint.
- `demo/test_demo_live.py` — end-to-end live guard over the real pipeline; skips
  without a key or the corpus.
- `demo/test_semantic_wiring.py` — proves Brick C's semantic retrieval is wired
  into the SERVING pipeline: the demo builds a `HybridRetriever` when the embedder
  is present, falls back to `LexicalRetriever` when it isn't, and a second build
  over the same corpus dir embeds zero chunks (cache hit). Live tests self-skip
  without fastembed/the corpus.

## extension/ (Brick D — Chrome browser extension, Manifest V3, no build step)
- `extension/manifest.json` — MV3 manifest: `identity`+`storage`+
  `nativeMessaging` permissions,
  host permissions for `github.com` and the hosted brain (Azure Container
  Apps), a content script matching `github.com/*/*/blob/*` pages
  loading `lib.js` then `content.js`, a background service worker
  (`background.js`), and a toolbar popup (`popup.html`).
- `extension/lib.js` — the pure, DOM-free parse/gate functions
  `parseLineHash`, `parseBlobPath`, `isConnectedRepo`, `createLatestOnly` --
  URL-decodes paths, rejects unsafe line numbers/encoding, and supplies
  generation gates for stale async responses; dual CommonJS/browser-
  global export so the SAME file runs unmodified as a plain `<script>` in the
  extension and under `node --test` (no bundler, no npm install).
- `extension/render.js` — Brick D4's pure HTML-string builders
  (`renderAnswerHtml`, `renderUnknownHtml`, `renderLoadingHtml`,
  `renderSignedOutHtml`, `renderErrorHtml`), same dual-export pattern as
  `lib.js`. Mirrors `demo/index.html`'s voice/structure (citation chips by
  source type, "No one wrote this down.") and labels the public alpha without
  paid-writer or training claims.
- `extension/content.js` — the on-page logic: gates on the caller's connected
  repo (`GET /status`, re-read on navigation/selection so Mac-side repo
  switches are visible), listens for a real line selection via
  the Navigation API's `navigate` event (live-verified: covers both SPA
  file-to-file navigation and hash-only line changes; GitHub's `popstate`/
  Turbo/pjax events do NOT fire for this -- checked live, none did), and
  drives a real state machine (trigger -> loading -> answer/unknown/error/
  signed-out) via `showTrigger`/`showPanel`, with a close button. The trigger
  is a bar (`showTrigger`), not a bare button: a line selection also renders
  an optional question input alongside "Ask Icarus" -- empty submits
  `/explain`'s default "what does this code do, and why is it here?"; typed
  text is forwarded as `/explain`'s optional `question` field (server-side
  support pre-existed; this just exposes it). All brain calls
  (`fetchConnectedRepoStatus`, `askIcarus`) go through `chrome.runtime.
  sendMessage` to `background.js`, never a direct `fetch()` here -- a content
  script's fetch runs inside the GitHub page's own document, so it's bound by
  the page's CORS policy and, since github.com is https and the brain can be
  a loopback address, Chrome's Private Network Access preflight too; our
  brain has no CORS/OPTIONS handling, so a direct fetch failed with a bare
  "Failed to fetch" before any response arrived, silently -- live-verified
  the first time the extension was actually exercised end to end (D5), fixed
  by relaying every brain call through the background service worker
  instead, which isn't a "document" and isn't subject to either restriction.
  Two earlier live-testing bugs, still fixed: the stylesheet was injected
  lazily only inside `showPanel` (the first trigger a user ever saw was
  completely unstyled), and an inline `panel.style.position="relative"`
  silently overrode the CSS class's `position:fixed` (the panel rendered
  off-screen, `left:-24px` in a 1440px viewport) -- both confirmed live via
  `getBoundingClientRect()`/`getComputedStyle`, not guessed from a screenshot.
- `extension/background_bridge.js` — testable native-message policy: call the
  Mac host `com.icarus.extension` first, accept a real app refusal as
  authoritative, and use the older OAuth path only when Chrome cannot launch
  the host. Validates successful status/explain shapes before UI rendering.
- `extension/background_bridge.test.js` — native-first/fallback boundary,
  refusal preservation, and malformed-response contract tests.
- `extension/background.js` — MV3 service worker: the GitHub sign-in flow via
  `chrome.identity.launchWebAuthFlow`, using `demo/github_oauth.py`'s new
  `extension` OAuth mode; stores the token in `chrome.storage.local`. Also the
  ONLY place that fetches the brain (`fetchStatus`, `fetchExplain`, plus
  `signIn`'s own calls) -- a service worker isn't bound by the CORS/Private
  Network Access restrictions that block a content script's direct fetch (see
  `content.js`); `content.js` relays every brain call here via
  `chrome.runtime.onMessage`/`sendMessage` instead of fetching directly.
- `extension/popup.html` / `extension/popup.js` — toolbar popup for explicitly
  connecting/reconnecting the installed Mac app plus fallback GitHub sign-in;
  both actions require a real user gesture.
- `extension/lib.test.js` — `node --test` (Node's built-in test runner, zero
  npm installs, mirrors the Python side's stdlib-only ethos): 13 tests over
  `parseLineHash`/`parseBlobPath`/`isConnectedRepo`, including the D0-derived
  edge cases (inverted range, PR-diff-view path, case-insensitive repo match).
- `extension/render.test.js` — 16 tests over `render.js`: HTML-escaping,
  every citation shape (with/without a URL), the private/public repo label,
  and the guard against reintroducing the "paid writer"/"trained" claim.
- `extension/manifest.test.js` — manifest/file/package consistency, icon shape,
  narrow GitHub match pattern, brain host permission, and native bridge
  permission/dependency guards.
- `extension/package.sh` — explicit-allowlist zip packager for the Web Store or
  load-unpacked distribution; now includes the native bridge policy.
- `extension/e2e/` — Playwright persistent-Chromium harness loading the real
  unpacked extension on real GitHub pages. The controlled suite covers Python,
  TypeScript, C, main/master, repo switching, double-submit, stale navigation
  races, indexing, auth/entitlement, malformed payloads, cited answers and
  honest unknowns; `live.spec.js` reaches the deployed brain on explicit opt-in.
  Run unit contracts with `node --test extension/*.test.js`.

## mac/ (the macOS app — SwiftPM, SwiftUI + AppKit)
- `mac/.gitignore` — ignores SwiftPM build artifacts and the assembled `.app`.
- `mac/Icarus/Package.swift` — SwiftPM manifest: `IcarusKit` (UI-free logic),
  `Icarus` (the app), their unit-test targets, and the KeyboardShortcuts +
  Sparkle dependencies.
- `mac/Icarus/Package.resolved` — pinned dependency versions.
- `mac/Icarus/Icarus-Info.plist` — bundle Info.plist (mic + speech usage strings)
  assembled into `Icarus.app` for TCC.
- `mac/Icarus/scripts/bundle.sh` — wraps the SwiftPM binary into an ad-hoc-signed
  `Icarus.app` (required for microphone access).
- `mac/Icarus/scripts/package_dmg.sh` — builds a shareable `Icarus.dmg`: runs
  `bundle.sh`, stamps `ICARUS_BRAIN_URL` and (when configured) the Sparkle
  update feed `SUFeedURL`/`SUPublicEDKey` into the bundle Info.plist, re-signs
  with the SAME identity `bundle.sh` used (re-signing ad-hoc here would
  silently undo a stable certificate), and lays out a drag-to-Applications DMG
  with a first-open `READ ME FIRST.txt`. Refuses a HALF-configured update feed
  (one of the two vars) and refuses to package an ad-hoc-signed app -- that
  would change its Keychain identity on every update.
- `mac/Icarus/scripts/make_signing_cert.sh` — one-time, run interactively:
  creates the self-signed "Icarus Self-Signed" code-signing certificate in the
  login keychain. Ad-hoc signing makes the app's designated requirement its own
  `cdhash`, which changes every build, so the login Keychain treats each update
  as a different app and re-prompts the user for their saved GitHub token
  (measured: `designated => cdhash H"877f0a45…"`). A certificate makes the
  requirement `certificate leaf`, stable across builds -- one prompt ever.
  Does NOT help Gatekeeper; the app is still unnotarized. `bundle.sh` detects
  the identity BEHAVIOURALLY (a self-signed cert is not "valid" to
  `security find-identity -p codesigning`, yet `codesign` signs with it fine)
  and falls back to ad-hoc, so a fresh clone or CI still builds.
- `mac/Icarus/scripts/make_update_keys.sh` — one-time, run interactively:
  wraps Sparkle's `generate_keys` to create the EdDSA pair that signs the
  update feed. The private half stays in the login keychain and is the entire
  security of the update path (Sparkle does not rely on notarization); lose it
  and you can never update an installed copy again, leak it and anyone can push
  code to every installed copy. Prints the public key to stamp via
  `ICARUS_UPDATE_PUBLIC_KEY`.

### mac/Icarus/Sources/IcarusKit (UI-free, unit-tested)
- `Models.swift` — the brain's JSON contract: `Verdict`, `Citation`,
  `AskResponse`, `RepoStatus`, `MemoryGap`, `MemoryGapsResponse`,
  `MemoryRecordResult`, and `IndexCounts` (real `/status` counts). Memory gaps
  carry the server's opaque ID and `open`/`proposed`/`resolved` lifecycle.
- `BrainClient.swift` — the HTTP client to the brain (`/ask`,`/connect`,
  `/disconnect`,`/status`,`/auth/github/begin`,`/auth/github/redeem`,
  `/auth/agent/session`,`/ledger?gaps=1`,`/memory-gaps/record`,`/explain`);
  attaches an `Authorization: Bearer` from a shared token; sends opaque gap IDs
  for memory proposals; injectable URLSession.
- `NativeMessageCodec.swift` — bounded 64 KiB Chrome native-message framing,
  one-message-per-process reader, and the closed `ping`/`status`/`explain`
  request contract.
- `NativeHostManifest.swift` — validates canonical Chrome extension origins,
  generates the exact-origin native-host manifest, and atomically installs it
  under the current user's Chrome configuration.
- `SharePreferences.swift` — the "help improve Icarus" toggle's store, read
  off the main actor at request time by `BrainClient`. Defaults **OFF**,
  matching the server's counts-only default: sharing the questions someone
  asks and the private code Icarus cites is not a decision a default gets to
  make, on either side of the wire. Shares one UserDefaults key with
  `SettingsView`'s `@AppStorage` so the two can never drift apart.
- `SharePreferencesTests.swift` — the store's contract: defaults to NOT
  sharing, both directions persist, and it reads the exact key `@AppStorage`
  writes.
- `SavedConnection.swift` — persists the last-connected repo
  (injectable UserDefaults) and the pure `isLost` check behind the
  eviction/restart lost-connection banner.
- `BrainEndpoint.swift` — resolves the brain URL from the bundle's
  `ICARUS_BRAIN_URL` Info.plist key (stamped at package time → hosted brain),
  falling back to `127.0.0.1:8000` for dev; pure + unit-tested.
- `WebAuth.swift` — the `WebAuthenticating` protocol (abstracts the auth sheet) +
  `parseCallbackSession` (pull the one-time session id from the `icarus://` URL).
- `TokenStore.swift` — the token-store protocol + an in-memory test double (the
  real store is `KeychainTokenStore`).
- `SpeechRecognizer.swift` — streaming speech-to-text protocol + a stub.
- `VoiceModel.swift` — `@Observable` push-to-talk orchestrator: live
  `partialTranscript`, silence → empty → not emitted.
- `VoiceLatencyTracker.swift` — bounded, duration-only Phase 3 measurement for
  hotkey hold, transcript finalization, brain answer, and system speech start;
  keeps the newest 50 samples in memory and derives release-to-speech p50/p95
  without accepting or retaining any content.
- `AskHistory.swift` — the real in-session ask record (most-recent-first,
  `unknowns` filter, `citedRate` nil until the first ask); powers the shell.
- `ShellNav.swift` — `ShellSurface`, the sidebar surfaces + their titles;
  `.startHere` (the guided tour) sits directly under Home, since it is the
  first experience with a newly connected repo, and `.investigate` follows it —
  something you DO, ahead of the two history surfaces you look back at.
- `Onboarding.swift` — the tour client-side: `OnboardingPlan`/`OnboardingStep`
  (`GET /onboarding`), `TourStepAnswer` (`POST /onboarding` -- decodes the FLAT
  `/ask` payload plus `step`/`title`, so one shape is decoded one way
  everywhere), and `TourModel`, an `@Observable` that walks the plan, fetches a
  step at most once, and keeps a transport FAILURE strictly separate from an
  abstention. Holds no session: the brain's tour is stateless, so interrupting
  and resuming costs nothing. An unknown step `kind` decodes to `.unsupported`
  and is skipped, so a newer brain can add steps without breaking an older app.
- `Freshness.swift` — `Freshness` + **`IndexFreshness`**, staleness as a
  CLOSED SET of cases (`matches` / `behind(Int?)` / `unknown` / `pinned`)
  rather than the optional Bool it decodes from. That is the whole point: a
  `Bool?` invites `?? false` at a call site, which would render "I could not
  check" as "up to date" — the one thing the server half was built never to
  do. An enum has no default to fall into. `offersRefresh` is false for
  `unknown` (offering a refresh implies knowing it is stale) and for `pinned`
  (the server forbids refreshing the demo corpus, so the button would lie).
  Decodes only what a view reads (`headCommit`/`checkedAt` were cut in the
  2026-07-30 ponytail audit — decoded but never rendered; add back the moment
  a view needs them).
- `Briefing.swift` — `Briefing` + **`BriefingChange`** (`firstVisit` /
  `nothingChanged` / `changed(Int)` / `unknown`), same reasoning: `?? 0` on
  `commits_since` would turn "couldn't work out what changed" into "nothing
  changed". The server also returns a `stored` block (the decision doc's
  transparency property); not decoded here since no view surfaces it yet
  (cut in the 2026-07-30 ponytail audit — add back with the view that needs it).
- `Investigation.swift` — `POST /investigate` decoded: `Support`
  (explicit/strong/weak/unsupported, each with a `headline` saying what it IS
  rather than how good it is — "weak" alone reads as a poor answer when it is
  actually a statement about what the repository RECORDED), `Finding`,
  `InvestigationStep`, `Contradiction` and `InvestigationTrace`. The answer
  itself decodes through the EXISTING `AskResponse`, so the trace is additive
  and there is never a second way to render a verdict. `orderedFindings` /
  `findingsBySupport` put what the repository states before what was inferred
  and keep them in separate groups — rendering both in one confident voice is a
  bluff the honesty gate cannot catch, since every citation under an inference
  is just as real. An unknown support class decodes to `.unrecognised` and
  renders in the most cautious voice, never the boldest. `needsCaveat` is true
  when a run was cut short or the evidence conflicts.
- `RepoMap.swift` — `GET /map` decoded: `indexed*` counts, documentation
  (`readme: nil` when none was indexed), `EntryPoint`/`EntryPointRule` (every
  entry point carries the RULE that produced it), truncation, exclusion RULES
  and limitations. Field names mirror the brain's on purpose -- the map
  describes what Icarus READ, never what exists in the repository. Decodes
  only the fields a view actually reads — `indexedChunksBySource`,
  `EntryPointRule.evidenceRef`, and `IndexedStructure`'s `unresolvedImportCount`/
  `Component.fileCount`/`.dependsOn`/`.evidenceRefs`/`CoreFile.evidenceRef` were
  cut in the 2026-07-30 ponytail audit as decoded-but-unrendered; the server
  still sends them, Codable just ignores what nothing reads.

### mac/Icarus/Sources/Icarus (the executable app)
- `IcarusApp.swift` — `@main`; no window, delegates to `AppDelegate`.
- `AppConfig.swift` — app-wide config; `brainBaseURL` resolves the brain via
  `BrainEndpoint` over `Bundle.main` (hosted in a shipped build, local otherwise).
- `AppDelegate.swift` — app wiring: activation policy, menu-bar item, hotkey,
  push-to-talk, shared models (auth/connect/voice/history/status), and the
  primary shell window (setup is folded into its Home gate). Also confirms and
  installs an exact-origin Chrome native bridge from the explicit
  `icarus://install-extension-bridge` callback.
- `OverlayController.swift` — owns the ⌘⇧I ask overlay + ask/voice/speak wiring;
  records each ask into the shared `AskHistory` and marks the live Phase 3
  release/transcript/answer/speech-start timeline.
- `FloatingPanel.swift` — a translucent, non-activating, chromeless `NSPanel` that
  floats above other apps (hidden transparent title bar).
- `OverlayView.swift` — the overlay UI: question, cited answer, honest unknown.
- `AskModel.swift` / `AuthModel.swift` / `ConnectModel.swift` — `@Observable`
  state for asking, GitHub web login (Keychain-persisted token), and repo connect
  (public alpha; saves/resumes the connection via `SavedConnection`,
  `disconnect()` deletes server-side data, `.lost` when the server drops the
  session). A re-read remains visibly in progress until `/status` confirms the
  refreshed index is current, preventing accepted background work from looking
  inert and blocking duplicate clicks. Shared via `AppDelegate`.
- `AppleWebAuth.swift` — the real `ASWebAuthenticationSession` sheet (GitHub login,
  captures the `icarus://` callback); ephemeral browser session so Sign out → pick
  another GitHub account. Completion handler is non-isolated (fires off-main).
- `KeychainTokenStore.swift` — the real `TokenStore`: the GitHub token in the login
  Keychain (`WhenUnlocked`), so sign-in persists across launches; Sign out deletes it.
- `AgentSessionCommand.swift` — the headless `Icarus --agent-session` bridge:
  uses the Keychain-backed app client to mint a short-lived read-only Icarus
  credential and writes only that credential, expiry, repo, and brain URL to
  stdout.
- `McpCommand.swift` — the production `Icarus --mcp` stdio server entry point:
  keeps JSON-RPC stdout clean, refuses redirects carrying an agent bearer,
  surfaces signed-out failures as tool errors after a successful handshake,
  and remints once after expiry, restart, or repository switching.
- `ClaudeConnector.swift` — finds Claude Code even from a GUI app's minimal
  PATH, diagnoses the effective `icarus` MCP registration, installs the app at
  user scope, migrates only the known checkout-only Python adapter, and refuses
  to overwrite an unrelated same-name server.
- `SettingsView.swift` — native Settings UI for explicit Claude Code
  install/repair without hand-editing configuration files.
- `ExtensionBridgeCommand.swift` — one-process/one-request Chrome native host;
  reads the Keychain-backed credential, proxies only `ping`, `status`, and
  `explain`, reports signed-out status honestly, and returns framed JSON without
  ever emitting the GitHub token.
- `Updater.swift` — in-app updates via Sparkle, so shipping a change stops
  meaning "email every tester and ask them to re-download". Sparkle signs its
  own feed with an EdDSA key, so this needs no Apple Developer ID -- it does
  not make the app notarized, it removes every step AFTER the first install.
  Deliberately INERT unless the build carries both `SUFeedURL` and
  `SUPublicEDKey`: a feed without a key would let Sparkle install an update it
  cannot verify, which is worse than having no updater, so it refuses rather
  than degrades. `isConfigured` lets the menu hide an item that would do
  nothing.
- `IconArt.swift` — the Icarus mark in Core Graphics (no asset pipeline): spread
  wings rising from a downward V. `markPath` is parametric (feather count, angle/
  length/width ramps, and `covertsReach` — the solid leading-edge mass, without
  which the separated feathers read as spikes rather than a wing), and ONE wing is
  built then mirrored, so the halves cannot drift. It is the single definition of
  the logo on this platform: `appIcon` (Dock tile), `menuBarGlyph` (monochrome
  template), `markGlyph` (flat, for the shell sidebar), the `.icns` baked by
  `IconExport`, and the four `extension/icons/*.png`. The website repeats the same
  geometry as SVG (`site/index.html` header mark + data-URI favicon) — generated
  from these numbers, NOT shared with them, so a change here must be regenerated
  there; nothing will fail if it isn't.
- `IconExport.swift` — headless renderers invoked by the bundler and by hand:
  `--render-iconset` (used by `bundle.sh`) bakes `IconArt.appIcon()` into a static
  `AppIcon.icns` so the Dock/Finder/DMG aren't a blank tile before first launch,
  and `--render-png <path> <px>` writes one square PNG — how `extension/icons/`
  is regenerated, so the browser icons come from the app's own drawing code rather
  than a hand-made asset. `Main` (in `IcarusApp.swift`) intercepts both.
- `Theme.swift` — the Honest-Brutalism tokens, DARK since 2026-08-10: the same
  token names the light palette used, carrying the website's values, so ~60
  call sites flipped without being edited. `citedBg`/`unknownBg` are now
  TINTS of their own tone (an opaque pastel has no dark equivalent).
  `display()` is the serif face, resolved once against what the Mac actually
  has (`Font.custom` falls back SILENTLY, so the family is probed explicitly);
  spent on hero moments only. Also `GlassPanel` — the overlay's CLEAR glass,
  which replaced `VisualEffectBackground` (deleted): transparent glass is the
  absence of vibrancy, so there is no `NSVisualEffectView` any more. Its alpha
  is 0.65 because 0.55 — chosen by eye and approved in a wireframe — measured
  3.56:1 against a white backdrop, under WCAG AA; pinned by a test, since the
  worst case (a white window behind clear glass) is invisible in a screenshot.
  Plus the shared views (`MonoLabel`, `CitationChip`, `PrimaryButton`,
  `WaveformView`, `FlowLayout`).
- `AppleSpeechRecognizer.swift` — `SFSpeechRecognizer` + `AVAudioEngine`; uses
  on-device recognition when available and Apple's service otherwise.
- `PushToTalkMonitor.swift` — hold Right Option (⌥) to talk via a global
  `.flagsChanged` monitor.
- `Speaker.swift` — `AVSpeechSynthesizer`; speaks the answer and the honest
  unknown, with barge-in; its delegate reports when system speech actually
  starts for latency measurement.

### mac/Icarus/Sources/Icarus/Shell (the full app shell — the primary window)
- `ShellView.swift` — sidebar + content router across four surfaces (passes
  auth/connect through to Home for its setup gate).
- `SidebarView.swift` — brand mark, nav rows, the real connected-repo footer
  (with the public-alpha badge), Disconnect
  repo + Sign out controls. Real macOS traffic-lights float over its top; no
  decorative dupes.
- `HomeView.swift` — until a repo is connected, the `SetupView` gate; once ready,
  the dashboard: hero (real ⌥ trigger), metrics (real `/status` counts + session
  cited-rate), recent asks, and the proof drawer — all real/honest data.
- `SetupView.swift` — the in-shell setup gate (Sign in with GitHub → connect a
  public repo), driving the shared `AuthModel`/`ConnectModel`; hosts
  the lost-connection banner (server restart/eviction → explicit Reconnect,
  never a silent fallback to the public default). Replaces the old separate
  onboarding window.
- `OnboardingView.swift` — the "Start here" surface: the guided tour. Shows
  the exact question Icarus asked on the user's behalf, renders an abstention
  in full (never skipped or softened) and splits "still indexing" from "no one
  wrote this down", renders a transport failure as a failure rather than an
  abstention, and opens with the writer-free `/map` overview (files, languages,
  folders, documentation, and where to start reading with each rule's reason).
  Back/Next plus "Ask your own question", which needs no session to return from.
- `ShellSurfaces.swift` — Decision history plus the Engineering Memory surface:
  observable open/proposed/recurring/resolved gaps, honest load failure, and the
  structured “Record engineering memory” reviewed-proposal sheet. Proposed
  gaps link to the existing pull request and cannot create another. The prior
  Ask-by-voice and Privacy-boundary navigation sections were removed; underlying
  voice and privacy enforcement remain elsewhere.
- `InvestigationModel.swift` — runs an investigation for the Investigate
  surface. Holds NO conversational state: the server owns what "it" refers to
  (`demo/investigations.py`), so every client resolves references the same way
  and a follow-up cannot be aimed at a subject the server never agreed to.
  `fresh: true` is sent on the first question of a transcript only — sending it
  on a follow-up would discard the very subject that follow-up depends on. A
  transport failure is kept strictly separate from an abstention.
- `InvestigationView.swift` — the Investigate surface: the answer with its
  receipts, then findings GROUPED by what the repository records versus what was
  inferred, what is still unknown, and the step trail ("HOW IT GOT THERE") that
  is the actual product. The caveat block (cut short / conflicting evidence)
  renders ABOVE the findings on purpose — after them it reads as a footnote to a
  conclusion already accepted. A follow-up shows the resolved subject, so a
  misunderstanding is visible BEFORE a confident answer about the wrong change.
- `LedgerModel.swift` — loads server-owned Memory Gap lifecycle state and submits
  a human-authored GitHub memory proposal by opaque gap ID, blocks overlapping
  submissions, and surfaces only an observed pull-request URL as success.
- `ShellComponents.swift` — shared shell views (`MarkView`, `NavRow`,
  `VerdictPill`, `HistoryRow`, `ShellCard`). `MarkView` RENDERS `IconArt` rather
  than redrawing the logo in SwiftUI, so the sidebar can never disagree with the
  Dock icon about what the mark is.
- `StatusModel.swift` — polls `/status` for the real repo + index counts.
- `MainWindowController.swift` — hosts the shell as the primary window with a
  chromeless (transparent, full-size-content) title bar.

### mac/Icarus/Tests/IcarusKitTests
- `WebAuthTests.swift` — `parseCallbackSession` pulls the session id from the
  `icarus://` callback; nil on a malformed/session-less URL.
- `ModelsTests.swift` — decoding the brain's JSON, including real `IndexCounts`
  and the `private` flag (absent → public default).
- `TokenStoreTests.swift` — the in-memory token store's save/load/delete.
- `VoiceModelTests.swift` — push-to-talk states; silence → no question.
- `VoiceLatencyTrackerTests.swift` — complete-stage arithmetic, out-of-order
  refusal, 50-sample bound, release-to-speech percentile calculation, and
  replacement of incomplete journeys.
- `AskHistoryTests.swift` — record order, unknowns filter, cited-rate (nil first).
- `BrainClientTests.swift` — the bearer token is sent when present, omitted when
  absent; `/disconnect` POSTs with the bearer and decodes the fresh snapshot;
  `/auth/agent/session` uses the GitHub bearer and decodes the scoped short
  credential; memory recording sends `gap_id` and never display text
  (URLProtocol stub).
- `LedgerTests.swift` — decodes the server-owned open/proposed/resolved Memory
  Gap contract, including the existing pull-request URL, and rejects unknown
  lifecycle states instead of inventing one.
- `ShellNavTests.swift` — the four surfaces' order, titles, and stable ids.
- `NativeBridgeTests.swift` — production pipe-reader framing, size, and
  one-frame-per-process guards; closed action decoding, exact Chrome origin
  allowlisting, and install-URL validation.
- `BrainEndpointTests.swift` — `BrainEndpoint.resolve` uses a valid hosted URL,
  falls back on missing/empty/invalid, and honors an explicit fallback.
- `OnboardingTests.swift` — the tour's decoding + `TourModel`: plan/step
  shapes, an unknown step kind surviving, an abstention decoded and shown
  as-is, question steps fetched once then remembered, map steps never billing
  the writer, the tour not running off either end, and a failed step surfacing
  as an ERROR rather than an abstention.
- `InvestigationTests.swift` — decoding + display rules: the answer reusing
  `AskResponse`, each support class's headline, an unrecognised class landing in
  the most cautious voice, recorded-before-inferred ordering that is stable
  within a class, caveats for truncation and conflict, and a trail step
  surviving a numeric argument or a missing reason.
- `RepoMapTests.swift` — `RepoMap` decoding, a missing README as nil (not an
  empty string), and deterministic biggest-first language/directory ordering.
- `BrainContractTests.swift` — decodes the brain's REAL captured responses
  (`Fixtures/*.json`, curled from a running `demo.server` on
  `simonw/sqlite-utils`, 2026-07-29) rather than hand-written ones: every other
  decoding test proves the decoder is self-consistent and nothing about the
  server, and a renamed key would surface to a user as "couldn't reach the
  brain". Also pins that the real map publishes no repository-total or
  excluded-file count, that every real entry point carries its rule, and that
  the real `purpose` step cites a `doc:` ref -- the measured README fix.
- `SavedConnectionTests.swift` — the saved-connection store round-trip/clear and
  every branch of the `isLost` downgrade check (ready-elsewhere = lost;
  indexing/error/no-save = not lost; case-insensitive repo match).

### mac/Icarus/Tests/IcarusAppTests
- `ThemeContrastTests.swift` — the palette's conscience. Every other test in
  the app is a logic test: all 219 passed, unchanged, while the entire
  interface was repainted light → dark, and would pass just as happily with
  muted text at 1.4:1 on the page. Measures WCAG contrast for every pairing
  the app renders (body, secondary, the three semantic tones, the hairline
  tripwire) and composites the overlay tint onto WHITE to prove the answer
  survives clear glass over someone else's document — the assertion that
  caught the eyeballed 0.55 alpha. Asserts RATIOS, not hex values, so a
  retune keeps passing and an unreadable retune fails.
- `InvestigationModelTests.swift` — failure truthfulness on the Investigate
  surface: 401/403/429/503 are server REFUSALS and are reported as what the
  server said (`BrainError.userMessage`), while only a real transport error
  reads as a connection problem. Collapsing the two told a signed-out user to
  check their network.
- `ConnectModelTests.swift` — app-model boundary proof that an accepted
  background repository re-read stays visibly in progress while the index is
  stale and completes only after `/status` confirms freshness.
- `ExtensionBridgeCommandTests.swift` — exercises the real native-host handler
  for signed-out status plus proxied status/explain response shapes without
  installing a host in the test browser.
- `McpCommandTests.swift` — newline-delimited stdio framing and notification
  silence, plus the stale repository-bound session remint/retry path.
- `ClaudeConnectorTests.swift` — shipped-app detection, safe legacy migration,
  current Claude CLI command shape, and refusal to overwrite a same-name custom
  server.

## .claude/agents/ and .codex/agents/
- `.claude/agents/opus-architect.md` — the opus-architect agent (principal
  architect / adversarial reviewer).
- `.claude/agents/sonnet-test-writer.md` — the sonnet-test-writer agent
  (adversarial test writer / bounded implementer).
- `.codex/agents/opus-architect.toml` / `.codex/agents/sonnet-test-writer.toml` —
  the same two agents defined for the Codex tooling.
