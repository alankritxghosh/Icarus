"""Run the Phase 1 eval board.

    python -m evals.run                 # uses the stub pipeline + the verified set
    python -m evals.run --k 10          # change retrieval cut-off

Exit code is 0 only when the honesty gates hold (groundedness and abstention
recall at 100%). A broken gate exits non-zero so CI can never go green on a bluff.
Quality below target does NOT fail the build -- it is the expected red baseline
until the real pipeline lands.
"""

import argparse
import json
import sys
from pathlib import Path

from .grader import grade
from .corpus import load_chunks
from .retriever import LexicalRetriever
from .pipeline import StubPipeline, RetrievalPipeline

DEFAULT_SET = Path(__file__).resolve().parent / "phase1_questions.json"
CORPUS = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"


def _fmt(value) -> str:
    if value is None:
        return "  n/a"
    return f"{value:5.1f}%"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Icarus Phase 1 eval board")
    parser.add_argument("--questions", type=Path, default=DEFAULT_SET, help="labelled set JSON")
    parser.add_argument("--k", type=int, default=5, help="retrieval recall cut-off")
    parser.add_argument("--pipeline", choices=["stub", "retrieval"], default="retrieval",
                        help="which pipeline to grade")
    args = parser.parse_args(argv)

    data = json.loads(args.questions.read_text())
    questions = data["questions"]
    if args.pipeline == "retrieval":
        pipeline = RetrievalPipeline(LexicalRetriever(load_chunks(CORPUS)))
        name = "RetrievalPipeline"
    else:
        pipeline = StubPipeline()
        name = "StubPipeline"
    board = grade(questions, pipeline, k=args.k)

    corpus = data.get("corpus", {})
    c = board["counts"]
    print("=" * 64)
    print(f"Icarus -- Phase 1 eval board   (pipeline: {name})")
    print(f"corpus: {corpus.get('repo', '?')} @ {corpus.get('commit', '?')[:12]}")
    print(f"questions: {c['total']}  ({c['answerable']} answerable, {c['unanswerable']} unanswerable)")
    print("=" * 64)

    print("\nGATES (must be 100% -- a drop here is a bluff):")
    print(f"  groundedness        {_fmt(board['gates']['groundedness'])}")
    print(f"  abstention recall   {_fmt(board['gates']['abstention_recall'])}")

    q = board["quality"]
    print(f"\nQUALITY (drive up, never at a gate's expense)   k={board['k']}:")
    print(f"  abstention precision {_fmt(q['abstention_precision'])}")
    print(f"  retrieval recall@k   {_fmt(q['retrieval_recall_at_k'])}")
    print(f"  citation correctness {_fmt(q['citation_correctness'])}")
    print(f"  answer correctness   {board['answer_correctness']}")

    print(f"\nSTATUS: {board['status']}")
    print("=" * 64)

    # Gate failure is the only thing that fails the build.
    return 0 if board["gates_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
