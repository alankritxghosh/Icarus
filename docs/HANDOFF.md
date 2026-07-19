# Icarus — Session Handoff (2026-07-19: tester-driven fixes — live PR/issue fetch, lean-ingest 2a+2b + scaled embed timeout, app banner, CI-now-green + DMG artifact job; voice-pill design chosen)

**READ THIS FIRST — supersedes every engineering-state claim below. Does NOT
supersede the 2026-07-16 business-path mandate** (ICP/pricing/trust-legal/
outreach is still the default once engineering settles). This session was
entirely tester-feedback-driven — real remarks from people trying Icarus,
fixed the prescribed way (reproduce/root-cause in real code → red→green →
verify → deploy). **Live revision at end of session: `icarus-brain--0000017`,
healthy, 100% traffic, 4 GiB/2 CPU, AST chunking ON. `main` tip is the handoff
commit (was `9ca9f61` before this doc update).**

## What shipped this session (all verified, not assumed)

**1. Live on-demand PR/issue #N fetch (fix "1"; commit `ed65505`, rev 0000015).**
Tester on react/react: "talk to me about PR 400" → "no one wrote this down".
Root cause: ingest indexes only the most-recent `PR_LIMIT=200` PRs, and react
has ~34k — PR #400 is never in the corpus. Also we never fetched PR/issue
COMMENTS (title+body only). Fix: `evals/ingest.fetch_ref_detail(repo, number)`
live-fetches ONE PR/issue + its comments (`gh pr view`→`gh issue view`,
fail-safe None); `GatedPipeline(live_fetch=…)` anchors an explicit `#N` that
isn't in the indexed slice; `synth.build_prompt` gives pr/issue the larger
(code) budget so comments reach the writer; `demo/library` wires it
**public-safe** (token-less — a private repo the server can't read fails to a
safe abstention, no exposure; private exact-ref would need the caller's
request-time token, a known gap). Live-verified: react PR #400 fetches with
body+comment. Board GREEN.

**2. Lean-ingest, brick by brick (the "why not a background task / we lose
code+docs" remark).** Decomposed into 2a/2b/2c:
- **2a — honest coverage (`f2161cd`).** The 50k-chunk / 100 MB caps already
  truncate a big repo but only logged to stderr — the user never knew the index
  was PARTIAL. Now `fetch_code` records a cap-hit (a `stats` out-param),
  `ingest_repo` threads it into `write_meta`'s new `truncated` field, and
  `/status` exposes it. Dropped-file "no one wrote this down" is now
  explainable, never mistaken for full coverage.
- **2b — packed float32 vectors (`5f02155`, rev 0000016).** The
  `dict{ref: list[float]}` representation is what OOM-killed the container:
  measured **248.5 MB → 30.7 MB (8.1×)** for 20k×384. `SemanticRetriever` now
  packs vectors into a numpy float32 matrix + row norms; search is one matmul
  (faster at scale too). numpy is LAZY (ships with fastembed → always in
  serving; ABSENT in the stdlib-only test env) with a pure-Python fallback —
  identical rankings both ways, proven on the paid board + both interpreters.
  Blast radius stayed inside `retriever.py` (the cache/library `{ref:vector}`
  contract untouched).
- **Scaled embed timeout (`9ca9f61`, rev 0000017).** Live-tested transformers
  (via local repro — 50,700 chunks, HIT the 50k cap so it's a partial index):
  **it does NOT OOM anymore — 2b confirmed** (ran on a 9 GB Mac at ~1.9% mem,
  nowhere near 4 GiB). But a NEW bottleneck surfaced: embedding is ~sequential
  and slow (~30-40 min for 50k), and the fixed **900s** background-embed timeout
  was silently killing it → stuck lexical-only. **Batched embedding was
  investigated and REFUTED — measured 3.3x SLOWER** on real code (fastembed pads
  every text in a batch to the longest one; confirms the pre-existing "batching
  is slower" note) — NOT built. Instead scaled the timeout: `_embed_timeout(n)` =
  `max(900s, ~0.1s/chunk)`, so a 50k repo gets ~83 min and its background
  semantic embed can finish. Big-repo story is now coherent: 2b (no OOM) + 2a
  (honest "partial index") + scaled timeout (semantic isn't cut off).
- **2c — true async background ingest with live progress: NOT STARTED.** The
  "background task instead of all at once" part. Next real brick (note: a big
  repo's semantic embed is inherently ~1 hr; 2c is about UX/progress, not speed —
  faster embedding would need length-bucketed batching or a smaller model, both
  deferred and unproven).

**3. App-side partial-index banner (`32fb86f`).** `RepoStatus` decodes the new
optional `truncated`; `HomeView` shows an amber "Large repo — partial index"
banner (honest-unknown palette) when set. **Compile-verified on CI only** — see
CI note below.

**4. CI was silently RED on Swift — now green, plus a real bug fixed.**
`Package.swift` declared swift-tools 6.0 but the `macos-14` runner had Swift
5.10, so the `swift` job failed at the tools-version gate on EVERY push
(independent of any change). Journey (recorded so it isn't re-attempted wrong):
lowering tools→5.10 was WRONG — the app is written against Swift 6's
actor-isolation model, so 5.10 cascaded `main actor-isolated … non-isolated`
errors across every SwiftUI view (a full re-annotation, not a fix). Reverted to
6.0 and pointed CI at **`macos-15` / Xcode 16.3+/Swift 6.1** (the pinned
`KeyboardShortcuts 2.4.0` needs tools 6.1, so even Xcode 16.0.3 was too old).
Now green (`76a5b63`). Also fixed a genuine **`VoiceModel` concurrency capture**
(`[weak self]` on the nested Task; `7db4bda`) surfaced along the way — correct
under 6.x too.

**5. On-demand DMG artifact CI job (`000366a`).** New `.github/workflows/dmg.yml`
(`workflow_dispatch` + `alpha-*` tags) builds `Icarus.dmg` on macos-15 via
`scripts/package_dmg.sh`, stamps the live brain URL, and uploads it as a run
artifact. **Verified by an actual run: a real 864 KB `Icarus-dmg` artifact.**
Testers now get a ready-to-run app WITHOUT a local Xcode: Actions → "dmg" → Run
workflow → download the artifact → follow the bundled READ ME FIRST.

**6. Voice-pill UI redesign — DESIGN CHOSEN, code NOT started.** Tester: the
speech-to-text surface is too big/clunky; wants a Wispr-Flow-style bottom-of-
screen pill ("wayform" = waveform + "glass finish"). Built 3 Figma mockups
(file `Icarus — Voice Pill Options`, key `wXMrZTiioqV9OLm3iPX4r1`, Pantheon
team). **Alankrit chose Option A: a glass pill that morphs upward into a flat,
honest answer card; hold-⌥ to talk.** Reusable pieces for the build:
`FloatingPanel` (reposition to bottom-center pill), `VoiceModel.partialTranscript`
(live transcript already streams), `PushToTalkMonitor`. Genuinely new work: the
pill layout, a REAL audio-reactive waveform (tap `AVAudioEngine`'s mic power —
must not be a fake loop, per "no fake confidence"), and the listening→answer
transition. Not built.

## Open / next (nothing here is started unless said)

- **Confirm transformers LIVE in the app** (only proxy-verified via local repro
  so far): connect it, watch it NOT OOM, reach lexical-ready fast, and finish
  the background semantic embed within the scaled timeout (~1 hr). Couldn't do
  this from here — /connect needs the caller's GitHub auth.
- **2c — async background ingest with live progress** (the remaining lean-ingest
  brick). NB: a big repo's embed is inherently ~1 hr — 2c improves the UX/
  progress of that wait, it does not speed it up.
- **Text-memory reduction** (only if a repo bigger than transformers OOMs
  despite 2b): BM25 keeps only tokens; load top-k full chunk text on demand.
  The chunk texts are the other big in-RAM cost 2b doesn't touch — NOT needed
  for transformers (which fits comfortably now), so this is speculative.
- **Faster embedding** is deferred and UNPROVEN: batched is 3.3× slower here;
  the only candidates are length-bucketed batching or a smaller model — don't
  attempt without measuring first.
- **Voice pill Option A** — design chosen, implement per §6.
- **DMG for testers** — run the `dmg` workflow (or push an `alpha-*` tag) to
  produce a build; the app banner ships with it.

## Environment constraints discovered this session (save the rediscovery)

- **This Mac has NO Xcode — Command Line Tools only** (`xcode-select` →
  `/Library/Developer/CommandLineTools`). So Swift can't be built/tested and the
  DMG can't be packaged LOCALLY here — use CI (now green) for both.
- **numpy** is present in serving (`.venv`, via fastembed) but ABSENT in the
  stdlib-only test env (system `python3`) — this is why 2b's numpy path is lazy
  with a pure-Python fallback; run numpy-path tests under `.venv`.
- Deploy path unchanged: `az acr build` is BLOCKED (ACR Tasks disabled) → build
  LOCALLY `--platform linux/amd64`, push to ACR `caec8849f1f0acr`,
  `az containerapp update`. Each redeploy resets active user sessions.

---

# Icarus — Session Handoff (2026-07-18 late: leanness pass shipped, AST-on-in-prod, live pressure test found+fixed a P0, capacity ceiling proven — 4 deploys)

**READ THIS FIRST — supersedes every engineering-state claim below. Does NOT
supersede the 2026-07-16 business-path mandate** (ICP / pricing / trust-legal /
outreach is still the default job once engineering settles). This was a long,
productive engineering session driven by real live testing — not open-ended
building. Live testing surfaced real gaps and they were fixed the prescribed
way (reproduce live → root-cause in real code → red→green → verify → deploy).
**The live revision at end of session is `icarus-brain--0000014`, healthy,
100% traffic, 4 GiB / 2 CPU.**

## What happened, in order (all verified, not assumed)

**1. Ponytail leanness pass (committed `07dbd7f`, deployed rev 0000011).**
Deleted dead hosted-embedding code (`GeminiEmbeddingProvider`/
`PaidGeminiEmbeddingProvider` + `has_embedding_provider_key` — nothing selected
them once serving standardized on `LocalEmbeddingProvider`), the
`_default_build_pipeline` alias, and two abandoned git worktrees. **Wired Brick
Q into serving** (`demo/library.py._build_retriever` now wraps the retriever in
`NormalizingRetriever` — it was proven-in-eval but dead in production). Net
~−90 dead lines; Brick Q's ~114 lines moved from dead to live. evals/demo green;
the query-normalization recall eval was re-run in the `.venv` (fastembed) and
passed (it self-skips without fastembed — that env gap is why my first runs
showed high skip counts).

**2. AST chunking flipped ON in production (rev 0000012).** `ICARUS_AST_CHUNKING`
was OFF; verified the tree-sitter grammars actually load in the deployed image
(tsx/js/java/kotlin/objc) BEFORE flipping. Now fresh connects AST-chunk Python +
JS/TS/JSX/ObjC/Java/Kotlin; `.h`/Go/Rust/C/Ruby stay on line-windows by design.
**T6 staleness means a previously-connected repo auto re-ingests on its next
connect** (scheme changed) — expected, not a bug. Verified live on excalidraw:
`.tsx` median chunk dropped ~10× (2,234 → ~229 tokens); ~22% of chunks still
exceed the 512-token embed budget (large single functions AST keeps whole — an
honest, disclosed limit, not a defect).

**3. Live pressure test — 10 heavy-LOC repos, honesty-first (scorecard artifact
built for tracking).** Result: **honesty groundedness held on 30/31 questions;
8/9 fabricated-premise probes correctly abstained.** Two verification lessons:
TWICE (excalidraw `types.ts`, tokio budget=128) a "why/what" I expected to trip
it was actually CORRECT — well-maintained repos document rationale in comments
more than a skeptic assumes. Also confirmed the morning's finding that **voice
transcription (not the brain) causes false abstentions** — a garbled mic
question ("X Calle draw") abstains where the typed version answers perfectly.

**4. THE P0, found + fixed + deployed same day (rev 0000014, commit `54b6cd4`).**
"How does Redis's **HYPERVECTOR** data type store embeddings?" got a confident
CITED answer. Redis has no HYPERVECTOR type, but its real vector code
(`modules/vector-sets/`, `src/vector.c`) let the writer ground to adjacent real
code and answer as if it existed — groundedness held, but the SUBJECT was
fabricated. This is the disclosed honesty gap (handoff Part 3, Decision 5), now
proven live. **Fixed with guard (c) in `evals/gate.py`** (`_named_identifiers`/
`_is_distinctive`): a question naming a distinctive code identifier (snake_case
/ camelCase / long non-acronym ALL-CAPS, reduced to the leaf of a qualified
name) that appears NOWHERE in the evidence the writer saw is forced to unknown.
Deterministic, fail-safe, evidence-gated, off for `.explain()`; common acronyms
+ single Title-case words deliberately not flagged (accepted gap: a fabricated
single-Capitalized-word type). Red→green: 7 new `EntityPresenceGuardTests`.
Verified: evals 437 / demo 189 green; **paid board GREEN — gates 100%/100%,
answer correctness 100% (zero real answers changed)**; and **confirmed live:
HYPERVECTOR now abstains** after redeploy. Memory: [[entity-presence-gate-fix]].

**5. Large-repo capacity ceiling PROVEN (rev 0000013 = the 4 GiB/2 CPU bump).**
`huggingface/transformers` OOM-killed the container at 2 GiB (exit 137);
`rust-lang/rust` OOM'd even at 4 GiB. Diagnosed via Azure system logs (exit 137
= OOM). **The fix is NOT more RAM** (whack-a-mole — kubernetes-scale won't fit,
and it burns the trial credit): it's the deferred **lean-ingest** work —
`git clone --depth 1` + streaming embeddings to disk instead of holding the
whole corpus + vector map in memory. Container left at 4 GiB / 2 CPU (helps
medium repos). kubernetes DID index fine at 4 GiB (Go/line-window).

## Open, unresolved (carried forward)

- **react / rails false-abstentions** (from the pressure test): honest (no
  bluff) but likely the **50k total-chunk cap silently truncating** large-repo
  indexes and dropping the real files. NOT root-caused yet. Cheap first step:
  compare `/status` code counts vs the repo's real size. Probably the same root
  as the OOMs → the lean-ingest fix likely resolves both.
- **Lean-ingest fix** (`--depth 1` + streaming embeds) — now the highest-value
  engineering brick: unblocks giant repos AND probably the truncation
  false-abstains. Deferred, well-motivated, not started.
- Business path (2026-07-16 Part 2) still the standing default once engineering
  settles.

## State right now (literally true)

- `main` @ `54b6cd4` (leanness pass + Brick Q wiring + entity-presence guard),
  pushed to GitHub. Nothing else uncommitted from this session except the
  usual pre-existing untracked paths (`.agents/`, `.claude/*`, `plugins/`).
- Azure rev **`icarus-brain--0000014`** live, healthy, 100% traffic, 4 GiB/2 CPU,
  image `alpha-20260718-entity-presence`. `ICARUS_AST_CHUNKING=1` is ON.
- Suites: evals 437, demo 189, both green (57/5 expected skips locally — the
  skips need `.venv` fastembed; the live boards pass there). Paid board GREEN.
- No `.dmg` rebuild happened or was needed this session — all changes are
  server-side Python brain.
- **Deploy gotcha unchanged:** `az acr build` is BLOCKED on this registry (ACR
  Tasks disabled) — build LOCALLY (`docker build --platform linux/amd64`),
  push to ACR `caec8849f1f0acr`, `az containerapp update`. Each redeploy resets
  active user sessions (data survives on durable `/data`).

---

# Icarus — Session Handoff (2026-07-18: T5+T7 landed — AST-chunking-all-languages arc complete; Ponytail leanness pass queued next)

**READ THIS FIRST — supersedes the engineering-state claims below (T1-T7 of
the AST-chunking-all-languages plan is now fully landed), does NOT supersede
the 2026-07-16 handoff's business-path mandate below.** Business decisions
are still next session's default job. The ONE exception, explicitly requested
by Alankrit this session: run a Ponytail-style leanness pass over the
codebase. That's scoped, bounded, and explicitly asked for — not license to
resume open-ended engineering.

## What happened, in order

**1. T5 (gold-label migration) confirmed landed** from earlier the same day's
arc: `evals/corpus/chunks.jsonl` migrated from 18 whole-file code chunks to
470 AST-chunked ones (PR/issue chunks byte-identical, untouched); all 13
answerable `comprehension_questions.json` citations hand-re-verified against
the real post-migration chunk content and re-pointed to line ranges;
`phase1_questions.json` needed zero changes (its answerable citations are
PR-only). Found+fixed a real bug this surfaced: `ast.FunctionDef.lineno`/
`ast.ClassDef.lineno` point at the `def`/`class` line, never a `@decorator`
line above it, which had been orphaning 15.9% of the corpus (92/580 chunks)
into contentless leftover chunks. Fixed with a `real_start()` helper in
`evals/ast_chunk.py`, 5 new red→green tests, corpus regenerated clean
(580→470 chunks, zero orphans).

**2. T7 (hybrid retriever rebalance) landed this session.** Root cause,
measured not assumed: once T5's AST chunking fixed semantic retrieval's
512-token truncation bug, plain 1:1 RRF fusion (`evals/retriever.py`'s
`HybridRetriever`) scored WORSE (69.2% recall@5 on the comprehension board)
than semantic retrieval alone (84.6%) — RRF structurally rewards consensus
(a ref ranking moderately in both lists) over one retriever's excellent rank,
and BM25 rescued zero questions semantic alone missed on this board. Fix:
`HybridRetriever` gained optional `semantic_weight`/`lexical_weight` params,
defaulting to `1.0`/`1.0` so `evals/test_retriever.py`'s 40 pre-existing
hand-computed-RRF-math tests needed zero changes. Production
(`demo/library.py`) now builds it with `semantic_weight=20.0,
lexical_weight=1.0`, chosen from a measured plateau (recall recovers to
semantic-alone's ceiling starting at weight=15, flat through 100). 5 new
tests (`WeightedHybridRetrieverTests`) hand-compute the weighted math the
same rigorous way the unweighted fixture does. The three live-eval files
that claim to measure Icarus's actual shipped retrieval quality
(`test_retrieval_eval.py`, `test_query_normalization_eval.py`,
`test_grep_comparison_eval.py`) were updated to use the real production
weighting instead of an unweighted stand-in; a new test
(`test_weighted_hybrid_recall_matches_semantic_alone`) proves, live, that
weighted hybrid recall now matches semantic-alone's 84.6% ceiling — the
bar the pre-existing "beats BM25" tests never actually checked, which is
why they stayed green through the whole regression without catching it.

**3. Verified side effect, not assumed:** T7's fix also resolved a
previously disclosed, seemingly-unrelated open regression in
`query_normalize.py`'s live eval
(`test_normalization_never_regresses_clean_phrasing_recall`, was
61.5% < 69.2%) — now green, re-run twice to confirm it's not a fluke,
without touching `query_normalize.py` itself. Documented as a verified
outcome; the shared-mechanism explanation (both were downstream of the same
RRF marginality) was not independently re-diagnosed from scratch, so it's
recorded as a strong inference, not a re-proven root cause.

**4. `docs/plans/2026-07-17-ast-chunking-all-languages.md` updated**: status
header and Tasks list mark T5/T7 LANDED; "What T5 found" and "What T7 found"
sections added with full mechanism writeups. This closes the entire T1-T7
arc except two explicitly-deferred, disclosed items: `.h` files stay on
`chunk_text` (neither the `c` nor `objc` grammar parses real RN headers
cleanly — a measured, honest gap, not a bug) and `ICARUS_AST_CHUNKING` — which,
as of the 2026-07-18 deploy below, is now **flipped ON in production** (see the
"State right now" note; this was the deliberate rollout decision, made before
morning testing).

**5. Full regression run, this session:** `evals` 441 tests (13 skipped, all
expected — self-skips needing live API keys/`RUN_*` flags not set locally),
`demo` 189 tests (2 skipped, expected), secrets scan clean.

**6. Investigated "Ponytail" (`github.com/DietrichGebert/ponytail`) at
Alankrit's request** — a third-party, MIT-licensed **Claude Code plugin**
(not a Python/project dependency), enforcing a YAGNI/minimalism decision
ladder on an agent's own coding behavior (does this need to exist? → stdlib?
→ platform? → installed dep? → one-liner? → minimum code; never skip
security/validation at trust boundaries). Read the actual `SKILL.md` content
directly from the repo, not a secondary summary — it's genuinely benign and
closely mirrors CLAUDE.md's own existing "Simplicity first" principles.
Flagged that secondary sources reported inconsistent star counts (68k vs
85.2k) for a single-author repo — worth mild skepticism, not a blocker.
**Could not install it myself**: the install (`/plugin marketplace add
DietrichGebert/ponytail` then `/plugin install ponytail@ponytail`) is
interactive-only, unavailable in a non-interactive session. Alankrit reports
running it via an interactive terminal himself.

## State right now (literally true)

- **Ponytail: Alankrit says it's installed via terminal, but it did NOT show
  up in this session's own available-skills list.** Plugin/skill installs
  take effect for new sessions, not sessions already running — this was
  never actually verified as active anywhere. **Next session's first step:
  confirm it's really available (check the skill list, or try invoking
  whatever command it exposes) before relying on it or assuming it already
  ran.**
- Large uncommitted diff spanning the whole T1-T7 arc: `evals/ast_chunk.py`,
  `evals/ts_chunk.py`, `evals/retriever.py`, `evals/test_retriever.py`,
  the committed corpus (`evals/corpus/chunks.jsonl` + `meta.json`),
  `evals/comprehension_questions.json`, `demo/library.py`, ~10 test files,
  and this plan doc. **Nothing committed this session** — matches the
  standing "only commit when asked" instruction. Run `git status` before
  assuming anything about what's landed vs. still working-tree-only.
- Suites confirmed green this session: evals 441 (13 expected skips), demo
  189 (2 expected skips), secrets scan clean.
- `ICARUS_AST_CHUNKING` **flipped ON in production 2026-07-18** (Azure revision
  `icarus-brain--0000012`), after the leanness pass shipped on `0000011`. Fresh
  connects now AST-chunk Python + JS/TS/JSX/ObjC/Java/Kotlin; `.h`/others stay
  on line-windows by design. T6 staleness means a previously-connected repo
  auto re-ingests on its next connect (scheme changed). tree-sitter grammars
  verified present in the deployed image before flipping.

## Next session's task (explicit, from Alankrit): a real leanness pass

Run Ponytail's minimalism ladder over this codebase — the actual plugin
command if the verification step above confirms it's live, or, if it isn't
available yet, apply the exact ruleset manually (already read in full this
session: YAGNI first, then stdlib, then platform/installed-dep, then a
one-liner, then minimum custom code; never skip security/validation at trust
boundaries; mark deliberate simplifications with `ponytail:` comments).
Recommend starting with a few genuinely large/dense files (e.g.
`demo/server.py`, `evals/ingest.py`, `evals/gate.py`) rather than a
whole-repo sweep in one pass. Hold this to the same bar as every other change
this session: any proposed deletion must be grep-verified unreferenced
first, no test or the honesty gate gets weakened to shrink line count, and
the full regression suite (`evals` + `demo`) must stay green after each
change — no "we could probably delete this" left unresolved and unverified.

---

# Icarus — Session Handoff (2026-07-16 late session: two live bugs found+fixed+deployed, docs de-drifted, Morphic pilot scoped)

**READ THIS FIRST — supersedes the engineering-state claims below, does NOT
supersede Part 2's business-path mandate.** This was a continuation of the
same 2026-07-16 day: private repos were already live from the earlier session
(below). This session did two things — proved the product against real,
unfamiliar repos live (not just the frozen eval board), and made real progress
on the business side. **Next session's job is still business decisions**
(ICP/pricing/trust-legal/outreach, per Part 2 below) — tonight's engineering
was legitimately tester-feedback-triggered (live testing found real gaps), not
a violation of "business first," and should not be read as license to go do
more unprompted engineering next.

## What happened, in order

**1. Live-tested Icarus against two real repos it had never seen: saltstack/salt
(~940k lines) and benawad/vsinder (a small TS/Svelte app).** Zero honesty
violations either time — the deterministic gate never emitted an ungrounded
citation, across 10 hand-verified pure-code-comprehension questions where I
read the real source myself before/after to check each answer. But found two
distinct, reproducible quality gaps:

- **False abstention**: a "how does X work" question where the correct
  evidence chunk was confirmed present in the pipeline's `retrieved` list, yet
  the verdict was still "unknown." Root cause, verified by reading the code
  directly: `GatedPipeline.answer()` (`evals/pipeline.py`) retrieved
  `recall_n=20` chunks for `retrieved`/recall measurement but only ever passed
  the top `writer_k=6` to the actual writer prompt — a chunk ranked 7th-20th
  was genuinely retrieved but the writer never saw its text.
- **Exact-ID retrieval miss**: asking about a real, open GitHub issue by
  number ("issue #260," genuinely exists, well within the repo's 224 total
  issues) returned "unknown" — `issue:260` never appeared in the retrieved
  list at all. Root cause: an issue/PR number lived only in its `ref`
  ("issue:260"), never in the chunk's searchable `text`, so BM25/semantic
  search had nothing to match.

**2. Fixed both, properly.** Explored the real code (two parallel Explore
agents), designed a plan (a Plan agent), confirmed judgment calls with
Alankrit (writer_k value, scope, regex), then implemented via strict
red→green:
- `evals/ingest.py`: `chunk_text`'s whole-file short-circuit now bounded by
  chars too, not just lines (a short-but-dense file could silently exceed the
  writer's 10,000-char cap even when retrieved); `fetch_prs`/`fetch_issues`
  now embed "PR #N:"/"Issue #N:" literally in the chunk text.
- `evals/pipeline.py`: `writer_k` default raised 6→10; `GatedPipeline.answer()`
  gained a deterministic anchor-lookup for an explicit "issue/PR #N" mention
  (`self._by_ref`, mirroring `.explain()`'s already-proven anchor-then-
  neighbors pattern) — a numeric identifier is an exact-match problem, not a
  similarity one.
- `evals/gate.py`: case-insensitive verdict check, accepts a lone string
  citation (fail-safe-only hardening).
- 18 new tests (new file `evals/test_exact_ref_lookup.py` + extensions to 4
  existing test files), each red before its fix, green after. Full suites:
  **evals 346** (328 + 18 new), **demo 176**, both fully green, zero
  regressions.
- Re-verified at scale against fresh, live re-ingests of both real repos (not
  just synthetic fixtures): Bug 2 confirmed fixed live (both "issue #260" and
  "issue 260" now retrieve correctly). Bug 1's exact historical repro cases no
  longer reproduce identically on a fresh corpus (re-ingesting shifts BM25/
  IDF statistics corpus-wide, a real and expected effect, not a failure) — the
  mechanism itself stays proven by the controlled unit test
  (`WriterVisibilityGapTests`), which engineers the exact rank rather than
  hoping a live corpus reproduces it.
- **One new, separate, NOT-yet-actioned finding**: `HybridRetriever`'s
  internal fusion pool (`evals/retriever.py`) has no headroom beyond the
  requested `k` — each underlying retriever only contributes its own top-`k`
  candidates to the fusion. Worth a future look; explicitly out of scope for
  this session's fix.

**3. Committed (`18b86f7`) and deployed to production.** Staged only this
task's files (left an unrelated pre-existing uncommitted `docs/HANDOFF.md`
diff and untracked dev paths alone). Built `--platform linux/amd64`, pushed to
ACR (`caec8849f1f0acr`), `az containerapp update`. **Live revision is now
`icarus-brain--0000010`** (image `alpha-20260716-retrieval-fixes`), confirmed
healthy (`/health`, `/status` both 200) and serving 100% of traffic. The Mac
app's `.dmg` did **not** need rebuilding — nothing in `mac/Icarus/` changed,
only the Python brain.

**4. Business: identified the first real test target — a Morphic Labs
engineer (8 years experience, gen-AI company), and made real scoping
decisions, not yet executed:**
- Given zero marketing budget (every question costs real Gemini API money),
  the right move is 1-3 hand-held design partners with an early price, never
  a free horde — the cost constraint and the correct strategy happen to agree.
- **Do not open with "index your whole 5M-line monorepo."** That's the
  highest-risk entry point — it hits an untested capacity ceiling
  (`ICARUS_BACKGROUND_UPGRADE`'s live premise was still unproven per the
  2026-07-13 handoff below). Decided instead: start with one bounded, real
  slice of Morphic's codebase; separately, cheaply prove the actual large-repo
  ceiling on a PUBLIC repo (not theirs) before ever promising whole-codebase
  coverage to a real customer.
- Lead with the honesty-gap caveat disclosed to testers, don't hide it — to a
  skeptical senior engineer, disclosing your own product's known failure mode
  first is the wedge, not a liability.
- **None of this outreach has actually happened yet** — it's scoped, not
  sent. That's the literal next action.
- Wrote a not-doing list with explicit reopen-triggers (no entity/ToS/Trust-
  page/GitHub-App/notarization/free-horde/raise until a specific trigger
  fires — see the strategy conversation this session for the full list).

**5. Found and fixed real drift across CLAUDE.md, docs/VISION.md,
docs/STRATEGY.md** — all three had gone stale relative to reality (some
self-contradicting: CLAUDE.md's own "Current stage" said "Pre-build" while
its own "Commands" section documented a fully-working private-repo feature).
Fixed all three to match reality (one model for all serving, private repos
live, Mac app/voice/extension shipped, SOC2/compliance reframed as a target
not a current claim, etc.) — read the files directly rather than trust this
summary, they're short. Added a "Current stage" pointer pattern to CLAUDE.md
(point to this file for what's actually next, don't re-embed a perishable
snapshot that will just go stale again).

**6. Confirmed the cross-model handoff mechanism already exists and is sound
— nothing new was built.** `AGENTS.md` (shared, model-agnostic constitution,
deliberately durable) + `CLAUDE.md`/`CODEX.md` (thin per-model adapters) +
this file (session-to-session state) already do exactly what was asked for.
The only actual gap was this file not being kept current — which is what this
entry is.

## State right now (literally true)

- Branch `main`, commit `18b86f7` is the tip, includes tonight's bug fixes.
  The CLAUDE.md/VISION.md/STRATEGY.md doc fixes from later in this session are
  **not yet committed** — check `git status` before assuming.
- Azure revision `icarus-brain--0000010` is live, healthy, serving 100% of
  traffic. Old revision `0000009` still exists at 0% traffic (normal, not a
  problem).
- Suites: evals 346, demo 176, both green, confirmed this session.
- Morphic outreach: scoped, not sent.

---

# Icarus — Session Handoff (2026-07-16, private repos live + business phase begins)

**READ THIS FIRST — supersedes everything below.** Private repos work now —
verified live on Alankrit's own private repo. The engineering core is done
enough to sell. **Next session's job is BUSINESS DECISIONS, not code.**
Alankrit has never launched a product before and does not know the path after
engineering — Part 2 below is written to teach that path, not just list tasks.
Do not start Part 3 (deferred engineering) until business decisions are made
and/or tester feedback arrives.

## Next session's ONLY job: drive Part 2 below to decisions

Five decisions, in order, all business/legal, none of them code:
1. **ICP** (who is the first customer) + **positioning** (the one-line promise).
2. **Pricing model** (rough number, not a finished pricing page).
3. **Trust/legal minimum** for the first design partner (Trust page, ToS/Privacy) —
   and whether to engage a startup lawyer now.
4. **Entity + billing** conversation (lawyer/accountant — Delaware C-corp vs LLC,
   Stripe + business bank account).
5. **Design-partner outreach** — draft it, start warm-network conversations.

I (the assistant) can draft anything text-based next session: the ICP
statement, positioning line, the Trust page (from the real, true data-isolation
story already built), outreach messages, a discovery-call script. The entity
formation, lawyer-reviewed contracts, and accountant decisions need a real
professional — I can prep material for them, not replace them.

---

## Part 1 — What shipped this session (2026-07-16), verified not assumed

Everything below was tested and, where it touches the cloud, proven against
the LIVE Azure endpoint — not just "tests pass."

**1. Full security audit of the whole codebase**, then fixed the two real
findings:
- **M1 (real vuln, fixed):** a negative/non-integer `Content-Length` slipped
  past the size guard and turned `rfile.read(length)` into a blocking
  `read(-1)` that held a server thread until the socket closed — a free
  thread-exhaustion foothold on the public endpoint. Reproduced with a raw-
  socket red test (it genuinely hung), fixed with a `_content_length()`
  validator + a 60s connection timeout, proven fixed against the live cloud
  (0.2s clean 400, was an indefinite hang). `demo/server.py`.
- **L3:** corrected a stale docstring in `evals/provider.py` that wrongly
  implied the Gemini key goes in a URL query string (the code already
  correctly uses the `x-goog-api-key` header — comment-only fix, no behavior
  change, but a misleading comment next to key-handling code is worth zero
  risk).
- Everything else from the audit (notarization, the honesty-gap disclosure,
  `--depth` clone, rate-limiter eviction) is either disclosed in
  `docs/TESTER_NOTES.md` or deferred to Part 3.

**2. `docs/TESTER_NOTES.md` written and committed** — the Gatekeeper
first-open step, the two honesty caveats (provenance-vs-faithfulness on
untrusted repo content; fake-code-shaped-like-real-code), what's normal vs a
bug, and how to report a problem (direct to Alankrit — no dead link).

**3. Shared public-repo cache** — a public repo's index is now built ONCE and
shared read-only across every user (deduped, like the original default-repo
sharing already did), instead of once per user. 30 testers connecting the same
repo now means 1 index job, not 30. Isolation for this is proven by test, not
assumed: shared corpus never lands under a user's identity dir; two users never
duplicate a public repo separately.

**4. Durable cloud storage** — Azure Files mounted at `/data`
(`ICARUS_STORAGE_ROOT=/data`), storage account `icarusbraindata`, share
`icarus-cache`. Proven live: connected a repo, force-restarted the container
(wipes local disk), reconnected — zero re-ingest, corpus survived. Deploys no
longer wipe every tester's index.

**5. 25× faster first-time indexing** — the GitHub fetch used to make one
subprocess call PER pull request and PER issue (N+1). Switched to
`gh pr list --json ...,body,...` / `gh issue list --json ...,body` — one
batched call each. Live-measured on a 47-PR/213-issue repo: fetch dropped from
~2.5 minutes to **5.9 seconds**. `evals/ingest.py`.

**6. Honest indexing progress** — `/status` now carries a `phase` field
("Reading the repository…", "Building smart search…") instead of a silent
spinner. Threaded through `demo/library.py` → `/status` → `RepoStatus.phase`
(Swift) → `SetupView`. Proven live via real-time `/status` polling during an
actual connect.

**7. Fixed the connect-failure bug that actually embarrassed Alankrit live**
on a second machine: a first-time connect that GENUINELY SUCCEEDED
server-side got reported to the user as "Can't reach Icarus's brain — check
your internet connection," because Azure's ~240s ingress timeout cut the
HTTP connection while the server kept working. Root-caused via live Azure
Log Analytics queries and a CPU-metrics timeline (found the real cause: 3
piled-up connect attempts from impatient re-clicking pinned the container's
one CPU core at 100% for 4 minutes). Three real fixes:
- `ConnectModel` no longer treats a dropped connect request as proof of
  failure — it falls through to the existing status poll, which is the only
  thing that actually knows what happened.
- Every real refusal the brain sends (401/403/429) now surfaces as a typed
  `BrainError` with an honest, specific message — never blames the network.
- The Connect button disables while a connect is in flight (a repeat click
  was starting a brand-new duplicate server-side index job, not checking on
  the existing one).
- `ICARUS_BACKGROUND_UPGRADE=1` switched on in the cloud (code already
  existed, was never enabled) — `/connect` now returns in seconds instead of
  blocking through the whole embed.

**8. PRIVATE REPOS RE-ENABLED — the commercial core.** This was the session's
real point (Alankrit, correctly, would not accept a public-repo-only product).
Full detail: memory `private-repos-reenabled`. Summary:
- A private repo (verified readable by the caller) routes to that user's OWN
  isolated storage `<storage>/<user_id>/private/<repo>/` — never the shared
  public cache, never pooled across users. Cloned with the caller's own
  GitHub token, held leak-safe (local variable only, never stored, logged, or
  returned in any status).
- Answered by the private-safe writer; the existing trust interlock enforces
  this at pipeline construction.
- **Isolation is proven by test, not hoped:** private corpus never lands in
  the shared cache; two users connecting the SAME private repo get separate,
  un-pooled copies; disconnect deletes a user's private corpus.
- OAuth scope widened `read:user` → `repo` (classic OAuth has no read-only
  private scope — this is a disclosed, deliberate tradeoff, Alankrit's own
  call: "scope now, GitHub App next"). **Existing app users must sign out and
  back in** to get a repo-scoped token; no DMG rebuild needed, this is
  server-side.
- **Proven live on Alankrit's own real private repo** (`alankritxghosh/Icarus`
  itself): connected in 4s, indexed 148 code files + 75 docs, answered a real
  question about the codebase's own trust interlock with a genuine citation,
  and confirmed an anonymous caller sees only the public default (zero leak).

**Cloud state at end of session:** Azure revision `icarus-brain--0000009`, tag
`alpha-5`. All prior tags (`alpha-1` through `alpha-4`) are earlier checkpoints
in this same session's arc, all superseded by `alpha-5`.
`mac/Icarus/Icarus.dmg` is the `alpha-4` Mac build — **no rebuild was needed
for private repos**, since the scope change and routing are server-side and
the app already sends the bearer token on every connect.

**Suites at end of session:** demo 176 (+ github_oauth tests for the scope
change), evals 328, Swift 57, extension 28, secrets scan clean throughout.

---

## Part 2 — The business path (teach, not just task-list — for a first-time founder)

You've built the engine. "Launching a product" adds three more layers most
first-time founders don't see coming until they hit them: **Commercial** (who
buys, what you charge), **Trust & Legal** (the real gate for a product that
ingests private code — not optional, not later), and **Operational** (the
plumbing to actually take money). Each below is a decision to make, not a task
to complete — next session should reach a decision on each, then act.

### 2A. Commercial decisions

**Decision 1 — ICP (who is the first customer).** Be narrow on purpose. A
product "for everyone" sells to no one, because no message resonates with
everyone. *Recommendation:* small engineering teams (~10–50 developers) who
feel real "why is this code like this?" pain — high engineer turnover, a big
legacy codebase, or fast onboarding where the answer to "why" walked out the
door with the person who wrote it. Buyer = the eng lead/CTO/technical founder.
User = every developer on the team. Start with the **warm network** —
ex-colleagues, friends' startups — people who'll hand over real code and give
an honest reaction, good or bad.

**Decision 2 — Positioning (the one-line promise).** This one line drives
every other message you'll write. Icarus's actual wedge is **honesty +
organizational memory** — it explains the *why* behind code with receipts,
and openly says "nobody wrote this down" when that's the truth. That's the
opposite of a code-writing copilot (which write code, and also confidently
make things up when they don't know). *Recommendation:* lead with "the
engineering brain that answers *why* — with receipts, and an honest 'no one
wrote this down' when there's no answer." Decide explicitly what you will
NOT claim (not a coding agent, doesn't write code for you).

**Decision 3 — Pricing & packaging.** What unit, what number. Options:
per-developer/month (simplest, standard for dev tools), per-repo, or a flat
team price. *Recommendation:* a simple per-seat monthly price (rough range
$20–40/dev/month to start), design partners at a steep discount or free while
they're proving the product with you. Real constraint: every question costs
real money (the Gemini API call is a real cost of goods) — price above that
floor. Don't over-build pricing before 2–3 real customers; the goal right now
is proving willingness to pay, not optimizing a pricing page.

### 2B. Trust & Legal — the launch gate first-timers usually miss

**This is not a nicety for a product that reads private source code — it is
the actual blocker.** A company's security or legal team will not let their
engineers pipe proprietary source code to an outside server without answers
to basic questions. The good news: Icarus's real data story is already
strong (per-tenant isolation, proven live this session; no training on
customer code; discard after each request) — the work now is writing it down
truthfully and backing it with the right paperwork, not building new
capability.

**Decision 4 — the minimum trust artifacts before a first paying customer.**
- **Terms of Service + Privacy Policy.** Table stakes. A template gets you
  started; have a lawyer do one real pass before a paying customer signs —
  don't ship pure boilerplate for a product that ingests private code.
- **A plain "Trust / Security" page**, stated truthfully: no training on
  customer code; code discarded after each request; per-tenant isolation
  (real, and tested this session); where data lives (Azure, region);
  sub-processors named (Google Gemini, Microsoft Azure, GitHub); deletion on
  disconnect (real, tested). This is mostly a writing task — the underlying
  claims are already true in the code. I can draft this next session from the
  actual implementation.
- **A DPA (Data Processing Agreement).** A security-conscious company's legal
  team will ask for one before signing. Standard template exists; needed
  before a paying customer beyond friendly early design partners, not
  necessarily for the very first one.
- **The GitHub App (per-repo, read-only access)** — the trust-correct
  replacement for the current broad `repo` OAuth scope (which grants access
  to a user's entire private-repo account, not just the one they connect). A
  security-conscious buyer will object to "give us everything." A GitHub App
  lets them grant exactly one repo, read-only. This is simultaneously an
  engineering task and a trust artifact — it's the single item most likely to
  convert "interesting demo" into "we can actually deploy this at our
  company." Can wait for the first 1–2 friendly design partners; should exist
  before any wider or paid rollout.
- **SOC 2** — the enterprise-scale gate. Months of work and real money. Not
  now — just know it exists and will eventually matter.

*Recommendation:* for the first 1–2 warm-network design partners, a truthful
Trust page plus a simple ToS/Privacy is enough to start. Before charging a
security-conscious company: DPA + the GitHub App. **Engage a startup lawyer
early** — this is the one area not to DIY. I can prepare draft material for
them to review; I am not a substitute for one.

**Decision 5 — the honesty-gap fix, before charging on the honesty promise.**
Disclosed in `docs/TESTER_NOTES.md`: a fabricated snippet shaped exactly like
real code in a connected repo can occasionally be described as if it were
real. Fine to disclose to friendly testers; not fine to still be true once
you're charging money for a product whose entire pitch is "it never bluffs."
The fix (an entity-presence check in `evals/gate.py`) is scoped and waiting in
Part 3 — sequence it before your first paid, security-conscious customer.

### 2C. Operational — the plumbing to actually take money

**Decision 6 — company entity.** Needed to sign contracts and take payment.
First-timer note: a Delaware C-corp is the default choice if you intend to
raise venture funding later; an LLC is simpler if you're not raising soon.
This is a lawyer/accountant conversation, worth getting right early — changing
entity type later is real friction and real cost.

**Decision 7 — billing.** Stripe is the standard way to collect recurring
payment from customers; you'll also need a business bank account. Both gate
on the entity existing, so this follows Decision 6.

### 2D. What "traction" actually means here, and the funding bridge

Alankrit's instinct (revenue before funding) is correct. With design
partners, the two things that matter are: **are they using it every week**
(real retention, not a one-time demo reaction), and **would they pay, even a
small amount** (willingness to pay is a stronger signal than any amount of
enthusiasm). Two or three paying design partners who keep coming back is a
stronger pre-seed story than a TAM slide. Raise AFTER that pull exists, not
before — funding is a later conversation, not a next-session one.

### The recommended order for next session (business only, no code)
1. Lock the ICP + the one-line positioning (fast, unblocks everything else).
2. Decide the pricing model and a rough number.
3. Decide the trust/legal minimum for the first design partner; decide
   whether to engage a startup lawyer now.
4. Start the entity + billing conversation.
5. Draft design-partner outreach (warm network first) and start real
   conversations.

---

## Part 3 — Engineering that WAITS for feedback (do not start unprompted)

- **GitHub App (per-repo access)** — replaces the broad `repo` OAuth scope.
  Business-gated (see 2B, Decision 4) — build when a real design partner
  needs it, or before wider paid rollout.
- **Private-repo badge in the Mac app** — `RepoStatus.private` is already sent
  by the server; the app just doesn't render it yet. Cosmetic, not a blocker.
- **Honesty-gap hardening** (Decision 5 above) — an entity-presence check in
  `evals/gate.py` so a question about a specific name/symbol that doesn't
  appear anywhere in the retrieved evidence is forced to "unknown." Do this
  before charging money on the honesty promise, not necessarily before the
  first free design partner.
- **Notarization** — removes the Gatekeeper "unverified app" wall entirely.
  Needs a paid Apple Developer ID ($99/yr) + real lead time. Before a public
  (not hand-to-hand design-partner) launch.
- **Post-alpha hardening** — `git clone --depth 1` (currently full-history
  clone), rate-limiter key eviction (unbounded dict growth on a long-lived
  server), a real concurrent-load test at actual numbers (never run), basic
  monitoring/alerting (right now: read Azure logs manually, no automation
  tells you when something breaks).

---

## Quick reference (commands, gotchas — unchanged from before, still true)

- **Tests:** `python3 -m unittest discover -t . -s evals` and `... -s demo`
  (repo root). Swift: `cd mac/Icarus && swift test`. Extension:
  `node --test extension/*.test.js`.
- **Deploy the brain:** build `--platform linux/amd64`, push to ACR
  `caec8849f1f0acr`, `az containerapp update --image …`. **No auto-deploy** —
  pushing to GitHub does not touch Azure.
- **Read cloud logs:** Azure Portal → container app → Monitoring → Log
  stream / Logs. (`az monitor log-analytics` CLI is broken on this Mac's
  Python 3.14 — use the Portal, or `az rest` against the Log Analytics query
  API directly.)
- **Spending cap:** set on the Gemini key — Google Cloud Console → Billing →
  Budgets (email-only alert) AND APIs & Services → Generative Language API →
  Quotas (the actual hard cap; the budget alone does not stop spending).
  Alankrit confirmed this is set.
- **Live cloud URL:**
  `https://icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io`
- **Redeploys reset each user's active-repo SESSION** (not their data — the
  corpus survives on durable storage, so reconnect is instant) — don't
  redeploy casually while real people are mid-session.

---

Everything below this line is prior-session history, still accurate as a
record, superseded by the above for what to do next.

---

# Icarus — Session Handoff (2026-07-13, public alpha release)

**READ THIS FIRST — supersedes the older same-day handoffs below.** The verified
backend is live on Azure revision `icarus-brain--0000003`, image
`icarus-brain:alpha-20260713-1715`. The fresh ad-hoc-signed Mac artifact is
`mac/Icarus/Icarus.dmg` and points to that Azure brain.

## Next session's ONLY job

Put the DMG in named engineers' hands and collect failures. This is a controlled,
**public-repository-only** alpha: OAuth requests `read:user`; the HTTP boundary
refuses private repositories before ingest. Do not promise private-code handling,
self-serve onboarding, notarization, or enterprise tenancy yet.

Verified before release: evals 321/321 (13 skipped), demo 172/172 (2 skipped),
Swift 52/52, extension 28/28, secrets scan clean, honesty gates 100%/100%.
Live checks: health 200, unauthenticated ask 401, real private repo 403, cited
answer 200, honest unknown 200 with zero citations.

## What happened this session, in order

1. **Killed the free/paid writer tier split — ONE model everywhere.**
   Alankrit's explicit call: "no free tier or paid tier anymore... one model that
   does all the fucking work." `demo/library.py`'s `_pick_writer()` deleted; both
   public and private pipelines now build through one `_build_gated_pipeline` →
   `make_provider("gemini-paid")` → `assert_safe_for_private()`. This directly
   removed the standing §0.2-#1 risk from the prior handoff (a weak free writer
   could self-declare "answer" on a real abstention). Memory:
   [[one-model-no-tier-split]].
2. **Zero-friction voice STT fix — the reported "works on my Mac, not others"
   bug.** Root cause (confirmed against Apple's own DevForums, not guessed):
   macOS has no API to install the on-device speech model from code, and the app
   hard-required it. Fix: `AppleSpeechRecognizer` now sets
   `requiresOnDeviceRecognition = recognizer.supportsOnDeviceRecognition` — on-
   device when the Mac has the model (audio never leaves), automatic Apple-cloud
   fallback when it doesn't (zero setup). Because that makes the old on-device-
   only promise sometimes false, **every "audio never leaves your Mac" claim in
   the app was corrected to be honest** (`Icarus-Info.plist` usage strings,
   `Shell/ShellSurfaces.swift` PrivacyBoundaryView). Memory:
   [[stt-on-device-model-bug]].
3. **First GPT-5.6 Sol adversarial review → NO-GO.** Sol reproduced, with runnable
   repros, that the honesty gate could confidently answer a "why" question using
   evidence that only stated the "what" (a bare code constant) — because
   `gate(raw, retrieved)` never saw the question or the evidence text, only
   citation membership. Also found: malformed line-range citations (`#L0`,
   inverted ranges) still grounded; a missing `GEMINI_PAID_API_KEY` produced a
   false "ready" status then crashed `/ask` with a dropped connection; two stale
   "free writer" UI strings survived the one-model change; the ingest chunk cap
   could overshoot silently; and a concurrency test was silently vacuous (it threw
   an `AttributeError` in-thread that the suite never surfaced — this closes the
   §0.2-#6 mystery from the prior handoff, "Sol saw a background-thread exception
   in an existing demo test").
4. **All of Sol's findings fixed and independently verified tonight** (not taken
   on faith — every fix was proven with a live repro before being called done):
   - **Gate (a)+(b), per Alankrit's explicit instruction.** (a): `evals/gate.py`'s
     module docstring and CLAUDE.md's "one non-negotiable" section were rewritten
     to state the TRUE boundary — groundedness (no fabricated citations) is fully
     provable in code; abstention-when-unrecorded is code-enforced only for the
     clear case, writer-reliant beyond it. Stopped overclaiming. (b): `gate()`
     gained optional `question`/`evidence` params (wired from
     `pipeline._answer_from`) and now refuses a rationale-seeking "why" answer
     unless a grounded chunk is a discussion source (pr/issue/doc) or its text
     states an actual reason — a bare code constant no longer justifies a
     confident "why". Scoped ON for `.answer()`, OFF for `.explain()` (selected-
     code explanation is legitimately a "what", not a dodge). First version of
     (b) over-abstained (board went 100%→50% answer correctness); refined to
     accept pr/issue/doc sources as recorded rationale, which fixed it — board
     back to 100%/100%/100%/100%. Live-verified: the exact q07/q08 "why is this
     constant exactly N" cases now abstain under BOTH clean and adversarially
     mangled phrasing. 8 new tests in `evals/test_gate.py`.
   - Malformed line-range citations (`#L0`, inverted `#L300-L250`) now forced to
     `unknown` in `_resolve` (`evals/gate.py`).
   - `/ask` and `/explain` (`demo/server.py`) now catch a writer exception and
     return a clean JSON 503 instead of dropping the connection; a loud stderr
     warning fires at `serve()` startup if `GEMINI_PAID_API_KEY` is unset.
   - The two remaining stale "free writer" strings fixed
     (`Shell/SetupView.swift`, `Shell/HomeView.swift`).
   - `evals/ingest.py`'s chunk cap enforced per-chunk (hard, was per-file which
     could overshoot) with a stderr truncation log.
   - The vacuous concurrency test (`demo/test_server.py`) rebuilt to actually wrap
     the slow library in a registry, join the thread, and assert the slow request
     really completed — it would now fail if requests were serialized.
   - Stale docs corrected: `general_index.md`'s gate description (overlap→
     containment, missing the (b) guard), `SpeechRecognizer.swift`'s "on-device"
     claim, `demo/test_demo_live.py`'s live-guard key check (was any free key;
     now requires `GEMINI_PAID_API_KEY`, matching the one-model serving path).
5. **Two Sol prompts written for next session — §P below.** Not yet run.

## State at the end of this session (literally true right now)

- Branch `fix/gate-grounding-and-option-b`, tip `b98e674` on disk, but **all of
  tonight's work (items 1-4 above) is UNCOMMITTED** in the working tree —
  Alankrit deliberately held off committing pending the two Sol re-audits.
  `git diff --stat`: **18 files changed, +384/−58** (`CLAUDE.md`, `demo/library.py`,
  `demo/server.py`, `demo/test_demo_live.py`, `demo/test_server.py`,
  `evals/gate.py`, `evals/ingest.py`, `evals/pipeline.py`, `evals/test_gate.py`,
  `general_index.md`, `mac/Icarus/Icarus-Info.plist`,
  `mac/Icarus/Sources/Icarus/AppleSpeechRecognizer.swift`,
  `mac/Icarus/Sources/Icarus/Shell/HomeView.swift`,
  `mac/Icarus/Sources/Icarus/Shell/SetupView.swift`,
  `mac/Icarus/Sources/Icarus/Shell/ShellSurfaces.swift`,
  `mac/Icarus/Sources/IcarusKit/SpeechRecognizer.swift`,
  `mac/Icarus/Sources/IcarusKit/VoiceModel.swift`,
  `mac/Icarus/Tests/IcarusKitTests/VoiceModelTests.swift`).
- **Suites green:** `evals` **321** (was 313; +8 gate tests), `demo` **172**
  (was 171; +1 writer-503 test), Swift `IcarusKit` **52**, all 0 failures.
- **Live gated board on the one model** (`gemini-paid`): STATUS **GREEN** — both
  honesty gates 100%, citation correctness 100%, answer correctness 100%.
- **Ponytail plugin (github.com/DietrichGebert/ponytail) — requested, NOT yet
  installed.** It's a Claude Code plugin (MIT license, injects a lean-code
  ruleset + `/ponytail-audit` and `/ponytail-review` commands) that Alankrit
  wants going forward for writing leaner code. Install is interactive-only
  (`/plugin marketplace add DietrichGebert/ponytail` then
  `/plugin install ponytail@ponytail`) — cannot be run from a non-interactive
  session. **Next session: if in an interactive terminal, run those two commands
  first**, before or alongside the Sol prompts.
- `.agents/`, `.claude/launch.json`, `plugins/` are pre-existing untracked paths
  (present before this session started) — not part of tonight's diff, left
  alone.

## §P — The two Sol prompts (verbatim, ready to paste)

### P1 — Re-audit prompt (checks tonight's fixes)

```
You are an INDEPENDENT, adversarial reviewer. Do NOT trust the author's
description, comments, or "tests pass." Reach your OWN verdict; prove every defect
with a runnable repro (command + expected vs actual). If you can't reproduce it,
call it a hypothesis, not a finding.

REPO: "/Users/alankritghosh/JARVIS /jarvis_engineering" (quote the space).
Python: .venv/bin/python. Swift: swift build/test from mac/Icarus.
GIT: main = a60986c; branch fix/gate-grounding-and-option-b (tip b98e674). The
author's fixes are UNCOMMITTED — review `git status`, `git diff` (working tree),
AND `git diff a60986c` (whole branch vs main). Everything ships together.

CONTEXT: your prior audit returned NO-GO and reproduced (P0) that the honesty gate
could emit a confident cited "what" answer to an undocumented "why" (gate only
checked citation-membership, never saw the question/evidence), plus malformed
line-ranges grounding, a missing-key crash, stale free-writer UI claims, a hard-
capless ingest overshoot, and a vacuous concurrency test. The author claims to
have fixed all of these. RE-AUDIT THE FIXES — do not assume they are correct.

INVARIANT (violation = automatic NO-GO): the gate must never emit "answer" with a
citation not corresponding to genuinely-retrieved evidence (valid, contained line
window), and must abstain when the answer was never written down.

ATTACK, reach your own verdict on each:

1. THE (b) RATIONALE GUARD (evals/gate.py + evals/pipeline.py). The gate now takes
   `question`+`evidence` and refuses a "why" question unless a grounded chunk is a
   pr/issue/doc source OR its text contains a rationale marker. Attack it:
   - Does the pr/issue/doc SOURCE pass open a NEW bluff path? Construct a "why"
     question whose only relevant evidence is a pr/issue that mentions the subject
     but states NO reason — does it now confidently answer (a laundered why→what)?
   - Is the `_SEEKS_RATIONALE` regex / `_RATIONALE_MARKERS` list gameable or
     brittle (why-questions it misses; markers that match almost any prose,
     defeating the guard; unicode/case)?
   - The guard is OFF for `.explain()` (author's scoping). Prove whether a
     why→what dodge is still reachable via `/explain` with the default question
     "What does this code do, and why is it here?" — is that an acceptable scope
     or a hole?
   - Does it OVER-abstain on any genuinely answerable why-question? Re-run the
     paid board and report gates + answer correctness.
2. MALFORMED-RANGE FIX (evals/gate.py `_resolve`). Confirm L0/negative/inverted no
   longer ground, AND hunt other malformed forms: huge numbers, `#L1-` partial,
   non-numeric, `#L5-L5`, ranges on a whole-file retrieved chunk, boundary equality.
3. MISSING-KEY / 503 (demo/server.py). Confirm /ask AND /explain return JSON 503
   (not a dropped connection) when the writer raises. Does the error leak the key
   or a stack trace to the client? Does /status still falsely report "ready" with
   no key — and is that acceptable? Is the startup warning actually emitted?
4. CHUNK CAP (evals/ingest.py). Confirm the per-chunk hard cap can't overshoot and
   always logs. Edge: cap hit exactly at a file boundary; cap of 0; a file whose
   single window equals the cap. Byte cap interaction.
5. CONCURRENCY TEST (demo/test_server.py). Confirm it now genuinely exercises
   concurrency (slow request wrapped in a registry, thread joined, 200 asserted)
   and would FAIL if requests were serialized — not another vacuous pass.
6. STALE CLAIMS. Grep the WHOLE repo (mac/, docs/, extension/, *.md) for surviving
   "free writer"/"public repos only"/"audio never leaves"/on-device-only claims
   that are now false. The author fixed some; find any missed.
7. WEAKENED TESTS. Confirm no existing assertion was deleted or loosened to make
   these changes pass. Confirm the 8 new gate tests and the new 503/concurrency
   tests actually assert the behavior (not tautological).

RUN: `.venv/bin/python -m unittest discover -t . -s evals` and `-s demo` (report
counts); `swift test` from mac/Icarus; if GEMINI_PAID_API_KEY is set,
`.venv/bin/python -m evals.run --pipeline gated --writer gemini-paid --judge gemini`.

DELIVERABLE: per-item verdict (1–7), an overall GO/NO-GO for testers, every finding
with severity (P0–P3) + a runnable repro, and an explicit list of what you could
not determine. Rank honesty-invariant threats first.
```

### P2 — Whole-codebase leanness / production-grade audit prompt

```
You are a principal engineer doing a LEANNESS + PRODUCTION-READINESS audit. The
goal is SUBTRACTION and hardening, not addition. Bias: quality over quantity.
Every file, function, and dependency must earn its place by serving Icarus's actual
job (retrieve evidence -> cite-or-abstain answer -> honest unknown, ingested from
GitHub, served over HTTP, driven by a Mac app + browser extension). If a line
doesn't contribute to that, it's a finding. Do NOT propose new features or new
abstractions. Prove every claim by reading the code; cite file:line.

REPO: "/Users/alankritghosh/JARVIS /jarvis_engineering" (quote the space).
Python: .venv/bin/python (suites: `-m unittest discover -t . -s evals` / `-s demo`).
Swift: mac/Icarus (swift build/test). JS: node --test extension/*.test.js.
Read CLAUDE.md, general_index.md, docs/ for intended scope, then VERIFY against the
code — flag where docs and code disagree.

FIND AND RANK (most impactful subtraction first):
A. DEAD / VESTIGIAL CODE — unused functions, unreferenced exports, retired paths
   (e.g. render.yaml/Render remnants after the Azure move, unused providers now
   that there's ONE writer, dead flags/env vars, orphaned test doubles, the
   `--writer groq/openrouter` eval dials if serving can never use them). For each,
   PROVE it's unreferenced (grep) before recommending deletion.
B. OVER-ENGINEERING — single-use abstractions, indirection with one caller,
   config/params never varied, defensive layers for cases that can't occur,
   parallel code paths that could be one. Propose the concrete collapse.
C. REDUNDANCY — duplicated logic across evals/ and demo/ (or mac/ and extension/)
   that should be one source of truth; near-identical functions; repeated parsing.
D. LEANNESS PER PONYTAIL LADDER — for the heaviest modules, ask: does this need to
   exist? is it already in the codebase? does stdlib/native cover it? could it be
   one line? Name the specific reductions and the LOC they save.
E. PRODUCTION-GRADE GAPS (hardening, honestly) — swallowed errors (bare except /
   ignore_errors that hide failure as success, e.g. shutil.rmtree ignore_errors),
   unbounded resources, silent truncation, shared mutable state under threads,
   secrets/tokens in argv/logs, injection surfaces, missing input validation on
   the HTTP boundary, and any stub/placeholder shipped as if real. These are the
   only "add code" findings allowed, and only where correctness/safety needs it.
F. COVERAGE OF PURPOSE — is there any module that does NOT play a role in Icarus
   working as intended? Any experiment/scaffold left in the shipping path? Map each
   top-level package to the job it serves; flag anything that maps to nothing.
G. TEST QUALITY — tests that are tautological, test the mock, or lock an
   implementation detail rather than behavior. Don't inflate coverage; flag noise.

CONSTRAINTS: preserve the honesty gate's determinism and the per-tenant/trust
interlock — never recommend removing a safety guard to save lines. Distinguish
"safe to delete now" (proven unreferenced) from "would need a small refactor."

DELIVERABLE: a ranked TABLE of subtraction/hardening opportunities — file:line,
what, why it's safe, estimated LOC delta (negative = removed), and a one-line
proof. End with: the 5 highest-leverage changes to make the codebase leaner and
production-grade, and an explicit list of anything you were unsure was dead (so it
isn't deleted on a guess). Do NOT rewrite the code; produce the plan.
```

## Open items carried forward, unresolved (from the pre-tester-gating handoff
immediately below — still true, not touched tonight)

- Option B's live premise (backgrounded embed actually getting CPU on the warm
  Azure replica) — still UNTESTED, flag stays OFF.
- 50k chunk cap vs the Azure container's real RAM — not confirmed.
- Azure $200 trial credit expires 2026-08-10.
- Merge/deploy timing — nothing merges to `main` or deploys until Sol clears
  both P1/P2 prompts above and Alankrit decides to ship.
- The "never trained on your code" claim in `PaidGeminiProvider`'s own docstring
  admits the written no-training policy isn't yet recorded — Sol flagged this
  independently too. Still open.

---

# Icarus — Session Handoff (2026-07-13): pre-tester gating — final testing + Sol audits

**READ THIS FIRST — this supersedes the 2026-07-11/12 handoff below as the top
priority.** Tonight's work is on a branch, NOT merged, NOT deployed. Icarus is
about to go to real testers. Before that, TWO gates must pass, and this handoff
is the checklist for both:

- **Track A — a final round of extensive, adversarial, real testing** (§A).
- **Track B — independent audits by GPT-5.6 Sol** (§B).

The bar: honesty is provably intact under load and adversarial input, quality is
mapped (not assumed), and the open risks in §0.2 are decided. A break found now
is the whole point — better us than a tester.

## 0.1 State at end of this session (what is literally true right now)

- Branch **`fix/gate-grounding-and-option-b` @ `b98e674`** (12 files, +589/-48).
  **NOT merged** (`main` is at `a60986c`) and **NOT deployed** to Azure. Nothing
  tonight is live for any user yet — it's all reversible on the branch.
- Full suites green at the commit: **evals 313, demo 171** (0 failures).
  Pre-commit secrets scan clean.
- Live checks tonight: paid board gates 100% (groundedness + abstention recall)
  with citation/answer correctness 100%; live code-only comprehension 3/3 on Go;
  adversarial gate probes all failed safe (no bluff-through).
- `.claude/launch.json` is intentionally left untracked (unrelated dev config).

### What landed this session (three changes — read the memories for depth)

1. **Gate code-citation grounding — HONESTY-CRITICAL** (`evals/gate.py`). The gate
   now grounds a code citation the writer reformatted (dropped `code:` prefix,
   display brackets, or narrowed a chunk window to the specific line it used),
   BUT only by CONTAINMENT (cited lines ⊆ retrieved window), matching source, and
   matching path — so a citation claiming lines beyond what was retrieved, a
   wrong source, or an unretrieved path is still refused. Fixes false-abstentions
   on code without opening a bluff hole. Memory:
   `code-answering-gaps-truncation-and-citation-format`. A prior overlap-not-
   containment bug (P0) was caught by the Sol review and fixed — see §B on why
   this file gets re-audited.
2. **Option B background embed — DEFAULT OFF** (`demo/library.py`,
   `demo/server.py`), behind env `ICARUS_BACKGROUND_UPGRADE` (only meaningful
   with `ICARUS_SYNC_CONNECT`). Blocks `/connect` through stage 1 (lexical
   "ready") and runs the semantic embed in the background so a large repo can't
   hit Azure's 240s ingress timeout; a monotonic connect generation guards the
   stage-2 swap against stale overwrites. Memory:
   `option-b-background-embed-and-100mb-cap`.
3. **Ingest caps** (`evals/ingest.py`): total code cap **25MB→100MB**, plus a new
   **50k total-chunk cap** to bound lexical stage-1 memory on a hostile
   many-short-lines repo. Both caps log to stderr on truncation.

## 0.2 OPEN decisions / risks to resolve BEFORE testers

1. **Free-tier verdict-trust gate breach — STILL OPEN, not fixed.** A weak (free)
   writer can self-declare verdict "answer" while its prose actually abstains,
   and the gate trusts that field → an abstention-recall breach on the public
   tier. Paid/private tier is unbreakable (64+ attempts). Memory:
   `gate-gap-writer-verdict-trust`. **Decide:** fix the gate to not trust the
   writer's verdict, or accept it as a documented public-tier-only limitation.
   If testers touch public repos on the free writer, this can surface.
2. **Option B live premise — UNTESTED.** Does a backgrounded embed actually get
   CPU on the always-warm Azure replica (`min-replicas=1`)? The flag stays OFF
   until this is proven live (§A-5). Don't enable it for testers before then.
3. **50k chunk cap vs real host RAM.** 50k was chosen as "far above any real
   repo, below explosion." Confirm the Azure container's actual memory and adjust
   if 50k × ~600B chunk text + BM25 index is still too much for it.
4. **Merge/deploy timing.** Nothing is live. Decide when to merge the branch to
   `main`, rebuild the DMG/extension if needed, and deploy to Azure.
5. **Azure $200 trial credit expires 2026-08-10** — upgrade to Pay-As-You-Go
   before then or the subscription disables.
6. **Sol saw a background-thread exception in an existing demo test** (suite still
   reported OK). Track it down — under Option B's daemon threads a stray
   exception shouldn't be shrugged off before load testing.

---

## §A — Track A: final testing rounds (execute, then record results)

Run against the branch. Honesty gates must be **100%** throughout; a drop is a
ship-blocker. Quality misses are findings to map, not blockers, as long as they
fail SAFE (honest "I don't know", never a bluff).

**A-1. Regression baseline (do first, every session).**
- `python3 -m unittest discover -t . -s evals` and `-s demo` — expect 313 / 171.
- `GEMINI_PAID_API_KEY=… python3 -m evals.run --pipeline gated --writer gemini-paid --judge gemini` — gates 100%, STATUS GREEN.
- Adversarial gate probe: hand the deterministic `gate()` fabricated files, lines
  outside/beyond the retrieved window, wrong/partial paths, cross-source
  collisions, non-string/empty citations — every one must be `unknown`; every
  legit reformatting (prefix drop / brackets / contained line) must ground.

**A-2. Language robustness at scale (Axis 1 — extend, don't just confirm).**
- Many more mangled questions ("horrid framing", typos, slang, missing words,
  keyword-stripped paraphrase) across several repos, on BOTH tiers (free Groq +
  paid Gemini). Hunt specifically for the §0.2-#1 free-tier verdict breach
  reproducing on real repos.

**A-3. Doc-answerable vs pure code-comprehension (Axis 2).**
- Split questions by what they need: answerable-from-docs (README/comments) vs.
  require line-by-line code reading with NO docs. Now that the gate grounds code
  citations, re-run the code-only case at real scale (many repos), not just the
  Go prototype. Verify answers against the actual source (grounded, not
  hallucinated) and that undocumented "why" still abstains.

**A-4. Repo diversity at both extremes (Axis 3 + 4).**
- Zero-doc + large; heavily-documented; and ACROSS LANGUAGES (the chunker
  supports Python, JS/TS, Go, Rust, Java, Ruby, C/C++, Swift, Kotlin, PHP, C#,
  Scala, Shell — Go is proven, exercise the rest). Confirm the chunker doesn't
  mangle a language, and that the 100MB/50k caps behave (watch the stderr
  truncation logs).

**A-5. Option B live premise + large-repo ceiling (the big infra test — needs
Azure access).**
- On Azure, with `ICARUS_BACKGROUND_UPGRADE=1`, connect a genuinely large repo:
  confirm `/connect` returns fast (stage-1 "ready") AND the backgrounded embed
  actually COMPLETES on the warm replica (inspect the retriever type / run a
  concept-only query — the same way semantic was verified before). If it
  completes → Option B is proven; if it's CPU-starved even warm → keep the flag
  OFF and pursue Premium ingress or a queue worker. Also confirm a repo past the
  ~1,900-2,000-chunk / 240s point behaves (either succeeds via Option B, or fails
  cleanly, never hangs).

**A-6. Concurrency / load (new — Option B makes this matter).**
- Concurrent `/ask` requests; concurrent `/connect` to different repos and to the
  SAME repo (exercise the generation guard live); whether the shared FastEmbed
  model is safe under concurrent calls (Sol could not establish this from the
  repo — verify it, or serialize embed calls if not). Watch for the stray
  background-thread exception (§0.2-#6).

**"Done" for Track A:** a written map of where honesty/quality holds and where it
breaks, with the §0.2 risks each either closed or consciously accepted.

---

## §B — Track B: independent audits by GPT-5.6 Sol

Sol's last pass returned **NO-GO** and caught a real P0 (a bluff-adjacent
groundedness gap) plus P1/P2 — all now fixed on the branch. So **the fixes
themselves must be re-audited**, not assumed correct. Run these read-only (e.g.
`codex --sandbox read-only review`) against the branch. For each, tell Sol to
reach its OWN verdict, distrust this author's claims, and prove every defect with
a runnable repro.

**B-1. Re-audit the gate (highest priority).** The P0 fix changed overlap→
containment and added source/known-source logic. Ask Sol to attack the UPDATED
`evals/gate.py`: any citation that grounds while claiming unretrieved
lines/paths/sources (bluff-through); any false-reject of a genuinely grounded
citation; parsing edge cases (paths with `:` or `#L`, unicode, empty, non-string,
whole-file vs windowed, boundary lines). Confirm the structural invariant
(every emitted citation ∈ `retrieved`) AND the stronger one Sol raised (no cited
line outside the retrieved window can ground).

**B-2. Audit Option B concurrency.** `demo/library.py` `connect_sync` /
`_upgrade_to_semantic` / the generation guard, and `demo/server.py`'s flag wiring.
Hunt for: lost updates beyond A→B→A, races on the pipeline swap under `_lock`,
the single-flight `_inflight` slot, concurrent vector-cache writes, concurrent
use of the shared embedder, and whether the DEFAULT (flag off) path is truly
unchanged.

**B-3. Audit the ingest caps.** `evals/ingest.py` 100MB + 50k-chunk caps: is 50k
actually safe for the deployment's real memory limit? Overshoot behavior (byte
cap can overshoot ~512KB; chunk cap by one file's windows). Whether the caps and
their truncation logging are correct and can't be bypassed.

**B-4. Full-diff review of the branch vs `main`** (`--base a60986c`): correctness,
tests that are meaningful vs vacuous, and confirm no existing test was weakened.

**Reusable Sol prompt skeleton** (adapt per audit; a fuller version was used last
round — reuse its shape):
> You are an INDEPENDENT, adversarial reviewer. Do NOT trust the author's
> description or "tests pass." Reach your own verdict; prove every defect with a
> runnable repro. Repo: "/Users/alankritghosh/JARVIS /jarvis_engineering" (quote
> the space). Venv: `.venv/bin/python`. Base commit `a60986c`; branch
> `fix/gate-grounding-and-option-b` @ `b98e674`. The ONE
> invariant: the honesty gate must never emit "answer" with a citation that
> doesn't correspond to genuinely-retrieved evidence (including no cited line
> outside the retrieved window). [then the per-audit scope from B-1..B-4]. Run
> `.venv/bin/python -m unittest discover -t . -s evals` and `-s demo` and report
> counts. Deliverable: per-area verdict, an overall GO/NO-GO, repros for every
> finding, and what you could not determine.

**Definition of done for Track B:** Sol returns GO on B-1..B-4 (or the remaining
findings are consciously accepted), with the gate re-audit explicitly clearing
the containment/source logic.

---

## §C — Commands & harnesses

Standard (from CLAUDE.md, run from repo root):
- Suites: `python3 -m unittest discover -t . -s evals` / `-s demo`;
  `node --test extension/*.test.js`.
- Gated board: `GEMINI_PAID_API_KEY=… python3 -m evals.run --pipeline gated
  --writer gemini-paid --judge gemini` (or `--writer groq` for the free tier).
- Local server matching prod posture: `ICARUS_ALLOWED_HOSTS=* ICARUS_REQUIRE_GITHUB_AUTH=1 .venv/bin/python -m demo.server`
  (add `ICARUS_SYNC_CONNECT=1 ICARUS_BACKGROUND_UPGRADE=1` to exercise Option B).

**Session-local test harnesses (EPHEMERAL — they lived in this session's
scratchpad and will NOT persist).** Recreate them (or ask to have them committed
under a `tools/`-style path if we want them durable for the tester phase). What
they did, so they can be rebuilt:
- `stress_harness.py` — battery of hand-crafted mangled variants (typos/slang/
  broken-grammar/missing-words/horrid/semantic) of the 10 labelled questions,
  run through the real `GatedPipeline` over the committed corpus with a chosen
  `--writer` and hybrid retriever; classifies each as grounded / honest-abstain /
  false-abstain / BLUFF. This is how the free-tier breach was found.
- `gate_gap_probe.py` — hammers the "embedded-fact multi-part why" framing at
  unanswerable questions to hunt gate false-positives on a chosen writer.
- `go_comprehension.py` — ingests a non-Python repo to a scratch dir, builds
  FULL-corpus and CODE-ONLY pipelines, and runs gold what/how (answer) + why
  (abstain) questions to test pure code comprehension per language. This is the
  Axis-2/4 harness; generalize it to more repos/languages for A-3/A-4.
- Ingest to a THROWAWAY dir (never the committed corpus):
  `ingest_repo("owner/name", "<scratch>/corpus", code_dir=".")`.

## §D — Ship-to-testers bar (definition of done)

1. Track A run and its findings written down; §0.2 risks each closed or accepted.
2. Track B (Sol) returns GO, gate re-audit explicitly clearing the new logic.
3. Free-tier verdict breach (§0.2-#1) decided (fixed or accepted-and-documented).
4. Option B either proven live (§A-5) and enabled, or left OFF with connects
   still working the blocking way.
5. Branch merged to `main` and deployed; DMG/extension rebuilt if the client
   surface changed (it didn't this session — brain-only).

Everything below is the prior 2026-07-11/12 handoff, still accurate history.

---

# Icarus — Session Handoff (2026-07-11/12, later: Azure migration, live)

**READ THIS FIRST — next session's #1 priority is EXTENSIVE TESTING, per
Alankrit's explicit expectation, not new hosting/infra work.** Icarus is
hosted, live, working (§Z below). The brain and app are stable enough now
that the highest-value next step is proving (or breaking) product quality
across a much wider surface than tonight's small samples ever touched.

## Y. Next session's mandate: extensive testing (Alankrit's explicit ask)

Four axes, all in scope, not just one:

1. **Language robustness, systematically, not just a handful of examples.**
   Tonight proved (small sample, `evals/gate.py` + `fmeyer/pydsl`) that broken
   grammar/slang/typos/missing words all still land grounded answers on the
   paid-writer tier. Alankrit wants this run **extensively** — many more
   questions, more repos, more mangling styles ("horrid framing" specifically
   named) — to find the actual failure boundary, not just confirm it mostly
   works.
2. **Deliberately split questions by what they require to answer:**
   - Questions answerable from **documentation already in the repo** (README,
     docs/, comments) — the "easy" case.
   - Questions that require **actual line-by-line code comprehension** with
     **no** documentation to lean on — the real test of whether Icarus reads
     code or just retrieves docs. Tonight's `fmeyer/pydsl` test (0 docs, 4
     chunks) is the *prototype* for this, not the finished version — needs
     repeating at real scale (see next point).
3. **Repo diversity — deliberately at both extremes:**
   - Public repos with **zero documentation AND 1M+ lines of code** — combines
     the hardest case from tonight (no docs) with a scale tonight never tested
     (max was ~220 chunks; this is orders of magnitude larger).
     **CONFIRMED hard ceiling, not just a risk (Alankrit flagged, verified
     against Microsoft's own docs — Envoy's own timeout doc + azureossd
     troubleshooting guide):** Azure Container Apps' default (non-Premium)
     ingress enforces a **240-second, non-configurable Envoy proxy timeout**
     on every HTTP request. `ICARUS_SYNC_CONNECT`'s blocking `/connect` WILL be
     killed by the platform itself past 240s, regardless of anything our
     app code does — this is enforced upstream of the container. Extrapolating
     tonight's real numbers (219 chunks ≈ 24-27s), the ceiling is roughly
     ~1,900-2,000 chunks before a sync connect can never succeed on this
     ingress tier — a real, likely-to-be-hit wall for a 1M+ LOC repo, not a
     hypothetical. **Known remedies, none implemented yet, needs a decision
     next session once the actual failure is confirmed live:**
     (a) **Premium ingress mode** — a paid workload-profile tier that allows a
     configurable idle timeout, bypassing the 240s ceiling directly. Simplest
     fix, but a real cost/infra change beyond Consumption plan.
     (b) **Revert to a background (non-blocking) `/connect`** for repos likely
     to be large — this reintroduces the original concern `ICARUS_SYNC_CONNECT`
     was built to solve (request-scoped CPU not reliably resourcing a
     background thread), BUT that concern was specifically about *scale-to-
     zero* Consumption billing; now that `min-replicas=1` keeps a replica
     permanently running (§Z below), it's a genuinely open question whether a
     background thread on an always-on replica behaves like a normal
     always-on process (no CPU starvation) or still gets throttled between
     requests regardless of replica lifetime. **Not yet tested either way —
     a real live test, not an assumption, is exactly what next session's
     large-repo testing should answer.**
     (c) **A real queue-based worker** (Azure Queue Storage/Service Bus +
     a separate ingest worker) — the architecturally "correct" cloud-native
     fix Alankrit's own research pointed at, but a genuinely bigger build
     (new infra, new code), not a config tweak.
   - **Heavily documented** codebases — the opposite extreme.
   - **Across languages, not just Python.** Correcting a stale claim: the
     repo-switch ingest (`evals/ingest.py`'s `_EXTENSION_SOURCES`) already
     supports Python, JS, TS/TSX, Go, Rust, Java, Ruby, C/C++, Swift, Kotlin,
     PHP, C#, Scala, and Shell — NOT Python-only as `general_index.md`
     previously stated (that line described the frozen `simonw/llm` benchmark
     corpus specifically, not the general capability). So multi-language
     testing is technically unblocked already — go ahead and use it.

**What "done" looks like:** a real map of where Icarus's honesty/quality
holds and where it breaks — not just more confirmations that it works on
easy cases. If something breaks (a bad framing that causes a bluff, a huge
repo that times out, a language the chunker mishandles), that's the valuable
finding, not a failure of the testing.

---

**Below this: Azure migration context, still accurate, but secondary to §Y
above for what to do first.** Icarus is now hosted on Azure Container Apps,
live, proven end to end. Render is suspended. Everything below (including
the 2026-07-10 block further down) is accurate history, superseded on
hosting.

## Z. Azure Container Apps is the live host — real OAuth, real distributable

**What changed:** the local-then-Oracle plan from the section below never
happened — Google's billing kept failing (autopay issue on his account), so
the session pivoted live to Azure Container Apps instead. Full migration
completed, verified, and shipped in one sitting:

- **Deployed:** `icarus-brain` on Azure Container Apps, Central India region
  (`icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io`).
  `az containerapp up --source .`'s remote build (ACR Tasks) is blocked on
  brand-new subscriptions (`TasksOperationsNotAllowed`, a real, confirmed
  restriction) — built locally with Docker and pushed instead. Full runbook
  now in `docs/DISTRIBUTION.md`.
- **`ICARUS_SYNC_CONNECT=1`** (new, `demo/server.py` + `demo/test_server.py`,
  commit `8c991a4`): request-scoped-CPU hosts (Cloud Run, Azure Container
  Apps) only reliably give a container CPU while a request is being
  processed — the old always-background `/connect` would have silently
  stranded the semantic upgrade here exactly like Render's 0.1 CPU did, for a
  different reason. `connect_sync()` itself is UNCHANGED; the flag only
  changes whether `/connect` blocks on it and returns the real final status
  (200) instead of backgrounding it (202). Verified live: a genuine cold
  embed of a 219-chunk private repo took **1.2s** on Azure (vs never-finishing
  on Render) — confirmed as real semantic retrieval via a conceptual query
  with zero keyword overlap, not a lexical fallback.
- **Real GitHub OAuth sign-in proven live**, through both the web demo and
  the rebuilt Mac app — a real browser/system authorization, no bypass. The
  Mac app's earlier `ICARUS_DEV_GH_TOKEN` local-test bypass (from the
  previous local-brain session) is now **fully removed** — `AppDelegate.swift`
  is byte-identical to before that bypass ever existed.
- **A real, undocumented question correctly triggered honest abstention**
  live: "why did we move to Azure instead of Render?" → "No one wrote this
  down" — proof the honesty gate holds even on a topic the repo has lots of
  *related* context for (HF migration docs, render.yaml) but no actual
  recorded answer to, since tonight's decision was only ever discussed in
  chat. This HANDOFF entry is what closes that gap for next time.
- **Cold-start: retry-only was tried first, then proven insufficient, then
  fixed for real with `min-replicas=1`.** Live-caught TWICE — a scaled-to-zero
  container's first request after idle transiently failed, then the identical
  next attempt succeeded with zero code involved. First response was a
  client-side retry (`mac/Icarus/Sources/IcarusKit/BrainClient.swift`, commit
  `294f90d`) rather than paying for always-warm (~$24/month, priced against
  Azure's own pricing) — reasonable at the time, but **the actual cold-start
  duration was never measured, only guessed.** Once real testers hit repeated
  failed connections, measured it properly: `az containerapp replica list`
  showed zero replicas, and a timed `/health` request took **24.15 seconds**
  cold — far longer than the retry's short delay ever covers. Set
  `--min-replicas 1` (2026-07-12): confirmed a replica now always running,
  `/health` at ~0.1s. **Do not revert this to `0` to save the ~$24/month** —
  it will silently reintroduce the exact failed-connection loop. The retry
  code stays as a harmless secondary safety net for genuine transient blips,
  it's just no longer the primary defense. Currently covered by Azure's
  $200/30-day free-account credit (expires 2026-08-10, subscription gets
  disabled at that point unless upgraded to Pay-As-You-Go first — flagged to
  Alankrit, deliberately deferred, not urgent yet but a real deadline).
- **Render suspended, not deleted** (`srv-d94153cvikkc73ba8ckg`, via the
  Render API — the CLI's workspace picker is interactive-only and doesn't
  work in a non-TTY context, so used `~/.render/cli.yaml`'s cached API key
  directly). Confirmed via `/health` returning 503. Fully reversible — Render
  supports resuming a suspended service. `render.yaml`/`Dockerfile` are
  untouched and still work unchanged if it's ever resumed.
- **A real distributable `Icarus.dmg` built** (`ICARUS_BRAIN_URL=<azure-url>
  scripts/package_dmg.sh`), stamped with the live Azure URL, ad-hoc signed —
  not just a locally-stamped test build.
- **Extension re-pointed** (commit `86ab2a0`): the last 2 `onrender.com`
  references (`background.js`'s `BRAIN_URL`, `manifest.json`'s
  `host_permissions`) swapped to the Azure URL — `content.js` no longer holds
  its own `BRAIN_URL` at all after the earlier CORS-routing fix this session.

**Open for next session:** the GitHub OAuth App's callback now points at
Azure (moved by Alankrit directly, per the single-callback constraint) —
if Render is ever resumed, that callback would need to move back or a
second OAuth App would be needed. Azure Container Apps is now
`min-replicas=1` (always warm, no cold starts, see above) — decide before
2026-08-10 whether to upgrade the subscription to Pay-As-You-Go (the $200
trial credit expires then and the subscription gets disabled if not
upgraded first).

---

# Icarus — Session Handoff (2026-07-10, later: local brain + stress tests)

**READ THIS BLOCK FIRST — it supersedes §5 below ("HF Spaces migration is #1").**
The HF migration is DEAD. Everything under the older handoff (starting at the
next H1) is still accurate history, but the hosting priority changed.

## A. Hosting pivot: HF migration ABANDONED → local now, Oracle Cloud later
- **HF free Docker Spaces no longer exist.** Hugging Face silently made Docker
  SDK + CPU-basic **PRO-only ($9/mo)** — confirmed via HF's own forums, an
  undocumented change. The migration plan's whole premise ("2 vCPU for $0") is
  gone. `docs/plans/2026-07-10-hugging-face-spaces-migration.md` is OBSOLETE.
- **Second error caught in that plan:** it claimed "GitHub OAuth Apps support
  multiple callback URLs." FALSE — *OAuth* Apps allow exactly ONE callback;
  only *GitHub* Apps allow up to 10. This matters for hosting (the single
  callback must move from onrender → the new host, it can't be added alongside).
- **Decided direction (Alankrit): perfect it locally, then host on Oracle Cloud
  Always-Free** (Ampere, ~4 vCPU/24GB, genuinely $0, but a raw VM = more ops).
  NOT HF PRO, NOT paid Render. See memory `hosting-direction-local-then-oracle`.
- **Reframe that justifies it:** the only expensive op is one-time, cacheable,
  per-repo corpus embedding (CPU-bound fastembed). Ask-time is already light. So
  we need real CPU for a ~30s burst per repo, not a beefy always-on box.

## B. Semantic PROVEN locally + rebuilt app driven end-to-end
- **Semantic works on real CPU.** The exact repo that ran 900s to failure on
  Render (`alankritxghosh/Icarus`, private, 219 chunks) connected in **26.7s** on
  the Mac → a real `HybridRetriever` (verified by inspecting the retriever type,
  §3's method). 400x-never-finishes → 27s.
- **Local brain stood up** (`python -m demo.server`, unbuffered, auth required)
  and proven: `/ask` cited answers + honest `unknown`, honesty gate held.
- **Mac app REBUILT and driven live against the local brain** — a cited answer
  rendered in the overlay for the private repo, semantic active. First time the
  900s `ConnectModel` fix actually compiled into a build.
  - The app gates connect behind GitHub sign-in even for public repos; local
    sign-in needs a loopback OAuth callback the single-slot OAuth App can't hold
    (see A). So a **dev-only bypass** was added: `AppDelegate.swift` seeds the
    token store from `ICARUS_DEV_GH_TOKEN` when set (env-gated, can NEVER fire in
    a shipped build). **Uncommitted on purpose** — local test affordance only.
    Launch via the inner binary so it inherits the env:
    `ICARUS_DEV_GH_TOKEN="$(gh auth token)" mac/Icarus/Icarus.app/Contents/MacOS/Icarus`.

## C. Commits landed this session (all on main, NOT pushed)
- `b1494c7` **fix(library): P1** — release the single-flight slot after stage 1,
  not after the whole two-stage call. Fixes §6's P1 (a reconnect during a pending
  semantic upgrade was swallowed, client polled forever). Red→green test added.
- `60ed92e` **chore(docker): non-root UID 1000** — required for any Docker host
  (was for HF; still good for Oracle). Verified with a local build + non-root run.
- `57948ac` **feat(synth): charitable phrasing** — see D. Gated board stayed
  GREEN. (Reverted an HF-only README front-matter change before committing.)

## D. Stress-test findings (all run live against the local brain)
- **Broken-English / slang / typos:** on the PAID writer (private repos, e.g.
  Icarus) it is **robust** — every mangled variant, incl. misspelled key terms,
  answered consistently and accurately. On the FREE writer (public repos, e.g.
  pydsl) it is **brittle on sparse corpora** — 2 of 4 mangled questions falsely
  abstained. Failure mode is ALWAYS fail-safe: honest `unknown`, never a bluff.
- **Code-only comprehension — the product's core claim, proven.** Connected
  `fmeyer/pydsl` (2009, **0 docs, 0 PRs, 0 issues** — pure code, 4 chunks). Every
  what/how question was answered **from the code, with code citations**, and
  verified accurate against the source. The **why** question (rationale never
  written down) correctly returned honest `unknown`. So Icarus genuinely READS
  CODE — it is NOT reliant on PRs/issues/docs — and the what/how-vs-why honesty
  boundary holds on undocumented legacy code.
- **Brick Q would NOT fix the mangled-question misses** (A/B proven): on a
  4-chunk corpus retrieval already surfaces all chunks, so recall was never the
  bottleneck; the false abstention is WRITER-stage. Brick Q only normalizes the
  *retrieval* query (leaves the writer's question untouched by design), so it
  can't help. **Brick Q is also NOT wired into serving** at all today.
- **The actual fix is writer quality** (confirmed by A/B/C/D): stronger writer
  (Gemini-paid) cleanly answers the mangled Q2/Q4 AND still abstains on the
  unanswerable Q5; normalizing the writer's question doesn't help; prompt-
  hardening is a partial free-tier win. → landed the prompt-hardening (`57948ac`).
  Net: the tier that matters (private/paid) is already robust; the free tier
  degrades safe.

## E. Runtime state at session end
- Local brain running (unbuffered, `ICARUS_REQUIRE_GITHUB_AUTH=1`); Mac app quit.
- Per-user corpora under `./data/<github-user-id>/` (git-ignored). Uncommitted:
  `AppDelegate.swift` (dev bypass) + `.claude/launch.json`.
- **Not yet done:** Oracle setup; remaining stress scenarios (concurrent asks,
  big-repo timing, P1-live-through-the-app); the extension walkthrough (still
  unverified, carried from before). §6's other findings (P2/P3s) untouched.

---

# Icarus — Session Handoff (2026-07-09 → 2026-07-10, private repos fixed)

Read this first next session. It supersedes the prior handoff ("D5 live-testing
session -- live service is stuck") entirely. That session ended with the brain
stuck cold-embedding forever on every boot. Tonight fixed that, then found and
fixed a second, more important problem underneath it: **private repos --
the actual product -- were not usable at all** on the current hosting tier.
Both are fixed and verified live. Don't re-derive any of this — it's below.

**Next session's actual end goal, per Alankrit directly (not just "do the HF
migration"):** ship a rebuilt, running app that reflects everything —
context-aware (semantic retrieval genuinely working, not silently falling
back to lexical-only), every fix from tonight actually live in the app the
user runs, not just source-committed. Concretely, that means the session
isn't done at "HF Space is live" — it's done at: HF migration complete AND
verified (§5) → `mac/Icarus/scripts/bundle.sh` rebuilt with both the 900s
timeout fix (§2, source-only as of tonight) AND the new HF brain URL
(§5's Task 4) → the rebuilt app actually launched and used, not just
compiled. A green test suite and a live curl check are necessary, not
sufficient — the bar is Alankrit actually running the finished app.

---

## 0. TL;DR — where things stand right now

- **The brain boots warm.** `/health`/`/status` on the default `simonw/llm`
  corpus come up `"ready"` in milliseconds, not stuck `"starting"` — fixed by
  baking the embedding model + vector cache into the Docker image at build
  time. Verified live, repeatedly, all night. §1.
- **Private repos are usable.** This was the real fire tonight: a connect to
  Alankrit's own `alankritxghosh/Icarus` repo ran a newly-added 15-minute
  embed timeout to completion on Render's free tier without embedding even
  10% of the corpus — confirmed root cause is Render's CPU (0.1 vCPU,
  verified against their pricing page), not a bug. Fixed with a two-stage
  connect: a fast, lexical-only pipeline publishes "ready" in seconds
  (verified live: `connect received` → success in well under a minute on the
  real repo, real infra), and a full semantic pipeline upgrades it silently
  in the background. §3.
- **`/ask` is proven live, including the honesty gate.** Alankrit ran five
  test questions against the connected `alankritxghosh/Icarus` repo tonight
  — all passed, including a deliberate "what's Icarus's pricing model?"
  probe that correctly triggered an honest "I don't know" instead of an
  invented answer. This is the first live proof this session that `/ask`
  actually works post-fixes — nobody had tested it end to end before this.
  **Caveat found right after, via logs (not guessed): those 5 answers were
  lexical-only.** The background semantic upgrade for that exact connect
  ran its full 900s bound and failed (`semantic upgrade failed for
  'alankritxghosh/Icarus' (TimeoutError); staying on lexical-only search`)
  — so tonight's `/ask` proof is real, but it did not exercise semantic
  retrieval at all. §4.
- **The Hugging Face Spaces migration is next session's #1 priority —
  confirmed, not optional.** Originally scoped as a "nice to have, no rush"
  follow-up, but the log line above changes that: semantic retrieval is
  currently NOT WORKING on Render for any real repo, confirmed live, not
  theoretical. Alankrit's explicit call: Icarus needs to be context-aware
  (semantic, not just keyword search) — that's the actual product, and it
  doesn't work on the current infra. Plan already written:
  `docs/plans/2026-07-10-hugging-face-spaces-migration.md`. Start here. §5.
- **D5's actual goal — the extension walkthrough — is still unverified.**
  Select lines on GitHub → click Ask Icarus → a real cited answer in the
  overlay has never been completed successfully, tonight or in any prior
  session. Not touched tonight; still the biggest untested surface. §6.
- **The Mac app's timeout fix is source-only, not rebuilt.** The app on
  Alankrit's machine still has the old 180s connect deadline. Matters much
  less now that connects land in seconds, but isn't actually verified in the
  running app. §7.
- **A GPT-5.6 Sol code review of tonight's diff found 5 real issues,
  including one genuine correctness bug in §3's two-stage connect** — a
  reconnect to a repo can be silently swallowed while its semantic upgrade
  is still pending, leaving the client polling forever. All 5 independently
  verified against the actual code (not taken on faith) — fix next session,
  starting with the bug. §6.
- `main` and `origin/main` are in sync at `f1837f0` — everything below is
  already pushed and live on Render.

---

## 1. Fix: the brain was stuck cold-embedding on every boot

**Symptom (start of tonight):** `/health` returned `{"ok": true, "state":
"starting"}` and `/status` was `503` for 10+ minutes after every deploy.

**Root cause, confirmed by reading the code:** `demo/library.py`'s
`_build_retriever` synchronously embeds the entire default corpus (243
chunks) via `fastembed` whenever no on-disk `vectors.json` cache exists —
true on every fresh Render deploy, since the cache is git-ignored and
Render's disk is wiped on every deploy/restart/idle-sleep.

**Fix (`b948376`):** `demo/warm_cache.py` (new) bakes the fastembed model
download AND the default corpus's `vectors.json` into the Docker image at
`docker build` time (`Dockerfile`'s new `RUN python -m demo.warm_cache`
step), so the container boots warm instead of cold. Verified with a real
local `docker build` + `docker run`: `/status` returned `"ready"` in **0.05
seconds**. Measured the actual speedup too: cold-embedding 243 chunks took
7.8s on my machine vs 0.04s from the baked cache — 197x. On Render's slower
CPU the gap was much larger in practice (this is what was causing the
10+ minute stuck-boot symptom).

---

## 2. Fix: connect had no timeout and no visibility

Before touching the "private repos don't work" problem, tonight first closed
an observability gap that made every subsequent diagnosis take far longer
than it should have:

**`2294de4`** — `evals/retriever.py`'s `SemanticRetriever` gained an optional
`timeout` (raises `TimeoutError` past it) and `on_progress(done, total)`
param; `demo/library.py` wires a 900s bound + progress logging into the real
embed path. Before this, a slow embed just hung forever with zero signal —
proven live tonight (a connect ran 35+ minutes with no way to tell if it was
almost done or truly stuck).

**`d9f9327`** — added a log line the instant `/connect` is accepted
(`demo/server.py`). Before this, the server's default request logging is
deliberately suppressed, so a connect request left literally no trace until
(if ever) it reached the embed loop's own progress logging. This is what
made it possible to prove, live, that a click had genuinely reached the
server vs. a stale browser tab silently polling a server that had since
redeployed out from under it (this happened at least twice tonight — every
push triggers a fresh Render deploy, which resets in-flight connects).

Client-side, `demo/index.html` and
`mac/Icarus/Sources/Icarus/ConnectModel.swift` both had their poll windows
bumped from 150s/180s to 900s to match the server's bound, and the web page
now says so honestly if it times out instead of leaving "indexing…" up
forever (a real bug found live — the old code just silently stopped
polling).

**This whole layer is now largely superseded by §3** — the 900s timeout and
progress logging still exist and still matter for the background semantic
upgrade, but they're no longer the thing standing between a user and a
working connect.

---

## 3. THE REAL FIX: private repos are usable (two-stage connect)

**What actually happened:** with §1 and §2 live, Alankrit tried connecting
his own `alankritxghosh/Icarus` repo (216 chunks: 144 code, 68 doc, 4
config, 0 PR/issue). It ran the full 900s embed timeout **to completion,
with zero progress log lines ever appearing** (the progress log fires every
~10%, i.e. every ~21 chunks) — meaning it embedded fewer than 21 chunks in
15 minutes. Locally, the same repo embeds in 22.7s. That's roughly a **400x**
slowdown, and it's not a fluke: Render's free tier is confirmed at **0.1
CPU** (a literal tenth of a core) via their own pricing page. **Private
repos were not usable on this infra, full stop** — no amount of more
patient timeouts or better logging fixes that; the CPU genuinely isn't fast
enough to embed a real repo interactively.

**A wrong idea, ruled out before shipping it:** the first hypothesis was
that `evals/retriever.py`'s per-chunk `provider.embed()` loop (one call per
chunk) was the bottleneck and batching all chunks into a single call would
help. Benchmarked directly against the real repo: batching was **~10x
SLOWER** (261s vs 22.3s), not faster. Good thing this was measured before
being "fixed" — would have made things worse.

**The actual fix (`fae482c`):** `Library.connect_sync` now connects in two
stages instead of one:
- **STAGE 1** builds a lexical-only (BM25) pipeline and publishes it as
  `"ready"` immediately — pure Python string processing, no CPU-bound ONNX
  inference at all, so it's fast regardless of how throttled the host's CPU
  is. This is not a stub or a fake mode — lexical-only is the same
  real fallback retrieval mode already used whenever the embedder is
  unavailable at all.
- **STAGE 2** then builds the full hybrid (lexical + semantic) pipeline in
  the background and swaps it in once the embed finishes. A slow host or an
  outright timeout there is explicitly **not a connect failure** anymore —
  the repo is already answerable via stage 1 — so stage 2 exceptions are
  logged to stderr and swallowed, never undoing a working connection. The
  swap only applies if the caller hasn't switched to a different repo in the
  meantime (a real race — two different repos' `connect_sync` calls can
  genuinely run concurrently on separate background threads — guarded under
  the lock and covered by a dedicated test).

`_build_retriever`, `_default_build_pipeline`,
`_default_build_private_pipeline`, and `LibraryRegistry._build` all gained a
`fast=False` param threaded through; the private-repo trust interlock
(`assert_safe_for_private`) is completely unaffected either way — `fast`
only changes which *retriever* gets built, never which *writer*.

**Verified, not assumed, at every level:**
- Full test suite: 298 evals + 163 demo, all green (3 new/replaced tests in
  `demo/test_library.py` covering stage order, a stage-2 timeout not undoing
  stage 1, and the repo-switch race).
- Live against the real embedder, real repo (not test doubles): status
  flipped to `"ready"` with a genuine, searchable `LexicalRetriever` at
  **4.4s**; upgraded to a real `HybridRetriever` at ~30s once the embed
  finished — both confirmed by inspecting the actual retriever object type
  at each point.
- Live on Render itself, the actual infra that failed: `connect received`
  logged, and Alankrit confirmed the connect succeeded well within a minute
  — on the exact repo that previously ran 15 minutes to a hard failure.

**Known, honest tradeoff — no longer hypothetical, measured live:** the
background semantic upgrade for tonight's real connect (`alankritxghosh/
Icarus`) ran its full 900s bound and failed:
`semantic upgrade failed for 'alankritxghosh/Icarus' (TimeoutError);
staying on lexical-only search` (Render logs, `19:39:10`). So this isn't "a
window that might be slow" — on Render's CPU, the semantic upgrade did not
complete even once tonight, for the one real repo tested. Every `/ask`
answer verified in §4 was lexical-only, not semantic. There's still no
client-visible signal of this (`/status`'s JSON shape wasn't touched) — a
user has no way to know whether they're getting keyword or meaning-based
search. **This is the confirmed reason the HF Spaces migration (§5) is now
next session's top priority, not a someday-nice-to-have.**

---

## 4. Verified live: `/ask` actually works, including the honesty gate

Nobody — not this session, not any prior one per the last handoff — had
actually tested `/ask` returning a real cited answer since any of tonight's
fixes landed. I structurally couldn't test this myself (requires Alankrit's
own GitHub bearer token). Alankrit ran five questions against the connected
`alankritxghosh/Icarus` repo:

1. Why one unified cloud instead of self-hosting (tests grounded "why",
   should cite `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md`)
2. How the two-stage connect avoids blocking on slow embedding (self-
   referential — tonight's own fix, should cite `demo/library.py`)
3. Whether Icarus trains on or retains a customer's code (privacy claim)
4. What happens when no grounded citation exists (self-referential — the
   honesty gate explaining itself)
5. Icarus's pricing model — **deliberately unanswerable**, nothing in the
   repo documents pricing (pre-revenue, pre-build per CLAUDE.md)

**All five passed**, including #5 triggering an honest "I don't know"
instead of an invented answer. That's the single most load-bearing proof
point of the whole product (CLAUDE.md's one non-negotiable: "it cannot
bluff") and it held up live, tonight, on real infra.

---

## 5. NEXT SESSION STARTS HERE: the Hugging Face Spaces migration

**Confirmed priority, not optional — Alankrit's explicit call.** Originally
scoped tonight as a "someday, no rush" follow-up once §3's connect fix
landed. That changed the moment §3's own semantic upgrade was checked
against real Render logs and found to have **failed** for the one real
repo tested tonight (see §3/§4's caveat) — meaning semantic, context-aware
retrieval does not currently work on Render for a real repo, full stop.
Icarus being context-aware (semantic search, not just keyword matching) is
the actual product, per Alankrit directly. Lexical-only search papering
over that with a fast "ready" status is a stopgap that got private repos
unstuck tonight, not the finished product.

`docs/plans/2026-07-10-hugging-face-spaces-migration.md` — the verified
case for moving off Render entirely: HF Spaces' free Docker tier is 2
vCPU/16GB vs Render's confirmed 0.1 CPU/512MB, a 20x CPU difference for the
same $0. Every real touchpoint enumerated by `grep`, not guessed (Dockerfile
non-root user requirement, 3 hardcoded Render URLs in `extension/`, the
GitHub OAuth callback needing a second registered URL, docs). Ordered as 5
tasks, smallest-loop-first — start at Task 1 (bare `/health` on a fresh
Space) and don't skip ahead to secrets/OAuth until that's proven.

**What "done" looks like for this, concretely:** a real, non-default repo
connect on the new infra reaches `HybridRetriever` (semantic upgrade
actually succeeds, not just lexical fallback) — verified the same way §3
was verified tonight: inspect the actual retriever type live, don't just
trust a "ready" status.

---

## 6. GPT-5.6 Sol code review findings — fix next session

Ran a review with OpenAI's GPT-5.6 Sol (`codex --sandbox read-only review
--base 13743e1`, read-only, no files modified) against tonight's full diff.
5 findings, all independently re-verified against the actual code before
trusting them (not taken on faith) — every one held up. Fix order below is
by severity: the P1 is a real bug, the P3s are efficiency/cleanliness.

**[P1 — real correctness bug] Reconnecting to a repo can be silently
swallowed while its semantic upgrade is still pending.**
[demo/library.py:247](../demo/library.py) — `self._inflight.discard(repo)`
only runs in the `finally` at the very end of the WHOLE two-stage
`connect_sync` call, meaning `_inflight` holds a repo for the entire
stage-1 + stage-2 duration, not just stage 1. Traced through the exact
scenario and confirmed it's real: connect A (stage 1 lands fast, stage 2
still embedding) → switch to B (fine, different repo) → reconnect A while
A's original stage 2 is still running → the reconnect hits the single-flight
guard (`already_indexing`) and returns immediately with **B's** status, not
A's — and nothing ever restarts a real connect for A. A client polling for
`repo=="A"` would wait forever; nothing will ever set `self._repo` back to
A. **Fix direction (Sol's, sound):** release `_inflight` after stage 1
completes (the repo IS genuinely usable at that point), and track the
stage-2 background upgrade with its own separate bookkeeping so a fresh
reconnect isn't blocked by an old upgrade still finishing.

**[P2 — real gap, my own docstring overclaims] The 900s timeout can't
actually interrupt a single stuck embedding call.**
[evals/retriever.py:142](../evals/retriever.py) — the timeout check only
runs *between* chunks, before starting the next one. If a single
`provider.embed()` call itself stalls, the loop is blocked inside that call
and the check never gets a chance to fire. In practice this is probably
bounded (fastembed is local CPU inference, not network I/O, so a single
call is unlikely to hang literally forever) but the docstring's claim
("fails loudly instead of hanging forever") isn't a true guarantee as
written. Either implement a real interrupting timeout (e.g. run the embed
call on its own thread, `join(timeout)`) or correct the docstring to state
the actual (softer) guarantee honestly.

**[P3 — real, lower severity] The two-stage design rebuilds most of the
pipeline twice.**
[demo/library.py:221](../demo/library.py) — both stage 1 and stage 2 reload
`chunks.jsonl` from disk, construct a fresh writer/provider, and rebuild the
BM25 lexical index from scratch; stage 2 discards all of stage 1's work
rather than reusing it. This is also what forces `fast=False` through
`_default_build_pipeline`, `_default_build_private_pipeline`,
`LibraryRegistry._build`, and every test double that constructs a `Library`.
Cleaner direction: load chunks + build BM25 + construct the provider ONCE,
publish stage 1 from that, and have stage 2 reuse the same objects rather
than rebuilding them. Directly serves Alankrit's "make the codebase leaner"
ask — a real simplification, not just a bug fix.

**[P3 — real, my own mistake] Client poll-window comments are now stale.**
[demo/index.html:237](../demo/index.html) and
[ConnectModel.swift:108](../mac/Icarus/Sources/Icarus/ConnectModel.swift) —
both were bumped to 900s with the comment "matches the server's own embed
timeout," written *before* §3's two-stage fix existed, when that reasoning
was correct (the server used to block until the full embed finished). After
the two-stage fix, the server reports `"ready"` in seconds under normal
operation — the 900s window now mostly protects against slow ingest or the
P1 bug above, not "waiting for semantic embedding," which the comments
still claim. Update the comments to reflect what's actually true post-fix;
the 900s VALUE is probably still fine, the STATED REASONING is what's wrong.

**[P3 — trivial, safe] Dead test code.**
[evals/test_retriever.py:181](../evals/test_retriever.py) —
`real_monotonic = time.monotonic` is assigned and never read. Removing it
also makes the `import time` at the top of the file unused (confirmed —
no other use of `time.` anywhere else in that file) — remove both together.

---

## 7. Open gaps — the real ones, not busywork

**D5's actual goal has never been verified, at all, ever.** Select lines on
a GitHub blob page → click "Ask Icarus" in the extension → a real cited
answer renders in the overlay. This has not happened successfully in this
session or (per the prior handoff) any session before it. Tonight was spent
on infra reliability, not this. **This is the single biggest untested
surface going into next session** if the extension is part of the demo
plan. Start here.

**The Mac app's timeout fix is source-only.** `ConnectModel.swift`'s 900s
deadline (was 180s) needs `mac/Icarus/scripts/bundle.sh` + a relaunch to
take effect in the app Alankrit actually runs. Matters less now (connects
land in seconds via stage 1) but hasn't been verified in the compiled app.

**No visibility into stage-2 (semantic upgrade) SUCCESS**, only failure —
`demo/library.py`'s stage-2 `except Exception` logs to stderr, but a
successful upgrade is silent. Fine for tonight; worth a one-line success log
if this needs debugging again.

**Two-independent-reviewer pass still owed.** Carried debt from Brick D's
early merge (`aecbda1`, explicitly flagged and approved by Alankrit at the
time — "review once D5 fully passes"). D5 still hasn't fully passed (see
above), so this review is still outstanding, and now covers a lot more
surface (all of tonight's fixes too). §6's GPT-5.6 Sol review is a genuine
first independent pass over TONIGHT's diff specifically (not Brick D's
original merge) — real signal, worth keeping as a habit, but it doesn't
retire this debt on its own.

**Render CLI/API access was set up tonight** for live log diagnosis (device-
auth login, `render whoami` confirms `Alankrit Ghosh`). The API key is
cached locally at `/tmp/.render_api_key` — a scratch, machine-local,
never-committed file, not durable across sessions/machines. If log access is
needed again, re-run `render login` (device-flow, opens a browser) rather
than assuming that file still exists.

---

## 8. Carried forward unchanged from prior handoffs

Still true, not re-verified tonight:
- **Brick E** (richer "why" — commit-message/git-blame provenance): sketched
  only, not task-broken.
- **Brick S** (structural comprehension): deliberately deferred-gated per
  CLAUDE.md's "do not build yet" list. Needs Alankrit's explicit go-ahead.
- **Remark 9** (Icarus writing/modifying real code): permanently off the
  table, a closed decision.
- **Voice**: Phase 3, deliberately deferred by the project's own stated
  build order (CLAUDE.md) — not an oversight, a sequencing decision. If any
  demo plan assumes voice interaction, that was never scheduled for this
  stage.
- **Billing/private-repo writer**: private repos use `GEMINI_PAID_API_KEY`
  (a dedicated key, gated by the trust interlock) but this is not yet
  confirmed as a genuinely billed/no-training tier in practice — acceptable
  pre-revenue, revisit before any real external customer's private code
  connects.

---

## 9. Commands

```bash
cd "/Users/alankritghosh/JARVIS /jarvis_engineering"

# Full offline suite on main (298 evals + 163 demo, all green as of 3a6053b)
.venv/bin/python -m unittest discover -t . -s evals
.venv/bin/python -m unittest discover -t . -s demo
node --test extension/*.test.js

# Live service
curl https://icarus-brain.onrender.com/health
curl https://icarus-brain.onrender.com/status

# Render CLI (device-auth login persists locally; re-login if it's expired)
render login
render whoami

# Local dev server, matching production's posture (needed for extension testing)
ICARUS_ALLOWED_HOSTS=* ICARUS_REQUIRE_GITHUB_AUTH=1 .venv/bin/python -m demo.server

# Load the extension in Chrome -- REPO ROOT, not any worktree:
#   chrome://extensions -> Load unpacked ->
#   /Users/alankritghosh/JARVIS /jarvis_engineering/extension
```
