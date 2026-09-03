# Claude Code handoff — history-failure pilot execution harness

Paste the section below into a fresh Claude Code session rooted at this
repository. This is a parallel implementation brick, not authorization to run
the experiment.

## Paste-ready task

You are sharing this dirty repository with another active builder. Read
`AGENTS.md`, `CLAUDE.md`, `docs/WORKFLOWS.md`, `docs/experiments/PROTOCOL.md`,
and `docs/experiments/2026-08-27-history-failure-reduction-pilot.md` before
acting. Read the Icarus vault entry path required by `AGENTS.md`; never read
`../brain/`. Preserve all unrelated and user-owned changes.

### Outcome

Build and test the **session-execution harness only** for the preregistered
paired history-failure pilot. It must be ready to consume a frozen manifest and
frozen treatment-context packet, but it must not launch a real agent session in
this task.

### Ownership boundary

You own only these new files:

- `scripts/history_pilot_sessions.py`
- `evals/test_history_pilot_sessions.py`
- `docs/experiments/2026-08-28-history-pilot-claude-execution-notes.md`

Do not edit the candidate ledger, preregistration, scorer, probe harness,
`general_index.md`, `detailed_index.md`, vault notes, or any existing experiment
record. The other builder owns those and will integrate your index/vault notes
after reviewing your handback. Do not commit, push, or delete anything.

### Current shared state — verify, do not assume

- Candidate ledger:
  `docs/experiments/2026-08-27-history-failure-pilot-candidates.jsonl`
- Expected selected pool: 30 probe-ready tasks — 12 refused, 6 superseded,
  6 constraint, 6 null; 19 rejected candidates retained.
- Deterministic technical validation is complete. No agent arm has run.
- `scripts/history_pilot_probe.py` is building exact pinned corpora under
  `~/Library/Application Support/Icarus/experiments/2026-08-27-history-pilot/`.
- Live Icarus probes are blocked until a real `GEMINI_PAID_API_KEY` is supplied.
  Never copy or relabel `GEMINI_API_KEY` as the paid attestation.
- The frozen manifest, its SHA-256, and frozen treatment contexts do not exist
  yet. Therefore your harness must stop before any real launch.

### Required harness contract

Keep this stdlib-only and surgical. The runner must:

1. Require an immutable manifest path, registered SHA-256, treatment-context
   packet path/hash, and output directory outside the repository.
2. Validate all 30 unique task IDs, the registered 12/6/6/6 strata, full commit
   SHAs, paired control/treatment records, deterministic arm order already
   frozen in the manifest, and exact context coverage before launch.
3. Never receive reviewer-only fields (`gold_landmine`, `gold_refs`, or
   `failure_conditions`) in either arm's prompt or checkout.
4. Give both arms the verbatim task and identical agent/model/build, limits,
   network policy, clean pinned checkout, and writable permissions. The sole
   informational difference is a clearly delimited, read-only Icarus context
   appended to treatment.
5. Keep Icarus MCP tools absent from **both** sessions. This is directed
   efficacy: Icarus context was obtained before the treatment run. Allowing a
   live tool would add an unregistered difference and repository-switch risk.
6. Use one fresh isolated clone/session per arm. No shared worktree, stash,
   cache, transcript, prior-arm output, or environment state. Check the pinned
   commit and clean tree immediately before launch and record both results.
7. Configure headless write permission explicitly. Prior experiments produced
   empty diffs because `claude -p` could not display an approval prompt; an
   unwritable arm must be void, never scored as a failed solution.
8. Capture the authoritative transcript, final response, patch/diff, technical
   check output, exit status, elapsed time, agent CLI version/model, repository
   commit, prompt hash, context hash (treatment only), and starting/ending tree
   status. Hash every artifact.
9. Fail closed and void the pair on missing transcript, dirty start, commit
   mismatch, unavailable/writable-session failure, leaked gold field, context
   mismatch, or arm configuration drift. Preserve invalid artifacts and their
   reason; never overwrite them with a rerun.
10. Support `--dry-run` that constructs and validates plans without cloning or
    invoking an agent, plus `--selftest` if useful. A real-launch flag must be
    explicit; the default cannot spend agent quota.
11. Never score `history_failure`. The output feeds a later blinded two-human
    review packet. Do not use Claude or any LLM as either reviewer.

Prefer a small functional core that returns launch plans plus a thin subprocess
boundary. Inject or patch that boundary in tests; do not make network calls or
invoke `claude` in the test suite.

### Required tests

At minimum prove:

- valid 30-task manifest produces exactly 60 isolated arm plans;
- manifest and context SHA mismatches fail before launch;
- wrong strata, duplicate task IDs, incomplete pairs, missing treatment
  context, and any reviewer-only prompt field fail closed;
- control and treatment prompts differ only by the registered context block;
- deterministic arm order is consumed exactly, not silently recomputed;
- output paths cannot sit inside the repository or collide across arms/reruns;
- default/dry-run cannot invoke the subprocess boundary;
- a dirty start, commit mismatch, missing transcript, or unwritable session
  voids the entire pair and preserves the invalid-run metadata.

Use temporary fake repositories and fake transcripts only to test the harness
boundary; do not mock away validation logic.

### Verification and handback

Run the focused tests, `python -m py_compile` for the new script, proportionate
existing tests, and `git diff --check` scoped to your three owned files. In the
execution-notes file, report:

- exact files changed;
- exact commands and observed results;
- the proposed CLI with a dry-run example;
- unresolved risks or product decisions;
- any `general_index.md` / `detailed_index.md` entries the integrating builder
  must add;
- confirmation that zero real agent sessions ran and zero credentials were
  printed or persisted.

Stop and ask Alankrit if a choice would change the registered protocol. Do not
reinterpret a convenient partial run as usable evidence.

## Integration split

While Claude owns the execution harness above, Codex owns candidate selection,
pinned corpus construction, live Icarus probes, probe rejection/replacement,
manifest/context freezing, final index/vault reconciliation, blinded packet
assembly, statistical analysis, and the evidence report. Neither builder
should edit the other's owned files until handback.
