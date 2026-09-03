#!/usr/bin/env python3
"""Build the blinded two-reviewer scoring packet for the history-failure pilot.

Turns the session runner's per-arm artifacts into one packet per reviewer in
which **the arm label is unrecoverable** and **no gold field appears**. Two
reviewers score independently; `--unblind` maps their verdicts back to arms only
after both have submitted.

What each reviewer sees per item: an opaque item id, the repository and pinned
commit, the verbatim task prompt, the agent's final response, its patch, and the
technical-check output. What they never see: which arm produced it, whether an
Icarus context block was present, the gold landmine, the gold refs, or the
registered failure conditions for that task.

The registered failure conditions ARE what the rubric applies, so they are
issued in a separate per-item rubric file keyed by item id -- the reviewer reads
the conditions for the item in front of them without ever seeing which arm it
came from. This is deliberate: blinding is about the ARM, not about the rubric.

Presentation order is shuffled with an explicit `--seed` so the packet is
reproducible and the shuffle is auditable, and the two arms of one task never
sit adjacent.

This script does not score anything and calls no model.

Usage::

    python3 scripts/history_pilot_blind.py --runs-dir ~/history-pilot-runs \\
        --out-dir ~/history-pilot-review --seed 20260827
    python3 scripts/history_pilot_blind.py --unblind --out-dir ~/history-pilot-review \\
        --verdicts reviewer-a.json --verdicts reviewer-b.json
    python3 scripts/history_pilot_blind.py --selftest
"""

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/experiments/2026-08-27-history-failure-pilot-candidates.jsonl"

# Read from the ledger for the rubric file only, never into a reviewer's item.
RUBRIC_FIELDS = ("failure_conditions",)

# An arm's own artifacts. `plan.json` carries the arm label and the context
# hash, so it is deliberately NOT copied into a blinded item.
FINAL_RESPONSE = "final_response.txt"
PATCH = "patch.diff"
CHECK = "technical_check.txt"


def item_id(task_id, arm, salt):
    """Opaque, deterministic, and NOT reversible without the mapping file."""
    return hashlib.sha256(f"{salt}\0{task_id}\0{arm}".encode()).hexdigest()[:12]


# An agent very often restates or quotes its own prompt in its final response.
# For a TREATMENT arm that prompt carries the delimited Icarus context block, so
# an unredacted response hands the reviewer the arm label outright. Found by this
# script's own audit while testing with a prompt-echoing agent, before any real
# session ran. Strip the block wherever it is reproduced verbatim.
#
# Irreducible residual, disclosed rather than papered over: an agent that USED
# the history will paraphrase it ("PR #18604 was refused because ..."), and that
# is unstrippable -- it is also the very thing `history_awareness` scores. Arm
# blinding is therefore partial by construction, not by omission. What this
# removes is the MECHANICAL tell (the delimiters and the verbatim block); what
# remains is a semantic signal that no packet design can erase.
_CONTEXT_START = "----- BEGIN READ-ONLY ICARUS ENGINEERING-MEMORY CONTEXT -----"
_CONTEXT_END = "----- END READ-ONLY ICARUS ENGINEERING-MEMORY CONTEXT -----"


def strip_context_block(text):
    """Remove every verbatim reproduction of the treatment context block."""
    if not text:
        return text
    while True:
        start = text.find(_CONTEXT_START)
        if start == -1:
            break
        end = text.find(_CONTEXT_END, start)
        text = (text[:start] + text[end + len(_CONTEXT_END):]) if end != -1 \
            else text[:start]
    # a lone delimiter (truncated echo) is just as much of a tell
    return text.replace(_CONTEXT_START, "").replace(_CONTEXT_END, "")


def _read(path):
    try:
        return strip_context_block(path.read_text(errors="replace"))
    except OSError:
        return ""


def collect(runs_dir):
    """Every valid arm result the runner produced, newest attempt per arm."""
    runs_dir = Path(runs_dir)
    arms = []
    for task_dir in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        if (task_dir / "PAIR_VOID.json").is_file():
            continue
        for arm in ("control", "treatment"):
            arm_dir = task_dir / arm
            if not arm_dir.is_dir():
                continue
            attempts = sorted(arm_dir.glob("attempt-*"))
            if not attempts:
                continue
            latest = attempts[-1]
            result_path = latest / "result.json"
            if not result_path.is_file():
                continue          # voided attempt, never scored
            result = json.loads(result_path.read_text())
            if not result.get("valid"):
                continue
            arms.append({
                "task_id": result["task_id"], "arm": result["arm"],
                "repo": result["repo"], "commit": result["commit"],
                "stratum": result["stratum"], "dir": latest,
                "technical_check_exit": result.get("technical_check_exit"),
            })
    return arms


def load_rubric():
    rubric = {}
    for line in LEDGER.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            rubric[row["task_id"]] = {f: row.get(f) for f in RUBRIC_FIELDS}
    return rubric


def _deinterleave(items, rng):
    """Shuffle, then push apart any two items sharing a task so a reviewer never
    sees a pair back to back (which would make the arms guessable by diffing)."""
    order = items[:]
    rng.shuffle(order)
    for _ in range(200):
        clashes = [i for i in range(len(order) - 1)
                   if order[i]["_task"] == order[i + 1]["_task"]]
        if not clashes:
            break
        for i in clashes:
            j = rng.randrange(len(order))
            order[i], order[j] = order[j], order[i]
    return order


def build(runs_dir, out_dir, seed, prompts):
    arms = collect(runs_dir)
    if not arms:
        raise ValueError("no valid arm results found; run the sessions first")
    rubric = load_rubric()
    salt = f"blind:{seed}"

    items, mapping = [], {}
    for arm in arms:
        iid = item_id(arm["task_id"], arm["arm"], salt)
        mapping[iid] = {"task_id": arm["task_id"], "arm": arm["arm"],
                        "stratum": arm["stratum"], "repo": arm["repo"]}
        items.append({
            "item_id": iid,
            "repo": arm["repo"], "commit": arm["commit"],
            "task": prompts.get(arm["task_id"], ""),
            "final_response": _read(arm["dir"] / FINAL_RESPONSE),
            "patch": _read(arm["dir"] / PATCH),
            "technical_check_output": _read(arm["dir"] / CHECK),
            "technical_check_exit": arm["technical_check_exit"],
            "_task": arm["task_id"],
        })

    order = _deinterleave(items, random.Random(seed))
    rubric_by_item = {i["item_id"]: rubric.get(i["_task"], {}) for i in order}
    for i in order:
        i.pop("_task")

    out_dir = Path(out_dir).expanduser().resolve()
    if out_dir == ROOT or ROOT in out_dir.parents:
        raise ValueError("review packets must live outside the repository")
    out_dir.mkdir(parents=True, exist_ok=True)

    packet = {"experiment": "20260827-history-pilot", "seed": seed,
              "items": order}
    (out_dir / "blinded-items.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n")
    (out_dir / "blinded-rubric.json").write_text(
        json.dumps(rubric_by_item, indent=2, sort_keys=True) + "\n")
    (out_dir / "UNBLIND-KEY.json").write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n")

    template = {i["item_id"]: {"history_failure": None, "history_awareness": None,
                               "notes": ""} for i in order}
    for name in ("verdicts-reviewer-a.template.json",
                 "verdicts-reviewer-b.template.json"):
        (out_dir / name).write_text(json.dumps(template, indent=2, sort_keys=True) + "\n")

    leaked = _audit(packet, out_dir)
    return {"items": len(order), "out_dir": str(out_dir), "leaks": leaked}


def _audit(packet, out_dir):
    """Fail loudly if an arm label or a gold field reached a blinded item."""
    blob = json.dumps(packet)
    banned = ["gold_landmine", "gold_refs", "icarus_probe", "arm",
              "BEGIN READ-ONLY ICARUS", "icarus_context"]
    return sorted({b for b in banned if b in blob})


def unblind(out_dir, verdict_files):
    out_dir = Path(out_dir).expanduser().resolve()
    mapping = json.loads((out_dir / "UNBLIND-KEY.json").read_text())
    reviewers = [json.loads(Path(p).read_text()) for p in verdict_files]
    if len(reviewers) < 2:
        raise ValueError("two independent reviewers are required before unblinding")

    ids = set(mapping)
    for index, verdicts in enumerate(reviewers, 1):
        missing = sorted(ids - set(verdicts))
        if missing:
            raise ValueError(f"reviewer {index} did not score: {missing}")
        for iid, v in verdicts.items():
            if not isinstance(v.get("history_failure"), bool):
                raise ValueError(f"reviewer {index} item {iid}: "
                                 f"history_failure must be a boolean")

    agree = sum(1 for i in ids
                if reviewers[0][i]["history_failure"] == reviewers[1][i]["history_failure"])
    disagree = sorted(i for i in ids
                      if reviewers[0][i]["history_failure"] != reviewers[1][i]["history_failure"])
    return {"items": len(ids), "agreed": agree, "raw_agreement": agree / len(ids),
            "disagreements": [{**mapping[i], "item_id": i} for i in disagree],
            "kappa": _kappa(reviewers[0], reviewers[1], ids)}


def _kappa(a, b, ids):
    """Cohen's kappa on the binary history_failure judgement."""
    n = len(ids)
    both_t = sum(1 for i in ids if a[i]["history_failure"] and b[i]["history_failure"])
    both_f = sum(1 for i in ids if not a[i]["history_failure"] and not b[i]["history_failure"])
    po = (both_t + both_f) / n
    pa = sum(1 for i in ids if a[i]["history_failure"]) / n
    pb = sum(1 for i in ids if b[i]["history_failure"]) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return None if pe == 1 else (po - pe) / (1 - pe)


def _selftest():
    import tempfile
    # opaque ids are deterministic per salt and differ across arms
    assert item_id("R02", "control", "s") == item_id("R02", "control", "s")
    assert item_id("R02", "control", "s") != item_id("R02", "treatment", "s")
    assert item_id("R02", "control", "s") != item_id("R02", "control", "t")

    # kappa: perfect agreement is 1.0, chance-level is ~0
    ids = {"a", "b", "c", "d"}
    same = {i: {"history_failure": i in ("a", "b")} for i in ids}
    assert abs(_kappa(same, same, ids) - 1.0) < 1e-9

    # audit catches a leaked arm label / context block
    leak = {"items": [{"final_response": "----- BEGIN READ-ONLY ICARUS ..."}]}
    assert "BEGIN READ-ONLY ICARUS" in _audit(leak, None)

    # the strip removes a whole echoed block, a truncated one, and several
    echoed = (f"I did it.\n{_CONTEXT_START}\nsecret history\n{_CONTEXT_END}\ndone.")
    assert strip_context_block(echoed) == "I did it.\n\ndone."
    assert _CONTEXT_START not in strip_context_block(f"x{_CONTEXT_START}y")
    twice = f"{_CONTEXT_START}a{_CONTEXT_END}mid{_CONTEXT_START}b{_CONTEXT_END}"
    assert strip_context_block(twice) == "mid"
    assert strip_context_block("") == "" and strip_context_block(None) is None

    # unblind refuses a single reviewer
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "UNBLIND-KEY.json").write_text(json.dumps(
            {"aa": {"task_id": "R02", "arm": "control", "stratum": "refused",
                    "repo": "o/r"}}))
        (tmp / "v1.json").write_text(json.dumps({"aa": {"history_failure": True}}))
        try:
            unblind(tmp, [tmp / "v1.json"])
        except ValueError as exc:
            assert "two independent reviewers" in str(exc)
        else:
            raise AssertionError("single reviewer accepted")

        # and refuses a non-boolean verdict
        (tmp / "v2.json").write_text(json.dumps({"aa": {"history_failure": "yes"}}))
        try:
            unblind(tmp, [tmp / "v1.json", tmp / "v2.json"])
        except ValueError as exc:
            assert "must be a boolean" in str(exc)
        else:
            raise AssertionError("non-boolean verdict accepted")
    print("selftest ok")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir")
    ap.add_argument("--out-dir")
    ap.add_argument("--manifest", help="frozen manifest, for the verbatim task prompts")
    ap.add_argument("--seed", type=int, default=20260827)
    ap.add_argument("--unblind", action="store_true")
    ap.add_argument("--verdicts", action="append", default=[])
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    try:
        if args.unblind:
            if not args.out_dir:
                ap.error("--out-dir is required")
            print(json.dumps(unblind(args.out_dir, args.verdicts), indent=2))
            return 0
        if not args.runs_dir or not args.out_dir or not args.manifest:
            ap.error("--runs-dir, --out-dir and --manifest are required")
        manifest = json.loads(Path(args.manifest).read_text())
        prompts = {t["task_id"]: t["prompt"] for t in manifest["tasks"]}
        out = build(args.runs_dir, args.out_dir, args.seed, prompts)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"history_pilot_blind: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(out, indent=2))
    if out["leaks"]:
        print("\nREFUSE TO SHIP: blinded items contain "
              f"{out['leaks']}", file=sys.stderr)
        return 1
    print("\nSend blinded-items.json + blinded-rubric.json to EACH reviewer "
          "separately.\nKeep UNBLIND-KEY.json away from both until both have "
          "submitted verdicts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
