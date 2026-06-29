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
import json
import re
import subprocess
import tempfile
from pathlib import Path

from .corpus_meta import write_meta

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"
PR_LIMIT = 200  # recent merged PRs; the 6 gold PRs are well within this range
OUT = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"
META = Path(__file__).resolve().parent / "corpus" / "meta.json"

ISSUE_REF = re.compile(r"#(\d+)")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Ingest a public GitHub repo into the corpus")
    p.add_argument("--repo", default=REPO, help="owner/name of a public repo")
    p.add_argument("--commit", default=None, help="commit SHA to pin (default: repo HEAD)")
    p.add_argument("--code-dir", default="llm", help="subtree to glob for *.py")
    return p.parse_args(argv)


def resolve_commit(repo: str, commit) -> str:
    """Explicit --commit wins; the default repo without one keeps the pinned SHA
    (reproducible board); any other repo resolves its HEAD via git ls-remote."""
    if commit:
        return commit
    if repo == REPO:
        return COMMIT
    out = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD"],
        check=True, capture_output=True, text=True,
    ).stdout
    return out.split()[0]


def _gh_json(args):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else None


def fetch_prs(repo):
    nums = [pr["number"] for pr in _gh_json(
        ["pr", "list", "-R", repo, "--state", "merged", "--limit", str(PR_LIMIT), "--json", "number"]
    )]
    chunks, issue_ids = [], set()
    for n in nums:
        pr = _gh_json(["pr", "view", str(n), "-R", repo, "--json", "title,body,closingIssuesReferences"])
        text = f"{pr['title']}\n\n{pr.get('body') or ''}"
        chunks.append({"ref": f"pr:{n}", "source": "pr", "text": text})
        for ref in pr.get("closingIssuesReferences", []):
            issue_ids.add(ref["number"])
        for m in ISSUE_REF.findall(pr.get("body") or ""):
            issue_ids.add(int(m))
    return chunks, issue_ids


def fetch_issues(repo, issue_ids):
    chunks = []
    for n in sorted(issue_ids):
        try:
            it = _gh_json(["issue", "view", str(n), "-R", repo, "--json", "title,body"])
        except subprocess.CalledProcessError:
            continue  # number was a PR, not an issue
        chunks.append({"ref": f"issue:{n}", "source": "issue", "text": f"{it['title']}\n\n{it.get('body') or ''}"})
    return chunks


def fetch_code(repo, commit, code_dir):
    chunks = []
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{repo}.git", d], check=True)
        subprocess.run(["git", "-C", d, "checkout", "--quiet", commit], check=True)
        for path in sorted(Path(d, code_dir).rglob("*.py")):
            rel = path.relative_to(d).as_posix()
            chunks.append({"ref": f"code:{rel}", "source": "code", "text": path.read_text(errors="replace")})
    return chunks


def ingest_repo(repo, out_dir, commit=None, code_dir="llm"):
    """Fetch a public repo and write chunks.jsonl + meta.json into out_dir.

    Returns the {pr, issue, code} counts. Reusable by the CLI (default corpus)
    and the demo's per-repo cache. Network (gh + git); public repos only."""
    commit = resolve_commit(repo, commit)
    prs, issue_ids = fetch_prs(repo)
    issues = fetch_issues(repo, issue_ids)
    code = fetch_code(repo, commit, code_dir)
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
