from __future__ import annotations

from textwrap import shorten
from typing import Any


def _evidence_by_id(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in report.get("evidence", [])}


def _first_matching_finding(report: dict[str, Any], group: str, needle: str) -> dict[str, Any] | None:
    for finding in report.get("findings", {}).get(group, []):
        if needle in finding.get("statement", "").casefold():
            return finding
    return None


def _cited_evidence(report: dict[str, Any], finding: dict[str, Any] | None, limit: int = 3) -> list[dict[str, Any]]:
    if not finding:
        return []
    evidence = _evidence_by_id(report)
    return [
        evidence[citation]
        for citation in finding.get("citations", [])[:limit]
        if citation in evidence
    ]


def _fallback_relevant_evidence(report: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    relevant = _first_matching_finding(report, "observed", "directly matches terms")
    return _cited_evidence(report, relevant, limit=limit)


def _answer_line(report: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    rationale = _first_matching_finding(report, "observed", "relevant repository text explicitly records both")
    rationale_evidence = _cited_evidence(report, rationale)
    if rationale and any(item.get("source_type") == "decision_record" for item in rationale_evidence):
        return (
            "JARVIS found documented repository evidence that directly records a decision and nearby rationale.",
            rationale,
        )

    unknown_rationale = _first_matching_finding(report, "unknown", "rationale requested")
    if unknown_rationale:
        return (
            f"JARVIS cannot prove the requested rationale from the inspected evidence. {unknown_rationale['statement']}",
            unknown_rationale,
        )

    relevant = _first_matching_finding(report, "observed", "directly matches terms")
    if relevant:
        relevant_evidence = _cited_evidence(report, relevant)
        if any(item.get("source_type") == "decision_record" for item in relevant_evidence):
            return (
                "JARVIS found a relevant decision record, but it did not extract a single explicit rationale sentence with high confidence. Use the cited ADR as the strongest evidence.",
                relevant,
            )
        return (
            "JARVIS found repository evidence related to the question, but it is not enough to claim a documented rationale.",
            relevant,
        )

    return (
        "JARVIS did not find enough relevant repository evidence to answer this confidently.",
        None,
    )


def render_text_report(report: dict[str, Any]) -> str:
    """Render the JSON report as a short, cited human answer."""
    repository = report.get("repository", {})
    slug = repository.get("slug", "unknown repository")
    head = str(repository.get("head_sha", ""))[:12] or "unknown commit"
    question = repository.get("question", "")

    answer, primary_finding = _answer_line(report)
    evidence_items = _cited_evidence(report, primary_finding)
    if not evidence_items:
        evidence_items = _fallback_relevant_evidence(report)

    lines = [
        f"Repository: {slug} @ {head}",
    ]
    if question:
        lines.append(f"Question: {question}")
    lines.extend(["", f"Answer: {answer}"])

    if evidence_items:
        lines.append("")
        lines.append("Evidence:")
        for index, item in enumerate(evidence_items, start=1):
            path = item.get("path", "unknown path")
            locator = item.get("locator", "")
            excerpt = shorten(" ".join(item.get("excerpt", "").split()), width=420, placeholder="...")
            source_type = item.get("source_type", "evidence")
            location = f"{path}:{locator}" if locator else path
            lines.append(f"{index}. {location} ({source_type})")
            if excerpt:
                lines.append(f"   {excerpt}")

    unknowns = report.get("findings", {}).get("unknown", [])
    if unknowns:
        lines.append("")
        lines.append("Limits:")
        for finding in unknowns[:3]:
            lines.append(f"- {finding.get('statement', '')}")

    warnings = report.get("warnings", [])
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        for warning in warnings[:3]:
            lines.append(f"- {warning}")

    lines.append("")
    lines.append("Use --format json for the full evidence packet.")
    return "\n".join(lines)
