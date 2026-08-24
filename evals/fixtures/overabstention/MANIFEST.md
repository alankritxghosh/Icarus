# Over-abstention fixture — provenance

`code:world_model_server/decay.py#L1-L56` from `SaravananJaichandar/world-model-mcp`
@ `5ec7fc63635b11e8375ded29f768dbcb1e9c6ac4` (MIT), extracted from a clone at the
pinned commit and rendered in `evals/ast_chunk.py`'s scope-header shape.

Line 34 of the real file is `EVIDENCE_TTL_DAYS`, the `evidence_type` -> TTL-days
mapping that four of the recorded unknowns say they cannot locate. The chunk
window (L1-L56) contains it, and this ref is what the recorded run cited.

The 20 unknowns themselves live in the test file rather than here: they are model
output, not repository content, and belong with the assertions that read them.

Unlike the fabrication fixture, this one **does reproduce the defect** — the
unknowns are replayed verbatim through the real `build_context_package`, which is
pure reshaping, so no writer and no corpus are involved.
