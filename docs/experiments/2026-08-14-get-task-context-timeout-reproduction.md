# `get_task_context`'s intermittent failure, reproduced and root-caused

Date: 2026-08-14

Closes consequence 3 of
[`2026-08-14-dogfood-meilisearch-swift-two-issues.md`](2026-08-14-dogfood-meilisearch-swift-two-issues.md),
which recorded `get_task_context` failing twice with `MCP error -32603:
Internal error` and working cleanly on the next issue, and asked for
reproduction rather than a note. It is not intermittent in the sense that
matters — it is a latency distribution straddling a flat timeout, and the
distribution is measurable.

## What the transcripts show

The dogfood session could not narrow this from the client side because no
error detail was returned. The detail is in the persisted transcripts
(`~/.claude/projects/-Users-alankritghosh-meilisearch-swift/*.jsonl`), read
the same way `scripts/agent_call_audit.py` reads tool use — self-report has
disagreed with the harness three times, so timings come from the record.

Every `mcp__icarus__*` call of that session, with elapsed wall time:

| time (UTC) | elapsed | tool | result |
|---|---|---|---|
| 15:24:41 | 3.2s | `explain_code_context` | ok |
| **15:40:34** | **61.1s** | **`get_task_context`** | **-32603** |
| **15:41:40** | **60.2s** | **`get_task_context`** | **-32603** |
| 15:42:50 | 2.6s | `get_change_context` | ok |
| 15:57:08 | 4.9s | `explain_code_context` | ok |
| 16:13:31 | 16.1s | `get_task_context` | ok |
| 16:25:00 | 6.8s | `explain_code_context` | ok |

Both failures land on 60s. Nothing else in the session comes close. That is a
timeout, not an internal error.

## Which adapter was actually running

`claude mcp get icarus` resolves the user-scoped server to
`.venv/bin/python -m demo.mcp_server` — the **Python** adapter in this
checkout, not the shipped `Icarus.app --mcp`. This matters twice: the
Swift server never emits `-32603` at all (every failure there becomes a tool
error), and the literal string `"Internal error"` appears in exactly one place
in the codebase, `demo/mcp_server.py`'s catch-all in `serve()`.

## Root cause

Two defects stacked, and the second is what hid the first.

1. **`_request` used a flat `timeout=60` for every route.** `/context` runs a
   bounded investigation — several writer calls — where `/ask` runs one. The
   same session's successful `get_task_context` took 16.1s, so 60s sat inside
   the normal spread rather than beyond it.

2. **A socket read timeout escaped `_request` entirely.** `urllib` wraps a
   *connect* timeout in `URLError`, but lets `getresponse()` raise a bare
   `TimeoutError` straight through — and `TimeoutError` matched none of
   `_request`'s except clauses. It escaped `handle_message`, hit `serve()`'s
   catch-all, and became a protocol-level `-32603` whose only detail was
   printed to **stderr**, which the client discards. That is precisely why the
   dogfood session reported "no error detail was returned" and could not
   narrow it further.

The shipped Swift adapter has the same latency problem from the other
direction: no explicit `timeoutInterval`, so URLSession's 60s default applies
to `/context` too, and a timeout there fell into the generic `catch` and read
as `"Icarus could not be reached"` — a different wrong diagnosis of the same
event, pointing the user at their network.

## Live reproduction

Same repo the failures happened on (the brain is still connected to
`meilisearch/meilisearch-swift` @ `fb3bae0`), the failing task string copied
verbatim from the transcript, three runs through the real adapter against the
live brain:

| run | elapsed |
|---|---|
| 1 | 52.1s |
| 2 | **62.0s** |
| 3 | 50.8s |

One of three exceeds 60s. Under the old ceiling run 2 is a `-32603` and the
other two are clean answers, from identical input — which is the whole of the
"same tool, same repo, different call, opposite reliability outcome, no
visible reason for the difference" the dogfood session observed.

## Fixed

- `demo/mcp_server.py`: `_timeout_for(path)` — `/context` and `/investigate`
  get 240s, `/status` 20s (it runs on every tool call), everything else keeps
  60s. 240s matches the Azure Container Apps ingress ceiling; waiting past it
  cannot succeed.
- `demo/mcp_server.py`: `TimeoutError` and any other unwrapped `OSError` are
  now `_ToolError`s naming the duration waited and the remedy, so a slow
  answer can never again present as a broken adapter.
- `mac/Icarus/Sources/Icarus/McpCommand.swift`: `timeout(forPath:)` mirroring
  the Python table, plus an explicit `URLError.timedOut` catch with the same
  message. Kept deliberately in step — the two adapters implement one contract.

Tests: `demo/test_mcp_server.py::RequestTimeoutTests` (both red first — the
escape test raised `TimeoutError` out of `handle_message`, which is the defect
itself), `McpCommandTests.testAnInvestigationGetsLongerThanASingleQuestion`.
634 Python demo tests, 902 evals tests, 261 Swift tests all pass.

## What this does NOT establish

- **The 240s ceiling is a guess bounded by infrastructure, not a measurement
  of the worst case.** Three samples on one task on one repo give a spread of
  50.8–62.0s; they say nothing about a large repo or a broad task. If a
  `/context` call is ever cut off at 240s, the answer is server-side latency,
  not another timeout bump — 240s is already the ACA ingress ceiling.
- **`/context` at ~55s median is itself the real cost**, and it is untouched
  here. The tool the description positions as the first call of any
  non-trivial task takes the better part of a minute. This fix stops that
  from being reported as a crash; it does not make it fast.
- Nothing here touches the two accuracy findings (citation-conflation,
  rejection-conflation) from the same dogfood session. Those are open.
