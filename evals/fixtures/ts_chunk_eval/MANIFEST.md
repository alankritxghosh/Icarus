# ts_chunk_eval fixtures — provenance

Real source files from three MIT-licensed public repos, copied verbatim
(unmodified) for T3 of `docs/plans/2026-07-17-ast-chunking-all-languages.md`:
proving `ts_chunk` beats `chunk_text`'s line-window baseline per language,
the same way `evals/test_ast_chunking_eval.py` proved it for Python -- with a
same-run, never-hardcoded comparison. Chosen over a live network clone at
test time (the `RUN_INGEST_SMOKE=1` pattern used elsewhere) so this eval is
deterministic, fast, and needs no network -- matching this codebase's existing
convention of committing real evidence (the `simonw/llm` corpus itself is
real, ingested GitHub content, not synthetic).

Each language's file set is the target file the labelled questions
(`evals/ts_chunk_eval_questions.json`) reference, plus real siblings from the
SAME directory (not hand-picked to make the comparison look better) -- the
first N alphabetically, so the file set a question is graded against is
exactly the kind of real, unremarkable neighboring code a retriever has to
rank against in production.

Sized at ~70 files per language (java capped at 47, its directory's entire
bounded pool) DELIBERATELY, not arbitrarily: an earlier ~20-file-per-language
cut made file-level recall@5 trivial for BOTH chunkers (100% vs 100%, no
signal) -- top-5 against only 20 candidate files is too generous a bar to
show a real difference. ~70 files tightens top-5 to a genuinely selective
~7% of the corpus, which is what actually let the comparison discriminate.

| lang   | dir                          | files | source repo                              | commit                                    |
|--------|------------------------------|-------|-------------------------------------------|--------------------------------------------|
| objc   | `objc/`                      | 72    | wix/react-native-navigation (MIT)         | `c9bbcb24ddc4361fd226033fd0f9627eb6df44f2` |
| java   | `java/`                      | 47    | wix/react-native-navigation (MIT)         | `c9bbcb24ddc4361fd226033fd0f9627eb6df44f2` |
| kotlin | `kotlin/`                    | 71    | facebook/react-native (MIT)               | `e979b0ef8dc805240482338e72f77f0284cca3ff` |
| tsx    | `tsx/`                       | 72    | bluesky-social/social-app (MIT)           | `007c21fa8e3eade0701ac809c0651eb21cfe10c3` |

Gold files (the question target per language) are DELIBERATELY 400-550+ real
lines -- `RNNCommandsHandler.mm` (539), `StackController.java` (528),
`MatrixMathHelper.kt` (510), `TextField.tsx` (460). An earlier draft targeted
small (~80-250 line) files and found BOTH chunkers hit 100% recall
identically: a file that short never triggers the 512-token truncation this
brick exists to fix, since `chunk_text` either doesn't split it at all or the
whole file already fits the embed budget. These four are real gold files
already present in each corpus (not appended separately).

Fetched 2026-07-17. `objc/` = `ios/*.mm` (top-level). `java/` =
`android/src/main/java/com/reactnativenavigation/viewcontrollers/**/*.java`
(recursive; the entire bounded pool in that directory -- widening further
would mean pulling in a much bigger, less thematically-related part of the
codebase, not just more distractors of the same kind; a same-named file
across subdirectories is prefixed `dup_<dir>_` to avoid a silent overwrite --
none occurred in this set). `kotlin/` = `.../uimanager/**/*.kt` (depth 2,
first 70 alphabetically + the target file). `tsx/` =
`bsky/src/components/**/*.tsx` (depth 3, first 70 alphabetically + the
target file).

All three upstream LICENSE files confirm MIT; original per-file copyright
headers (where present, e.g. Meta's on the Kotlin/ObjC files) are preserved
verbatim in the copied files themselves.
