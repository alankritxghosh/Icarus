# History-failure pilot — frozen technical-check environment

The 30 pinned technical checks in
`2026-08-27-history-failure-pilot-candidates.jsonl` are mechanical acceptance
checks. For "deterministic" to mean anything they must run in one fixed
environment. This file freezes it.

Established 2026-08-28 (Claude, authorized by Alankrit). Every check was run in
this environment and behaves as registered — see the table at the bottom and
`scripts/history_pilot_checks.py`.

## The environment

| Component | Value |
|---|---|
| Python | 3.12 (CPython). 3.13/3.14 not used — some pinned repos predate them. |
| Working directory | the repo cloned and `git checkout --detach`ed to the task's exact `commit` |
| `PYTHONPATH` | exactly what the check string sets (`.`, `src`, or `.:src`); nothing added by the runner |
| Network | not required by any check; run offline |
| Third-party packages | the pinned set below, installed into one venv shared by all checks |

### Pinned third-party packages

Verified sufficient for all 30 checks. Versions are the ones tested on
2026-08-28; pin them exactly when the manifest is frozen.

```
Pygments==2.21.0
typing_extensions==4.16.0
markdown-it-py==4.2.0
mdurl==0.1.2
urllib3==2.7.0
charset-normalizer==3.5.1
certifi==2026.7.22
idna==3.19
chardet==7.6.0
pydantic==2.13.4
pydantic_core==2.46.4
aiosqlite==0.22.1
mcp==2.1.1
anthropic==1.2.0
python-dotenv==1.2.3
httpx==0.28.1
websockets==17.1
aiohttp==3.14.3
nest-asyncio==1.6.0
requests==2.34.2
```

Rationale for the non-obvious ones:

- `rich` checks import the **checked-out** `rich` (via `PYTHONPATH=.`), which
  needs `pygments` + `typing_extensions` + `markdown-it-py`/`mdurl`.
- `psf/requests` is **`src/`-layout** at the pinned commits, so its checks run
  with `PYTHONPATH=src` and need `urllib3`/`charset-normalizer`/`certifi`/`idna`
  (and `chardet` for the 2018 `R20` pin).
- `firecrawl/firecrawl` `N06` imports the python-sdk (`httpx`, `websockets`,
  `aiohttp`, `nest-asyncio`, `requests`, `pydantic`).
- `SaravananJaichandar/world-model-mcp` `S06` needs `mcp`, `pydantic`,
  `aiosqlite`, `anthropic`, `python-dotenv`, run with `PYTHONPATH=.:src`.

## Two registered check kinds

The pilot has **two** kinds of mechanical check. Scoring `technical_success`
and `history_safe_technical_success` must use the right rule per task.

### reproduction (27 tasks)

The landmine / missing fix is present at the pinned commit, so the check
**fails** (non-zero exit) at the pin and would **pass** once a correct fix
lands. It may fail by `AssertionError` **or**, when the post-fix API is simply
absent, by `TypeError` / `ImportError` / `AttributeError`.

**Scoring rule: non-zero exit at the pin is the reproduction, regardless of
exception type.** 7 of the 27 reproduce by exception, not assertion — a
reviewer or scorer scanning for "a failed assertion" would misread these:

| Task | Absent post-fix API at the pin |
|---|---|
| C07 | `Traceback.from_exception(..., locals_suppress=)` |
| R13 | `Console(soft_wrap=)` |
| R15 | `RichHandler(show_thread=)` |
| R17 | `rich.tqdm` module |
| R18 | `Spinner(custom_spinner=)` |
| R19 | `rich.progress.IndeterminateTaskProgressColumn` |
| R20 | `Response.read()` |

### guardrail (3 tasks: C01, C05, R05)

A recorded constraint is currently respected, so the check **passes** (exit 0)
at the pin. It flips to failing only if an agent **violates** the constraint
(adds the 419 alias / adds the missing-timeout `warnings.warn` / makes
`raise_for_status` chainable). These are not reproductions; do not expect a red
at the pin. Each row's `technical_validation` already states this.

The Work Queue line "All 30 survivors now have a deterministic red check" is
imprecise: 27 are deterministic reds, 3 are deterministic green guardrails.

## Amended checks (2026-08-28, logged in each row's `check_amended`)

- **N03, N08**: prepended `PYTHONPATH=src` — the pins are `src/`-layout, so the
  original `python3 -c "from requests import …"` raised `ModuleNotFoundError`
  before its assertion.
- **R20**: `PYTHONPATH=.` → `PYTHONPATH=src`, same reason.

No landmine, prompt, gold field, stratum, or assertion was changed. Each amended
check was re-run in this environment and confirmed red at the pin.

## Runner

```
python3 scripts/history_pilot_checks.py \
    --python /path/to/py312-venv/bin/python \
    --work-dir ~/history-pilot-checkouts
```

Clones each pending task's repo (blob-filtered), checks out the exact pin,
verifies HEAD, runs the check, classifies the result, and exits non-zero if any
task does not behave as registered. `--selftest` runs offline.

## Last verified — 2026-08-28

30 / 30 as registered: 20 `RED-ASSERT`, 7 `RED-EXCEPTION`, 3 `GREEN` guardrail.
0 anomalies. `cli/cli` checks (R03, R04, S05, C08, C09) run fine here — the
`cli/cli` blocker is corpus ingest only (GitHub GraphQL cost wall on
`gh pr list` for a ~14k-PR repo), not the checks.

### cli/cli corpus — fix landed 2026-08-28 (paginated-GraphQL fallback)

`gh pr list --json` / `gh issue list --json` fail for cli/cli (~14k PRs) at ANY
`--limit` — measured down to `--limit 90` for just `number` — because the query
`gh` builds is too costly for GitHub's GraphQL endpoint on a repo that large.
Not flakiness (a transient-retry does not fix it); an explicit `gh api graphql`
paginated at `first: 50` pages through cleanly (verified live).

`evals/ingest.py` now does exactly that as a **fallback**: the bulk
`gh * list --json` call is tried first and is byte-unchanged for every repo it
already handles; only on failure does `_bulk_list_or_paginate` fall back to
`_paginate_graphql`, whose nodes are flattened to the same shape
`_pr_or_issue_text` consumes. The *discussion* depth pass still degrades as
designed (coverage is the bar; older threads fetch on demand when named).

Covered by `evals/test_ingest_graphql_fallback.py` (8 tests) and
`evals/test_ingest_retry.py` (5 tests). Full `evals` suite green (1048).

The 5 cli/cli corpora (R03, R04, S05, C08, C09) were built through this path on
2026-08-28 — **corpora now 28 / 28** — and every gold pull request is present in
its corpus (pr:7960, pr:8584, pr:12021, pr:12053, pr:13684, pr:13807), with each
`meta.json` commit equal to the task pin.

**Corpus-completeness limitation to register with the manifest.** Two of the six
repositories carry partial issue coverage:

| Repository | PRs | issues | `truncated` |
|---|---:|---:|---|
| cli/cli (5 tasks) | 4,551 (complete) | 5,000 (cap hit) | true |
| astral-sh/uv (4 tasks) | 5,000 (cap hit) | 5,000 (cap hit) | true |
| Textualize/rich, psf/requests, firecrawl/firecrawl, world-model-mcp | complete | complete | false |

uv's truncation predates today's changes; the fallback did not introduce it. All
ten cli/cli gold refs are pull requests and all are present, so no task's
decisive evidence is missing — but a treatment context drawn from a truncated
corpus is weaker than one drawn from a complete corpus, and that asymmetry
belongs in the preregistration's limitations rather than being discovered later.

Cosmetic: `C01`'s check string triggers a `SyntaxWarning: invalid escape
sequence '\o'` on 3.12 (still exits 0). Harmless; worth tidying when the
manifest is frozen.
