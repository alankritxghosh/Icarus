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
import tempfile
from pathlib import Path
from typing import Optional

from .corpus_meta import write_meta

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"
PR_LIMIT = 200  # recent merged PRs; the 6 gold PRs are well within this range
OUT = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"
META = Path(__file__).resolve().parent / "corpus" / "meta.json"

ISSUE_REF = re.compile(r"#(\d+)")

# Resource bounds so a huge or hostile repo can't fill disk / hang / OOM.
_SUBPROCESS_TIMEOUT = 120       # seconds, per git/gh call
_MAX_FILE_BYTES = 512 * 1024    # skip any single file bigger than this
_MAX_TOTAL_BYTES = 25 * 1024 * 1024  # stop reading code past this total

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
    """
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path  # not under root; still check by name/extension below

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
    p.add_argument("--code-dir", default="llm", help="subtree to glob for *.py")
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


def _gh_json(args, token=None):
    out = subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT,
        env=_gh_env(token),
    ).stdout
    return json.loads(out) if out.strip() else None


def fetch_prs(repo, token=None):
    nums = [pr["number"] for pr in _gh_json(
        ["pr", "list", "-R", repo, "--state", "merged", "--limit", str(PR_LIMIT), "--json", "number"],
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
        for path in sorted(base.rglob("*.py")):
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue  # skip an oversized single file
            if total > _MAX_TOTAL_BYTES:
                break  # stop once we've read enough code
            rel = path.relative_to(root).as_posix()
            text = path.read_text(errors="replace")
            total += len(text.encode("utf-8", "replace"))
            chunks.append({"ref": f"code:{rel}", "source": "code", "text": text})
    return chunks


def ingest_repo(repo, out_dir, commit=None, code_dir="llm", token=None):
    """Fetch a repo and write chunks.jsonl + meta.json into out_dir.

    Returns the {pr, issue, code} counts. Reusable by the CLI (default corpus)
    and the demo's per-repo cache. Network (gh + git); public repos by default.
    An optional caller token (never from the CLI -- programmatic callers only)
    authenticates git/gh as that caller for a private repo, via env only."""
    commit = resolve_commit(repo, commit, token=token)
    prs, issue_ids = fetch_prs(repo, token=token)
    issues = fetch_issues(repo, issue_ids, token=token)
    code = fetch_code(repo, commit, code_dir, token=token)
    all_chunks = prs + issues + code
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "chunks.jsonl").open("w") as f:
        for c in all_chunks:
            f.write(json.dumps(c) + "\n")
    counts = {"pr": len(prs), "issue": len(issues), "code": len(code)}
    write_meta(out_dir / "meta.json", repo=repo, commit=commit, code_dir=code_dir, counts=counts)
    return counts


def main(argv=None):
    args = parse_args(argv)
    counts = ingest_repo(args.repo, OUT.parent, commit=args.commit, code_dir=args.code_dir)
    total = sum(counts.values())
    print(f"wrote {total} chunks ({counts['pr']} pr, {counts['issue']} issue, {counts['code']} code) "
          f"from {args.repo} -> {OUT}")


if __name__ == "__main__":
    main()
