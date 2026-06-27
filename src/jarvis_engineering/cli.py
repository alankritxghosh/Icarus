from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .contracts import ErrorCode, InspectionError, InspectionLimits
from .inspector import inspect_repository
from .render import render_text_report
from .resolve import resolve_invocation


class _JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InspectionError(
            ErrorCode.INVALID_ARGUMENTS,
            "Invalid command-line arguments.",
            details={"reason": message},
        )


def _parser() -> argparse.ArgumentParser:
    parser = _JsonArgumentParser(
        prog="jarvis-engineering",
        description="Read-only Repository Decision Intelligence.",
    )
    parser.add_argument(
        "positionals",
        nargs="*",
        help="No args starts repo chat. Otherwise: question, optional path plus question, or legacy github_url checkout question.",
    )
    parser.add_argument("--github-url", help="Public HTTPS GitHub repository URL override.")
    parser.add_argument(
        "--repositories-root",
        help="Configured root directory containing permitted repository checkouts.",
    )
    parser.add_argument("--max-files", type=int, default=80)
    parser.add_argument("--max-file-bytes", type=int, default=131_072)
    parser.add_argument("--max-total-bytes", type=int, default=2_097_152)
    parser.add_argument("--max-tracked-paths", type=int, default=20_000)
    parser.add_argument("--max-evidence-items", type=int, default=80)
    parser.add_argument("--git-timeout-seconds", type=int, default=20)
    parser.add_argument(
        "--format",
        choices=("auto", "text", "json"),
        default="auto",
        help="Output format. auto uses text in a terminal and JSON when piped.",
    )
    return parser


def _resolve_args(args: argparse.Namespace) -> tuple[str, str, str, str, bool]:
    positionals = list(args.positionals)
    if len(positionals) == 0:
        raise InspectionError(
            ErrorCode.INVALID_ARGUMENTS,
            "No one-shot question was supplied.",
            details={"reason": "no positionals"},
        )
    if len(positionals) == 1:
        path_arg = None
        question = positionals[0]
    elif len(positionals) == 2:
        path_arg, question = positionals
    elif len(positionals) == 3 and args.github_url is None:
        github_url, checkout, question = positionals
        if args.repositories_root is None:
            raise InspectionError(
                ErrorCode.INVALID_ARGUMENTS,
                "Legacy invocation requires --repositories-root.",
                details={"reason": "legacy invocation requires --repositories-root"},
            )
        return github_url, checkout, args.repositories_root, question, False
    else:
        raise InspectionError(
            ErrorCode.INVALID_ARGUMENTS,
            "Expected a question, optional path plus question, or legacy github_url checkout question.",
            details={"reason": "invalid positional argument count"},
        )

    github_url, checkout, repositories_root, derived_identity = resolve_invocation(
        path_arg,
        args.github_url,
        args.repositories_root,
        timeout=args.git_timeout_seconds,
    )
    return github_url, checkout, repositories_root, question, derived_identity


def _default_protected_root() -> Path:
    value = os.environ.get("JARVIS_PROTECTED_ROOT")
    if not value:
        raise InspectionError(
            ErrorCode.PROTECTED_ROOT_ACCESS,
            "JARVIS_PROTECTED_ROOT must be set; repository inspection is fail-closed when the protected root is unconfigured.",
        )
    return Path(value).expanduser().resolve()


def _emit(payload: dict[str, object], stream: object) -> None:
    json.dump(payload, stream, sort_keys=True, indent=2, ensure_ascii=True)
    stream.write("\n")


def _wants_text(args: argparse.Namespace, stream: object) -> bool:
    if args.format == "text":
        return True
    if args.format == "json":
        return False
    isatty = getattr(stream, "isatty", None)
    return bool(isatty and isatty())


def _limits_from_args(args: argparse.Namespace) -> InspectionLimits:
    return InspectionLimits(
        max_files=args.max_files,
        max_file_bytes=args.max_file_bytes,
        max_total_bytes=args.max_total_bytes,
        max_tracked_paths=args.max_tracked_paths,
        max_evidence_items=args.max_evidence_items,
        git_timeout_seconds=args.git_timeout_seconds,
    )


def _inspect_resolved(
    args: argparse.Namespace,
    github_url: str,
    checkout: str,
    repositories_root: str,
    question: str,
) -> dict[str, object]:
    return inspect_repository(
        github_url,
        checkout,
        repositories_root,
        question,
        limits=_limits_from_args(args),
        protected_root=_default_protected_root(),
    )


def _inspect_chat_turn(
    args: argparse.Namespace,
    question: str,
    *,
    path_arg: str | None,
    derived_identity_cache: dict[str, bool],
) -> dict[str, object]:
    github_url, checkout, repositories_root, derived_identity = resolve_invocation(
        path_arg,
        args.github_url,
        args.repositories_root,
        timeout=args.git_timeout_seconds,
    )
    report = _inspect_resolved(args, github_url, checkout, repositories_root, question)
    cache_key = f"{github_url}\0{checkout}\0{repositories_root}"
    should_warn = derived_identity and not derived_identity_cache.get(cache_key)
    if should_warn:
        report["warnings"].append(
            "Repository identity was derived from remote.origin.url and was not verified against GitHub reachability."
        )
        derived_identity_cache[cache_key] = True
    return report


def _chat(args: argparse.Namespace) -> int:
    path_arg = args.positionals[0] if args.positionals else None
    derived_identity_cache: dict[str, bool] = {}
    print("JARVIS Engineering online. Ask this repo a question. Type exit or quit to leave.")
    while True:
        try:
            question = input("\nYou > ").strip()
        except EOFError:
            print()
            return 0
        if not question:
            continue
        if question.casefold() in {"exit", "quit", "bye"}:
            return 0
        try:
            report = _inspect_chat_turn(
                args,
                question,
                path_arg=path_arg,
                derived_identity_cache=derived_identity_cache,
            )
        except InspectionError as exc:
            print(f"JARVIS could not answer: {exc.message}")
            continue
        print()
        print(render_text_report(report))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
        _default_protected_root()
        if not args.positionals:
            return _chat(args)
        github_url, checkout, repositories_root, question, derived_identity = _resolve_args(args)
        report = _inspect_resolved(args, github_url, checkout, repositories_root, question)
        if derived_identity:
            report["warnings"].append(
                "Repository identity was derived from remote.origin.url and was not verified against GitHub reachability."
            )
    except InspectionError as exc:
        _emit(exc.to_dict(), sys.stdout)
        return 2
    except (KeyboardInterrupt, BrokenPipeError):
        return 130
    except Exception as exc:
        error = InspectionError(
            ErrorCode.INSPECTION_FAILED,
            "Repository inspection failed unexpectedly.",
            details={"exception_type": type(exc).__name__},
        )
        _emit(error.to_dict(), sys.stdout)
        return 1

    if _wants_text(args, sys.stdout):
        sys.stdout.write(render_text_report(report))
        sys.stdout.write("\n")
    else:
        _emit(report, sys.stdout)
    return 0
