# History-failure pilot — review handoff for Codex

Paste-ready. Claude Code hands off after collecting the agent sessions; the
weekly agent limit is ~exhausted, so no further sessions run for now.

## State at handoff (2026-08-29)

- **17 of 23 pairs complete** (may be 18–19 if the running round lands S06/S07;
  check the runs dir). Every completed pair passed integrity verification: no
  rate-limit ghosts, no Icarus tool calls, no dirty starts, no wrong-pin, no
  empty final responses.
- Completed: `C01 C03 C09 N03 N06 N07 N08 N09 R03 R05 R13 R14 R15 R16 R17 R18 R19`
- **NOT completed:** `S03 S06 S07 S08` (superseded stratum — 0 pairs so far),
  `N10 R02` (null / refused). `R02 S03` are `astral-sh/uv` (Rust — cargo builds
  fill the disk and take 4+ min); `N10 S08` are `firecrawl` (Node). Deferred on
  disk + agent-limit grounds, not a design decision.
- Stratum coverage at 17 pairs: refused 9, constraint 3, null 5, **superseded 0**.
- Spend so far ~$25 in agent credits. 97 rate-limited arms voided (artifacts kept).

### Paths

- Frozen manifest / packet (outside repo):
  `~/Library/Application Support/Icarus/experiments/2026-08-27-history-pilot/frozen/`
  - `manifest.json` SHA-256 `df7748428e116e766cf4ab09027e5fc87aeaf4f29bd27553cff125c7a1acb0c2`
  - `context-packet.json` SHA-256 `84c652d7bf46251e8b40f0452598952592ef1a622888cc69759d6e1b6b0144ff`
  - `forbidden-strings.json`
- Session output: `~/history-pilot-runs/` (per task: `<id>/<arm>/attempt-NN/`)
- Preregistration + Amendments 1–5:
  `docs/experiments/2026-08-27-history-failure-reduction-pilot.md`
- Tooling (all `--selftest`, stdlib only):
  `scripts/history_pilot_{sessions,freeze,blind,score,checks}.py`,
  `scripts/history_pilot_review.html`

## Hard rule (Amendment 3)

**Codex is NOT a reviewer and neither is any LLM.** The primary endpoint
`history_failure` is scored by a **human** reading the blinded packet. Codex owns
everything *around* the scoring — packet assembly, verification, stats, the
report — but a person must apply the rubric. Amendment 3 already registered this
run as single-reviewer, κ unevaluated, not confirmatory-eligible. If a second
independent human is secured **before scoring starts**, Amendment 3 voids itself
and the two-reviewer flow applies.

## Codex's tasks

### 1. Decide the collection cut, and register it

If the running round has stopped, freeze the pool at whatever completed. Write
**Amendment 6** to the preregistration Result section:

- name every deferred/incomplete task and the reason (agent weekly limit +
  disk cost of Rust/Node builds — not a history-related choice);
- state the final n and per-stratum n;
- flag that **superseded may be n=0**, so no superseded-stratum reading is
  possible and the "largest effect on refused + superseded" prediction (reg.
  prediction 2) is only testable on refused;
- repository-clustered bootstrap still needs ≥2 repos — confirm how many the
  final pool spans (rich, requests, cli/cli, world-model-mcp = 4 if S06 lands,
  3 if not).

Do **not** relax any rule to backfill. A thin pilot honestly reported is the
registered outcome; an inflated one is not.

### 2. Build the blinded packet

```bash
python3 scripts/history_pilot_blind.py \
  --runs-dir ~/history-pilot-runs \
  --manifest "~/Library/Application Support/Icarus/experiments/2026-08-27-history-pilot/frozen/manifest.json" \
  --out-dir ~/history-pilot-review \
  --seed 20260827
```

It writes `blinded-items.json`, `blinded-rubric.json`, `UNBLIND-KEY.json`, and
two verdict templates. It **refuses to emit a packet whose leak audit is not
clean** (arm label / gold field / verbatim Icarus context block). If it reports
a leak, stop and fix — do not hand a leaky packet to a reviewer.

Sanity-check before handing over:
- item count == 2 × (completed pairs);
- `grep -c "ICARUS ENGINEERING-MEMORY" ~/history-pilot-review/blinded-items.json` → 0;
- every item has a non-empty `failure_conditions` entry in `blinded-rubric.json`.

### 3. Human scores

Give the reviewer **only** `blinded-items.json` + `blinded-rubric.json` and open
`scripts/history_pilot_review.html` in a browser (local file, no server). They
score `history_failure` (bool) and `history_awareness` (bool) per item, export
`verdicts.json`. Keep `UNBLIND-KEY.json` away from the reviewer until they submit.

`history_failure` endpoint definition (also shown in the UI): true if the output
repeats a refused approach without acknowledging it, treats a superseded
proposal/past state as current, violates a recorded constraint/decision, claims
no prior attempt exists when one does, or asserts an unsupported rationale.
**Not mentioning history is NOT a failure** if the delivered outcome is
history-safe — that is `history_awareness`, recorded separately.

### 4. Unblind + score

```bash
# single reviewer (Amendment 3): pass the same file twice — the tool requires
# two and the duplication is recorded as a deliberate deviation
python3 scripts/history_pilot_blind.py --unblind \
  --out-dir ~/history-pilot-review \
  --verdicts ~/history-pilot-review/verdicts.json \
  --verdicts ~/history-pilot-review/verdicts.json
```

Then assemble the `runs.json` the scorer wants — one row per history-bearing
completed pair (null-stratum pairs included but excluded from the primary
estimate by the scorer):

```json
{"runs": [
  {"task_id": "...", "repo": "owner/name", "stratum": "refused|superseded|constraint|null",
   "control":   {"valid": true, "history_failure": <bool from verdicts, mapped via UNBLIND-KEY>},
   "treatment": {"valid": true, "history_failure": <bool>}}
]}
```

```bash
python3 scripts/history_pilot_score.py runs.json
```

Reports both arm rates, absolute + relative reduction, repo-clustered bootstrap
95% CI, exact McNemar p, discordance table. On n this small most of these will
be wide/unstable — report them, do not suppress them.

### 5. Secondary endpoints (mechanical, no reviewer)

- `technical_success`: re-run each task's `technical_check` against the arm's
  patch applied to a fresh pinned checkout. Remember Amendment 2 / check-env:
  27 checks are red-at-pin reproductions, 3 (C01, C05, R05) are green-at-pin
  guardrails, and 7 reproduce by exception not assertion — a non-zero exit at
  the pin is the reproduction regardless of exception type. C05 is not in this
  pool.
- `history_awareness`: from the reviewer's second bool.
- elapsed / turns / cost: already in each `result.json` under `cli_summary`.

### 6. Write the evidence report + close the vault

- preregistration Result: final table, all endpoints, every amendment
  cross-referenced, the no-public-claim boundary restated (now binding on three
  grounds: pilot status, single reviewer, partial blinding);
- `general_index.md` + `detailed_index.md`: entries for the new scripts
  (`history_pilot_{checks,freeze,blind,score}.py`, `history_pilot_review.html`)
  and the `ingest.py` fallback clause — Claude added `history_pilot_checks` and
  `history_pilot_freeze`; `blind` and `score` and the review HTML still need
  index lines;
- vault: `Work Queue.md` status → done/blocked-on-review, `Agent Mode.md` the
  result, `Learning.md` already has the credential-read-as-absent, the
  retrieval-ceiling, the partial-blinding, and the quota-refusal entries —
  add the final result once scored;
- the 7/30 probe-miss finding is already the strongest standalone result and is
  written up in Amendment 1 — the report should lead with it.

### 7. Optional: finish the deferred 6 later

When the agent weekly limit resets and disk allows (~8 GB free needed for a
cargo build), run just those tasks and fold them in:

```bash
python3 scripts/history_pilot_sessions.py \
  --manifest "$F/manifest.json" --manifest-sha256 df7748428e116e766cf4ab09027e5fc87aeaf4f29bd27553cff125c7a1acb0c2 \
  --context-packet "$F/context-packet.json" --context-sha256 84c652d7bf46251e8b40f0452598952592ef1a622888cc69759d6e1b6b0144ff \
  --forbidden-strings "$F/forbidden-strings.json" \
  --expect-strata '{"refused":10,"superseded":4,"constraint":3,"null":6}' \
  --output-dir ~/history-pilot-runs --execute --resume \
  --only-task N10 --only-task R02 --only-task S03 --only-task S06 --only-task S07 --only-task S08
```

`--resume` skips the 17 already banked. Then rebuild the packet and re-score.
If the deferred tasks are added after the first scoring, that is a **second**
scoring pass and must be registered as such (it cannot retroactively become
confirmatory).

## What must not happen

- No LLM scores `history_failure`.
- No rule relaxed to hit a stratum target.
- No pair scored from a session that shows a rate-limit refusal (the guard
  handles this, but verify `void_reason` counts before scoring).
- No public "X% fewer" claim from this pilot regardless of the point estimate.
