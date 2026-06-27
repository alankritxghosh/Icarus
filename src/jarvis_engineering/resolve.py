from __future__ import annotations

from pathlib import Path

from .contracts import ErrorCode, InspectionError
from .isolation import (
    normalize_remote_url,
    read_origin,
    run_git,
)


def _contains_jsonl(path: Path) -> bool:
    return any(part.casefold().endswith(".jsonl") for part in path.parts)


def _git_toplevel(path: Path, *, timeout: int) -> Path:
    try:
        output = run_git(
            path,
            ["rev-parse", "--show-toplevel"],
            timeout_seconds=timeout,
        )
    except InspectionError as exc:
        if exc.code == ErrorCode.GIT_COMMAND_FAILED:
            raise InspectionError(
                ErrorCode.NOT_GIT_REPOSITORY,
                "The current directory or supplied path is not inside a Git repository.",
                details=exc.details,
            ) from exc
        raise
    return Path(str(output).strip()).expanduser().resolve(strict=True)


def resolve_invocation(
    path_arg: str | None,
    github_url_flag: str | None,
    repositories_root_flag: str | None,
    *,
    timeout: int,
) -> tuple[str, str, str, bool]:
    """Resolve a friendly CLI invocation into inspect_repository arguments."""
    raw_path = Path(path_arg).expanduser() if path_arg else Path.cwd()
    if _contains_jsonl(raw_path):
        raise InspectionError(ErrorCode.JSONL_ACCESS_DENIED, "JSONL paths are never permitted.")

    toplevel = _git_toplevel(raw_path, timeout=timeout)

    if github_url_flag:
        github_url = github_url_flag
        derived_identity = False
    else:
        origin = read_origin(toplevel, timeout_seconds=timeout)
        normalized = normalize_remote_url(origin) if origin else None
        if normalized is None:
            raise InspectionError(
                ErrorCode.INVALID_ARGUMENTS,
                "Could not infer a canonical GitHub URL from remote.origin.url; pass --github-url.",
                details={"reason": "missing or non-GitHub remote.origin.url; pass --github-url"},
            )
        github_url = normalized
        derived_identity = True

    repositories_root = repositories_root_flag if repositories_root_flag else str(toplevel.parent)
    return github_url, str(toplevel), repositories_root, derived_identity
