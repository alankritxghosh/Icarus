#!/usr/bin/env python3
"""Freeze the history-failure pilot manifest and treatment-context packet.

Consumes the reviewer-only candidate ledger plus the probe records written by
`scripts/history_pilot_probe.py`, and emits the two immutable inputs
`scripts/history_pilot_sessions.py` consumes, plus their SHA-256s:

* **manifest.json** — 30 tasks with `task_id` / `repo` / `commit` / `stratum` /
  `prompt` / `technical_check` / `arm_order`, the registered strata, and the
  pinned agent config. Reviewer-only fields are NEVER copied in; the sessions
  harness rejects the manifest outright if one appears.
* **context-packet.json** — the verified directed Icarus answer per task, bound
  to the manifest's own hash so the pair cannot drift apart.
* **forbidden-strings.json** — the reviewer-only landmine texts, for the
  sessions harness's defence-in-depth prompt leak scan. Written OUTSIDE the
  manifest and never handed to an agent.

Arm order comes from `history_pilot_sessions.derive_arm_order`, imported rather
than reimplemented, so the freezer and the runner can never disagree about it.

A task may only be frozen if a human has approved its probe. Approval is an
explicit `--approved` list (or a file of task IDs); this script never decides
for itself that a probe was faithful, because "the gold ref was in the evidence"
is not the same claim as "the answer states the recorded decision correctly".

Usage::

    python3 scripts/history_pilot_freeze.py --probe-dir <dir> \\
        --approved-file approved.txt --out-dir <dir outside the repo>
    python3 scripts/history_pilot_freeze.py --selftest
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from history_pilot_sessions import (  # noqa: E402
    EXPECTED_STRATA, EXPERIMENT, derive_arm_order,
)

LEDGER = ROOT / "docs/experiments/2026-08-27-history-failure-pilot-candidates.jsonl"
SELECTED_STATUS = "pending_icarus_probe"

# Copied into the manifest. Everything else in a ledger row -- gold_landmine,
# gold_refs, failure_conditions, icarus_probe, icarus_probe_refs, bounded_search,
# technical_validation, check_amended, rejection_reason -- is reviewer-only and
# must never reach an agent.
MANIFEST_FIELDS = ("task_id", "repo", "commit", "stratum", "prompt",
                   "technical_check")

# Pinned agent configuration, identical for both arms of every pair.
AGENT = {
    "cli": "claude",
    "model": "claude-sonnet-5",
    "args": [],
    # bypassPermissions, NOT acceptEdits. acceptEdits auto-accepts file edits
    # only; the agent still needs Bash to explore, build and run the repo's
    # tests, and each of those raises a prompt a headless `claude -p` cannot
    # display -- the session then records a permission denial and the arm is
    # void. Measured twice: the 2026-08-27 solo arm lost all 13 sessions this
    # way ("missing bypassPermissions -- redoing") before reaching 17/17, and
    # the first live batch here voided C03/treatment identically on 2026-08-28.
    # An arm that cannot act is not evidence about history, so this must be
    # right before the batch, not after.
    "write_flags": ["--permission-mode", "bypassPermissions"],
    "timeout_seconds": 3600,
    "network": "default (no additional restriction); Icarus MCP absent in BOTH arms",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_ledger():
    rows = []
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("status") == SELECTED_STATUS:
                rows.append(row)
    return {row["task_id"]: row for row in rows}


def load_probes(probe_dir):
    probes = {}
    for path in sorted(Path(probe_dir).glob("*.json")):
        if path.name == "probe-summary.json":
            continue
        record = json.loads(path.read_text())
        probes[record["task_id"]] = record
    return probes


def answer_text(probe):
    """The Icarus answer that becomes the treatment context, verbatim."""
    result = probe.get("result") or {}
    text = (result.get("answer") or "").strip()
    citations = result.get("citations") or result.get("shown") or []
    if not text:
        return ""
    if citations:
        text += "\n\nCited evidence: " + ", ".join(str(c) for c in citations)
    return text


def build(probe_dir, approved, out_dir, expect_strata=None):
    expect_strata = expect_strata or EXPECTED_STRATA
    ledger = load_ledger()
    probes = load_probes(probe_dir)

    missing_probe = sorted(set(approved) - set(probes))
    if missing_probe:
        raise ValueError(f"approved tasks with no probe record: {missing_probe}")
    unknown = sorted(set(approved) - set(ledger))
    if unknown:
        raise ValueError(f"approved tasks not in the selected ledger: {unknown}")

    tasks, contexts = [], {}
    for task_id in sorted(approved):
        row = ledger[task_id]
        task = {field: row.get(field) for field in MANIFEST_FIELDS}
        task["arm_order"] = list(derive_arm_order(task_id))
        tasks.append(task)

        text = answer_text(probes[task_id])
        if not text:
            raise ValueError(f"{task_id}: probe produced no answer text to freeze")
        contexts[task_id] = {"repo": row["repo"], "commit": row["commit"],
                             "icarus_context": text}

    counts = {}
    for task in tasks:
        counts[task["stratum"]] = counts.get(task["stratum"], 0) + 1
    if counts != expect_strata:
        raise ValueError(
            f"frozen strata {counts} != expected {expect_strata}; "
            f"a replacement is owed before freezing"
        )
    if expect_strata != EXPECTED_STRATA:
        print(f"NOTE: freezing amended strata {counts}, not the originally "
              f"registered {EXPECTED_STRATA}. This must be recorded as a dated "
              f"amendment in the preregistration's Result section, with the "
              f"probe-miss reason, before any session runs.", file=sys.stderr)

    out_dir = Path(out_dir).expanduser().resolve()
    if out_dir == ROOT or ROOT in out_dir.parents:
        raise ValueError("freeze outputs must live outside the repository")
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"experiment": EXPERIMENT, "strata": dict(expect_strata),
                "agent": dict(AGENT), "tasks": tasks}
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    manifest_sha = sha256_file(manifest_path)

    packet = {"experiment": EXPERIMENT, "manifest_sha256": manifest_sha,
              "contexts": contexts}
    packet_path = out_dir / "context-packet.json"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    packet_sha = sha256_file(packet_path)

    forbidden = sorted({
        s for task_id in approved
        for s in ([ledger[task_id].get("gold_landmine")]
                  + list(ledger[task_id].get("failure_conditions") or []))
        if s
    })
    forbidden_path = out_dir / "forbidden-strings.json"
    forbidden_path.write_text(json.dumps(forbidden, indent=2) + "\n")

    return {"manifest": str(manifest_path), "manifest_sha256": manifest_sha,
            "context_packet": str(packet_path), "context_sha256": packet_sha,
            "forbidden_strings": str(forbidden_path), "tasks": len(tasks)}


def _selftest():
    # The pool after Amendment 1 (2026-08-28): seven probe misses rejected.
    amended = {"refused": 10, "superseded": 4, "constraint": 3, "null": 6}
    ledger = load_ledger()
    counts = {}
    for row in ledger.values():
        counts[row["stratum"]] = counts.get(row["stratum"], 0) + 1
    assert counts == amended, counts
    assert len(ledger) == sum(amended.values()), len(ledger)
    # arm order is the runner's own definition, not a copy
    from history_pilot_sessions import derive_arm_order as d
    assert d("R02") == derive_arm_order("R02")
    assert set(derive_arm_order("R02")) == {"control", "treatment"}
    # reviewer-only fields are not in the copied field list
    for banned in ("gold_landmine", "gold_refs", "failure_conditions",
                   "icarus_probe", "icarus_probe_refs", "technical_validation",
                   "bounded_search", "check_amended"):
        assert banned not in MANIFEST_FIELDS, banned
    print("selftest ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--probe-dir")
    ap.add_argument("--approved", action="append", default=[],
                    help="task id a human approved; repeatable")
    ap.add_argument("--approved-file",
                    help="file of approved task ids, one per line")
    ap.add_argument("--out-dir")
    ap.add_argument("--expect-strata",
                    help='JSON stratum->count the frozen pool must match. '
                         'Omit for the originally registered 12/6/6/6. Supplying '
                         'a different shape is an AMENDMENT and must be recorded '
                         'in the preregistration Result section with its reason.')
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.probe_dir or not args.out_dir:
        ap.error("--probe-dir and --out-dir are required")

    approved = list(args.approved)
    if args.approved_file:
        approved += [l.strip() for l in Path(args.approved_file).read_text().splitlines()
                     if l.strip() and not l.startswith("#")]
    if not approved:
        ap.error("no approved task ids; a human must approve each probe")

    try:
        expect = json.loads(args.expect_strata) if args.expect_strata else None
        out = build(args.probe_dir, approved, args.out_dir, expect_strata=expect)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"history_pilot_freeze: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(out, indent=2))
    print("\nRegister these hashes in the preregistration before launching.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
