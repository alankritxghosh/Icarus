"""Stage 3 mechanics: index a prospect's repo, ask it questions, grade answers.

Sales tooling. It USES Icarus as a read-only library and writes only into its
own scratch dir -- it never touches evals/corpus, and never runs the
`evals.ingest` CLI (which overwrites the committed eval board).

    python3 sales/ask_repo.py index OWNER/REPO
    python3 sales/ask_repo.py digest OWNER/REPO
    python3 sales/ask_repo.py ask   OWNER/REPO questions.json answers.json

Run with .venv/bin/python. System Python has no fastembed and the pipeline
degrades SILENTLY to lexical-only, which measurably weakens every answer.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SCRATCH = Path(__file__).resolve().parent.parent / "outputs" / "leads" / "corpora"
HISTORY_SOURCES = {"pr", "commit", "issue"}
# a PR body containing one of these actually records a REASON, not just a title
REASON_WORDS = re.compile(
    r"\b(because|instead of|root cause|turned out|regression|the reason|"
    r"we chose|rather than|caused by|to avoid|workaround)\b", re.I)


def corpus_dir(repo):
    return SCRATCH / repo.replace("/", "__")


def index(repo):
    """Ingest the whole repo into our own scratch dir. Skips if already there."""
    out = corpus_dir(repo)
    if (out / "chunks.jsonl").exists():
        print(f"already indexed: {out}")
        return out
    import os
    os.environ.setdefault("ICARUS_AST_CHUNKING", "1")
    from evals.ingest import ingest_repo
    out.mkdir(parents=True, exist_ok=True)
    counts = ingest_repo(repo, str(out), code_dir=".")
    print(f"indexed {repo}: {counts}")
    return out


def digest(repo, limit=40):
    """Reason-bearing PR/issue openers -- the raw material for questions.

    Questions must come from history that records a REASON. Inventing them from
    the README is what produces a demo full of abstentions.
    """
    rows = []
    for line in (corpus_dir(repo) / "chunks.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("source") not in ("pr", "issue") or len(d.get("text", "")) < 400:
            continue
        if not REASON_WORDS.search(d["text"]):
            continue
        rows.append({"ref": d["ref"], "source": d["source"],
                     "opener": d["text"].split("\n")[0][:110]})
    rows = rows[:limit]
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return rows


def ask(repo, questions_path, out_path):
    """Ask each question through the real serving pipeline and grade the answer.

    ONE retrieval configuration, one pass. Never re-run with different settings
    and keep whichever flatters the result.
    """
    from evals.env_file import load_env_file
    from demo import library
    from demo.library import _build_gated_pipeline

    # Serving budgets the embed at 0.1s/chunk so a slow host can't wedge a
    # request; this Mac measured ~0.11s/chunk and a 18,120-chunk prospect died
    # at 16,495. Nobody is waiting on a request here, so raise OUR ceiling.
    # Local to this process -- the product's constant is untouched.
    library._EMBED_SECONDS_PER_CHUNK = 0.5
    # the writer key lives in the gitignored .env, same as serving
    load_env_file(Path(__file__).resolve().parent.parent / ".env")
    questions = json.loads(Path(questions_path).read_text())
    pipeline = _build_gated_pipeline(str(corpus_dir(repo)))

    results = []
    for q in questions:
        text = q if isinstance(q, str) else q["question"]
        r = pipeline.answer(text)
        sources = {c.split(":")[0] for c in r.citations}
        results.append({
            "question": text,
            "verdict": r.verdict,
            "answer": r.answer,
            "citations": r.citations,
            # HISTORY = reconstructed from PRs/issues/commits, the product working.
            # doc-only = read out of a file they wrote, which proves nothing to them.
            "grade": ("unknown" if r.verdict != "answer" else
                      "HISTORY" if sources & HISTORY_SOURCES else "doc-only"),
        })
        print(f"  [{results[-1]['grade']:8}] {text[:70]}")

    Path(out_path).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    counts = {g: sum(1 for r in results if r["grade"] == g)
              for g in ("HISTORY", "doc-only", "unknown")}
    print(f"\n{counts} -> {out_path}")
    return results


def self_check():
    assert corpus_dir("a/b").name == "a__b"
    assert REASON_WORDS.search("this was caused by a stale cache")
    assert REASON_WORDS.search("We chose Rust here")
    assert not REASON_WORDS.search("bump deps to 1.2.3")
    hist = {"pr", "code"} & HISTORY_SOURCES
    assert hist == {"pr"}
    assert not ({"doc"} & HISTORY_SOURCES)
    print("self-check ok")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("index", "digest"):
        s = sub.add_parser(name)
        s.add_argument("repo")
    a = sub.add_parser("ask")
    a.add_argument("repo")
    a.add_argument("questions")
    a.add_argument("out")
    sub.add_parser("self-check")

    args = p.parse_args()
    if args.cmd == "index":
        index(args.repo)
    elif args.cmd == "digest":
        digest(args.repo)
    elif args.cmd == "ask":
        ask(args.repo, args.questions, args.out)
    else:
        self_check()


if __name__ == "__main__":
    main()
