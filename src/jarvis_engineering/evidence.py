from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .contracts import ErrorCode, EvidenceItem, InspectionError, InspectionLimits
from .isolation import RepositoryTarget, run_git


_TEXT_EXTENSIONS = {
    ".adoc", ".asciidoc",
    ".c", ".cc", ".cfg", ".conf", ".cpp", ".cs", ".css", ".env", ".go",
    ".h", ".hpp", ".html", ".ini", ".java", ".js", ".json", ".jsx", ".kt",
    ".kts", ".md", ".mjs", ".php", ".plist", ".properties", ".proto", ".py",
    ".rb", ".rs", ".rst", ".scala", ".sh", ".sql", ".swift", ".tf", ".toml",
    ".ts", ".tsx", ".txt", ".xml", ".yaml", ".yml",
}
_SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".h", ".hpp", ".java", ".js", ".jsx",
    ".kt", ".kts", ".mjs", ".php", ".py", ".rb", ".rs", ".scala", ".swift",
    ".ts", ".tsx",
}
_MANIFESTS = {
    "build.gradle", "build.gradle.kts", "cargo.toml", "composer.json", "gemfile",
    "go.mod", "package.json", "pom.xml", "project.clj", "pyproject.toml",
    "requirements.txt", "setup.cfg", "setup.py",
}
_CI_NAMES = {
    ".gitlab-ci.yml", "appveyor.yml", "azure-pipelines.yml", "bitbucket-pipelines.yml",
    "buildkite.yml", "circle.yml", "jenkinsfile", "travis.yml",
}
_DEPLOYMENT_NAMES = {
    "docker-compose.yml", "docker-compose.yaml", "dockerfile", "fly.toml",
    "heroku.yml", "netlify.toml", "procfile", "render.yaml", "serverless.yml",
    "vercel.json",
}
_DECISION_RE = re.compile(
    r"\b(?:decision|decided|we chose|we selected|adopted|rejected|instead of|"
    r"intended for|trade[- ]?off|rfc|adr|proposal)\b",
    re.IGNORECASE,
)
_RATIONALE_RE = re.compile(
    r"\b(?:because|so that|in order to|rationale|reason|why|therefore|due to|"
    r"motivated by|trade[- ]?off)\b",
    re.IGNORECASE,
)
_STRUCTURE_RE = re.compile(
    r"\b(?:architecture|boundary|component|service|module|pipeline|deploy|"
    r"configuration|dependency|interface|entrypoint)\b",
    re.IGNORECASE,
)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?ix)^("
    r"\s*(?:export\s+)?"
    r"[\"']?"
    r"[\w.-]*(?:"
    r"api[_-]?key|access[_-]?key(?:[_-]?id)?|secret(?:[_-]?key)?|"
    r"secret[_-]?access[_-]?key|access[_-]?token|auth[_-]?token|"
    r"client[_-]?secret|github[_-]?token|password|private[_-]?key|"
    r"database[_-]?url|db[_-]?url"
    r")[\w.-]*"
    r"[\"']?\s*[:=]\s*)"
    r"(.+)$"
)
_INLINE_SECRET_RES = (
    re.compile(r"\bsk_(?:live|test)_[A-Za-z0-9]{6,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}\b"),
    re.compile(r"\bpostgres(?:ql)?://[^:\s/@]+:[^@\s]+@[^\s\"']+"),
    re.compile(r"\bmysql://[^:\s/@]+:[^@\s]+@[^\s\"']+"),
    re.compile(r"\bmongodb(?:\+srv)?://[^:\s/@]+:[^@\s]+@[^\s\"']+"),
)
_PRIVATE_KEY_BEGIN_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_PRIVATE_KEY_END_RE = re.compile(r"-----END [A-Z ]*PRIVATE KEY-----")
_IGNORED_PARTS = {
    ".git", ".next", "build", "coverage", "dist", "generated", "node_modules",
    "target", "vendor",
}
_SOURCE_ORDER = (
    "readme",
    "decision_record",
    "documentation",
    "manifest",
    "ci",
    "deployment_config",
    "configuration",
    "source",
)


@dataclass(frozen=True)
class CollectionResult:
    evidence: list[EvidenceItem]
    warnings: list[str]
    tracked_path_count: int
    inspected_file_count: int
    inspected_bytes: int
    skipped_jsonl_count: int
    truncated: bool


def _classify(path: PurePosixPath) -> tuple[str, int] | None:
    parts = tuple(part.casefold() for part in path.parts)
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if name.endswith(".jsonl") or any(part.endswith(".jsonl") for part in parts):
        return None
    if any(part in _IGNORED_PARTS for part in parts):
        return None
    if name.startswith("readme") and suffix in {".md", ".rst", ".txt", ""}:
        return "readme", 100
    decision_record_extensions = {".adoc", ".asciidoc", ".md", ".rst", ".txt"}
    if (
        any(part in {"adr", "adrs", "decisions", "decision-records", "rfcs", "rfc", "oteps", "otep"} for part in parts)
        or re.search(r"(?:^|[-_.])(adr|rfc)[-_.]?\d*", name)
    ) and suffix in decision_record_extensions:
        return "decision_record", 95
    if parts[:2] == (".github", "workflows") or name in _CI_NAMES:
        return "ci", 85
    if name in _MANIFESTS:
        return "manifest", 80
    if (
        name in _DEPLOYMENT_NAMES
        or any(part in {"deploy", "deployment", "helm", "infra", "k8s", "kubernetes", "terraform"} for part in parts)
    ) and (suffix in _TEXT_EXTENSIONS or suffix == ""):
        return "deployment_config", 75
    if any(part in {"chapters", "docs", "documentation", "specification"} for part in parts) and suffix in {
        ".adoc", ".asciidoc", ".md", ".rst", ".txt"
    }:
        return "documentation", 70
    if suffix in _SOURCE_EXTENSIONS:
        source_bonus = 8 if re.search(r"(?:architecture|core|main|app|service|config)", name) else 0
        return "source", 40 + source_bonus
    if suffix in _TEXT_EXTENSIONS and name.startswith((".env", "config", "settings")):
        return "configuration", 55
    return None


def _tracked_paths(target: RepositoryTarget, head_sha: str, limits: InspectionLimits) -> tuple[list[str], bool]:
    raw = run_git(
        target.checkout_path,
        ["ls-tree", "-r", "-z", head_sha],
        timeout_seconds=limits.git_timeout_seconds,
        text=False,
    )
    rows = bytes(raw).split(b"\0")
    decoded: list[str] = []
    for row in rows:
        if not row:
            continue
        header, _, raw_path = row.partition(b"\t")
        parts = header.split()
        if len(parts) < 2 or parts[1] != b"blob":
            continue
        decoded.append(raw_path.decode("utf-8", errors="surrogateescape"))
    truncated = len(decoded) > limits.max_tracked_paths
    return decoded[: limits.max_tracked_paths], truncated


def _grep_focus_paths(
    target: RepositoryTarget,
    head_sha: str,
    focus_terms: set[str],
    limits: InspectionLimits,
) -> set[str]:
    if not focus_terms:
        return set()
    arguments = ["grep", "-i", "-F", "-l"]
    for term in sorted(focus_terms):
        arguments.extend(["-e", term])
    arguments.extend([head_sha, "--"])
    try:
        output = run_git(
            target.checkout_path,
            arguments,
            timeout_seconds=limits.git_timeout_seconds,
        )
    except InspectionError as exc:
        if exc.code == ErrorCode.GIT_COMMAND_FAILED:
            return set()
        raise
    return {line.split(":", 1)[1] for line in str(output).splitlines() if ":" in line}


def _diversify_candidates(
    candidates: list[tuple[int, str, str]],
) -> list[tuple[int, str, str]]:
    first_by_type: dict[str, tuple[int, str, str]] = {}
    for candidate in candidates:
        first_by_type.setdefault(candidate[2], candidate)
    prioritized = [
        first_by_type[source_type]
        for source_type in _SOURCE_ORDER
        if source_type in first_by_type
    ]
    selected_paths = {candidate[1] for candidate in prioritized}
    prioritized.extend(candidate for candidate in candidates if candidate[1] not in selected_paths)
    return prioritized


def _blob_size(target: RepositoryTarget, object_spec: str, limits: InspectionLimits) -> int:
    output = run_git(
        target.checkout_path,
        ["cat-file", "-s", object_spec],
        timeout_seconds=limits.git_timeout_seconds,
    )
    try:
        return int(str(output).strip())
    except ValueError as exc:
        raise InspectionError(
            ErrorCode.GIT_COMMAND_FAILED,
            "Git returned an invalid blob size.",
            details={"object": object_spec, "value": str(output).strip()[:100]},
        ) from exc


def _read_blob(target: RepositoryTarget, object_spec: str, limits: InspectionLimits) -> bytes:
    output = run_git(
        target.checkout_path,
        ["cat-file", "blob", object_spec],
        timeout_seconds=limits.git_timeout_seconds,
        text=False,
    )
    return bytes(output)


def _is_probably_binary(content: bytes) -> bool:
    return b"\0" in content[:8192]


def _redact_line(line: str) -> str:
    match = _SECRET_ASSIGNMENT_RE.match(line)
    if match:
        return f"{match.group(1)}[REDACTED]"
    redacted = line
    for pattern in _INLINE_SECRET_RES:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _excerpt(text: str, focus_terms: set[str] | None = None) -> tuple[str, str, bool, bool]:
    lines = text.splitlines()
    decision_lines = [index for index, line in enumerate(lines) if _DECISION_RE.search(line)]
    rationale_lines = [index for index, line in enumerate(lines) if _RATIONALE_RE.search(line)]
    focused_lines = [
        index
        for index, line in enumerate(lines)
        if focus_terms and any(term in line.casefold() for term in focus_terms)
    ]
    explicit_decision = bool(decision_lines)
    explicit_rationale = any(
        abs(decision_index - rationale_index) <= 4
        for decision_index in decision_lines
        for rationale_index in rationale_lines
    )

    if focused_lines:
        focus = focused_lines[0]
    elif decision_lines:
        focus = decision_lines[0]
    else:
        structured = next((index for index, line in enumerate(lines) if _STRUCTURE_RE.search(line)), None)
        substantive = next((index for index, line in enumerate(lines) if line.strip()), 0)
        focus = structured if structured is not None else substantive
    start = max(0, focus - 2)
    end = min(len(lines), start + 12)
    selected_lines = []
    in_private_key = False
    for line in lines[start:end]:
        if in_private_key:
            if _PRIVATE_KEY_END_RE.search(line):
                in_private_key = False
            continue
        if _PRIVATE_KEY_BEGIN_RE.search(line):
            selected_lines.append("[REDACTED PRIVATE KEY BLOCK]")
            in_private_key = True
            continue
        selected_lines.append(_redact_line(line))
    selected = "\n".join(selected_lines).strip()
    if len(selected) > 1200:
        selected = selected[:1197].rstrip() + "..."
    locator = f"L{start + 1}-L{max(start + 1, end)}"
    return locator, selected, explicit_decision, explicit_rationale


def collect_evidence(
    target: RepositoryTarget,
    head_sha: str,
    limits: InspectionLimits,
    focus_terms: set[str] | None = None,
) -> CollectionResult:
    tracked_paths, tracked_truncated = _tracked_paths(target, head_sha, limits)
    focus_paths = _grep_focus_paths(target, head_sha, focus_terms or set(), limits)
    skipped_jsonl = sum(1 for path in tracked_paths if path.casefold().endswith(".jsonl"))
    candidates: list[tuple[int, str, str]] = []
    for value in tracked_paths:
        path = PurePosixPath(value)
        classified = _classify(path)
        if classified is None:
            continue
        source_type, score = classified
        if value in focus_paths:
            score += 120
        elif focus_terms and any(term in value.casefold() for term in focus_terms):
            score += 60
        depth_penalty = min(len(path.parts), 10)
        candidates.append((score - depth_penalty, value, source_type))
    candidates.sort(key=lambda item: (-item[0], item[1].casefold(), item[1]))
    candidates = _diversify_candidates(candidates)

    evidence: list[EvidenceItem] = []
    warnings: list[str] = []
    inspected_files = 0
    inspected_bytes = 0
    oversized = 0
    binary = 0
    truncated = tracked_truncated

    for _, path, source_type in candidates:
        if inspected_files >= limits.max_files or len(evidence) >= limits.max_evidence_items:
            truncated = True
            break
        object_spec = f"{head_sha}:{path}"
        size = _blob_size(target, object_spec, limits)
        if size > limits.max_file_bytes:
            oversized += 1
            continue
        if inspected_bytes + size > limits.max_total_bytes:
            truncated = True
            break
        content = _read_blob(target, object_spec, limits)
        inspected_files += 1
        inspected_bytes += len(content)
        if _is_probably_binary(content):
            binary += 1
            continue
        text = content.decode("utf-8", errors="replace")
        locator, excerpt, explicit_decision, explicit_rationale = _excerpt(text, focus_terms)
        relevance = {
            "readme": "Repository overview and stated operating context.",
            "decision_record": "Explicit architecture or product decision record.",
            "documentation": "Design or operational documentation.",
            "manifest": "Declared build system and dependency surface.",
            "ci": "Automated validation or delivery configuration.",
            "deployment_config": "Deployment or infrastructure configuration.",
            "configuration": "Runtime or development configuration.",
            "source": "Source code relevant to architecture or explicit decisions.",
        }[source_type]
        evidence.append(
            EvidenceItem(
                id=f"e{len(evidence) + 1:03d}",
                source_type=source_type,
                path=path,
                locator=locator,
                sha256=hashlib.sha256(content).hexdigest(),
                relevance=relevance,
                excerpt=excerpt,
                explicit_decision_language=explicit_decision,
                explicit_rationale_language=explicit_rationale,
            )
        )

    if tracked_truncated:
        warnings.append(
            f"Tracked-path scan was capped at {limits.max_tracked_paths} entries."
        )
    if truncated:
        warnings.append("Evidence collection reached one or more configured bounds.")
    if skipped_jsonl:
        warnings.append(f"Skipped {skipped_jsonl} JSONL file(s); JSONL access is prohibited.")
    if oversized:
        warnings.append(f"Skipped {oversized} file(s) larger than max_file_bytes.")
    if binary:
        warnings.append(f"Skipped {binary} file(s) that appeared to be binary.")

    return CollectionResult(
        evidence=evidence,
        warnings=warnings,
        tracked_path_count=len(tracked_paths),
        inspected_file_count=inspected_files,
        inspected_bytes=inspected_bytes,
        skipped_jsonl_count=skipped_jsonl,
        truncated=truncated,
    )
