from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .contracts import ErrorCode, InspectionError


_GITHUB_COMPONENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,98}[A-Za-z0-9])?$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class RepositoryTarget:
    github_url: str
    owner: str
    repository: str
    checkout_path: Path
    repositories_root: Path

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repository}"


def validate_github_url(value: str) -> tuple[str, str, str]:
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise InspectionError(ErrorCode.INVALID_GITHUB_URL, "GitHub URL is malformed.") from exc

    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise InspectionError(
            ErrorCode.INVALID_GITHUB_URL,
            "Expected an HTTPS public GitHub repository URL without credentials, query, or fragment.",
            details={"value": value},
        )

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise InspectionError(
            ErrorCode.INVALID_GITHUB_URL,
            "GitHub URL must have exactly an owner and repository.",
            details={"value": value},
        )
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not owner or not repository or not _GITHUB_COMPONENT.fullmatch(owner) or not _GITHUB_COMPONENT.fullmatch(repository):
        raise InspectionError(
            ErrorCode.INVALID_GITHUB_URL,
            "GitHub owner or repository name is invalid.",
            details={"value": value},
        )
    canonical = urlunsplit(("https", "github.com", f"/{owner}/{repository}", "", ""))
    return canonical, owner, repository


def _contains_jsonl(path: Path) -> bool:
    return any(part.casefold().endswith(".jsonl") for part in path.parts)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_target(
    github_url: str,
    checkout: str,
    repositories_root: str,
    *,
    protected_root: Path | None,
) -> RepositoryTarget:
    canonical_url, owner, repository = validate_github_url(github_url)

    raw_root = Path(repositories_root).expanduser()
    if _contains_jsonl(raw_root):
        raise InspectionError(ErrorCode.JSONL_ACCESS_DENIED, "JSONL paths are never permitted.")
    try:
        root = raw_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InspectionError(
            ErrorCode.INVALID_REPOSITORIES_ROOT,
            "The configured repositories_root does not exist or cannot be resolved.",
            details={"repositories_root": str(raw_root)},
        ) from exc
    if not root.is_dir():
        raise InspectionError(
            ErrorCode.INVALID_REPOSITORIES_ROOT,
            "The configured repositories_root must be a directory.",
            details={"repositories_root": str(root)},
        )

    raw_checkout = Path(checkout).expanduser()
    if _contains_jsonl(raw_checkout):
        raise InspectionError(ErrorCode.JSONL_ACCESS_DENIED, "JSONL paths are never permitted.")
    candidate = raw_checkout if raw_checkout.is_absolute() else root / raw_checkout
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise InspectionError(
            ErrorCode.CHECKOUT_NOT_FOUND,
            "The explicitly provided local checkout path does not exist or cannot be resolved.",
            details={"checkout": str(candidate)},
        ) from exc
    if not resolved.is_dir():
        raise InspectionError(
            ErrorCode.CHECKOUT_NOT_FOUND,
            "The local checkout path must be a directory.",
            details={"checkout": str(resolved)},
        )
    if not _is_within(resolved, root):
        raise InspectionError(
            ErrorCode.CHECKOUT_OUTSIDE_ROOT,
            "The local checkout resolves outside the configured repositories_root.",
            details={"checkout": str(resolved), "repositories_root": str(root)},
        )

    if protected_root is not None:
        protected = protected_root.expanduser().resolve()
        if _is_within(resolved, protected) or resolved == protected:
            raise InspectionError(
                ErrorCode.PROTECTED_ROOT_ACCESS,
                "Access to the personal JARVIS root is prohibited.",
                details={"checkout": str(resolved), "protected_root": str(protected)},
            )

    return RepositoryTarget(canonical_url, owner, repository, resolved, root)


def run_git(
    repository: Path,
    arguments: list[str],
    *,
    timeout_seconds: int,
    text: bool = True,
) -> str | bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            shell=False,
            check=False,
            capture_output=True,
            text=text,
            encoding="utf-8" if text else None,
            errors="replace" if text else None,
            env=env,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise InspectionError(
            ErrorCode.GIT_COMMAND_TIMEOUT,
            "A read-only Git command timed out.",
            details={"command": ["git", "-C", str(repository), *arguments]},
        ) from exc
    except OSError as exc:
        raise InspectionError(
            ErrorCode.GIT_COMMAND_FAILED,
            "Git could not be executed.",
            details={"reason": str(exc)},
        ) from exc
    if result.returncode != 0:
        stderr = result.stderr if text else result.stderr.decode("utf-8", errors="replace")
        raise InspectionError(
            ErrorCode.GIT_COMMAND_FAILED,
            "A read-only Git command failed.",
            details={
                "arguments": arguments,
                "returncode": result.returncode,
                "stderr": stderr.strip()[:1000],
            },
        )
    return result.stdout


def resolve_head(repository: Path, *, timeout_seconds: int) -> str:
    try:
        output = run_git(
            repository,
            ["rev-parse", "--verify", "HEAD^{commit}"],
            timeout_seconds=timeout_seconds,
        )
    except InspectionError as exc:
        if exc.code == ErrorCode.GIT_COMMAND_FAILED:
            raise InspectionError(
                ErrorCode.NOT_GIT_REPOSITORY,
                "The checkout is not a Git repository with a resolvable HEAD.",
                details=exc.details,
            ) from exc
        raise
    sha = str(output).strip().lower()
    if not _SHA.fullmatch(sha):
        raise InspectionError(
            ErrorCode.GIT_COMMAND_FAILED,
            "Git returned an invalid immutable HEAD SHA.",
            details={"value": sha},
        )
    return sha


def normalize_remote_url(value: str) -> str | None:
    candidate = value.strip()
    if candidate.startswith("git@github.com:"):
        candidate = "https://github.com/" + candidate.removeprefix("git@github.com:")
    elif candidate.startswith("ssh://git@github.com/"):
        candidate = "https://github.com/" + candidate.removeprefix("ssh://git@github.com/")
    try:
        canonical, _, _ = validate_github_url(candidate)
    except InspectionError:
        return None
    return canonical.casefold()


def read_origin(repository: Path, *, timeout_seconds: int) -> str | None:
    try:
        value = run_git(
            repository,
            ["config", "--get", "remote.origin.url"],
            timeout_seconds=timeout_seconds,
        )
    except InspectionError as exc:
        if exc.code == ErrorCode.GIT_COMMAND_FAILED and exc.details.get("returncode") == 1:
            return None
        raise
    return str(value).strip() or None
