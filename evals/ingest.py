# evals/ingest.py
"""Generate the Phase 1 corpus from simonw/llm into evals/corpus/chunks.jsonl.

One-time generation tool (needs `gh` + `git`). Sources, per the locked Phase 1
scope: PR descriptions + linked issues (the "why"), and Python source files
(distractors + future code-question evidence). Review comments are deferred:
the repo is solo-maintained. Run from the repo root:

    python3 -m evals.ingest

The committed chunks.jsonl is the pinned corpus; re-running may pull newer PRs,
but the artifact in git is the source of truth for evals.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"
PR_LIMIT = 200  # recent merged PRs; the 6 gold PRs are well within this range
OUT = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"

ISSUE_REF = re.compile(r"#(\d+)")


def _gh_json(args):
    out = subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout
    return json.loads(out) if out.strip() else None


def fetch_prs():
    nums = [pr["number"] for pr in _gh_json(
        ["pr", "list", "-R", REPO, "--state", "merged", "--limit", str(PR_LIMIT), "--json", "number"]
    )]
    chunks, issue_ids = [], set()
    for n in nums:
        pr = _gh_json(["pr", "view", str(n), "-R", REPO, "--json", "title,body,closingIssuesReferences"])
        text = f"{pr['title']}\n\n{pr.get('body') or ''}"
        chunks.append({"ref": f"pr:{n}", "source": "pr", "text": text})
        for ref in pr.get("closingIssuesReferences", []):
            issue_ids.add(ref["number"])
        for m in ISSUE_REF.findall(pr.get("body") or ""):
            issue_ids.add(int(m))
    return chunks, issue_ids


def fetch_issues(issue_ids):
    chunks = []
    for n in sorted(issue_ids):
        try:
            it = _gh_json(["issue", "view", str(n), "-R", REPO, "--json", "title,body"])
        except subprocess.CalledProcessError:
            continue  # number was a PR, not an issue
        chunks.append({"ref": f"issue:{n}", "source": "issue", "text": f"{it['title']}\n\n{it.get('body') or ''}"})
    return chunks


def fetch_code():
    chunks = []
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "clone", "--quiet", f"https://github.com/{REPO}.git", d], check=True)
        subprocess.run(["git", "-C", d, "checkout", "--quiet", COMMIT], check=True)
        for path in sorted(Path(d, "llm").rglob("*.py")):
            rel = path.relative_to(d).as_posix()
            chunks.append({"ref": f"code:{rel}", "source": "code", "text": path.read_text(errors="replace")})
    return chunks


def main():
    prs, issue_ids = fetch_prs()
    issues = fetch_issues(issue_ids)
    code = fetch_code()
    all_chunks = prs + issues + code
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as f:
        for c in all_chunks:
            f.write(json.dumps(c) + "\n")
    print(f"wrote {len(all_chunks)} chunks ({len(prs)} pr, {len(issues)} issue, {len(code)} code) -> {OUT}")


if __name__ == "__main__":
    main()
