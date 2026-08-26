# Disclosure fields (`later_merged_count`/`later_merged_probed`) — production measurement

**Date:** 2026-08-27
**Repo under test:** `SaravananJaichandar/world-model-mcp` @ `5ec7fc63635b11e8375ded29f768dbcb1e9c6ac4`
**Surface:** `get_task_context` (MCP) → `POST /context`, deployed brain
**Deploy under test:** `main` @ `4950cc0`, GitLab pipeline `#61` (`2793304885`), deploy job triggered manually 2026-08-27
**Fix this measures:** `docs/experiments/2026-08-26-temporal-flag-successor-probe-production.md`'s "Defect found by this run" section

## What changed since the prior measurement

`build_context_package` was copying only `rests_on_deferred` and `later_merged`
onto a decision, silently dropping `later_merged_count` and
`later_merged_probed` — the two fields `deferred_claims` sets specifically so a
reader can tell a 3-wide probe window from a complete list. Fixed in `4950cc0`,
proven red→green offline (2 failures without it), never before measured live.

## Task string (verbatim, identical to both prior runs)

> Add a new evidence_type category with its own decay window, wiring it through
> the model, the decay engine, and the retrieval consumers

## Result — the fields are present in all three trials

| | decisions | `rests_on_deferred` | `later_merged` | `later_merged_count` | `later_merged_probed` |
|---|---|---|---|---|---|
| 08-26 (probe fix, pre-disclosure-fix) | 2/3/3 | TRUE ×3 | `["pr:24","pr:25"]` | **absent** | **absent** |
| **08-27 (disclosure fix) T1** | 2 | TRUE | `["pr:24","pr:25"]` | **2** | **True** |
| **08-27 T2** | 3 | TRUE | `["pr:24","pr:25"]` | **2** | **True** |
| **08-27 T3** | 3 | TRUE | `["pr:24","pr:25"]` | **2** | **True** |

Everything else is unchanged from the 08-26 measurement: same decision counts,
same `prs: ["pr:22"]`, same 6 unknowns. Only the two disclosure fields moved,
from absent to present, in every trial.

`later_merged_count: 2` matches `len(later_merged)` exactly, and `probed: True`
correctly reflects that both successors came from the bounded probe rather than
from gathered evidence (`prs` never held `pr:24` or `pr:25`). A reader can now
tell, from the payload alone, that "2" is a small probe window and not an
exhaustive count — which is the entire reason these fields exist.

## What this does not change

The underlying claim is still false and still `support: explicit`; this fix
never claimed to touch that. It only makes the ANNOTATION honest about its own
strength. See the 08-26 record for what still isn't fixed.

## Protocol notes

- Same deploy-then-reconnect-then-wait-for-semantic-index sequence as 08-26.
  Confirmed `indexing: false` before any trial via `/status`, not assumed.
- Deploy triggered via `glab api ... /play` against the specific manual job on
  pipeline #61, confirmed against the commit SHA in the job payload
  (`4950cc0cc651af936ecc67136b1c7fa9a402f385`) before treating it as the right
  target — the pipeline for the LATEST push (website work, no brain changes)
  never produced a build/deploy stage at all, gated by `.image_sources` as
  documented; #61 was the one with the actual disclosure fix.
