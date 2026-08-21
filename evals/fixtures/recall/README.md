# evals/fixtures/recall/

A real corpus, ingested from `simonw/sqlite-utils` @ `56dd0970` on 2026-08-21 by
`evals.ingest.ingest_repo(..., code_dir=".")`. 2,294 chunks: 590 issues, 250
pull requests, 1,199 commits, 154 code, 88 doc, 13 config.

**Committed whole, not trimmed.** A recall board measures how a gold ref ranks
*against everything else in the repository*, so deleting the "irrelevant" chunks
would delete the competition that is the measurement. It is 3.8MB, comparable to
the 3.1MB committed `simonw/llm` board it sits beside.

**Why this repository.** The two boards it backs came from live dogfooding on
2026-08-21, and this is where the decisive case lives: `issue:841` carries a
maintainer comment asking that agents not work on a change — a fact recorded
nowhere in the code or `git log`, which is exactly the class of evidence Icarus
exists to surface.

**Frozen on purpose**, like the main board. Do not refresh it to be current: the
ranks recorded in `evals/recall_questions.json` and the answers measured in
`evals/test_writer_uses_evidence.py` are only comparable across runs while the
corpus underneath them holds still. A newer ingest is a different measurement,
and belongs in a new fixture beside this one.
