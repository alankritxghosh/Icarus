from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .contracts import ErrorCode, InspectionError, InspectionLimits
from .inspector import inspect_repository


DEFAULT_BENCHMARK = Path(__file__).resolve().parents[2] / "benchmarks" / "large_repos.json"
BENCHMARK_LIMITS = InspectionLimits(
    max_files=140,
    max_file_bytes=262_144,
    max_total_bytes=12_582_912,
    max_tracked_paths=300_000,
    max_evidence_items=140,
    git_timeout_seconds=30,
)


def _default_protected_root() -> Path:
    value = os.environ.get("JARVIS_PROTECTED_ROOT")
    if not value:
        raise InspectionError(
            ErrorCode.PROTECTED_ROOT_ACCESS,
            "JARVIS_PROTECTED_ROOT must be set; benchmark inspection is fail-closed when the protected root is unconfigured.",
        )
    return Path(value).expanduser().resolve()


def _load_benchmark(benchmark: dict[str, Any] | Path | str) -> dict[str, Any]:
    if isinstance(benchmark, dict):
        return benchmark
    path = Path(benchmark).expanduser()
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise InspectionError(
            ErrorCode.INVALID_ARGUMENTS,
            "Benchmark file does not exist.",
            details={"benchmark": str(path)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise InspectionError(
            ErrorCode.INVALID_ARGUMENTS,
            "Benchmark file is not valid JSON.",
            details={"benchmark": str(path), "reason": str(exc)},
        ) from exc
    if not isinstance(data, dict):
        raise InspectionError(
            ErrorCode.INVALID_ARGUMENTS,
            "Benchmark file must contain a JSON object.",
            details={"benchmark": str(path)},
        )
    return data


def _question_ids(repo: dict[str, Any]) -> list[str]:
    return [str(question.get("id", "<missing-id>")) for question in repo.get("questions", [])]


def _resolve_checkout(repo: dict[str, Any], repositories_root: str) -> Path:
    checkout = Path(str(repo.get("checkout", ""))).expanduser()
    if checkout.is_absolute():
        return checkout
    return Path(repositories_root).expanduser() / checkout


def _is_unknown_rationale(finding: dict[str, Any]) -> bool:
    statement = str(finding.get("statement", "")).casefold()
    return "rationale requested" in statement or ("rationale" in statement and "unknown" in statement)


def _cited_paths(report: dict[str, Any]) -> list[str]:
    evidence = {item["id"]: item["path"] for item in report.get("evidence", [])}
    paths: list[str] = []
    seen: set[str] = set()
    for group in report.get("findings", {}).values():
        for finding in group:
            for citation in finding.get("citations", []):
                path = evidence.get(citation)
                if path and path not in seen:
                    paths.append(path)
                    seen.add(path)
    return paths


def _unknown_rationale_count(report: dict[str, Any]) -> int:
    return sum(
        1
        for finding in report.get("findings", {}).get("unknown", [])
        if _is_unknown_rationale(finding)
    )


_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def _all_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [finding for group in report.get("findings", {}).values() for finding in group]


def _rationale_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Findings that assert something about a rationale.

    Used to scope the ``max_confidence`` ceiling to decision/rationale claims so
    it does not trip on the inspector's always-present ``observed/high``
    infrastructure findings (HEAD resolution, evidence-collection counts).
    """
    return [
        finding
        for finding in _all_findings(report)
        if "rationale" in str(finding.get("statement", "")).casefold()
    ]


def _cited_excerpts(report: dict[str, Any]) -> str:
    """Casefolded text of every evidence excerpt that a finding actually cites."""
    excerpts = {item["id"]: str(item.get("excerpt", "")) for item in report.get("evidence", [])}
    cited_ids: list[str] = []
    seen: set[str] = set()
    for finding in _all_findings(report):
        for citation in finding.get("citations", []):
            if citation in excerpts and citation not in seen:
                cited_ids.append(citation)
                seen.add(citation)
    return " ".join(excerpts[cid] for cid in cited_ids).casefold()


def _unique_warnings(rows: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for warning in row.get("warnings", []):
            text = str(warning)
            if text not in seen:
                warnings.append(text)
                seen.add(text)
    return warnings


def _safety_warnings(warnings: list[str]) -> list[str]:
    safety_terms = ("protected root", "personal", "prohibited", "isolation")
    return [warning for warning in warnings if any(term in warning.casefold() for term in safety_terms)]


def _evaluate_success(report: dict[str, Any], question: dict[str, Any]) -> tuple[bool, str | None, list[str]]:
    expected = question.get("expected", {})
    cited_paths = _cited_paths(report)
    unknown_count = _unknown_rationale_count(report)

    if expected.get("must_report_unknown_rationale") and unknown_count == 0:
        return False, "expected unknown rationale finding, but none was reported", cited_paths

    if expected.get("must_not_be_unknown") and unknown_count > 0:
        return False, "expected documented rationale, but rationale was reported unknown", cited_paths

    likely = expected.get("likely_evidence") or []
    if likely and not any(path in cited_paths for path in likely):
        return False, f"none of the likely evidence paths were cited: {likely}", cited_paths

    classification = expected.get("classification")
    if classification:
        findings = report.get("findings", {}).get(classification, [])
        if not findings:
            return False, f"expected at least one {classification} finding", cited_paths

    confidence = expected.get("confidence")
    if confidence:
        candidates = (
            report.get("findings", {}).get(classification, [])
            if classification
            else _all_findings(report)
        )
        if not any(str(finding.get("confidence")) == confidence for finding in candidates):
            return False, f"expected a {confidence}-confidence finding, found none", cited_paths

    min_keyword_hits = expected.get("min_keyword_hits")
    if min_keyword_hits:
        keywords = expected.get("keywords") or []
        excerpts = _cited_excerpts(report)
        hits = sum(1 for keyword in keywords if str(keyword).casefold() in excerpts)
        if hits < min_keyword_hits:
            return (
                False,
                f"expected at least {min_keyword_hits} of keywords {keywords} in cited excerpts, found {hits}",
                cited_paths,
            )

    forbidden_evidence = expected.get("forbidden_evidence") or []
    if forbidden_evidence and cited_paths:
        corroborating = [path for path in cited_paths if path not in forbidden_evidence]
        if not corroborating:
            return (
                False,
                f"every citation came from forbidden evidence {forbidden_evidence}; needs corroborating evidence",
                cited_paths,
            )

    max_confidence = expected.get("max_confidence")
    if max_confidence:
        ceiling = _CONFIDENCE_ORDER.get(max_confidence, max(_CONFIDENCE_ORDER.values()))
        over = [
            str(finding.get("confidence"))
            for finding in _rationale_findings(report)
            if _CONFIDENCE_ORDER.get(str(finding.get("confidence")), 0) > ceiling
        ]
        if over:
            return (
                False,
                f"a rationale finding exceeded max_confidence={max_confidence}: {over}",
                cited_paths,
            )

    return True, None, cited_paths


def _question_result(
    repo: dict[str, Any],
    question: dict[str, Any],
    *,
    repositories_root: str,
    protected_root: Path,
    limits: InspectionLimits,
) -> dict[str, Any]:
    started = time.perf_counter()
    question_id = str(question.get("id", "<missing-id>"))
    expected = question.get("expected", {})
    expected_error = expected.get("error_code")
    base: dict[str, Any] = {
        "id": question_id,
        "question": question.get("question", ""),
        "type": question.get("type"),
        "passed": False,
        "skipped": False,
        "skip_reason": None,
        "failure_reason": None,
        "cited_paths": [],
        "warnings": [],
        "safety_warnings": [],
        "duration_seconds": 0.0,
    }
    try:
        report = inspect_repository(
            str(repo["github_url"]),
            str(repo["checkout"]),
            repositories_root,
            str(question["question"]),
            limits=limits,
            protected_root=protected_root,
        )
    except InspectionError as exc:
        if expected_error:
            passed = exc.code.value == expected_error
            base["passed"] = passed
            base["error_code"] = exc.code.value
            if not passed:
                base["failure_reason"] = f"expected {expected_error}, got {exc.code.value}"
            base["duration_seconds"] = round(time.perf_counter() - started, 6)
            return base
        base["error_code"] = exc.code.value
        base["failure_reason"] = exc.message
        base["duration_seconds"] = round(time.perf_counter() - started, 6)
        return base

    if expected_error:
        base["failure_reason"] = f"expected {expected_error}, but inspection succeeded"
        base["duration_seconds"] = round(time.perf_counter() - started, 6)
        return base

    passed, reason, cited_paths = _evaluate_success(report, question)
    base["passed"] = passed
    base["cited_paths"] = cited_paths
    base["warnings"] = list(report.get("warnings", []))
    base["safety_warnings"] = _safety_warnings(base["warnings"])
    base["unknown_rationale_count"] = _unknown_rationale_count(report)
    if reason:
        base["failure_reason"] = reason
    base["duration_seconds"] = round(time.perf_counter() - started, 6)
    return base


def _skipped_repo(repo: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "slug": repo.get("slug"),
        "skipped": True,
        "skip_reason": reason,
        "duration_seconds": 0.0,
        "warnings": [],
        "safety_warnings": [],
        "questions": [
            {
                "id": question_id,
                "passed": False,
                "skipped": True,
                "skip_reason": reason,
                "failure_reason": None,
                "cited_paths": [],
                "warnings": [],
                "safety_warnings": [],
                "duration_seconds": 0.0,
            }
            for question_id in _question_ids(repo)
        ],
    }


def _summary(repos: list[dict[str, Any]], duration_seconds: float) -> dict[str, Any]:
    questions = [question for repo in repos for question in repo.get("questions", [])]
    skipped = sum(1 for question in questions if question.get("skipped"))
    passed = sum(1 for question in questions if question.get("passed") and not question.get("skipped"))
    failed = len(questions) - passed - skipped
    return {
        "total": len(questions),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "warnings": _unique_warnings(repos),
        "safety_warnings": _unique_warnings([{"warnings": repo.get("safety_warnings", [])} for repo in repos]),
        "duration_seconds": round(duration_seconds, 6),
    }


def _filter_benchmark(
    data: dict[str, Any],
    *,
    repo_filter: str | None,
    question_filter: str | None,
) -> dict[str, Any]:
    repos = list(data.get("repos", []))
    if repo_filter:
        repos = [repo for repo in repos if repo.get("slug") == repo_filter]
        if not repos:
            raise InspectionError(
                ErrorCode.INVALID_ARGUMENTS,
                "Unknown benchmark repo filter.",
                details={"repo": repo_filter},
            )
    if question_filter:
        filtered_repos: list[dict[str, Any]] = []
        for repo in repos:
            questions = [
                question
                for question in repo.get("questions", [])
                if question.get("id") == question_filter
            ]
            if questions:
                copy = dict(repo)
                copy["questions"] = questions
                filtered_repos.append(copy)
        if not filtered_repos:
            raise InspectionError(
                ErrorCode.INVALID_ARGUMENTS,
                "Unknown benchmark question filter.",
                details={"question": question_filter, "repo": repo_filter},
            )
        repos = filtered_repos
    copy = dict(data)
    copy["repos"] = repos
    return copy


def run_benchmark(
    benchmark: dict[str, Any] | Path | str,
    *,
    protected_root: Path | None = None,
    repos_root_override: str | None = None,
    limits: InspectionLimits | None = None,
    repo_filter: str | None = None,
    question_filter: str | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    data = _load_benchmark(benchmark)
    data = _filter_benchmark(data, repo_filter=repo_filter, question_filter=question_filter)
    repositories_root = repos_root_override or str(data.get("repositories_root", ""))
    protected = protected_root or _default_protected_root()
    active_limits = limits or BENCHMARK_LIMITS
    active_limits.validate()

    repo_results: list[dict[str, Any]] = []
    for repo in data.get("repos", []):
        repo_started = time.perf_counter()
        checkout_path = _resolve_checkout(repo, repositories_root)
        if not checkout_path.exists():
            repo_results.append(_skipped_repo(repo, f"checkout not found: {checkout_path}"))
            continue
        if not checkout_path.is_dir():
            repo_results.append(_skipped_repo(repo, f"checkout is not a directory: {checkout_path}"))
            continue

        question_results = [
            _question_result(
                repo,
                question,
                repositories_root=repositories_root,
                protected_root=protected,
                limits=active_limits,
            )
            for question in repo.get("questions", [])
        ]
        repo_results.append(
            {
                "slug": repo.get("slug"),
                "skipped": False,
                "skip_reason": None,
                "duration_seconds": round(time.perf_counter() - repo_started, 6),
                "warnings": _unique_warnings(question_results),
                "safety_warnings": _unique_warnings(
                    [{"warnings": question.get("safety_warnings", [])} for question in question_results]
                ),
                "questions": question_results,
            }
        )

    duration = time.perf_counter() - started
    return {
        "summary": _summary(repo_results, duration),
        "warnings": _unique_warnings(repo_results),
        "safety_warnings": _unique_warnings([{"warnings": repo.get("safety_warnings", [])} for repo in repo_results]),
        "repos": repo_results,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run JARVIS Engineering benchmark questions.",
        allow_abbrev=False,
    )
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK), help="Benchmark JSON file.")
    parser.add_argument("--repositories-root", help="Override benchmark repositories_root.")
    parser.add_argument("--repo", help="Run only one repository slug from the benchmark.")
    parser.add_argument("--question", help="Run only one benchmark question ID.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="json",
        help="Output format. Defaults to JSON.",
    )
    parser.add_argument("--max-files", type=int, default=BENCHMARK_LIMITS.max_files)
    parser.add_argument("--max-file-bytes", type=int, default=BENCHMARK_LIMITS.max_file_bytes)
    parser.add_argument("--max-total-bytes", type=int, default=BENCHMARK_LIMITS.max_total_bytes)
    parser.add_argument("--max-tracked-paths", type=int, default=BENCHMARK_LIMITS.max_tracked_paths)
    parser.add_argument("--max-evidence-items", type=int, default=BENCHMARK_LIMITS.max_evidence_items)
    parser.add_argument("--git-timeout-seconds", type=int, default=BENCHMARK_LIMITS.git_timeout_seconds)
    return parser


def render_text_result(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    lines = [
        "JARVIS Big Repo Benchmark",
        "",
        f"Total: {summary.get('total', 0)}",
        f"Passed: {summary.get('passed', 0)}",
        f"Failed: {summary.get('failed', 0)}",
        f"Skipped: {summary.get('skipped', 0)}",
        f"Runtime: {summary.get('duration_seconds', 0):.2f}s",
        "",
    ]
    warnings = result.get("safety_warnings", []) or summary.get("safety_warnings", [])
    if warnings:
        lines.append("Safety warnings:")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    failed_questions: list[tuple[str, dict[str, Any]]] = []
    for repo in result.get("repos", []):
        questions = repo.get("questions", [])
        passed = sum(1 for question in questions if question.get("passed"))
        failed = sum(1 for question in questions if not question.get("passed") and not question.get("skipped"))
        skipped = sum(1 for question in questions if question.get("skipped"))
        lines.append(
            f"{repo.get('slug')}: {passed}/{len(questions)} passed"
            f" ({failed} failed, {skipped} skipped, {repo.get('duration_seconds', 0):.2f}s)"
        )
        for question in questions:
            status = "SKIP" if question.get("skipped") else "PASS" if question.get("passed") else "FAIL"
            lines.append(f"  {status} {question.get('id')} ({question.get('duration_seconds', 0):.2f}s)")
            if not question.get("passed") and not question.get("skipped"):
                failed_questions.append((str(repo.get("slug")), question))
    if failed_questions:
        lines.extend(["", "Failed:"])
        for slug, question in failed_questions:
            lines.append(f"- {slug} / {question.get('id')}")
            reason = question.get("failure_reason") or "No failure reason recorded."
            lines.append(f"  Reason: {reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    limits = InspectionLimits(
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
        max_tracked_paths=args.max_tracked_paths,
        max_evidence_items=args.max_evidence_items,
        git_timeout_seconds=args.git_timeout_seconds,
    )
    try:
        result = run_benchmark(
            args.benchmark,
            repos_root_override=args.repositories_root,
            limits=limits,
            repo_filter=args.repo,
            question_filter=args.question,
        )
    except InspectionError as exc:
        json.dump(exc.to_dict(), sys.stdout, sort_keys=True, indent=2)
        sys.stdout.write("\n")
        return 2
    if args.format == "text":
        sys.stdout.write(render_text_result(result))
        sys.stdout.write("\n")
    else:
        json.dump(result, sys.stdout, sort_keys=True, indent=2)
        sys.stdout.write("\n")
    return 1 if result.get("summary", {}).get("failed", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
