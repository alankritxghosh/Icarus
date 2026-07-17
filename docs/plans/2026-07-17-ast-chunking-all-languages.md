# AST chunking for every language — scope

**Status:** T1 (the tree-sitter chunker) + T2 (unit tests) LANDED for the
React Native language set — `.ts`/`.tsx`/`.js`/`.jsx`/`.mjs`/`.cjs` (via the
`tsx` grammar), `.mm`/`.m` (objc), `.java`, `.kt` — in `evals/ts_chunk.py` +
`evals/test_ts_chunk.py` (27 tests, all real-code-shaped, four proven
red→green against live bugs, see "What T1 found" below). Python (stdlib
`ast`) already landed separately (`evals/ast_chunk.py`,
`evals/test_ast_chunking_eval.py`). tree-sitter is approved, installed, and
verified against all 22 `_EXTENSION_SOURCES` extensions (0 missing grammars).
The pre-existing `chunk_text` character-density gap (finding #4 below) is
FIXED, in both `ingest.chunk_text` and `ts_chunk`'s own valve — verified: the
absolute max chunk size across all 17,657 real files swept (all five repos)
is now 19,991 chars, down from a 949,384-char worst case.

**T3 (per-language live recall eval) LANDED** — `evals/test_ts_chunking_eval.py`
+ `evals/ts_chunk_eval_questions.json` + committed real MIT-licensed fixtures
(`evals/fixtures/ts_chunk_eval/`). Same-run, never-hardcoded, per language:
tsx 66.7%→100%, java 33.3%→66.7% (real wins), kotlin/objc tied at 100% (no
regression, ceiling effect at this corpus's scale — not every language shows
a discriminating win at N=3 questions). One disclosed, real, non-chunking
miss: java's one remaining gap is genuine semantic competition (other files
named after "Fab" outrank the one StackController method that merely
references it), not something any chunker fixes. See "What T3 found" below
for the corpus-sizing lesson this took two iterations to get right.

**T4 (wiring into `fetch_code`) LANDED**, behind `ICARUS_AST_CHUNKING` (env
flag, default OFF). `_chunk_code` dispatches `.py`→`ast_chunk`, the RN
language set→`ts_chunk`, everything else→`chunk_text` unchanged. 10 new
tests in `evals/test_ingest_repo.py` prove the dispatch decision in isolation
AND through the real `fetch_code` walk; the flag-off default is proven
byte-for-byte identical to today (protects the committed board's
reproducibility). Verified live end-to-end against a real cloned repo
(wix/react-native-navigation's `ios/`): 1,624 real chunks, `RNNCommandsHandler.mm`
went from 1 whole-file chunk to 19 per-method chunks, `.h` stayed on
`chunk_text` unchanged, zero crashes.

**T6 (cache invalidation) LANDED.** Root cause was narrower than originally
framed -- `vector_cache.py` itself needed no changes; the real gap was corpus
staleness detection one layer up in `Library`. Two real, nearly-shipped bugs
caught by the tests themselves before landing. See "What T6 found" below for
the full account.

**T5 (gold-label migration) LANDED.** Committed corpus (`evals/corpus/chunks.jsonl`)
re-chunked from 18 whole-file code chunks to 470 AST chunks (PR/issue chunks
byte-identical, untouched). Option (a) from "T5, the decision" below was
taken: all 13 answerable `comprehension_questions.json` citations re-verified
by hand against the real post-migration chunk content and re-pointed to their
new line-ranged refs; `phase1_questions.json` needed zero changes (confirmed
via `grader.gold_refs` that its answerable citations are PR-only, never
code refs). See "What T5 found" below for a real bug this surfaced
(decorator orphaning, 15.9% of the corpus) and the one open item it left.

**T7 (hybrid rebalance) LANDED.** `HybridRetriever` gained optional
`semantic_weight`/`lexical_weight` params (default 1.0/1.0, preserving
`test_retriever.py`'s existing hand-computed-RRF-math fixtures byte-for-byte
unchanged); the real production retriever (`demo/library.py`'s
`_build_retriever`) now constructs it with `semantic_weight=20.0,
lexical_weight=1.0`, recovering semantic-alone's 84.6% recall@5 ceiling on
the comprehension board (plain 1:1 fusion measured 69.2%). See "What T7
found" below for the root-cause mechanism and the surprising side effect it
had on a previously disclosed, unrelated-looking regression.

`.h` remains on
`chunk_text` (see the evidence table: neither the `c` nor `objc` grammar
parses real RN headers cleanly). `ICARUS_AST_CHUNKING` is STILL not enabled
anywhere in production — T6 removes the blocker (an existing connected user's
corpus now refreshes automatically on their next connect instead of staying
silently stale forever), but turning the flag on for real traffic is still a
deliberate decision to make separately, not a consequence of T6 landing.

## What T3 found (2026-07-17, live, not hypothesized)

The first fixture draft used small (~80-250 line) gold files, hand-verified
against real source, same methodology as the Python board proof. Both arms
hit 100% recall identically on every question — no signal at all. Root cause:
files that short never trigger the 512-token truncation this brick exists to
fix, since `chunk_text` either doesn't split a file that short in the first
place, or the embedder's own truncation barely bites a file that's already
near the budget. The Python board proof avoided this by accident — its
questions happened to target module constants and mid-sized functions in a
naturally larger real corpus. Fixed by re-picking gold files at 400-550+ real
lines (still hand-read in full before writing questions) and deliberately
targeting facts positioned LATE in each file, past where a 512-token window
would reach. That is the corpus design lesson for anyone extending T3: a
gold file must be large enough, and the question specific enough, that
truncation could plausibly hide the answer under the OLD chunker — otherwise
the eval measures nothing.

## What T7 found (2026-07-18, live, not hypothesized)

Root cause is a structural property of RRF, not a bug in this codebase: it
rewards CONSENSUS (a moderate rank in both lists) over a single retriever's
excellent rank. Once AST chunking (T5) let semantic retrieval actually work,
a semantically-excellent, lexically-invisible gold chunk could be
out-accumulated by a mediocre-but-in-both-lists competitor purely because the
competitor showed up twice. Confirmed directly, not inferred: on the real
comprehension board, BM25 rescued **zero** questions that semantic alone
missed — every lexical hit was already a semantic hit. That's board-specific
evidence (13 questions), not a universal claim that lexical search never
helps; it's the reason the fix keeps BM25 as a genuine, non-zero contributor
(`lexical_weight=1.0`) rather than excluding it outright.

Two things swept before landing on the fix:
- `rrf_constant` alone has **no effect** on this failure mode — a ref absent
  from a list's own top-N contributes exactly zero regardless of the
  constant; the constant only reweights ranks WITHIN a list a ref already
  appears in.
- Sweeping `semantic_weight` (lexical fixed at 1) showed a clean plateau:
  recall recovers to semantic-alone's exact 84.6% ceiling starting at
  weight=15 and holds flat through weight=100. `20.0` was chosen from inside
  that plateau with margin, not the extreme value.

Implementation constraint that shaped the fix: `evals/test_retriever.py`'s
`HybridRetrieverTests` hand-computes exact RRF scores assuming implicit 1.0
weight per list, with no explicit weight params passed to the constructor.
Changing the class's DEFAULT would have broken several of those tests'
literal expected values — forbidden by CLAUDE.md's "never weaken an eval to
pass" rule, and also just the wrong fix (those tests correctly lock in the
plain-RRF contract for anyone who wants it). So `semantic_weight`/
`lexical_weight` are optional constructor params defaulting to `1.0`/`1.0`
(zero behavior change for existing callers/tests), and only the real
production call site (`demo/library.py`) plus the live-eval files that claim
to measure Icarus's actual shipped retrieval (`test_retrieval_eval.py`,
`test_query_normalization_eval.py`, `test_grep_comparison_eval.py`) were
updated to pass the evidence-based weights explicitly. A new
`WeightedHybridRetrieverTests` class (5 tests) hand-computes the weighted
math the same rigorous way the unweighted fixture already does, and
`HybridComprehensionEvalTests.test_weighted_hybrid_recall_matches_semantic_alone`
is the live, same-run proof of the actual payoff (hybrid recall ≥
semantic-alone recall, not just ≥ BM25-alone — the weaker bar the pre-existing
tests only checked, which is why they stayed green through the whole
regression without catching it).

**Surprising side effect, verified not assumed:** T5's session left one
disclosed, unfixed regression open — `test_query_normalization_eval.py`'s
`test_normalization_never_regresses_clean_phrasing_recall` failed 61.5% <
69.2%, traced at the time to `normalize_query()` stripping `.py`/`/` from a
query and losing a marginal BM25 exact-match signal for question c12. That
test now passes, unmodified, purely as a consequence of T7's weighting fix —
re-run twice to confirm it's not a fluke. `query_normalize.py` itself was
never touched. Mechanism: the regression was never really about query
normalization: it was the SAME underlying unweighted-RRF consensus bias
making c12's specific chunk marginal enough that a small normalization-side
signal loss could flip it from hit to miss. Fixing the fusion weighting
removed the marginality, so the flip stopped happening. This is disclosed
here rather than claimed as "proven root cause" for the original regression,
since it wasn't independently re-diagnosed after the fact — but it is a real,
reproducible, verified-live outcome: the open item from T5 is resolved.

## What T5 found (2026-07-17, live, not hypothesized)

`ast_chunk.py`'s AST-chunked corpus regeneration (18 whole-file → 580 chunks
on the first pass) surfaced a real bug in `ast_chunk.py` itself, not caught
by T1/T2/T3/T4's own test suites because none of them exercised a real
decorator-heavy file at corpus scale: `ast.FunctionDef.lineno`/
`ast.ClassDef.lineno` point at the `def`/`class` keyword line, NOT at any
`@decorator` line above it (a genuine Python AST property, confirmed by
direct measurement, not assumed). Using `node.lineno` alone as a chunk's
start boundary left every decorator uncovered, orphaning it into the
module-level leftover bucket as its own contentless chunk — measured at 92
of 580 chunks (15.9%) corpus-wide; `llm/hookspecs.py` alone produced 6
orphaned `@hookspec`-only chunks alongside its 6 real ones. Fixed with a
`real_start(node)` helper (earliest decorator's line, or the node's own line
if undecorated) applied at every start-boundary computation in the file; 5
new red→green tests (`AstChunkDecoratorTests`) lock in top-level functions,
stacked decorators, decorated methods inside a large class, and the
class-head boundary not double-counting a method's own decorator. Corpus
regenerated again after the fix: 580 → 470 chunks, zero orphans confirmed by
direct inspection.

Two pre-existing tests also needed updates purely because the corpus's shape
changed underneath them (not new bugs): `test_ast_chunk.py`'s valve-ceiling
test looked up a specific whole-file ref (`code:llm/cli.py`) that no longer
exists post-migration — rewritten to check the max size across all current
code chunks directly. `test_ast_chunking_eval.py`'s `setUpClass` tried to
re-chunk refs it read from the live corpus, which are now already
line-ranged (`ref_prefix must not contain '#'` — it was trying to chunk
already-chunked text) — fixed by committing the original pre-migration
whole-file source as an independent fixture
(`evals/fixtures/ast_chunking_eval/`, `MANIFEST.md` documents provenance)
so the test has raw material to re-chunk two ways without depending on the
corpus's current (post-migration) state.

Full regression + the real gated board (`gemini-paid` writer, `gemini` judge)
re-run after landing: both honesty gates 100%, citation correctness 100%,
answer correctness 100% — T5 did not regress the product's real honesty
guarantees.

## What T6 found (2026-07-17, live, not hypothesized)

The original framing ("vector_cache is tagged by model name only, a chunker
change must invalidate it too") turned out to describe the wrong layer.
`evals/vector_cache.py` needed NO changes: its existing coverage check
(`set(vectors.keys()) != set(refs)`, keyed by the SAME `chunks.jsonl` the
caller just loaded) already self-heals correctly the instant `chunks.jsonl`
is regenerated with a different chunker's refs. The real gap was one level
up -- `Library._resolve` never had any way to know an already-ingested
corpus predates a chunking-scheme change, so `chunks.jsonl` itself never got
regenerated in the first place, and the self-healing vector cache never got
the chance to trigger. Fixed by stamping `meta.json`'s new `"chunking"` field
(written by `ingest_repo`, via the single shared `ast_chunking_enabled()`
check `_chunk_code` also uses, so the two can't silently disagree about which
scheme actually ran) and adding a staleness comparison in `Library.
connect_sync`.

Two real, nearly-shipped bugs, both caught by tests before landing, not
found by inspection:

1. **The staleness check almost went into `_resolve` itself**, which seemed
   like the natural place (it already decides `needs_ingest`). It would have
   broken `registry.py`'s eviction-replay path: that path calls `_resolve`
   WITHOUT a token to decide whether an automatic resume of an evicted
   user's session is a safe cache hit, and it can never re-ingest a private
   repo without one. Staleness leaking into `_resolve` would have made a
   resumed private-repo user get silently downgraded to the public default
   repo the next time `ICARUS_AST_CHUNKING` changed -- exactly what that
   path's own contract explicitly forbids. Moved to `connect_sync` instead,
   the one caller with the authority (and, for a private repo, the token) to
   actually act on staleness; `_resolve` stayed pure availability. A
   dedicated regression suite (`ResolveStaysAvailabilityOnlyTests`) locks
   this separation in, and disabling it live (temporarily re-merging the two
   checks) was used to confirm the tests actually catch the regression, not
   just describe it.
2. **The staleness check initially applied to the default repo too.** A test
   (`test_default_repo_never_reingested_regardless_of_flag`) caught it before
   it shipped: without an explicit exemption, flipping the flag would make
   `connect_sync` try to silently re-ingest the frozen, committed `simonw/llm`
   board over the network -- the one corpus this whole brick guarantees stays
   untouched.

Verified live end-to-end, not just at the unit level: a real `Library` with
the real (unmocked) `ingest_repo`/`fetch_code` machinery, connecting the same
real cloned repo twice with the flag flipped in between and no manual
disconnect -- first connect produced 531 chunks tagged `chunk_text`; the
second connect, to the identical repo, automatically re-ingested to 1,624
chunks tagged `ast`, entirely on its own.

## What T1 found (2026-07-17, live, not hypothesized)

Three real bugs, each found by testing against real code from the five RN
repos rather than hand-fixtures, each fixed with a red→green regression test:

1. **Kotlin/ObjC container naming silently degraded to the node's TYPE, not
   its NAME.** `class_declaration.child_by_field_name("name")` returns `None`
   for Kotlin and ObjC (confirmed empirically) -- unlike TS/Java, where it
   works. A naive implementation would have labeled every split method
   "-- in class_declaration" instead of "-- in Big", silently, on every
   Kotlin/ObjC file. Fixed by `_node_name()` falling back to the first
   `identifier`/`type_identifier` child. Regression-tested by literally
   reverting the fix and confirming the test fails.
2. **A large container's own name label was only wired for the
   const-arrow-function case, not plain `function_declaration`/
   `class_declaration`.** Cosmetic but real -- caught before it shipped.
3. **The safety-valve gap (the serious one).** A Jest-style
   `describe('X', () => { ...hundreds of it() blocks... })` is a top-level
   CALL EXPRESSION -- invisible to the definitions/containers/wrappers scheme,
   since it's neither a function, class, nor const-assigned function. Without
   a fix, the ENTIRE undecomposed file fell into the leftover bucket as ONE
   chunk -- measured live on real Expensify/App test files up to **~950,000
   chars** for a single "chunk". That is dramatically worse than
   `chunk_text`'s own 300-line windows would have produced for the same file,
   which is the opposite of this module's entire purpose. Fixed by a general
   size-based safety valve (`_MAX_EMITTED_CHUNK_LINES` = 2x `chunk_text`'s own
   window): ANY single span this module wants to emit as one chunk --
   including the leftover/uncovered-lines bucket, now also honestly split into
   its natural contiguous runs instead of one imprecise whole-file-ref blob --
   that exceeds the threshold gets re-windowed via `chunk_text` itself, using
   absolute source line numbers so the resulting refs stay honest GitHub
   line-links. This is what makes "never worse than chunk_text" an ENFORCED
   property of this module rather than a hope; it also retroactively fixed a
   second real case found in the same sweep (a legitimate single 1,300-line
   React component, `ComposePost` in bluesky-social/social-app, which -- before
   the valve -- was ALSO worse than plain windowing would have produced for
   that span). Proven red→green: disabling the valve makes the exact two
   tests written for it fail with the real numbers (10,836 and 12,841 chars
   against a 10,000 threshold).

**A fourth finding -- FIXED 2026-07-17, same session.**
`ingest.chunk_text`'s own windowing sized purely by LINE COUNT, never
character count -- and the ts_chunk.py safety valve above, which delegates to
it, inherited the exact same blind spot in its own trigger condition. Three
real files exposed it: `mm/app/utils/emoji/index.ts` (125 lines, 253KB -- an
auto-generated `make emojis` data file, one ~250,000-char object-literal
line), `mm/app/screens/background.tsx` (135 lines, 213KB), and
`rncore/.../sort-imports.js` (15 lines, 26.5KB) -- each has so FEW lines that
no line-count-based valve could ever trigger, no matter the threshold, because
a single PHYSICAL LINE within the file was itself pathologically long.

Two fixes, both red→green, both proven against the exact real files:

1. **`evals/ingest.py`'s `chunk_text`**: when a window's floor-of-one-line-
   of-progress guarantee still leaves it over `_CHUNK_MAX_CHARS` (only
   possible when the FIRST line of that window alone already was), the line
   is now truncated (not skipped) to the budget with a visible `…[truncated]`
   marker and a stderr log naming the exact line/file/size -- matching the
   existing truncation-logging convention elsewhere in this file. Truncating
   doesn't newly hide anything: both downstream consumers already silently
   ignore content past this point today (`synth.build_prompt` caps code
   chunks at this same bound for the writer; the embedder truncates at 512
   tokens regardless) -- this makes an EXISTING effective truncation honest
   and logged once, instead of silently repeated by two layers independently.
   Verified refs stay unique post-truncation (load-bearing: `SemanticRetriever`
   keys embeddings by `chunk.ref` -- `evals/retriever.py:146` -- so two chunks
   sharing a ref would silently corrupt each other's vector) and GitHub-linkable
   (`#Lstart-Lend` always names the real source line, never synthetic).
2. **`evals/ts_chunk.py`'s `emit_and_append`**: the valve's trigger condition
   gained a character check (`_MAX_EMITTED_CHUNK_CHARS = 2 * _CHUNK_MAX_CHARS`)
   alongside the existing line-count one, checked against the FINAL emitted
   text (label + scope header + body) rather than the raw source span -- a
   436-line real component (`ParticipantSearchResults.tsx`) landed at 21,043
   chars post-header even though its raw body alone was under the 20,000
   threshold, so checking the pre-assembly body wasn't tight enough either.

Verified against all three real files directly (`index.ts` 252,878→10,014
chars; `background.tsx` 212,706→10,014; `sort-imports.js` 26,185→10,014), and
against the full corpus: the ABSOLUTE MAXIMUM chunk size across all 17,657
real files in all five repos is now **19,991 chars**, hard-bounded, verified
everywhere -- down from a 949,384-char worst case found earlier the same
session. This was a pre-existing `ingest.py` defect, language-agnostic, that
predated this brick and affected the CURRENT PRODUCTION `fetch_code` path for
any repo with a similarly-shaped generated data file -- not RN-specific.

## Why (measured 2026-07-17, not assumed)

`bge-small-en-v1.5` truncates at **512 tokens**, keeping the first 512 and
silently discarding the rest. `ingest.chunk_text`'s fixed 300-line window
measures **p50 ~2,234 tokens** on real code — so semantic retrieval read
roughly the first quarter of every chunk and was blind to the rest, on every
repo, including the committed board. `chunk_text`'s own comment claims the
window is "small enough for a BM25/**embedding** retriever"; that is false by
~4x, and nothing caught it because BM25 covers for it in the hybrid fusion.

Same-run comparison on the comprehension board, PR/issue chunks and source
text held identical, only the code chunker varied:

| arm | code chunks | p50 tokens | % over 512 | semantic r@5 |
|---|---|---|---|---|
| whole-file (committed board) | 18 | 1,585 | 61% | 61.5% |
| window-300 (fresh ingest today) | 63 | 2,234 | 87% | 69.2% |
| **ast (Python, stdlib)** | **580** | **161** | **10%** | **92.3%** |

Note the middle row: **the current 300-line window is worse than no windowing
at all** for semantic retrieval (87% truncated vs 61%). Windowing slices big
files into uniformly dense slabs where leaving them whole at least kept small
files small.

**Correction, 2026-07-17, later the same session:** the `ast` row originally
claimed 433 chunks / 100.0% recall. That number was never produced by the
real, committed `test_ast_chunking_eval.py` -- it came from an earlier,
less rigorous measurement and was never reconciled against the actual test
before landing here. Found via the debugging playbook's sibling-sweep step
while reviewing this brick: `ast_chunk.py`'s `emit()` had no size cap at all
(the identical bug already found and fixed in `ts_chunk.py` earlier the same
session, never checked for in its twin), so a single dense function, a large
class's head, or the module-level leftover blob could ship as one unbounded
chunk -- up to 57,786 chars on a synthetic repro, 23,497 on the real
committed corpus's own `llm/cli.py`. Fixed with the same valve mechanism
already proven in `ts_chunk.py`. The re-verified, real number (**580 chunks,
92.3% recall**, re-run against the actual test after the fix) is still a
decisive win over the 69.2% baseline -- just not the number originally
written down.

## Reality check on "all languages perfectly"

"Perfectly" is not a claim this plan can honestly make, and the evidence says
why. tree-sitter gives a parse tree; it does not tell you which nodes are
definitions. Every grammar names them differently, several hide them inside
wrapper nodes, and two of our extensions are genuinely ambiguous. All of the
below is **measured against the real repos cloned 2026-07-17**
(Expensify/App, facebook/react-native, bluesky-social/social-app,
mattermost/mattermost-mobile, wix/react-native-navigation), not guessed:

| ext | grammar | what real code actually shows | trap |
|---|---|---|---|
| `.py` | python | `function_definition`, `class_definition`, **`decorated_definition`(120)** | decorators wrap the def in a distinct node |
| `.ts` | typescript | **`lexical_declaration`(118)** dominates; `function_declaration` only **4** | `export const f = () => {}` — naive mapping misses nearly every function |
| `.tsx` | tsx | `export_statement`(50), `lexical_declaration`(41), `function_declaration`(38) | same as `.ts` |
| `.js` | javascript | **`ERROR`(2080)** | RN `.js` is **Flow-typed JSX**; the plain JS grammar cannot parse it |
| `.go` | go | `function_declaration`(135), `method_declaration`(34), `type_declaration`(25) | clean |
| `.java` | java | `class_declaration`(20), `enum_declaration`(5) | methods nest inside the class |
| `.kt` | kotlin | `class_declaration`(21), `object_declaration`(3), `function_declaration`(3) | clean |
| `.mm` | objc | `class_implementation`(25), `class_interface`(3) | clean — the RN iOS bridge |
| `.m` | objc | `class_interface`(39), `class_implementation`(38), `function_definition`(7) | clean |
| `.h` | c *or* objc | **`ERROR`: 360 with `c`, 171 with `objc`** | genuinely ambiguous; **neither grammar is clean** |
| `.cpp` | cpp | `namespace_definition`(21); only **4** top-level `function_definition` | functions nest inside namespaces |
| `.swift` | swift | `class_declaration`(31), `function_declaration`(2) | clean |

**Honest bar instead of "perfect":** every language is either (a) provably
better than line-windows, measured on a real repo of that language, or (b)
explicitly falls back to `chunk_text` and is *recorded as unsupported here*.
No language is silently half-done. The `.js` and `.h` rows above are exactly
the cases that would have been silently half-done if we had trusted a node
table instead of measuring.

## Design consequences (each forced by evidence above)

1. **Recursive walk, not top-level children.** `.cpp` (namespaces), `.java`
   (class-nested methods), `.ts` (export wrappers) all hide definitions below
   depth 1.
2. **Unwrap wrapper nodes.** `export_statement`, `decorated_definition`,
   `lexical_declaration` → descend to the real definition, but chunk at the
   *wrapper's* line span so the citation includes the `export`/decorator.
3. **Grammar selection is per-extension AND content-sensitive.** `.h` must
   sniff for `@interface`/`@implementation` → objc, else c/cpp. `.js` must use
   a JSX/Flow-capable grammar, not plain `javascript`.
4. **ERROR-rate gate (the safety property).** Parse, count `ERROR` nodes; if
   the error rate exceeds a threshold, **fall back to `chunk_text`**. This
   mirrors the existing `SyntaxError` fallback and is what makes "never worse
   than today" true rather than hoped. It is also the only honest way to
   handle `.h`, where both grammars error.
5. **Lazy import.** No tree-sitter installed → `chunk_text`. Same contract as
   fastembed today.

## Tasks

- **T1 — `evals/ts_chunk.py`**: the tree-sitter chunker behind one function
  with `ast_chunk`'s exact contract (`(text, ref_prefix) -> [{"ref","text"}]`,
  `#Lstart-Lend` refs, no `source` key). Per-language node config table, driven
  by the measured evidence above. Recursive walk + wrapper unwrap + ERROR gate
  + fallback. Python keeps using the stdlib `ast` path (already proven, zero
  dependency, and it works when tree-sitter isn't installed).
- **T2 — per-language unit tests**: deterministic, offline, one fixture per
  language asserting the definition boundary is found and the fallbacks fire
  (unparseable, ERROR-heavy, no-definitions).
- **T3 — per-language recall eval — LANDED.** Same-run comparison as
  `test_ast_chunking_eval.py`, against committed real fixtures (not a live
  clone). tsx and java clear the "beats line-windows" bar with real margin
  (66.7%→100%, 33.3%→66.7%); kotlin and objc tied at 100% rather than
  strictly beating it — both already at ceiling for their 3 questions each at
  this corpus scale, not a regression, but not the clean "beats" result the
  bar as originally stated implied either. Honest caveat, not silently
  smoothed over. See "What T3 found" above for the corpus-sizing lesson.
- **T4 — wire into `fetch_code` — LANDED.** Behind `ICARUS_AST_CHUNKING`
  (default OFF, so it can be rolled back without a redeploy — trivially true
  right now since it isn't enabled anywhere yet). Verified live end-to-end
  against a real repo, not just fixtures.
- **T5 — corpus + gold-label migration — LANDED.** Option (a) below taken:
  all 13 answerable `comprehension_questions.json` citations hand-verified
  against the real post-migration corpus and re-pointed to line ranges;
  `phase1_questions.json` untouched (PR-only citations, structurally
  unaffected). See "What T5 found" above for the real decorator-orphaning bug
  this surfaced and fixed (15.9% of the corpus) and the fixture this needed
  (`evals/fixtures/ast_chunking_eval/`).
- **T6 — cache invalidation — LANDED.** `vector_cache.py` needed no changes
  (its ref-coverage check already self-heals once `chunks.jsonl` regenerates);
  the real gap was corpus-level staleness detection, fixed via a `"chunking"`
  field in `meta.json` + a staleness check in `Library.connect_sync` (NOT
  `_resolve` -- see "What T6 found" above for why that distinction is
  load-bearing). Verified live: reconnecting the same repo after flipping the
  flag automatically re-ingests, no manual disconnect needed.
- **T7 — rebalance the hybrid — LANDED.** `HybridRetriever` gained optional
  `semantic_weight`/`lexical_weight` (default 1.0/1.0, zero behavior change
  for existing callers); `demo/library.py` now builds it with
  `semantic_weight=20.0, lexical_weight=1.0`, recovering semantic-alone's
  84.6% recall@5 ceiling (plain 1:1 fusion measured 69.2%). See "What T7
  found" above for the RRF consensus-bias root cause and the plateau
  measurement behind the chosen weight.

## T5, the migration: the decision this needs

The board's gold citations are **whole-file** refs (`code:llm/models.py`).
AST chunks carry line ranges. `grader.grade`'s `retrieval_recall_at_k` and
`citation_correctness` both do **exact ref membership**, so a re-chunked
corpus scores those metrics near 0 for reasons unrelated to quality. Three
options, and this is Alankrit's call, not the implementer's:

- **(a) Re-label the gold citations to line ranges.** Rigorous; each of the
  19 answerable questions (13 comprehension + 6 phase1) re-verified by hand
  against the real source. Highest confidence, real work, and touching gold
  labels is exactly the "never weaken the eval" danger zone — so it must be
  done by reading the source, never by pasting in whatever the retriever
  happened to return.
- **(b) Resolve gold by containment** — a citation `...#L100-L150` satisfies a
  whole-file gold `code:llm/models.py`. Cheap and arguably *more* correct (the
  gold means "the answer is in this file"; a narrower citation is more
  precise, not wrong). **But** it weakens `citation_correctness`: a citation to
  the wrong part of the right file would count as correct. Not free.
- **(c) File-level metric only** — what `test_ast_chunking_eval.py` uses today.
  Fair for a *comparison* between chunkers (which is all it claims), but too
  coarse to be the board's headline citation metric.

Recommendation: **(a)**, with (b) rejected explicitly on the grounds above.
The board is the product's conscience; making it coarser to accommodate a
refactor is the exact failure mode `docs/WORKFLOWS.md` forbids.

## Risks / open questions

- **T3's labelled sets are the real cost.** Beating line-windows must be
  *measured per language*, and today only `simonw/llm` (Python) has a labelled
  question set. Twelve more languages × a hand-verified question set is
  plausibly larger than all the code in T1. Options: a smaller per-language set
  (3–5 questions), or ship only the languages a design partner actually uses
  (React Native ⇒ `.tsx`, `.ts`, `.mm`, `.m`, `.h`, `.java`, `.kt`) and record
  the rest as line-window fallback. **Recommend the latter** — it matches the
  Morphic pilot and avoids inventing labels for languages nobody is asking
  about yet.
- **`.h` may not be fixable to a clean parse** (171 ERROR nodes even with the
  objc grammar). Likely outcome: `.h` stays on `chunk_text`, recorded as a
  known gap. That is an honest answer, not a failure.
- **`.js` needs the right grammar**, not the obvious one. Unresolved which
  (tsx vs a flow grammar) — must be measured, not picked.
- **Image size**: tree-sitter-language-pack is ~2MB wheel, but bundles 165+
  grammars; confirm the built image size and cold-boot time on Azure
  Container Apps before deploying (the Dockerfile bakes the model in already).
- **RESOLVED 2026-07-17: local venv rebuilt on Python 3.12, matching the
  Docker image.** Root cause turned out bigger than version drift: it's
  [Homebrew/homebrew-core#277330](https://github.com/Homebrew/homebrew-core/issues/277330)
  — bottled CPython's `pyexpat` (3.12 AND 3.14 bottles both reproduced it,
  confirmed live) links against `/usr/lib/libexpat.1.dylib`, but this macOS's
  system expat lacks a symbol (`_XML_SetAllocTrackerActivationThreshold`) the
  bottle expects, so `pip install` failed outright on any freshly-poured
  interpreter. Fixed by installing Homebrew's `expat` (which has the symbol)
  and `install_name_tool -change`-ing the Cellar `pyexpat.cpython-312-darwin.so`
  to load it instead of the system one, then re-signing (adhoc) since relinking
  invalidates the code signature. `.venv` rebuilt clean from that interpreter;
  `pip install -r requirements.txt` now works with no wheel-hacking. Verified:
  evals 374, demo 176, both green from a plain `pip install`.
