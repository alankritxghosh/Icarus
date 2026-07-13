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
