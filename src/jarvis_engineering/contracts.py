from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


SCHEMA_VERSION = "1.0"


class ErrorCode(StrEnum):
    INVALID_GITHUB_URL = "INVALID_GITHUB_URL"
    INVALID_REPOSITORIES_ROOT = "INVALID_REPOSITORIES_ROOT"
    CHECKOUT_NOT_FOUND = "CHECKOUT_NOT_FOUND"
    CHECKOUT_OUTSIDE_ROOT = "CHECKOUT_OUTSIDE_ROOT"
    PROTECTED_ROOT_ACCESS = "PROTECTED_ROOT_ACCESS"
    JSONL_ACCESS_DENIED = "JSONL_ACCESS_DENIED"
    NOT_GIT_REPOSITORY = "NOT_GIT_REPOSITORY"
    GIT_COMMAND_FAILED = "GIT_COMMAND_FAILED"
    GIT_COMMAND_TIMEOUT = "GIT_COMMAND_TIMEOUT"
    REMOTE_MISMATCH = "REMOTE_MISMATCH"
    INVALID_LIMIT = "INVALID_LIMIT"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    UNSUPPORTED_QUESTION = "UNSUPPORTED_QUESTION"
    ISOLATION_VIOLATION_BLOCKED = "ISOLATION_VIOLATION_BLOCKED"
    INSPECTION_FAILED = "INSPECTION_FAILED"


class InspectionError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "schema_version": SCHEMA_VERSION,
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
            },
        }


@dataclass(frozen=True)
class InspectionLimits:
    max_files: int = 80
    max_file_bytes: int = 131_072
    max_total_bytes: int = 2_097_152
    max_tracked_paths: int = 20_000
    max_evidence_items: int = 80
    git_timeout_seconds: int = 20

    def validate(self) -> None:
        values = asdict(self)
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in values.values()):
            raise InspectionError(
                ErrorCode.INVALID_LIMIT,
                "All inspection limits must be positive integers.",
                details={"limits": values},
            )
        if self.max_file_bytes > self.max_total_bytes:
            raise InspectionError(
                ErrorCode.INVALID_LIMIT,
                "max_file_bytes cannot exceed max_total_bytes.",
                details={"limits": values},
            )


@dataclass(frozen=True)
class EvidenceItem:
    id: str
    source_type: str
    path: str
    locator: str
    sha256: str
    relevance: str
    excerpt: str
    explicit_decision_language: bool
    explicit_rationale_language: bool


@dataclass(frozen=True)
class Finding:
    id: str
    classification: str
    confidence: str
    statement: str
    citations: tuple[str, ...]


def report_to_dict(
    *,
    repository: dict[str, Any],
    limits: InspectionLimits,
    evidence: list[EvidenceItem],
    observed: list[Finding],
    inferred: list[Finding],
    unknown: list[Finding],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "ok": True,
        "schema_version": SCHEMA_VERSION,
        "repository": repository,
        "limits": asdict(limits),
        "evidence": [asdict(item) for item in evidence],
        "findings": {
            "observed": [asdict(item) for item in observed],
            "inferred": [asdict(item) for item in inferred],
            "unknown": [asdict(item) for item in unknown],
        },
        "warnings": warnings,
    }
