# History-failure pilot — Claude Code execution-harness handback

Parallel-work brick from
`docs/experiments/2026-08-28-history-pilot-claude-handoff.md`. Scope was the
**session-execution harness only**. No manifest, context packet, or agent session
exists yet, and none was created here.

## Files changed

New, and only these three (the handoff's ownership boundary):

- `scripts/history_pilot_sessions.py` — the harness.
- `evals/test_history_pilot_sessions.py` — 26 focused tests.
- `docs/experiments/2026-08-28-history-pilot-claude-execution-notes.md` — this file.

No existing file was edited. The candidate ledger, preregistration, scorer,
probe harness, `general_index.md`, `detailed_index.md`, and vault notes are
untouched.

## Commands run and observed results

```
$ python3 -m py_compile scripts/history_pilot_sessions.py
compile ok

$ python3 scripts/history_pilot_sessions.py --selftest
selftest ok

$ python3 -m unittest evals.test_history_pilot_sessions -v
Ran 26 tests in 0.207s
OK

$ git add -N scripts/history_pilot_sessions.py evals/test_history_pilot_sessions.py
$ git diff --check -- scripts/history_pilot_sessions.py evals/test_history_pilot_sessions.py
diff --check clean

$ python3 -m unittest evals.test_attempts evals.test_gate
Ran 77 tests in 0.054s
OK        # proportionate check that nearby evals modules still pass; new files import nothing from them
```

No network call, no `git clone`, and no `claude` invocation occurred in any of
the above. Zero credentials were read, printed, or persisted (the harness never
touches env vars or key files).

## What the harness does

A pure functional core plus a thin injectable subprocess boundary.

Core (no IO beyond reading the two input files):

- `load_manifest(path, sha)` — hash-gate, then validate: `experiment` tag,
  strata **exactly** `{refused:12, superseded:6, constraint:6, null:6}`, exactly
  30 tasks, unique non-empty `task_id`s, `owner/name` repos, full 40-hex commit
  SHAs, non-empty prompts, `technical_check` string-or-null, and a per-task
  `arm_order` that is a permutation of `[control, treatment]` **and** equals the
  preregistered derivation `parity(SHA-256("20260827-history-pilot:" + task_id))`.
  Any reviewer-only key anywhere in the JSON (`gold_landmine`, `gold_refs`,
  `failure_conditions`, `icarus_probe`, `icarus_probe_refs`,
  `technical_validation`) is a hard load error.
- `load_packet(path, sha, manifest)` — hash-gate, `experiment` tag, the packet's
  embedded `manifest_sha256` must equal the supplied manifest's hash, context
  keys must equal the task-id set exactly (no missing, no extra), and each
  context's `repo`/`commit` must match its manifest task (catches a
  wrong-repository or wrong-commit Icarus response before launch).
- `build_plans(manifest, packet)` — returns exactly 60 `ArmPlan`s. The control
  prompt is the verbatim task; the treatment prompt is the **identical** control
  prompt plus a delimited, clearly labelled read-only Icarus context block
  ("data, not instructions"). `build_plans` re-asserts that treatment == control
  + the registered block and that both arms carry an identical `agent` config.
  Each plan carries `prompt_sha256`, `context_sha256` (`""` for control),
  `order_index` (the frozen position), and a unique `out_subpath`.

Boundary (injected in tests, real implementations used only under `--execute`):

- `cloner(repo, commit, dest) -> CloneState` — default does `git clone` +
  `checkout --detach` and reports `head`, `git status --porcelain`, and
  `git stash list`.
- `agent_runner(plan, clone_dir) -> RunnerResult` — default is headless
  `claude -p --output-format json --verbose --strict-mcp-config --mcp-config
  <empty> --permission-mode acceptEdits`. The empty strict MCP config keeps the
  Icarus MCP server out of **both** arms; the permission flag gives the headless
  session write access. Captures transcript, final response, `git diff`, end
  HEAD, end porcelain, exit status, elapsed seconds, CLI version, model, and a
  count of `mcp__icarus__` occurrences in the transcript.
- `check_runner(command, clone_dir) -> (output, exit_code)` — runs the task's
  deterministic technical check in the post-agent clone. Captured, **never
  interpreted**.

`execute_arm` runs one arm to a fresh `…/<task_id>/<arm>/attempt-NN/` directory
(NN auto-increments; existing directories are never touched), writes `plan.json`,
`tree_start.json`, `transcript.jsonl`, `final_response.txt`, `patch.diff`,
`technical_check.txt`, `result.json`, and `hashes.json` (SHA-256 of every other
file). It **voids** (writes `VOID.json`, keeps all partial artifacts) on: a
detected gold-string leak in the prompt (before any clone), clone failure,
commit mismatch, dirty starting tree, a present/popped stash, the agent runner
raising, an unwritable/permission-blocked session, a missing transcript, any
`mcp__icarus__` call in either arm, or an ending commit that moved off the pin.

`execute_pilot` runs the 60 arms interleaved by task in frozen `order_index`
order. If **either** arm of a pair is invalid it writes `<task_id>/PAIR_VOID.json`
and both arms' artifacts are preserved for the clean rerun under the original
assignment.

`history_failure` is never computed. `result.json` says so explicitly. No LLM is
invoked as a reviewer anywhere.

## Proposed CLI

```
python3 scripts/history_pilot_sessions.py \
    --manifest        <frozen-manifest.json> \
    --manifest-sha256 <registered hex> \
    --context-packet  <frozen-context-packet.json> \
    --context-sha256  <registered hex> \
    --output-dir      <path OUTSIDE this repo> \
    [--forbidden-strings reviewer-only-strings.json]   # defense-in-depth leak scan
    [--execute]                                        # the only real-launch path
```

Dry-run example (the default — builds and validates plans, no clone, no agent):

```
$ python3 scripts/history_pilot_sessions.py \
    --manifest /tmp/manifest.json --manifest-sha256 c346ef… \
    --context-packet /tmp/packet.json --context-sha256 91af… \
    --output-dir ~/history-pilot-runs
dry run OK: 60 arm plans across 30 pairs written to /Users/…/history-pilot-runs/plans.json
no clone performed, no agent invoked. pass --execute to launch.
```

`--selftest` runs the in-module end-to-end check with fakes (no args needed).

## Tests (`evals/test_history_pilot_sessions.py`, 26 cases)

Valid 30-task manifest → exactly 60 isolated arm plans (30/30 split); manifest
and context SHA mismatch fail before launch; every reviewer-only field, wrong
strata counts, duplicate task IDs, short commit SHA, missing `arm_order`,
tampered `arm_order`, incomplete/extra context coverage, and wrong-repo context
fail closed; control and treatment prompts differ only by the registered block;
the frozen arm order drives plan order and is not silently recomputed; output
dir cannot sit inside the repo and reruns produce `attempt-02` not an overwrite;
the default CLI path never calls the clone boundary and returns plans; dirty
start, commit mismatch, popped stash, missing transcript, unwritable session,
and an Icarus tool call each void the whole pair while `VOID.json` metadata is
preserved; a healthy pair writes the full artifact + hash set. The module
`_selftest()` is also asserted green from the suite.

The boundary is injected with fake repos/transcripts; validation logic is run
for real, not mocked.

## Index entries the integrating builder should add

`general_index.md`, under `## Security automation (per-commit + CI)` (next to the
other `history_pilot_*` scripts):

> - `scripts/history_pilot_sessions.py` — session-execution harness for the
>   paired history-failure pilot. Pure core (`load_manifest`/`load_packet`/
>   `build_plans`) that hash-gates the frozen manifest and treatment-context
>   packet, enforces the 12/6/6/6 strata, 30 unique tasks, full commit SHAs,
>   exact context coverage, and the preregistered per-task arm order, then emits
>   exactly 60 isolated `ArmPlan`s whose treatment prompt is the control prompt
>   plus one delimited read-only Icarus block. A thin injected boundary
>   (`cloner`/`agent_runner`/`check_runner`) runs each arm to its own
>   never-reused `attempt-NN` directory, hashes every artifact, keeps Icarus MCP
>   out of both arms, and fails closed — voiding the whole pair, preserving
>   invalid artifacts — on dirty start, commit mismatch, popped stash, missing
>   transcript, unwritable session, gold-field leak, or any `mcp__icarus__`
>   call. Never scores `history_failure`; default action is a dry run,
>   `--execute` is the only real-launch path. `--selftest` runs end to end with
>   fakes.

Under `## evals/ (the Phase 1 eval harness …)`:

> - `evals/test_history_pilot_sessions.py` — the session harness's contract (26
>   cases, stdlib only, boundary injected): 30-task manifest → 60 isolated
>   plans, SHA mismatches and every reviewer-only field / wrong strata /
>   duplicate ID / incomplete-pair / wrong-repo-context case failing closed,
>   control vs treatment differing only by the registered context block, the
>   frozen arm order consumed not recomputed, output paths neither inside the
>   repo nor colliding across reruns, the default CLI never touching the
>   subprocess boundary, and dirty-start / commit-mismatch / missing-transcript
>   / unwritable-session / Icarus-tool-call each voiding the pair with metadata
>   preserved.

`detailed_index.md` only covers `evals/`; add a short line for the new test
module there if that file's convention warrants it.

## Unresolved risks / product decisions for Alankrit or the integrating builder

1. **Manifest schema is proposed, not ratified.** The preregistration froze the
   *per-task* JSON shape but not the wrapper. This harness expects
   `{experiment, strata, agent, tasks:[…]}` with a per-task `arm_order`. If the
   manifest freezer (Codex) emits a different envelope, `load_manifest` needs a
   one-line adjustment. The per-task fields match the preregistration minus the
   gold fields.
2. **Arm-order derivation.** Preregistration says "SHA-256 of
   `20260827-history-pilot:<task_id>` … balanced by parity". This harness uses
   the **last** byte's low bit (even → control first). If Codex's freezing step
   used a different bit/encoding, the manifest and harness will disagree and
   `load_manifest` will reject the manifest — which is the safe direction, but
   the two must be reconciled before freezing. Recommend Codex import
   `derive_arm_order` from this module when writing the manifest so there is one
   definition.
3. **Unwritable-session detection is heuristic** in the default runner
   (`"permission" in stderr and returncode != 0`). The structural guarantee is
   the `--permission-mode acceptEdits` flag being passed; the heuristic is a
   backstop. A dedicated "did the agent actually get to write" probe would be
   stronger. Given prior empty-diff failures, also recommend the reviewer treat
   *any* empty-diff arm as suspect at scoring time (the harness records
   `diff_is_empty` but does not void on it — an agent may legitimately conclude
   "do not implement this", especially in the refused stratum, which the
   preregistration's recorded secondary-endpoint tension already flags).
4. **`claude_cli_runner` is real code but unverified end to end** — no live
   `claude -p` run happened (correctly, per the handoff). The exact flag set,
   `--output-format json` transcript shape, and transcript location should be
   confirmed against the pinned CLI version during a single non-scored smoke
   before the 60-arm launch.
5. **`--forbidden-strings`** lets the integrator pass the reviewer-only landmine
   texts for a substring leak scan without the harness itself holding the
   ledger. It is optional; the structural guarantee is that gold *keys* can
   never enter a plan because `build_plans` only reads whitelisted fields.

## Confirmation

Zero real agent sessions ran. Zero `git clone`s ran. Zero credentials were
printed or persisted. Only the three owned files were created; nothing was
committed, pushed, or deleted.

---

# Addendum 2026-08-28 — items 3, 4, 13 (explicitly re-authorized by Alankrit)

Alankrit re-authorized Claude Code to do three of Codex's mechanical,
non-judgment items after GPT ran out of usage: (4) finish + hash the
exact-commit corpora, (13) run the experiment test suites, (3) spot-check a
sample of the pinned technical checks. Task selection, scoring, manifest
freezing, ledger edits, and live sessions remain out of scope and untouched.

Nothing in the repository was modified for this addendum except this owned
file. Corpora live only under
`~/Library/Application Support/Icarus/experiments/2026-08-27-history-pilot/`
(outside the repo, git-ignored by location).

## Item 13 — test suites: all green

```
python3 -m py_compile scripts/history_pilot_{sessions,score,probe}.py   -> OK
python3 scripts/history_pilot_sessions.py --selftest                    -> selftest ok
python3 scripts/history_pilot_score.py    --selftest                    -> selftest ok
python3 scripts/history_pilot_probe.py    --selftest                    -> selftest ok
python3 -m unittest evals.test_history_pilot_sessions                   -> 26 passed
python3 -m unittest discover -t . -s evals                              -> 1035 passed, 69 skipped
python3 -m unittest discover -t . -s demo                               -> 668 passed, 5 skipped
```

## Item 4 — exact-commit Icarus corpora

Ran `scripts/history_pilot_probe.py --ingest-only` (no model key needed, no
model call). **23 of 28 distinct pinned corpora built**, each with `meta.json`
and `experiment-provenance.json` carrying `history_chunks_sha256` /
`pinned_chunks_sha256`. Covered: `astral-sh/uv` (4), `Textualize/rich` (11),
`SaravananJaichandar/world-model-mcp` (1), `firecrawl/firecrawl` (3),
`psf/requests` (5 — N03/N08/N09 share one pin).

**Blocked: all 5 `cli/cli` pins** (S05, R04, R03, C09, C08). `gh pr list -R
cli/cli --state all --limit 5000 --json …` returns HTTP 502/504 or
`unexpected end of JSON input` from GitHub's GraphQL API — reproduced 4×,
including bare retries with backoff. `cli/cli` has ~14k PRs and the single
unpaginated query with full `body` is too heavy for the endpoint. Rate limit
was full (5000/5000) each time, so this is a query-size limit, not throttling.

Fix options for Codex (all touch `history_pilot_probe.py` / `evals/ingest.py`,
which Claude does not own):
- lower the PR/issue fetch `--limit` for `cli/cli` (the ingest already
  degrades gracefully elsewhere: "discussion attached to the 200 most recent
  prs of 3333; older ones indexed by description"), or
- page the `gh pr list` call, or
- drop `body` from the bulk list and fetch threads on demand (ingest already
  supports on-demand thread fetch for named refs).

## Item 3 — ALL 30 pinned technical checks re-run at their exact commit

Extended from the 9-task sample to all 30. Every repo cloned, checked out to its
exact pin (HEAD == pin verified for all 30), check run in that tree. Two passes:
bare system Python (stdlib only), then a Python 3.12 venv with common
third-party deps (`pygments`, `typing_extensions`, `markdown-it-py`, `urllib3`,
`charset_normalizer`, `certifi`, `idna`, `pydantic`) and `PYTHONPATH=.:src`.

Expected at the pin: **RED** (landmine present / acceptance not yet met).

| Class | n | Tasks |
|---|---|---|
| Clean `AssertionError` RED, bare stdlib | 16 | C03, C08, C09, N07, N10, R02, R03, R04, R14, R16, R18\*, S03, S04, S05, S07, S08 |
| Clean `AssertionError` RED once `PYTHONPATH=src` set | 3 | N03, N08, N09 |
| RED only via `TypeError` / `ImportError: cannot import name` — post-fix API genuinely absent at the pin, but fails by exception not assertion | 5 | C07, R13, R15, R17, R19 |
| **GREEN at the pin** (exit 0) | 3 | C01, C05, R05 |
| **Cannot run** — needs the repo's own pinned deps, not guessable | 3 | N06 (`requests`), R20 (`chardet`, old vendored), S06 (`aiosqlite`) |

\* R18 fails via `TypeError: Spinner.__init__() got an unexpected keyword
argument 'custom_spinner'` — same fragile pattern as the `TypeError`/`ImportError`
group, not a clean assertion. Counted RED but flagged.

**19 of 30 are clean deterministic assertion reds.** The other 11 need Codex
(check definitions live in the ledger — not Claude's to edit):

1. **No frozen dependency environment exists.** 14 of 30 checks import the
   checked-out package or a third-party lib; there is no pinned per-repo
   environment spec in the experiment artifacts. "Deterministic" is not
   established for those 14 until that environment is frozen with the manifest —
   and the dep versions themselves can flip a result (a newer `pygments`
   changes `rich`'s traceback rendering, which is what C07 inspects).
2. **`psf/requests` is `src/`-layout at these pins.** N03/N08/N09 only red once
   `PYTHONPATH=src` is set; as written they throw `ModuleNotFoundError`. R20
   also needs `chardet`; C01/R05 read a path that may not exist under `src/`.
3. **5 fragile reds** (C07, R13, R15, R17, R19; plus R18): the check exercises
   the post-fix API (`locals_suppress=`, `soft_wrap=`, `show_thread=`,
   `rich.tqdm`, `IndeterminateTaskProgressColumn`, `custom_spinner=`), absent at
   the pin, so it fails with `TypeError`/`ImportError` not `AssertionError`. A
   reviewer or scorer scanning for a failed assertion could misread these as a
   broken check. Rewrite them to assert-on-absence, or make the rubric
   explicitly accept `TypeError`/`ImportError: cannot import name` at the pin as
   a valid red.
4. **3 GREEN at the pin** — C01, C05, R05. Either intentional constraint
   guardrails (fail when the agent *introduces* the bad pattern) — in which case
   the Work Queue's "all 30 survivors have a deterministic red check" is
   imprecise and must distinguish reproduction checks from guardrails — or the
   checks are wrong. C05 reads `requests/sessions.py` (not `src/…`) yet exits 0;
   confirm whether `0192aac2` predates the `src/` migration or `ast.parse`
   silently matched nothing.

## Confirmation (addendum)

No live agent session ran. No scoring, manifest freezing, or preregistration
edit occurred. `--ingest-only` made no model call and used no
`GEMINI_PAID_API_KEY` (still absent). Nothing committed, pushed, or deleted.

---

# Addendum 2026-08-28 (round 2) — Alankrit authorized the fenced-file work

"start them but be careful." Scope granted: cli/cli corpus fix, the flagged
technical-check defects, the frozen check environment, ledger currency.

### 1. Frozen technical-check environment — DONE

New artifacts (both additive, owned by no one else):

- `docs/experiments/2026-08-27-history-pilot-check-env.md` — the spec: Python
  3.12, the exact pinned third-party deps, cwd = repo root at the pin,
  `PYTHONPATH` as the check sets it, and the **two registered check kinds**
  (reproduction = red at pin; guardrail = green at pin by design).
- `scripts/history_pilot_checks.py` — stdlib runner + `--selftest`. Clones each
  pending task's repo at its pin, runs the check in the frozen env, classifies,
  exits non-zero if any task deviates from what is registered.

**Result: 30 / 30 behave as registered.** 20 `RED-ASSERT`, 7 `RED-EXCEPTION`
(C07, R13, R15, R17, R18, R19, R20 — post-fix API genuinely absent at the pin),
3 `GREEN` guardrails (C01, C05, R05). 0 anomalies. This resolves item 3: the
checks are deterministic; what was missing was the environment, now frozen.

### 2. Ledger check amendments — DONE (3 rows, minimal)

My earlier "~11 problem checks" reduced on inspection to **3 genuine bugs**, all
the same: the check hard-codes `PYTHONPATH=.` (or omits it) but the `psf/requests`
pin is `src/`-layout, so `from requests import …` raised `ModuleNotFoundError`
before the assertion.

| Task | Change | Re-verified |
|---|---|---|
| N03 | prepend `PYTHONPATH=src` | red at pin, clean `AssertionError` |
| N08 | prepend `PYTHONPATH=src` | red at pin, clean `AssertionError` |
| R20 | `PYTHONPATH=.` → `PYTHONPATH=src` | red at pin, `AttributeError` (feature absent) |

Each row now carries a `check_amended` field recording the change, date,
authorization, and re-verification. **No landmine, prompt, gold field, stratum,
gold_ref, or assertion was touched.** Strata still 12/6/6/6; 30 pending; JSONL
valid; `history_pilot_probe.py --selftest` and `history_pilot_score.py
--selftest` still pass.

The other flagged checks needed **no edit**: the 7 exception-reds are correct
reproduction checks (they fail at the pin, pass after a real fix); the 3
guardrails are correct by design (`technical_validation` already says so). What
they need is the rubric note — non-zero exit at the pin is the reproduction
regardless of exception type — now in the check-env doc.

### 3. cli/cli corpus fix — `evals/ingest.py`, DONE + tested (two parts)

**Part A — transient retry.** GitHub's GraphQL endpoint intermittently 502/504s
on bulk `gh` calls and succeeds on retry. `_gh_json` now retries a **transient**
failure (`TimeoutExpired`, or `CalledProcessError` whose stderr names
502/503/504/gateway/timeout/EOF) up to 3× with backoff; a non-transient failure
(bad repo, auth, real GraphQL error) is **not** retried. Happy path unchanged.
`evals/test_ingest_retry.py` — 5 tests.

**Part B — paginated-GraphQL fallback.** Part A alone did not unblock cli/cli:
`gh pr list --json` / `gh issue list --json` fail for cli/cli (~14k PRs) at ANY
`--limit` — measured down to `--limit 90` for just `number` — because the query
`gh` builds is too costly for that repo. An explicit `gh api graphql` paged at
`first: 50` pages through cleanly (verified live). So `_bulk_list_or_paginate`
now tries the direct `gh * list` call first (**byte-unchanged** for every repo
that works today) and, only on failure, falls back to `_paginate_graphql`;
`_flatten_graphql_node` reshapes each node to exactly what `_pr_or_issue_text`
consumes. The discussion depth pass still degrades as designed.
`evals/test_ingest_graphql_fallback.py` — 8 tests (flatten correctness,
direct-call-never-touches-graphql, disabled-issues still re-raises, fallback
paginates + flattens, `fetch_prs` end-to-end via the fallback).

- Full `evals` suite: **1048 passed** (+13), 69 skipped. Full `demo`: 668 passed.
- cli/cli ingest re-run via `history_pilot_probe.py --ingest-only`: **succeeded
  through the fallback. Corpora now 28 / 28.** The direct `gh pr list` failed
  all three attempts as expected, the fallback paginated 4,551 PRs, and all five
  cli/cli corpora (R03, R04, S05, C08, C09) were built with provenance hashes.

**Gold-ref presence verified in every cli/cli corpus** (the check that actually
matters — a built corpus that lacks the decisive PR would be worse than none):

| Task | gold ref(s) | present | chunks | commit matches pin |
|---|---|---|---|---|
| C08 | pr:7960 | yes | 17,326 | yes |
| C09 | pr:13807 | yes | 23,124 | yes |
| R03 | pr:13684 | yes | 23,016 | yes |
| R04 | pr:8584 | yes | 22,788→17,659 | yes |
| S05 | pr:12021, pr:12053 | both | 22,788 | yes |

**Disclosed limitation — issue truncation.** Every cli/cli corpus records
`truncated: true`: PR coverage is complete (4,551 < the 5,000 cap) but the issue
fetch hit `ISSUE_LIMIT` at 5,000, so older issues are indexed only when named.
This is **not** introduced by the fallback — the four `astral-sh/uv` corpora
were already `truncated: true` (5,000/5,000) before any change today. rich,
requests, firecrawl and world-model-mcp are all untruncated. Two of six
repositories therefore carry partial issue coverage; that belongs in the
manifest and in the limitations section, since a treatment context drawn from a
truncated corpus is a weaker treatment than one drawn from a complete corpus.
All ten gold refs across the five cli/cli tasks are pull requests, and all are
present, so no task's decisive evidence is affected.

### 4. Ledger currency — DONE

The 3 `check_amended` entries are the only ledger change. No task rejected or
replaced — none needed it. No new candidates (that needs discovery + the blocked
Icarus probe). Rejection ledger unchanged (still 19).

### Index entries the integrating builder should add

`general_index.md`, under `## Security automation (per-commit + CI)`:

> - `scripts/history_pilot_checks.py` — runs every pinned technical check of the
>   history-failure pilot in the frozen environment
>   (`docs/experiments/2026-08-27-history-pilot-check-env.md`) and confirms each
>   behaves as registered: 27 reproduction checks red at their pin (assertion or
>   feature-absent exception), 3 guardrail checks (C01/C05/R05) green at their
>   pin by design. Clones each repo at its exact commit, verifies HEAD, exits
>   non-zero on any deviation. `--selftest` offline. Never scores
>   `history_failure`.

`general_index.md`, under `## evals/`:

> - `evals/test_ingest_retry.py` — `_gh_json` retries a transient GitHub failure
>   (`TimeoutExpired`, or a `CalledProcessError` whose stderr names
>   502/503/504/gateway/timeout/EOF) up to 3× with backoff, and does NOT retry a
>   real one (bad repo, auth). Live-found on cli/cli's bulk `gh pr list`.

The `evals/ingest.py` entry should gain a clause noting `_gh_json` now retries
transient `gh` failures.

`detailed_index.md` covers `evals/` only — add a line for `_gh_json`'s retry and
for `test_ingest_retry` if that file's convention warrants it.

### Confirmation (round 2)

Files touched: `evals/ingest.py` (+transient-retry in `_gh_json`),
`evals/test_ingest_retry.py` (new), `scripts/history_pilot_checks.py` (new),
`docs/experiments/2026-08-27-history-pilot-check-env.md` (new),
`docs/experiments/2026-08-27-history-failure-pilot-candidates.jsonl` (3
`check_amended` rows — N03/N08/R20 `PYTHONPATH`, nothing else), this notes file.
Full `evals` suite 1040 pass / 69 skip; full `demo` 668 pass / 5 skip; all
`history_pilot_*` selftests pass; ledger JSONL valid, strata 12/6/6/6.

No preregistration edit. No manifest freeze. No agent session. No scoring. No
model call. `GEMINI_PAID_API_KEY` still absent and not needed for any of this.
Nothing committed, pushed, or deleted.

Still outstanding at the end of round 2: the Icarus probes, manifest freeze, the
sessions, blinded packets, human review, statistics, final write-up.

---

# Addendum 2026-08-28 (round 3) — probes, freeze, Amendment 1

Alankrit authorized steps 1–4 (probes, probe review, replacements, freeze) and
explicitly deferred the agent sessions on usage credits. He then chose option A:
freeze the surviving pool and report the probe misses as a result.

## The key was never missing

`GEMINI_PAID_API_KEY` was in the gitignored `.env` the entire time — 53 chars,
distinct from `GEMINI_API_KEY`, live-verified `private_safe: True` and answering.
`scripts/history_pilot_probe.py` just never called `load_env_file`, which
`evals/run.py` does. Its own error string said the key was required and everyone
— the experiment record, the vault, three of my own status reports — believed
the string rather than checking the state behind it. One-line fix at the probe
entry point; the interlock is unchanged and the free key was never relabelled.

`PROTOCOL.md` §5, one layer down. Written up in the vault's `Learning.md`.

## Probes: 30 ran, 23 pass, 7 miss

All 30 on the production paid writer against the exact-commit corpora.

| stratum | pass | miss |
|---|---:|---:|
| refused | 10 | 2 (R04, R20) |
| superseded | 4 | 2 (S04, S05) |
| constraint | 3 | 3 (C05, C07, C08) |
| null | 6 | 0 |

The seven misses all returned verdict `unknown` with **zero citations** — the
decisive record never reached the writer. Rejected into the ledger with reason;
inclusion rule 6 is not negotiable and nothing was substituted under time
pressure. Two soft misses were approved on review: `N08` (null) answered with
textbook bounded absence, `R13` answered substantively from a non-gold ref.

A 546-line reviewer packet (probe question, gold landmine, verbatim answer,
citations, approve box per task) is at
`…/2026-08-27-history-pilot/probe-review-packet.md`.

**The miss rate is reported as a result, not a screening artefact.** On a pool
selected *because* its history was known to be recorded, production retrieval
failed to surface the decisive record for 23% of tasks. Same shape as the
description-recall board's `intent`-phrasing miss.

## Freeze: n = 23

New `scripts/history_pilot_freeze.py` — copies only the six agent-visible
fields, imports `derive_arm_order` from the runner, writes the reviewer-only
landmine texts to a separate forbidden-strings file, and refuses to freeze
unless the pool matches the expected strata (a shape other than the registered
12/6/6/6 must be passed explicitly and is printed as an amendment).

```text
manifest.json        SHA-256 6b084f285643e1cb0a6d0dfe4c443cfc63cd41860191de5cf42d93fe91cc27f3
context-packet.json  SHA-256 06d09b3a1a6b89e162e3748fb426b8092c640f1bd09702e0fab1e9860c64b9ef
```

Validated end to end through the session runner: 23 tasks → **46 isolated arm
plans**, 46 unique output paths, treatment prompt == control prompt + one
delimited read-only Icarus block, and **0 of the 56 reviewer-only strings
present in any assembled prompt**.

`load_manifest` now takes `expect_strata` (defaulting to the registered
12/6/6/6) rather than hardcoding it — a manifest still cannot declare its own
size, the caller must state what was registered and the manifest must match.

## Records updated

- **Preregistration** — Amendment 1 appended below `## Result`; the frozen text
  above that line is untouched. Records the credential finding, the probe table,
  the seven rejections, the n=30→23 reduction and its power cost, both hashes,
  the corpus-truncation limitation, and the check-environment rules.
- **Ledger** — the seven misses moved to `rejected_icarus_probe` with reasons
  (now 23 pending / 26 rejected).
- **Vault** — `Work Queue.md` rewritten to the real gate; two new `Learning.md`
  entries (the credential-read-as-absent day, and the retrieval-ceiling finding).
- **`general_index.md`** — entries for `history_pilot_checks.py`,
  `history_pilot_freeze.py`, `test_ingest_retry.py`,
  `test_ingest_graphql_fallback.py`, and the `ingest.py` fallback clause.

## Verification (round 3)

```
evals suite                    1048 passed, 69 skipped
demo suite                      668 passed,  5 skipped
history_pilot_{sessions,score,probe,checks,freeze} --selftest    all ok
history_pilot_checks.py (frozen env, 23 tasks)   23/23 as registered
check_detailed_index.py         52/52 modules, every symbol resolves
scan_secrets.sh                 clean
```

## What is left, and who owns it

1. **46 agent sessions** — deferred on credits. `history_pilot_sessions.py
   --execute` is ready and takes the two hashes above.
2. Arm verification and blinded packet assembly — mechanical, mine when 1 lands.
3. **Two independent human reviewers** — neither Claude nor Codex may be one.
   The hard blocker on any result.
4. Statistics (`history_pilot_score.py`) and the evidence report.

No agent session ran. No `history_failure` was scored. No LLM judged any
outcome. Nothing committed, pushed, or deleted.

---

# Addendum 2026-08-28 (round 4) — the free work, done ahead of the sessions

"Let's do the cheap ones first." Everything here costs zero agent credits.

## 1. Dry run of all 46 arms — clean

```
dry run OK: 46 arm plans across 23 pairs
no clone performed, no agent invoked.
```

46 plans · 46 unique output paths · 23 control / 23 treatment · every commit a
full 40-hex SHA · every treatment plan carries a context hash and every control
plan carries none · six repositories.

Two fixes this surfaced: `--expect-strata` was wired into `load_manifest` but
not the CLI (so the amended pool could not actually be launched), and the dry-run
line printed a hardcoded `30 pairs` for a 23-task manifest — a misleading number
in an experiment report, now derived from the manifest.

## 2. `scripts/history_pilot_blind.py` — blinded packet builder + unblinder

Per item: opaque id, repo/commit, verbatim task, final response, patch,
technical-check output. Never the arm, never a gold field. The registered
`failure_conditions` ship in a **separate per-item rubric file** — blinding is
about the arm, not the rubric. Order is seeded/reproducible and the two arms of
one task are pushed apart so a reviewer cannot diff a pair. `unblind` refuses a
single reviewer, refuses a non-boolean verdict, and reports raw agreement plus
Cohen's kappa.

### It caught a real unblinding hole before any session ran

Tested end to end against a deliberately **prompt-echoing** fake agent — because
that is what coding agents do — the audit refused to ship the packet:

```
items: 46 leaks: ['BEGIN READ-ONLY ICARUS']
```

The treatment prompt carries the Icarus context block; an agent that restates its
prompt reproduces that block in its final response and hands the reviewer the arm
label on every treatment item. `strip_context_block` now removes every verbatim
reproduction and any lone delimiter, from all reviewer-visible text. Re-run:
`leaks: NONE`, no marker anywhere in the packet, control/treatment mean response
lengths 108 vs 110 chars.

**The residual is irreducible and is now registered as Amendment 2** rather than
left to be discovered during scoring: an agent that actually used the history
paraphrases it, which no redaction can strip and which is exactly what
`history_awareness` measures. Blinding hides the mechanical tell, not the
semantic one. Kappa measures rubric reproducibility and must never be cited as
evidence that blinding held.

## Verification (round 4)

```
history_pilot_{sessions,score,probe,checks,freeze,blind} --selftest   all ok
evals suite                        1048 passed, 69 skipped
check_detailed_index.py            52/52 modules, every symbol resolves
dry run                            46 plans, 0 gold leaks, no clone, no agent
```

Records updated: preregistration Amendment 2, vault `Learning.md` (blinding is
partial by construction), `general_index.md` entry for the blinding tool.

## Remaining, unchanged in shape

1. 46 agent sessions (`--execute`, plus `--expect-strata`) — credits.
2. Arm verification + real blinded packet — mechanical, minutes, once 1 lands.
3. **Two independent human reviewers** — the hard blocker.
4. Statistics + evidence report.

Steps 2 and 4's tooling is now built and selftested, so the only work left after
the sessions is running it and the human review.

---

# Addendum 2026-08-28 (round 5) — the one-arm smoke, and the three bugs it found

Ran `claude_cli_runner` for real, once, on a throwaway task (`octocat/Hello-World`,
task id `SMOKE-not-a-pilot-task`, "create SMOKE.txt containing ok") — a
repository and id that appear **nowhere** in the frozen manifest, so it cannot
contaminate the experiment. Cost: **$0.11**, 7 seconds.

It found three defects. Every one of them would have survived into the batch and
corrupted the result, and none was visible from unit tests.

### 1. `final_response.txt` was EMPTY for every arm — the worst one

`claude -p --output-format json --verbose` emits a **JSON list of stream
events**, not an object with a top-level `result`. The runner did
`json.loads(...).get("result", "")` inside a `try/except json.JSONDecodeError`,
so a list produced `""` and the exception never fired. Every arm would have
been recorded `valid: true` with an empty final response — and the final
response is the primary artifact a blinded reviewer scores. All 46 arms would
have been unscorable, and the run would have looked perfectly healthy.

Fixed with `parse_cli_transcript`, which walks the list backwards for the
`type: "result"` event. That event also carries real `usage`, `total_cost_usd`,
`num_turns`, `is_error`, `stop_reason` and `permission_denials`, all now recorded
in `result.json` under `cli_summary`. Five new tests in
`evals/test_history_pilot_sessions.py` pin the list shape, the tolerated dict
shape, a missing result event, garbage input, and a permission denial.

### 2. `patch.diff` was empty whenever a fix ADDED a file

`git diff HEAD` does not show untracked files. The smoke agent created
`SMOKE.txt`, did real work, and the captured patch was empty. Any pilot task
whose correct fix adds a file (a new test, a new module) would have produced an
empty patch — precisely the signal the preregistration treats as suspicious, so
this would have manufactured false negatives in the review packet. Now `git add
-N .` (intent-to-add, no content staged) runs after the true end-state porcelain
is snapshotted, so new files appear in the diff.

### 3. The harness littered the arm's working tree

The empty MCP config was written to `<clone>/.history-pilot-empty-mcp.json`, so
it appeared in `tree_end_porcelain` and would have appeared in the diff — harness
output inside the artifact under review. Now written beside the clone, not into
it. Confirmed: end porcelain is `?? SMOKE.txt` alone.

### Also improved

`permission_blocked` now reads the CLI's structural `permission_denials` array
rather than grepping stderr for "permission". An unwritable arm voids the pair;
the old heuristic was a guess, and prior runs were void for exactly this reason.

### Verified after the fixes (second smoke)

```
valid true · exit 0 · 6.8s · icarus_tool_calls 0 · technical_check_exit 0
diff_is_empty false · final_response_is_empty false · tree_end_porcelain "?? SMOKE.txt"
cli_summary: subtype success, is_error false, num_turns 2, total_cost_usd 0.105754,
             permission_denials [], stop_reason end_turn
final_response.txt: "Created `SMOKE.txt` containing `ok`."
patch.diff: a real new-file diff
```

Flags confirmed working against CLI `2.1.238`: `-p`, `--output-format json`,
`--verbose`, `--strict-mcp-config --mcp-config <empty>` (Icarus absent, 0 tool
calls), `--permission-mode acceptEdits` (agent wrote successfully, zero denials),
`--model`.

### Cost anchor for the batch

The smoke reports `total_cost_usd` per session, so the 46-arm cost is now
measurable rather than guessed — but a trivial task on a 1-file repo is a floor,
not an estimate. The pilot's tasks are real bug-fixes on uv / cli/cli / rich /
requests, which the 2026-08-27 solo arm measured at ~20 API calls and ~1.2M
cache-read tokens per session against this smoke's 2 turns.

Suites after the fixes: `evals` **1053 passed** (+5), `demo` 668 passed, all six
harness selftests ok. Smoke artifacts deleted.
