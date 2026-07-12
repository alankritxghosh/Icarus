# evals/ingest.py
"""Generate a corpus from a public GitHub repo into evals/corpus/chunks.jsonl.

One-time generation tool (needs `gh` + `git`). Sources: PR descriptions + linked
issues (the "why"), and Python source files (the "what"). Run from the repo root:

    python3 -m evals.ingest                         # the pinned simonw/llm corpus
    python3 -m evals.ingest --repo OWNER/REPO       # any public repo (HEAD)
    python3 -m evals.ingest --repo OWNER/REPO --commit SHA --code-dir src

With no args it reproduces the pinned simonw/llm corpus exactly (so the eval
board stays reproducible). Any --repo override ingests that repo and writes a
meta.json recording the provenance, which the demo reads for citation links.
Public repos only while on free models (see CLAUDE.md).
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from .corpus_meta import write_meta

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"
PR_LIMIT = 200  # recent PRs (any state); the 6 gold PRs are well within this range
ISSUE_LIMIT = 500  # all open+closed issues; generous headroom over a typical repo's issue count
OUT = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"
META = Path(__file__).resolve().parent / "corpus" / "meta.json"

ISSUE_REF = re.compile(r"#(\d+)")

# Resource bounds so a huge or hostile repo can't fill disk / hang / OOM.
_SUBPROCESS_TIMEOUT = 120       # seconds, per git/gh call
_MAX_FILE_BYTES = 512 * 1024    # skip any single file bigger than this
# Stop reading code past this total. Raised 25 MB -> 100 MB (2026-07-13) so a
# large repo isn't artificially truncated. NOTE: on the hosted (Azure Container
# Apps) path this is NOT the binding limit -- the 240s ingress timeout caps a
# sync connect at ~1,900-2,000 chunks (docs/HANDOFF.md), which a repo this large
# hits first. Lifting this cap helps local ingest and any host without that
# timeout; the embed-time bottleneck is tracked separately.
_MAX_TOTAL_BYTES = 100 * 1024 * 1024
# Hard cap on how many CODE/doc/config chunks one repo can yield, independent of
# bytes. Guards the memory/CPU of the (non-backgrounded) lexical stage-1 BM25
# build: a hostile 100 MB repo of many short lines could otherwise produce
# ~190k 300-line windows and OOM a small container (flagged in a 2026-07-13
# review). 50k is far above any real repo we can actually serve -- the 240s
# embed ceiling caps a usable repo at ~2k chunks -- so it only ever trips on a
# pathological/hostile tree. PRs/issues are separately bounded (PR_LIMIT/
# ISSUE_LIMIT), so this need only bound the code walk. Approximate: the walk
# stops at the next file boundary, so it can overshoot by one file's windows.
_MAX_TOTAL_CHUNKS = 50_000

# Extension allowlist -> citation source tag (Task A1). Tight and Phase-1-scale
# on purpose: enough languages/formats to cover a typical mixed repo, not a
# general-purpose language database. Extend this table, not the logic below,
# if a new extension needs a home.
_EXTENSION_SOURCES = {
    # code
    ".py": "code", ".js": "code", ".ts": "code", ".tsx": "code", ".go": "code",
    ".rs": "code", ".java": "code", ".rb": "code", ".c": "code", ".h": "code",
    ".cpp": "code", ".swift": "code", ".kt": "code", ".php": "code",
    ".cs": "code", ".scala": "code", ".sh": "code",
    # doc
    ".md": "doc", ".rst": "doc", ".txt": "doc",
    # config
    ".yaml": "config", ".yml": "config", ".toml": "config", ".cfg": "config",
    ".ini": "config", ".sql": "config",
}

# Path segments that exclude a file regardless of extension (vendored/build/VCS
# noise -- never signal, just volume).
_DENY_DIR_SEGMENTS = {".git", "node_modules", "vendor", "dist", "build", ".venv"}

# Specific noisy filenames/patterns skipped even though their extension would
# otherwise pass: generated lockfiles (huge, machine-authored, zero "why"
# signal) and minified assets (unreadable, and always a build artifact of
# source we already ingest separately).
_DENY_FILENAMES = {
    "package-lock.json", "yarn.lock", "Pipfile.lock", "poetry.lock", "Cargo.lock",
}
_DENY_FILENAME_SUFFIXES = (".min.js", ".min.css")

_BINARY_SNIFF_BYTES = 8192  # how much of the file head to check for a null byte

# Line-window chunking (Task A2). A window of 300 lines is small enough for a
# BM25/embedding retriever to score a chunk as a coherent unit and for a writer
# prompt to consume several chunks without blowing its context, while staying
# large enough that most functions/classes fit inside one window rather than
# being fragmented on every chunk boundary. 40 lines of overlap (~13% of the
# window) is enough that a definition straddling a boundary is still whole in
# at least one of the two windows, without materially inflating chunk count.
# Both are plain module constants, not derived from any measurement -- if a
# future eval shows retrieval quality wants different numbers, change these.
_CHUNK_WINDOW_LINES = 300
_CHUNK_OVERLAP_LINES = 40
assert _CHUNK_OVERLAP_LINES < _CHUNK_WINDOW_LINES, (
    "overlap must be smaller than the window, or chunk_text's stride "
    "would be <= 0 and its while loop would never advance"
)


def chunk_text(text: str, ref_prefix: str) -> List[dict]:
    """Split `text` into size-bounded, overlapping line-windows.

    `ref_prefix` is the ref a caller would have used for a single whole-file
    chunk (e.g. `f"{source}:{rel_path}"`, exactly what `fetch_code` builds
    today). Returns a list of `{"ref": ..., "text": ...}` dicts -- no
    `"source"` key, by design: the caller already has the source tag baked
    into `ref_prefix` and builds the rest of the chunk dict itself (matching
    how `fetch_prs`/`fetch_issues`/`fetch_code` all assemble
    `{"ref": ..., "source": ..., "text": ...}` at their own call sites); this
    keeps `chunk_text` ignorant of the source taxonomy entirely.

    If `text` has at most `_CHUNK_WINDOW_LINES` lines, returns exactly ONE
    chunk with `ref_prefix` unchanged (no line range) -- this is today's
    existing whole-file ref format and must not gain a spurious line range
    just because it went through this function. Otherwise splits into
    consecutive windows of `_CHUNK_WINDOW_LINES` lines with
    `_CHUNK_OVERLAP_LINES` lines of overlap between neighbors, each ref
    carrying a 1-indexed, inclusive `#Lstart-Lend` suffix (GitHub's own
    line-link convention, so a later citation-link update can parse it
    directly). The last window ends exactly at the real last line -- no
    padding past end-of-file, no phantom trailing window.

    Pure and offline: no filesystem, no network. `splitlines()` (not a raw
    split on "\n") so a missing/extra trailing newline in `text` doesn't
    produce a spurious empty final "line".

    `ref_prefix` must not itself contain "#" -- a real repo-relative path
    never does, so this is a caller-contract assertion, not a real-world
    case: a downstream ref parser (e.g. a citation-link builder recovering
    the path via `ref.split("#")[0]`) would otherwise silently see a
    malformed two-`#` ref for a windowed chunk instead of a caller bug
    failing loudly here.
    """
    assert "#" not in ref_prefix, f"ref_prefix must not contain '#': {ref_prefix!r}"

    lines = text.splitlines()
    total = len(lines)

    if total <= _CHUNK_WINDOW_LINES:
        return [{"ref": ref_prefix, "text": text}]

    stride = _CHUNK_WINDOW_LINES - _CHUNK_OVERLAP_LINES
    chunks = []
    start = 0  # 0-indexed line offset into `lines`
    while start < total:
        end = min(start + _CHUNK_WINDOW_LINES, total)
        window_lines = lines[start:end]
        ref = f"{ref_prefix}#L{start + 1}-L{end}"
        chunks.append({"ref": ref, "text": "\n".join(window_lines) + "\n"})
        if end == total:
            break
        start += stride
    return chunks


def classify_file(path: Path, root: Path) -> Optional[str]:
    """Decide whether `path` (a file somewhere under `root`) should be
    ingested, and under which citation source tag.

    Returns "code" / "doc" / "config" if the file should be ingested, or None
    if it should be skipped. Pure and offline -- no filesystem writes, no
    network. Per-file only: does not enforce the total-byte ingest budget
    (that's `_MAX_TOTAL_BYTES`, a stateful concern for the caller walking a
    tree); it only rejects a file already larger than `_MAX_FILE_BYTES`.

    `root` lets deny-listed directory segments (e.g. `node_modules`) be
    checked against the path relative to the repo root, matching how
    `fetch_code` already computes `path.relative_to(root)` for citation refs.
    Contract: `path` must be under `root` -- callers walk a tree (e.g. via
    `rglob`) rooted there. `path.relative_to(root)` raises `ValueError` on a
    misuse (a path outside the walked root) rather than silently falling back
    to scanning the absolute path's own segments, which could spuriously
    match a deny-listed name (e.g. a real filesystem prefix containing
    `vendor` or `.git`) and misclassify a file relative to the wrong tree.

    Extension matching is case-sensitive by design: `Script.PY` or
    `README.MD` classify as None. Uppercase extensions are rare enough on
    real repos/case-sensitive filesystems that special-casing them isn't
    worth it at Phase-1 scale.
    """
    rel = path.relative_to(root)

    if set(rel.parts) & _DENY_DIR_SEGMENTS:
        return None

    name = path.name
    if name in _DENY_FILENAMES:
        return None
    if name.endswith(_DENY_FILENAME_SUFFIXES):
        return None

    source = _EXTENSION_SOURCES.get(path.suffix)
    if source is None:
        return None

    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
    except OSError:
        return None

    try:
        with path.open("rb") as f:
            head = f.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return None
    if b"\x00" in head:
        return None

    return source


def _git_env(token=None):
    """Subprocess env for git. A token authenticates via GIT_CONFIG_* env
    (http.extraHeader with Basic x-access-token) -- never argv (visible in ps),
    never the URL (lands in git config). The token is never logged."""
    env = dict(os.environ)
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        })
    return env


def _gh_env(token=None):
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token  # per-call, never the server's ambient identity
    return env


def _safe_code_dir(clone_dir, code_dir):
    """Resolve code_dir inside clone_dir; refuse anything that escapes it
    (absolute paths, ``..``). Prevents ingesting files outside the clone."""
    root = Path(clone_dir).resolve()
    target = (root / code_dir).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"code_dir escapes the clone: {code_dir!r}")
    return target


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Ingest a public GitHub repo into the corpus")
    p.add_argument("--repo", default=REPO, help="owner/name of a public repo")
    p.add_argument("--commit", default=None, help="commit SHA to pin (default: repo HEAD)")
    p.add_argument("--code-dir", default=None,
                    help="subtree to walk (default: 'llm' for the pinned repo, "
                         "the whole clone root for any other repo)")
    return p.parse_args(argv)


def resolve_commit(repo: str, commit, token=None) -> str:
    """Explicit --commit wins; the default repo without one keeps the pinned SHA
    (reproducible board); any other repo resolves its HEAD via git ls-remote."""
    if commit:
        return commit
    if repo == REPO:
        return COMMIT
    out = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD"],
        check=True, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT,
        env=_git_env(token),
    ).stdout
    return out.split()[0]


def resolve_code_dir(repo: str, code_dir) -> str:
    """Explicit --code-dir wins; the default repo without one keeps its
    historical 'llm' subtree (byte-scope-reproducible board -- same repo,
    commit, and subtree, per the resolved Brick A ambiguity); any other repo
    walks the whole clone root. Mirrors resolve_commit's shape exactly."""
    if code_dir:
        return code_dir
    if repo == REPO:
        return "llm"
    return "."


def _gh_json(args, token=None):
    out = subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT,
        env=_gh_env(token),
    ).stdout
    return json.loads(out) if out.strip() else None


def fetch_prs(repo, token=None):
    nums = [pr["number"] for pr in _gh_json(
        ["pr", "list", "-R", repo, "--state", "all", "--limit", str(PR_LIMIT), "--json", "number"],
        token=token,
    )]
    chunks, issue_ids = [], set()
    for n in nums:
        pr = _gh_json(["pr", "view", str(n), "-R", repo, "--json", "title,body,closingIssuesReferences"], token=token)
        text = f"{pr['title']}\n\n{pr.get('body') or ''}"
        chunks.append({"ref": f"pr:{n}", "source": "pr", "text": text})
        for ref in pr.get("closingIssuesReferences", []):
            issue_ids.add(ref["number"])
        for m in ISSUE_REF.findall(pr.get("body") or ""):
            issue_ids.add(int(m))
    return chunks, issue_ids


def fetch_all_issue_ids(repo, token=None):
    """All issue numbers (open AND closed) up to ISSUE_LIMIT, unfiltered by
    whether anything links to them -- closes the coverage gap where a
    standalone, never-linked issue (e.g. an open bug report) was invisible to
    fetch_issues because fetch_prs only ever surfaces issues mentioned by a
    merged PR."""
    items = _gh_json(
        ["issue", "list", "-R", repo, "--state", "all", "--limit", str(ISSUE_LIMIT), "--json", "number"],
        token=token,
    )
    return {it["number"] for it in items}


def fetch_issues(repo, issue_ids, token=None):
    chunks = []
    for n in sorted(issue_ids):
        try:
            it = _gh_json(["issue", "view", str(n), "-R", repo, "--json", "title,body"], token=token)
        except subprocess.CalledProcessError:
            continue  # number was a PR, not an issue
        chunks.append({"ref": f"issue:{n}", "source": "issue", "text": f"{it['title']}\n\n{it.get('body') or ''}"})
    return chunks


def fetch_code(repo, commit, code_dir, token=None):
    # Full clone keeps the pinned-commit checkout byte-reproducible (the eval
    # board depends on it); timeouts bound the clone, size caps bound memory so a
    # hostile/huge repo can't hang or OOM us.
    chunks, total = [], 0
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{repo}.git", d],
                       check=True, timeout=_SUBPROCESS_TIMEOUT, env=_git_env(token))
        subprocess.run(["git", "-C", d, "checkout", "--quiet", commit],
                       check=True, timeout=_SUBPROCESS_TIMEOUT, env=_git_env(token))
        # Resolve once, consistently: _safe_code_dir already resolves its own
        # return value, and on macOS /var is a symlink to /private/var, so an
        # unresolved `d` used in relative_to() below would mismatch against
        # paths yielded by the resolved `base` -- resolving `d` too keeps refs
        # relative to the clone root (unchanged format) while fixing that.
        root = Path(d).resolve()
        base = _safe_code_dir(d, code_dir)
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            source = classify_file(path, root)
            if source is None:
                continue  # not ingestable (deny-listed, wrong extension, binary, oversized, ...)
            if total > _MAX_TOTAL_BYTES or len(chunks) >= _MAX_TOTAL_CHUNKS:
                # Stop once we've read enough across all sources, by bytes OR by
                # chunk count. Not silent: a truncated corpus must not read as
                # "covered everything" (esp. before sharing with testers).
                why = "byte" if total > _MAX_TOTAL_BYTES else "chunk"
                print(f"ingest: {why} cap reached; truncating code walk of {repo!r} "
                      f"at {len(chunks)} chunks / {total} bytes", file=sys.stderr)
                break
            rel = path.relative_to(root).as_posix()
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue  # e.g. vanished mid-walk, permission change, a dangling
                          # symlink/socket/fifo classify_file's is_file() let through
            total += len(text.encode("utf-8", "replace"))
            for sub in chunk_text(text, f"{source}:{rel}"):
                chunks.append({"ref": sub["ref"], "source": source, "text": sub["text"]})
    return chunks


def ingest_repo(repo, out_dir, commit=None, code_dir="llm", token=None):
    """Fetch a repo and write chunks.jsonl + meta.json into out_dir.

    Returns counts keyed by every source tag actually ingested -- always "pr"
    and "issue" (0 if none), "code" (0 if none, kept present for backward
    compatibility), plus "doc"/"config" whenever fetch_code's whole-repo walk
    finds files of those kinds. Reusable by the CLI (default corpus) and the
    demo's per-repo cache. Network (gh + git); public repos by default. An
    optional caller token (never from the CLI -- programmatic callers only)
    authenticates git/gh as that caller for a private repo, via env only."""
    commit = resolve_commit(repo, commit, token=token)
    prs, issue_ids = fetch_prs(repo, token=token)
    # Union with ALL issue numbers (open+closed), not just ones a merged PR
    # happens to link -- closes the standalone-issue coverage gap (Brick B1)
    # without touching fetch_prs' own linked-issue detection.
    issue_ids = issue_ids | fetch_all_issue_ids(repo, token=token)
    issues = fetch_issues(repo, issue_ids, token=token)
    code = fetch_code(repo, commit, code_dir, token=token)
    all_chunks = prs + issues + code
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "chunks.jsonl").open("w") as f:
        for c in all_chunks:
            f.write(json.dumps(c) + "\n")
    # code may now yield "code"/"doc"/"config" chunks (Task A3's whole-repo
    # walk), not just "code" -- bucket by whatever source tags actually
    # appeared, so every chunk's source is reflected in the counts.
    counts = {"pr": len(prs), "issue": len(issues)}
    for c in code:
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    counts.setdefault("code", 0)
    write_meta(out_dir / "meta.json", repo=repo, commit=commit, code_dir=code_dir, counts=counts)
    return counts


def main(argv=None):
    args = parse_args(argv)
    code_dir = resolve_code_dir(args.repo, args.code_dir)
    counts = ingest_repo(args.repo, OUT.parent, commit=args.commit, code_dir=code_dir)
    total = sum(counts.values())
    breakdown = ", ".join(f"{n} {k}" for k, n in counts.items())
    print(f"wrote {total} chunks ({breakdown}) from {args.repo} -> {OUT}")


if __name__ == "__main__":
    main()
