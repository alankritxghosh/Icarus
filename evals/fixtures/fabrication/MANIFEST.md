# Fabrication fixture — provenance

16 chunks reconstructed from `SaravananJaichandar/world-model-mcp` @
`5ec7fc63635b11e8375ded29f768dbcb1e9c6ac4` (MIT licensed; code and data).

**What these are.** Every ref that `get_change_context` actually retrieved on
2026-08-24 for the question in `evals/test_fabricated_terms.py`, minus
`index:overview` (which Icarus computes rather than ingests). Source text is real
— extracted from a clone at the pinned commit, and issue #37 via `gh`.

**What these are NOT: byte-identical production chunks.** The production corpus
for this repository is per-user and not committed anywhere, so chunk text here is
*reconstructed to match ingest's shapes* — `ast_chunk`'s `# path -- in class X`
scope header plus leading imports for code, ingest's `COMMIT <short>: <subject>`
/ `[author on date]` framing for commits, `ISSUE #N: title` / `[STATE by author]`
for issues, and plain line windows for `CHANGELOG.md` docs.

That gap is load-bearing and is why the live board in the test file does not
reproduce the recorded defect. Do not describe this fixture as a reproduction of
the production corpus. If the defect ever needs to be reproduced offline, the
first thing to try is capturing the real chunk text and retrieval ORDER from a
live `/ask` with evidence included, not widening this fixture further — that was
already tried at 5 and 16 chunks and changed nothing.

**Regenerate:** see the generator inline in the session record; it needs a clone
at the pinned commit and `gh` authed. Nothing here is machine-generated at test
time, so the fixture is stable and offline.
