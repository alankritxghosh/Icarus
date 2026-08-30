#!/usr/bin/env python3
"""Score paired history-failure experiment results without external packages.

The experiment's public effect is a percentage reduction in recorded-history
failures, not a raw count. The denominator and paired structure remain visible:
the script reports both arm rates, absolute percentage-point reduction,
relative reduction, paired discordances, an exact McNemar p-value, and
repository-clustered bootstrap confidence intervals.

Input is a JSON object with a ``runs`` list. Each run must contain ``task_id``,
``repo``, ``stratum``, and ``control``/``treatment`` objects. An arm is usable
only when ``valid`` is true and ``history_failure`` is a JSON boolean. Null
stratum tasks are validated but excluded from the primary efficacy estimate.

Usage:
    python3 scripts/history_pilot_score.py results.json
    python3 scripts/history_pilot_score.py --selftest
"""

import argparse
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path


PRIMARY_STRATA = {"refused", "superseded", "constraint"}
ALL_STRATA = PRIMARY_STRATA | {"null"}
DEFAULT_SEED = 20260827
DEFAULT_ITERATIONS = 20_000


def load_pairs(path):
    """Load and strictly validate result pairs from *path*."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or not isinstance(data.get("runs"), list):
        raise ValueError("input must be an object containing a runs list")

    seen = set()
    pairs = []
    for index, row in enumerate(data["runs"], 1):
        if not isinstance(row, dict):
            raise ValueError(f"run {index}: must be an object")
        task_id = row.get("task_id")
        repo = row.get("repo")
        stratum = row.get("stratum")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"run {index}: task_id must be a non-empty string")
        if task_id in seen:
            raise ValueError(f"run {index}: duplicate task_id {task_id!r}")
        seen.add(task_id)
        if not isinstance(repo, str) or "/" not in repo:
            raise ValueError(f"run {index}: repo must be owner/name")
        if stratum not in ALL_STRATA:
            raise ValueError(f"run {index}: unknown stratum {stratum!r}")

        failures = {}
        for arm in ("control", "treatment"):
            value = row.get(arm)
            if not isinstance(value, dict):
                raise ValueError(f"run {index}: {arm} must be an object")
            if value.get("valid") is not True:
                raise ValueError(f"run {index}: {arm} is not a valid scored arm")
            failure = value.get("history_failure")
            if not isinstance(failure, bool):
                raise ValueError(
                    f"run {index}: {arm}.history_failure must be a boolean"
                )
            failures[arm] = failure
        pairs.append(
            {
                "task_id": task_id,
                "repo": repo,
                "stratum": stratum,
                **failures,
            }
        )
    return pairs


def effects(pairs):
    """Return paired primary effect statistics for history-bearing tasks."""
    primary = [row for row in pairs if row["stratum"] in PRIMARY_STRATA]
    if not primary:
        raise ValueError("no history-bearing task pairs")
    n = len(primary)
    control_failures = sum(row["control"] for row in primary)
    treatment_failures = sum(row["treatment"] for row in primary)
    benefited = sum(row["control"] and not row["treatment"] for row in primary)
    harmed = sum(not row["control"] and row["treatment"] for row in primary)
    control_rate = control_failures / n
    treatment_rate = treatment_failures / n
    absolute_reduction = control_rate - treatment_rate
    relative_reduction = (
        absolute_reduction / control_rate if control_rate else None
    )
    return {
        "n": n,
        "repos": len({row["repo"] for row in primary}),
        "control_failures": control_failures,
        "treatment_failures": treatment_failures,
        "control_rate": control_rate,
        "treatment_rate": treatment_rate,
        "absolute_reduction": absolute_reduction,
        "relative_reduction": relative_reduction,
        "benefited": benefited,
        "harmed": harmed,
        "mcnemar_p": exact_mcnemar(benefited, harmed),
    }


def exact_mcnemar(benefited, harmed):
    """Two-sided exact McNemar p-value from the discordant pair counts."""
    discordant = benefited + harmed
    if discordant == 0:
        return 1.0
    tail = sum(
        math.comb(discordant, k) for k in range(min(benefited, harmed) + 1)
    ) / (2 ** discordant)
    return min(1.0, 2 * tail)


def _percentile(sorted_values, probability):
    """Linearly interpolated percentile of an already-sorted sequence."""
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1 - fraction) + sorted_values[upper] * fraction


def clustered_bootstrap(pairs, iterations=DEFAULT_ITERATIONS, seed=DEFAULT_SEED):
    """Repository-clustered paired bootstrap CIs for absolute/relative effects."""
    primary = [row for row in pairs if row["stratum"] in PRIMARY_STRATA]
    by_repo = defaultdict(list)
    for row in primary:
        by_repo[row["repo"]].append(row)
    repos = sorted(by_repo)
    if len(repos) < 2:
        raise ValueError("clustered bootstrap requires at least two repositories")

    rng = random.Random(seed)
    absolute, relative = [], []
    for _ in range(iterations):
        sample = []
        for repo in rng.choices(repos, k=len(repos)):
            sample.extend(by_repo[repo])
        result = effects(sample)
        absolute.append(result["absolute_reduction"])
        if result["relative_reduction"] is not None:
            relative.append(result["relative_reduction"])

    absolute.sort()
    relative.sort()
    return {
        "absolute": (
            _percentile(absolute, 0.025),
            _percentile(absolute, 0.975),
        ),
        "relative": (
            _percentile(relative, 0.025),
            _percentile(relative, 0.975),
        ),
    }


def _pct(value):
    return "not estimable" if value is None else f"{100 * value:.1f}%"


def _pp(value):
    return "not estimable" if value is None else f"{100 * value:.1f} percentage points"


def render(pairs, iterations=DEFAULT_ITERATIONS, seed=DEFAULT_SEED):
    """Render the preregistered primary analysis as human-readable text."""
    result = effects(pairs)
    ci = clustered_bootstrap(pairs, iterations=iterations, seed=seed)
    null_pairs = [row for row in pairs if row["stratum"] == "null"]
    lines = [
        "History-failure reduction — paired primary analysis",
        f"eligible task pairs: {result['n']} across {result['repos']} repositories",
        f"control failure rate:   {_pct(result['control_rate'])}",
        f"treatment failure rate: {_pct(result['treatment_rate'])}",
        f"absolute reduction:     {_pp(result['absolute_reduction'])}",
        f"  clustered 95% CI:      {_pp(ci['absolute'][0])} to {_pp(ci['absolute'][1])}",
        f"relative reduction:     {_pct(result['relative_reduction'])}",
        f"  clustered 95% CI:      {_pct(ci['relative'][0])} to {_pct(ci['relative'][1])}",
        f"discordant pairs: treatment helped {result['benefited']}; harmed {result['harmed']}",
        f"exact McNemar p-value:  {result['mcnemar_p']:.4f}",
        f"null-history pairs:     {len(null_pairs)} (reported separately)",
    ]
    return "\n".join(lines)


def _selftest():
    """Prove validation, pairing, effect calculation, and exact test behavior."""
    rows = [
        {"task_id": "a", "repo": "o/r1", "stratum": "refused",
         "control": True, "treatment": False},
        {"task_id": "b", "repo": "o/r1", "stratum": "superseded",
         "control": True, "treatment": True},
        {"task_id": "c", "repo": "o/r2", "stratum": "constraint",
         "control": False, "treatment": False},
        {"task_id": "d", "repo": "o/r2", "stratum": "refused",
         "control": False, "treatment": False},
        {"task_id": "n", "repo": "o/r2", "stratum": "null",
         "control": False, "treatment": True},
    ]
    result = effects(rows)
    assert result["n"] == 4, result
    assert result["control_rate"] == 0.5, result
    assert result["treatment_rate"] == 0.25, result
    assert result["absolute_reduction"] == 0.25, result
    assert result["relative_reduction"] == 0.5, result
    assert result["benefited"] == 1 and result["harmed"] == 0, result
    assert exact_mcnemar(1, 0) == 1.0
    assert exact_mcnemar(6, 0) == 0.03125
    ci = clustered_bootstrap(rows, iterations=200, seed=1)
    assert ci["absolute"][0] <= 0.25 <= ci["absolute"][1], ci

    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "results.json"
        serializable = {
            "runs": [
                {
                    "task_id": row["task_id"],
                    "repo": row["repo"],
                    "stratum": row["stratum"],
                    "control": {"valid": True, "history_failure": row["control"]},
                    "treatment": {"valid": True, "history_failure": row["treatment"]},
                }
                for row in rows
            ]
        }
        path.write_text(json.dumps(serializable))
        assert len(load_pairs(path)) == 5
        serializable["runs"][0]["treatment"]["history_failure"] = "no"
        path.write_text(json.dumps(serializable))
        try:
            load_pairs(path)
        except ValueError as exc:
            assert "must be a boolean" in str(exc), exc
        else:
            raise AssertionError("invalid outcome was accepted")
    print("selftest ok")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="?", type=Path)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    if args.results is None:
        parser.error("results JSON path is required unless --selftest is used")
    try:
        pairs = load_pairs(args.results)
        print(render(pairs, iterations=args.iterations, seed=args.seed))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"history_pilot_score: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
