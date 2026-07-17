# ast_chunking_eval fixtures — provenance

Raw, unmodified source from `simonw/llm @ 94769b8b076cde9392059d76bd766453cf900180`
(the same pinned commit `evals/corpus/chunks.jsonl` itself is built from) --
extracted from the corpus's OWN whole-file code chunks as they existed before
the 2026-07-17 AST-chunking migration (T5 of
`docs/plans/2026-07-17-ast-chunking-all-languages.md`).

Committed here, independent of `evals/corpus/chunks.jsonl`'s current state,
because `test_ast_chunking_eval.py`'s whole methodology is re-chunking the
SAME raw text two different ways (window-300 vs ast) for a same-run
comparison -- it needs whole-file source to start from. Before this file
existed, that test read the committed corpus's own code chunks directly,
which worked only because the corpus was whole-file at the time; once T5
migrated `evals/corpus/chunks.jsonl` to AST-chunked code (the exact change
this test exists to prove is worth making), that assumption broke -- the
corpus is now one of the two arms being compared, not raw material for both.

18 files under `llm/`, mirroring the original repo layout.
