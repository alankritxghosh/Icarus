from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .contracts import ErrorCode, Finding, InspectionError, InspectionLimits, report_to_dict
from .evidence import collect_evidence
from .isolation import (
    normalize_remote_url,
    read_origin,
    resolve_head,
    resolve_target,
)


def _finding(
    sequence: int,
    classification: str,
    confidence: str,
    statement: str,
    citations: tuple[str, ...] = (),
) -> Finding:
    prefix = {"observed": "o", "inferred": "i", "unknown": "u"}[classification]
    return Finding(f"{prefix}{sequence:03d}", classification, confidence, statement, citations)


_QUESTION_TERMS = {
    "architecture", "component", "dependency", "decision", "design", "impact",
    "module", "rationale", "replace", "service", "tradeoff", "why",
}
_STOP_WORDS = {
    "a", "an", "and", "are", "does", "for", "how", "in", "is", "it", "of",
    "on", "the", "this", "to", "use", "uses", "what", "which", "with",
}
_RELEVANCE_TOPIC_STOP_WORDS = _STOP_WORDS | {
    "checkout", "choose", "chose", "component", "components", "decide",
    "decided", "decision", "did", "main", "selected", "service", "we", "why",
}
_FOCUS_STOP_WORDS = _RELEVANCE_TOPIC_STOP_WORDS | {
    "api", "chosen", "do", "does", "evolve", "evolved", "guidance", "guidelines", "http",
    "libraries", "library", "over", "prefer", "rationale", "time", "way",
    "was",
}
_CHANGE_STEMS = {"chang", "change", "delet", "drop", "dropp", "remov", "removal", "replac"}
# "use" is intentionally excluded: it is ubiquitous in decision questions ("why does X
# use Y?"). Reverse-dependency on "uses" is handled by the narrow front-of-question check
# in _asks_unsupported_reasoning instead.
_DEPENDENCY_STEMS = {"call", "consum", "depend", "dependent", "import", "reli", "rely"}
_IMPACT_STEMS = {"affect", "break", "fail", "happen", "impact", "stop", "updat"}
_IMPACT_NOUNS = {"consequence", "consequences", "effect", "effects", "radius"}
_CHANGE_CUES = {"after", "follow", "following", "if", "once", "removal", "when", "whenever"}
_GRAPH_SUBJECTS = {
    "code", "component", "components", "module", "modules", "service", "services",
    "test", "tests", "thing", "things",
}
# Explicit decision/rationale framing. A question that asks for a rationale is a
# documented-decision question, so the heuristic impact/dependency rules below must never
# refuse it. This is the "favor answering" bias: borderline mixed questions are answered
# (with cited evidence or an honest-unknown) rather than refused.
_DECISION_CUES = {
    "why", "rationale", "reason", "reasons", "chose", "choose", "chosen", "choosing",
    "decide", "decided", "decides", "deciding", "decision", "decisions",
    "motivation", "motivated", "motivating",
}
_REVERSE_INTERROGATIVES = {"show", "what", "which", "who"}


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _question_words(question: str) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9_.-]*", question.casefold())


def _word_stem(word: str) -> str:
    if word in {"relies", "relying"}:
        return "reli"
    if word in {"uses", "using", "used"}:
        return "use"
    if word in {"imports", "importing", "imported"}:
        return "import"
    if word.endswith("ies") and len(word) > 4:
        word = word[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) > len(suffix) + 2:
            return word[: -len(suffix)]
    return word


def _contains_stem_window(stems: list[str], left: set[str], right: set[str], *, window: int = 8) -> bool:
    for index, stem in enumerate(stems):
        if stem not in left:
            continue
        end = min(len(stems), index + window + 1)
        if any(candidate in right for candidate in stems[index + 1:end]):
            return True
    return False


def _asks_unsupported_reasoning(question: str) -> bool:
    lowered = question.casefold()
    words = _question_words(question)
    stems = [_word_stem(word) for word in words]
    word_set = set(words)
    stem_set = set(stems)

    # Unambiguous impact/dependency vocabulary — always refused, even with a "why" framing,
    # because this wording only ever asks for dependency graphs or change blast radius.
    if "dependency" in stem_set or "dependencies" in word_set:
        return True
    if "downstream" in word_set or "upstream" in word_set:
        return True
    if "ripple" in word_set and "effect" in word_set:
        return True
    if "blast" in word_set and "radius" in word_set:
        return True
    if "change impact" in lowered or "what will break" in lowered:
        return True

    # Favor answering: an explicit decision/rationale question is supported, so the
    # heuristic rules below never refuse it.
    if word_set & _DECISION_CUES:
        return False

    # Change-impact: a consequence verb tied to a change ("what is affected by removing X",
    # "what breaks when we delete Y"). Change framing is required — a lone subject noun or a
    # bare "by" is not enough.
    if stem_set & _IMPACT_STEMS and (stem_set & _CHANGE_STEMS or word_set & _CHANGE_CUES):
        return True

    # Consequence noun of a change ("what are the consequences of removing X").
    if word_set & _IMPACT_NOUNS and stem_set & _CHANGE_STEMS:
        return True

    # Change <-> consequence adjacency in either order.
    if _contains_stem_window(stems, _CHANGE_STEMS, _IMPACT_STEMS | _IMPACT_NOUNS):
        return True
    if _contains_stem_window(stems, _CHANGE_CUES, _CHANGE_STEMS):
        return True
    if _contains_stem_window(stems, _IMPACT_STEMS, _CHANGE_STEMS | _CHANGE_CUES):
        return True

    # Reverse-dependency tracing: "what/which/who calls|imports|depends on|relies on X".
    if words and words[0] in _REVERSE_INTERROGATIVES and stem_set & _DEPENDENCY_STEMS:
        return True

    # Narrow reverse-"uses": "what/which/who uses X". The use-stem must be governed by the
    # leading interrogative (near the front), so "why does X use Y" and "what is the
    # rationale for X using Y" stay supported.
    if words and words[0] in _REVERSE_INTERROGATIVES and "use" in stems[:4]:
        return True

    return False


def _question_tokens(question: str) -> set[str]:
    if any(value in question.casefold() for value in ("../", ".jsonl", "brain/")):
        raise InspectionError(
            ErrorCode.ISOLATION_VIOLATION_BLOCKED,
            "The question attempts to reference prohibited local or personal data.",
        )
    if _asks_unsupported_reasoning(question):
        raise InspectionError(
            ErrorCode.UNSUPPORTED_QUESTION,
            "Change-impact and dependency tracing questions are not supported in this v1 documented-decision retrieval milestone.",
        )
    tokens = {
        token
        for token in _question_words(question)
        if token not in _STOP_WORDS
    }
    if not question.strip() or not (tokens & _QUESTION_TERMS or len(tokens) >= 2):
        raise InspectionError(
            ErrorCode.UNSUPPORTED_QUESTION,
            "Ask an architecture, decision, dependency, evolution, or change-impact question.",
        )
    return tokens


def _relevant_evidence(
    question_tokens: set[str],
    evidence: list[Any],
    focus_terms: set[str] | None = None,
) -> list[Any]:
    scoring_tokens = focus_terms or (question_tokens - _RELEVANCE_TOPIC_STOP_WORDS)
    if not scoring_tokens:
        scoring_tokens = question_tokens
    scored: list[tuple[int, Any]] = []
    for item in evidence:
        path = item.path.casefold()
        excerpt = item.excerpt.casefold()
        overlap = sum(2 if token in path else 1 for token in scoring_tokens if token in path or token in excerpt)
        if overlap:
            scored.append((overlap, item))
    scored.sort(key=lambda row: (-row[0], row[1].path.casefold(), row[1].id))
    if not scored:
        return []
    strongest_overlap = scored[0][0]
    relevant = [item for overlap, item in scored if overlap >= max(1, strongest_overlap - 2)]
    rationale_records = [
        item
        for _, item in scored
        if item.source_type == "decision_record" and item.explicit_rationale_language
    ]
    seen = {item.id for item in relevant}
    relevant.extend(item for item in rationale_records if item.id not in seen)
    return relevant


def _focus_terms(question_tokens: set[str], owner: str, repository: str) -> set[str]:
    repo_terms = set(re.findall(r"[a-z0-9]+", f"{owner} {repository}".casefold()))
    terms = {
        token
        for token in question_tokens - _FOCUS_STOP_WORDS - repo_terms
        if len(token) >= 3 and "." not in token
    }
    expanded = set(terms)
    for token in terms:
        if token.endswith("ing") and len(token) > 5:
            expanded.add(token[:-3])
        if token.endswith("ies") and len(token) > 5:
            expanded.add(token[:-3] + "y")
        if token.endswith("s") and len(token) > 4:
            expanded.add(token[:-1])
    return expanded


def inspect_repository(
    github_url: str,
    checkout: str,
    repositories_root: str,
    question: str,
    *,
    limits: InspectionLimits | None = None,
    protected_root: Path | None = None,
) -> dict[str, Any]:
    question_tokens = _question_tokens(question)
    active_limits = limits or InspectionLimits()
    active_limits.validate()
    if protected_root is None:
        raise InspectionError(
            ErrorCode.PROTECTED_ROOT_ACCESS,
            "A protected root is required; repository inspection is fail-closed when personal-root protection is unconfigured.",
        )
    target = resolve_target(
        github_url,
        checkout,
        repositories_root,
        protected_root=protected_root,
    )
    head_sha = resolve_head(
        target.checkout_path,
        timeout_seconds=active_limits.git_timeout_seconds,
    )
    protected = protected_root.expanduser().resolve()
    origin = read_origin(
        target.checkout_path,
        timeout_seconds=active_limits.git_timeout_seconds,
    )
    warnings: list[str] = []
    if _path_is_within(protected, target.repositories_root):
        warnings.append(
            "The configured protected root is inside repositories_root; personal-workspace protection may be too narrow."
        )
    if origin is None:
        warnings.append("The checkout has no remote.origin.url; URL-to-checkout identity could not be verified.")
    else:
        normalized_origin = normalize_remote_url(origin)
        if normalized_origin is None:
            warnings.append("The checkout origin is not a canonical GitHub URL; URL-to-checkout identity could not be verified.")
        elif normalized_origin != target.github_url.casefold():
            raise InspectionError(
                ErrorCode.REMOTE_MISMATCH,
                "The checkout origin does not match the supplied GitHub URL.",
                details={"github_url": target.github_url, "origin": origin},
            )

    focus_terms = _focus_terms(question_tokens, target.owner, target.repository)
    collection = collect_evidence(
        target,
        head_sha,
        active_limits,
        focus_terms=focus_terms,
    )
    relevant = _relevant_evidence(question_tokens, collection.evidence, focus_terms=focus_terms)
    warnings.extend(collection.warnings)
    warnings.append("Public reachability was not checked; the GitHub URL was validated syntactically only.")

    observed: list[Finding] = [
        _finding(1, "observed", "high", f"Git resolved HEAD to immutable commit {head_sha}."),
    ]
    source_groups: dict[str, list[str]] = {}
    for item in collection.evidence:
        source_groups.setdefault(item.source_type, []).append(item.id)
    for source_type in sorted(source_groups):
        citations = tuple(source_groups[source_type][:8])
        observed.append(
            _finding(
                len(observed) + 1,
                "observed",
                "high",
                f"Collected {len(source_groups[source_type])} bounded {source_type} evidence item(s).",
                citations,
            )
        )

    relevant_decisions = [item for item in relevant if item.explicit_decision_language]
    relevant_rationales = [item for item in relevant_decisions if item.explicit_rationale_language]
    # When the question asks "why" but no relevant rationale was matched, the
    # answer to this question is unknown (see the unknown branch below). In that
    # state the repo-wide rationale scan must not also assert a high-confidence
    # decision-and-rationale finding: that language exists somewhere in the repo
    # but not for the question asked, so claiming it at high confidence next to
    # an "unknown" verdict is a self-contradiction (§7 P1 false confidence).
    rationale_unknown = "why" in question_tokens and not relevant_rationales

    explicit_decisions = [item for item in collection.evidence if item.explicit_decision_language]
    explicit_rationales = [item for item in explicit_decisions if item.explicit_rationale_language]
    if explicit_decisions:
        observed.append(
            _finding(
                len(observed) + 1,
                "observed",
                "high",
                "Explicit decision language appears in the cited repository text.",
                tuple(item.id for item in explicit_decisions[:8]),
            )
        )
    if explicit_rationales and not rationale_unknown:
        observed.append(
            _finding(
                len(observed) + 1,
                "observed",
                "high",
                "Decision and rationale language occur near each other in the cited text.",
                tuple(item.id for item in explicit_rationales[:8]),
            )
        )

    inferred: list[Finding] = []
    if "ci" in source_groups:
        inferred.append(
            _finding(
                len(inferred) + 1,
                "inferred",
                "medium",
                "The repository likely uses automated validation or delivery workflows.",
                tuple(source_groups["ci"][:8]),
            )
        )
    if "deployment_config" in source_groups:
        inferred.append(
            _finding(
                len(inferred) + 1,
                "inferred",
                "medium",
                "The repository likely contains an explicitly configured deployment or infrastructure path.",
                tuple(source_groups["deployment_config"][:8]),
            )
        )
    if "manifest" in source_groups:
        inferred.append(
            _finding(
                len(inferred) + 1,
                "inferred",
                "medium",
                "The cited manifests expose part of the build and dependency surface.",
                tuple(source_groups["manifest"][:8]),
            )
        )

    if relevant:
        observed.append(
            _finding(
                len(observed) + 1,
                "observed",
                "high",
                "The cited repository evidence directly matches terms in the engineering question.",
                tuple(item.id for item in relevant[:8]),
            )
        )

    unknown: list[Finding] = [
        _finding(1, "unknown", "low", "Whether the supplied GitHub repository is publicly reachable was not verified."),
        _finding(2, "unknown", "low", "Repository history, issues, pull requests, and external discussions were not inspected."),
    ]
    if "why" in question_tokens and not relevant_rationales:
        if collection.truncated:
            rationale_statement = (
                "The rationale requested by this question is unknown within the inspected evidence; "
                "the scan was partial because configured bounds were reached, so relevant rationale may exist in files not inspected."
            )
        else:
            rationale_statement = "The rationale requested by this question is unknown because no relevant explicit decision-and-reason language was found."
        unknown.append(
            _finding(
                len(unknown) + 1,
                "unknown",
                "low",
                rationale_statement,
                tuple(item.id for item in relevant[:8]),
            )
        )
    elif relevant_rationales:
        observed.append(
            _finding(
                len(observed) + 1,
                "observed",
                "high",
                "Relevant repository text explicitly records both a decision and nearby rationale.",
                tuple(item.id for item in relevant_rationales[:8]),
            )
        )
    if collection.truncated:
        unknown.append(
            _finding(
                len(unknown) + 1,
                "unknown",
                "low",
                "Additional relevant evidence may exist beyond the configured collection bounds.",
            )
        )

    repository = {
        "github_url": target.github_url,
        "slug": target.slug,
        "checkout_path": str(target.checkout_path),
        "repositories_root": str(target.repositories_root),
        "head_sha": head_sha,
        "origin": origin,
        "question": question,
        "tracked_paths_considered": collection.tracked_path_count,
        "files_inspected": collection.inspected_file_count,
        "bytes_inspected": collection.inspected_bytes,
    }
    return report_to_dict(
        repository=repository,
        limits=active_limits,
        evidence=collection.evidence,
        observed=observed,
        inferred=inferred,
        unknown=unknown,
        warnings=warnings,
    )
