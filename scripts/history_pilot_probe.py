#!/usr/bin/env python3
"""Build pinned Icarus corpora and run the preregistered history probes.

Runtime corpora and answers must live outside the repository. GitHub history is
fetched once per repository, then combined with code and commit messages from
each exact task pin. This keeps every probe commit-correct without repeatedly
spending GitHub API quota on an identical discussion snapshot.

The script never promotes a task automatically. It records whether a gold ref
was in the evidence shown to Icarus; a human must still verify that the answer
states the registered decision (or bounded absence) faithfully.
"""

import argparse
import dataclasses
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEFAULT_TASKS = ROOT / "docs/experiments/2026-08-27-history-failure-pilot-candidates.jsonl"
SELECTED_STATUS = "pending_icarus_probe"
GITHUB_REF = re.compile(r"github\.com/[^/]+/[^/]+/(pull|issues)/(\d+)(?:\b|/)")


def load_tasks(path, requested_ids=()):
    requested = set(requested_ids)
    tasks = []
    seen = set()
    with Path(path).open() as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            task_id = row.get("task_id")
            if task_id in seen:
                raise ValueError(f"line {line_number}: duplicate task_id {task_id!r}")
            seen.add(task_id)
            if row.get("status") != SELECTED_STATUS:
                continue
            if requested and task_id not in requested:
                continue
            for field in ("repo", "commit", "stratum", "icarus_probe", "gold_refs"):
                if not row.get(field):
                    raise ValueError(f"{task_id}: missing {field}")
            tasks.append(row)
    missing = requested - {row["task_id"] for row in tasks}
    if missing:
        raise ValueError(f"requested task IDs are absent or not probe-ready: {sorted(missing)}")
    return sorted(tasks, key=lambda row: (row["repo"], row["commit"], row["task_id"]))


def normalized_gold_refs(urls):
    refs = []
    for url in urls:
        match = GITHUB_REF.search(url)
        if match:
            source = "pr" if match.group(1) == "pull" else "issue"
            refs.append(f"{source}:{match.group(2)}")
    return sorted(set(refs))


def corpus_key(repo, commit):
    digest = hashlib.sha256(f"{repo}\0{commit}".encode()).hexdigest()[:16]
    return f"{repo.replace('/', '__')}--{digest}"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load_jsonl(path):
    with Path(path).open() as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prepare_history(repo, anchor_commit, output_dir):
    from evals.ingest import ingest_repo

    history_dir = Path(output_dir) / "history" / repo.replace("/", "__")
    chunks_path = history_dir / "chunks.jsonl"
    meta_path = history_dir / "meta.json"
    if not chunks_path.exists() or not meta_path.exists():
        history_dir.mkdir(parents=True, exist_ok=True)
        ingest_repo(repo, history_dir, commit=anchor_commit, code_dir=".")
    chunks = [row for row in load_jsonl(chunks_path) if row.get("source") in {"pr", "issue"}]
    history_path = history_dir / "history-only.jsonl"
    if not history_path.exists():
        with history_path.open("w") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk) + "\n")
    meta = json.loads(meta_path.read_text())
    return chunks, meta, history_path


def prepare_corpus(task, history, history_meta, history_hash, output_dir):
    from evals import ingest
    from evals.corpus_meta import load_meta, write_meta

    corpus_dir = Path(output_dir) / "corpora" / corpus_key(task["repo"], task["commit"])
    chunks_path = corpus_dir / "chunks.jsonl"
    meta_path = corpus_dir / "meta.json"
    existing = load_meta(meta_path)
    if chunks_path.exists() and existing:
        if existing.get("repo") != task["repo"] or existing.get("commit") != task["commit"]:
            raise ValueError(f"stale corpus provenance at {corpus_dir}")
        return corpus_dir

    resolved = ingest.resolve_commit(task["repo"], task["commit"])
    if resolved != task["commit"]:
        raise ValueError(f"{task['task_id']}: commit resolved to {resolved}, expected {task['commit']}")
    stats = {}
    commits = ingest.fetch_commits(task["repo"], resolved, stats=stats)
    code = ingest.fetch_code(task["repo"], resolved, ".", stats=stats)
    chunks = history + commits + code
    corpus_dir.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("w") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk) + "\n")
    counts = {
        "pr": sum(row.get("source") == "pr" for row in history),
        "issue": sum(row.get("source") == "issue" for row in history),
        "commit": len(commits),
    }
    for row in code:
        counts[row["source"]] = counts.get(row["source"], 0) + 1
    counts.setdefault("code", 0)
    chunking = (
        ingest.CHUNKING_SCHEME_AST
        if ingest.ast_chunking_enabled()
        else ingest.CHUNKING_SCHEME_LINE_WINDOW
    )
    write_meta(
        meta_path,
        repo=task["repo"],
        commit=resolved,
        code_dir=".",
        counts=counts,
        chunking=chunking,
        truncated=bool(history_meta.get("truncated") or stats.get("truncated")),
    )
    provenance = {
        "history_chunks_sha256": history_hash,
        "history_snapshot_generated_at": history_meta.get("generated_at"),
        "pinned_chunks_sha256": sha256_file(chunks_path),
    }
    write_json(corpus_dir / "experiment-provenance.json", provenance)
    return corpus_dir


def run_probe(task, corpus_dir, output_dir):
    from demo.library import _build_gated_pipeline

    result_path = Path(output_dir) / "probes" / f"{task['task_id']}.json"
    if result_path.exists():
        return json.loads(result_path.read_text())
    pipeline = _build_gated_pipeline(corpus_dir)
    result = pipeline.answer(task["icarus_probe"], per_claim=True)
    expected = normalized_gold_refs(task["gold_refs"])
    shown = set(result.shown)
    record = {
        "task_id": task["task_id"],
        "repo": task["repo"],
        "commit": task["commit"],
        "stratum": task["stratum"],
        "probe": task["icarus_probe"],
        "expected_gold_refs": expected,
        "gold_ref_shown": sorted(shown.intersection(expected)),
        "candidate_gate": "pass" if shown.intersection(expected) else "miss",
        "corpus_key": corpus_dir.name,
        "corpus_chunks_sha256": sha256_file(corpus_dir / "chunks.jsonl"),
        "result": dataclasses.asdict(result),
    }
    write_json(result_path, record)
    return record


def selftest():
    assert normalized_gold_refs([
        "https://github.com/o/r/pull/12",
        "https://github.com/o/r/issues/9#issuecomment-1",
    ]) == ["issue:9", "pr:12"]
    assert corpus_key("o/r", "a" * 40) == corpus_key("o/r", "a" * 40)
    assert corpus_key("o/r", "a" * 40) != corpus_key("o/r", "b" * 40)
    print("selftest ok")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default=str(DEFAULT_TASKS))
    parser.add_argument("--output-dir")
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--ingest-only", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.selftest:
        selftest()
        return 0
    if not args.output_dir:
        raise ValueError("--output-dir is required")
    output_dir = Path(args.output_dir).expanduser().resolve()
    if output_dir == ROOT or ROOT in output_dir.parents:
        raise ValueError("runtime corpora must be written outside the repository")
    # The paid attestation normally lives in the gitignored .env, exactly as
    # `evals/run.py` reads it. Not loading it here made a PRESENT key look
    # ABSENT and reported this experiment as credential-blocked for a day
    # (found 2026-08-28). The interlock below is unchanged: a genuinely missing
    # key still refuses, and the free GEMINI_API_KEY is never accepted for it.
    from evals.env_file import load_env_file
    load_env_file(ROOT / ".env")
    if not args.ingest_only and not os.environ.get("GEMINI_PAID_API_KEY"):
        raise RuntimeError("GEMINI_PAID_API_KEY is required for production Icarus probes")

    tasks = load_tasks(args.tasks, args.task_id)
    by_repo = defaultdict(list)
    for task in tasks:
        by_repo[task["repo"]].append(task)
    records = []
    for repo in sorted(by_repo):
        repo_tasks = by_repo[repo]
        history, history_meta, history_path = prepare_history(
            repo, repo_tasks[0]["commit"], output_dir
        )
        history_hash = sha256_file(history_path)
        corpora = {}
        for task in repo_tasks:
            key = (task["repo"], task["commit"])
            if key not in corpora:
                corpora[key] = prepare_corpus(
                    task, history, history_meta, history_hash, output_dir
                )
            corpus_dir = corpora[key]
            if args.ingest_only:
                print(f"prepared {task['task_id']} {corpus_dir}", flush=True)
            else:
                record = run_probe(task, corpus_dir, output_dir)
                records.append(record)
                print(
                    f"probed {task['task_id']} {record['candidate_gate']} "
                    f"{','.join(record['gold_ref_shown']) or '-'}",
                    flush=True,
                )
    if records:
        write_json(Path(output_dir) / "probe-summary.json", {"probes": records})
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"history_pilot_probe: {exc}", file=sys.stderr)
        raise SystemExit(2)
