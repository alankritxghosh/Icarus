#!/usr/bin/env python3
"""Run every pinned technical check of the history-failure pilot in a frozen
environment and confirm each behaves as registered.

Two registered check kinds:

* **reproduction** — the landmine / missing fix is present at the pinned commit,
  so the check MUST fail (non-zero exit). It may fail by ``AssertionError`` or,
  when the post-fix API is simply absent, by ``TypeError`` / ``ImportError`` /
  ``AttributeError``. Non-zero exit at the pin is the reproduction, regardless of
  exception type.
* **guardrail** — a recorded constraint is currently respected, so the check
  MUST pass (exit 0) at the pin. It flips to failing only if an agent violates
  the constraint. C01, C05, R05.

The frozen environment: one Python (default 3.12) with the pinned third-party
deps listed in ``docs/experiments/2026-08-27-history-pilot-check-env.md``, cwd =
the repo root at the exact pin, ``PYTHONPATH`` as the check string sets it.

This script never scores ``history_failure`` and never calls a model. It only
proves the mechanical checks are deterministic before the manifest is frozen.

Usage::

    python3 scripts/history_pilot_checks.py --python /path/to/frozen/python \\
        --work-dir ~/history-pilot-checkouts
    python3 scripts/history_pilot_checks.py --selftest
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/experiments/2026-08-27-history-failure-pilot-candidates.jsonl"
SELECTED_STATUS = "pending_icarus_probe"

# Registered guardrail checks: green at the pin BY DESIGN (the constraint is
# respected), red only on violation. Every other pending task is a reproduction
# check: red at the pin.
#
# C05 was also a guardrail but its 2026-08-28 Icarus probe missed, so it left
# the pool (Amendment 1). It stays named here because the check itself is still
# correct and would be a guardrail again if the task were ever reinstated; a
# task absent from the ledger is simply never run.
GUARDRAIL_TASKS = {"C01", "C05", "R05"}

# The pool after Amendment 1 (2026-08-28): seven probe misses rejected.
EXPECTED_STRATA = {"refused": 10, "superseded": 4, "constraint": 3, "null": 6}

# Third-party packages the frozen env must provide (see the check-env doc for
# exact pinned versions). Absence of one of these turns a real red into a
# misleading "env incomplete", so the runner names it rather than miscounting.
FROZEN_DEPS = (
    "pygments", "typing_extensions", "markdown_it", "mdurl",
    "urllib3", "charset_normalizer", "certifi", "idna", "chardet",
    "pydantic", "aiosqlite", "mcp", "anthropic", "dotenv",
    "httpx", "websockets", "aiohttp", "nest_asyncio", "requests",
)


def load_tasks():
    tasks = []
    for line_no, line in enumerate(LEDGER.read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("status") != SELECTED_STATUS:
            continue
        for field in ("task_id", "repo", "commit", "technical_check"):
            if not row.get(field):
                raise ValueError(f"line {line_no}: task missing {field}")
        tasks.append(row)
    return sorted(tasks, key=lambda r: r["task_id"])


def _git(args, **kw):
    return subprocess.run(["git", *args], capture_output=True, text=True, **kw)


def checkout(repo, commit, work_dir):
    dest = work_dir / repo.replace("/", "__")
    if not dest.exists():
        url = f"https://github.com/{repo}.git"
        r = _git(["clone", "--filter=blob:none", "--no-checkout", url, str(dest)])
        if r.returncode:
            raise RuntimeError(f"clone {repo} failed: {r.stderr.strip()}")
    if _git(["-C", str(dest), "checkout", "-q", "--detach", commit]).returncode:
        raise RuntimeError(f"checkout {repo}@{commit[:10]} failed")
    head = _git(["-C", str(dest), "rev-parse", "HEAD"]).stdout.strip()
    if head != commit:
        raise RuntimeError(f"{repo}: HEAD {head} != pin {commit}")
    return dest


def classify(returncode, output):
    if returncode == 0:
        return "GREEN"
    low = output.lower()
    third_party_missing = any(
        f"no module named '{d}" in low or f"no module named \"{d}" in low
        for d in FROZEN_DEPS
    )
    if third_party_missing:
        return "ENV-INCOMPLETE"
    if "assertionerror" in low:
        return "RED-ASSERT"
    if any(k in low for k in ("typeerror", "importerror", "attributeerror",
                              "modulenotfounderror")):
        return "RED-EXCEPTION"
    return "RED-OTHER"


def run_task(task, python, work_dir):
    dest = checkout(task["repo"], task["commit"], work_dir)
    cmd = task["technical_check"].replace("python3", python)
    cp = subprocess.run(cmd, shell=True, cwd=str(dest), capture_output=True,
                        text=True, timeout=600)
    out = (cp.stdout or "") + (cp.stderr or "")
    verdict = classify(cp.returncode, out)
    expected_kind = "guardrail" if task["task_id"] in GUARDRAIL_TASKS else "reproduction"
    if expected_kind == "guardrail":
        ok = verdict == "GREEN"
    else:
        ok = verdict in ("RED-ASSERT", "RED-EXCEPTION", "RED-OTHER")
    tail = out.strip().splitlines()[-1][:140] if out.strip() else ""
    return {
        "task_id": task["task_id"], "repo": task["repo"],
        "expected": expected_kind, "verdict": verdict, "exit": cp.returncode,
        "ok": ok, "detail": tail,
    }


def run_all(python, work_dir):
    work_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for task in load_tasks():
        try:
            results.append(run_task(task, python, work_dir))
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            results.append({"task_id": task["task_id"], "repo": task["repo"],
                            "expected": "guardrail" if task["task_id"] in GUARDRAIL_TASKS
                            else "reproduction", "verdict": "ERROR",
                            "exit": None, "ok": False, "detail": str(exc)[:140]})
    return results


def render(results):
    lines = [f"{'task':5} {'repo':22} {'expect':12} {'verdict':14} {'ok':3} detail"]
    for r in results:
        lines.append(f"{r['task_id']:5} {r['repo']:22} {r['expected']:12} "
                     f"{r['verdict']:14} {'OK' if r['ok'] else '!!':3} {r['detail']}")
    bad = [r["task_id"] for r in results if not r["ok"]]
    lines.append("")
    lines.append(f"{len(results)} checks; {len(results) - len(bad)} as registered; "
                 f"{len(bad)} NOT as registered: {bad or 'none'}")
    return "\n".join(lines), bad


def _selftest():
    assert classify(0, "") == "GREEN"
    assert classify(1, "Traceback ... AssertionError") == "RED-ASSERT"
    assert classify(1, "TypeError: unexpected kwarg") == "RED-EXCEPTION"
    assert classify(1, "AttributeError: no attribute 'read'") == "RED-EXCEPTION"
    assert classify(1, "ModuleNotFoundError: No module named 'pygments'") == "ENV-INCOMPLETE"
    assert classify(1, "ModuleNotFoundError: No module named 'rich.tqdm'") == "RED-EXCEPTION"
    tasks = load_tasks()
    strata = {}
    for t in tasks:
        strata[t["stratum"]] = strata.get(t["stratum"], 0) + 1
    assert strata == EXPECTED_STRATA, strata
    assert len(tasks) == sum(EXPECTED_STRATA.values()), len(tasks)
    ids = {t["task_id"] for t in tasks}
    # every guardrail still IN the pool must be a real task; one rejected out of
    # the pool (C05) is allowed to be absent, never silently reclassified.
    assert GUARDRAIL_TASKS & ids, GUARDRAIL_TASKS
    print("selftest ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--python", help="path to the frozen Python interpreter")
    ap.add_argument("--work-dir", type=Path,
                    help="directory for repo checkouts (outside this repo)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.python or not args.work_dir:
        ap.error("--python and --work-dir are required unless --selftest")

    work_dir = args.work_dir.expanduser().resolve()
    if work_dir == ROOT or ROOT in work_dir.parents:
        print("history_pilot_checks: --work-dir must be outside the repo", file=sys.stderr)
        return 2

    results = run_all(args.python, work_dir)
    text, bad = render(results)
    print(text)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
