# evals/test_writer_uses_evidence.py
"""The writer-side board: when retrieval delivers the decisive evidence, does
the answer USE it?

WHY THIS IS A SEPARATE BOARD. `evals/test_description_recall.py` measures where
a gold ref RANKS. Building it corrected a diagnosis: on the live case that
started this work, retrieval ranked the decisive chunk **first** and the answer
was written from something else. Ranking was not the defect there; what happened
after ranking was. Two failures wearing the same face -- "Icarus did not tell me"
-- and they need opposite fixes, so they get separate boards.

THE CASE. `simonw/sqlite-utils` issue 841 carries a maintainer comment:

    "(So don't let your agent work on this, I'll do this if and when 5 becomes a
     thing in the future.)"

Asked "should I fix rows_where and delete_where to raise an error on a
non-existent table?", the live brain answered from `issue:315` and
`db.py#L3680-L3705` -- correct as far as it went, and it omitted the one
sentence that changes what a caller does next. `issue:841` was rank 1.

WHAT IS MEASURED. Two things, deliberately separate, because they fail
independently:

  * CITED -- is the gold ref among the answer's citations? Deterministic, and
    the weaker of the two: a writer can cite a chunk and still not convey what
    matters in it.
  * CONVEYED -- does the prose actually carry the decisive fact? Semantic, so it
    is scored by the existing judge (evals/judge.py) against a reference answer,
    exactly as answer-correctness is scored on the main board. The judge is a
    quality dial and touches no gate here either.

DISCLOSED LIMITS.
  * Live, non-deterministic, and it costs money: needs GEMINI_PAID_API_KEY, and
    self-skips without it. Two runs can disagree; that is a property of the
    thing being measured, not a flaw in measuring it, so the report prints per
    case rather than reducing to one number.
  * It measures the SERVING path end to end (retrieve -> writer -> gate), so a
    retrieval regression will also turn it red. The `evidence_was_retrieved`
    check exists to tell those apart at a glance.
  * A judge is not truth. It replaces "a human read it" with "a different model
    read it", which is weaker, and it is why CITED is reported beside CONVEYED
    rather than being replaced by it.
"""
import json
import os
import unittest
from pathlib import Path

from .corpus import Chunk
from .env_file import load_env_file
from .judge import Judge
from .pipeline import GatedPipeline
from .provider import make_provider
from .query_normalize import build_vocabulary
from .retriever import (
    HybridRetriever,
    LexicalRetriever,
    NormalizingRetriever,
    SemanticRetriever,
)

_HERE = Path(__file__).resolve().parent
_CORPUS = _HERE / "fixtures" / "recall" / "sqlite_utils_chunks.jsonl"

# Every case is real: asked live on 2026-08-21 against simonw/sqlite-utils.
# `must_convey` is the reference answer the judge scores against -- the fact a
# caller needs in order to act correctly, not a paraphrase of the whole chunk.
CASES = [
    {
        "id": "w01",
        "question": ("Should I fix rows_where and delete_where to raise an error "
                     "on a non-existent table?"),
        "gold_ref": "issue:841",
        "must_convey": ("No. The maintainer has deliberately held this change for a "
                        "future version 5 because it breaks compatibility, and has "
                        "explicitly asked that agents not work on it."),
    },
    {
        "id": "w02",
        "question": "Is it safe to change how delete_where handles a missing table?",
        "gold_ref": "issue:841",
        "must_convey": ("Not without checking with the maintainer: the behaviour is "
                        "known and intentional for now, with the breaking change "
                        "deferred to a future version 5."),
    },
    {
        "id": "w03",
        "question": "Does delete_where commit its changes in the 3.x series?",
        "gold_ref": "issue:815",
        "must_convey": ("No -- it fails to commit in 3.x. That was fixed in 4.0 and the "
                        "fix is wanted as a 3.x dot-release backport."),
    },
]


def _load_chunks():
    return [
        Chunk(**json.loads(line))
        for line in _CORPUS.read_text().splitlines()
        if line.strip()
    ]


def _pipeline(chunks):
    from .provider import make_embedding_provider

    embedder = make_embedding_provider("local")
    hybrid = HybridRetriever(LexicalRetriever(chunks), SemanticRetriever(chunks, embedder))
    retriever = NormalizingRetriever(hybrid, build_vocabulary(chunks))
    # gemini-paid is the one production writer; measuring any other one would
    # measure a writer nobody is served by.
    return GatedPipeline(retriever, chunks, make_provider("gemini-paid"))


class WriterUsesRetrievedEvidence(unittest.TestCase):
    """RED where the writer walks past evidence retrieval put in front of it."""

    @classmethod
    def setUpClass(cls):
        load_env_file(".env")
        try:
            import fastembed  # noqa: F401
        except ImportError:                          # pragma: no cover
            raise unittest.SkipTest("fastembed not installed")
        if not os.environ.get("GEMINI_PAID_API_KEY"):
            raise unittest.SkipTest("GEMINI_PAID_API_KEY not set; live board")
        if not _CORPUS.exists():                     # pragma: no cover
            raise unittest.SkipTest("fixture corpus missing")

        chunks = _load_chunks()
        cls.present = {c.ref for c in chunks}
        pipeline = _pipeline(chunks)
        judge = Judge(make_provider("gemini")) if os.environ.get("GEMINI_API_KEY") else None
        cls.judge_available = judge is not None

        cls.rows = []
        for case in CASES:
            result = pipeline.answer(case["question"])
            retrieved = case["gold_ref"] in (result.retrieved or [])
            cited = case["gold_ref"] in (result.citations or [])
            conveyed = None
            if judge is not None and result.verdict == "answer":
                conveyed = judge.is_correct(
                    case["question"], case["must_convey"], result.answer)
            cls.rows.append({
                "id": case["id"], "gold": case["gold_ref"], "verdict": result.verdict,
                "retrieved": retrieved, "cited": cited, "conveyed": conveyed,
                "answer": (result.answer or "")[:160],
            })

    def test_the_evidence_was_retrieved(self):
        """GREEN, and the diagnostic that keeps this board honest: if this fails,
        the board below is measuring a RETRIEVAL regression and belongs in
        test_description_recall.py, not here."""
        for row in self.rows:
            self.assertTrue(
                row["retrieved"],
                f"{row['id']}: {row['gold']} was not retrieved at all -- this is a "
                f"recall failure, not a writer failure")

    def test_the_answer_cites_the_decisive_evidence(self):
        """GREEN on this fixture, and kept as the diagnostic that isolates the
        failure below. Measured 2026-08-21: all three cases cite the gold ref,
        so the writer is NOT ignoring the evidence -- it reads it and draws the
        wrong actionable conclusion, which is a strictly worse failure than
        skipping it and a strictly harder one to see.

        The live brain, on its own larger index of the same repository, cited
        `issue:315` instead for w01. Same question, different corpus, different
        citation: that gap is itself worth watching, and it is why the case set
        records the fixture commit."""
        misses = [f"{r['id']} (wanted {r['gold']}, verdict={r['verdict']})"
                  for r in self.rows if not r["cited"]]
        self.assertEqual(
            [], misses,
            "the decisive evidence was retrieved and not cited:\n  " + "\n  ".join(misses))

    def test_the_answer_conveys_the_decisive_fact(self):
        """RED, and this is the finding. Measured 2026-08-21 on w01, citing
        `issue:841` correctly:

            "Yes, the project maintainer intends to update `rows_where()` and
             `delete_where()` to raise an error when called on a non-existent
             table, though this change is being held for a future v5 release to
             avoid breaking compatibility."

        Every clause is true and it opens with **Yes** to "should I fix this?",
        when the maintainer's answer in the cited chunk is don't. An agent acts
        on the first word. The citation resolves, so groundedness passes it --
        the honesty gate is working exactly as designed and cannot catch this,
        because the defect is not a false claim, it is a true summary that
        inverts what the caller should do.

        A citation the reader has to open is not the same as being told."""
        if not self.judge_available:                 # pragma: no cover
            self.skipTest("GEMINI_API_KEY not set; judge unavailable")
        misses = [f"{r['id']}: {r['answer']!r}" for r in self.rows if r["conveyed"] is not True]
        self.assertEqual(
            [], misses,
            "the answer did not carry the fact a caller needs to act on:\n  "
            + "\n  ".join(misses))

    def test_board_report(self):
        """Always passes. A live board that only prints PASS/FAIL cannot show a
        change moving a case from 'not retrieved' to 'retrieved but ignored',
        which is the whole distinction this board exists to draw."""
        lines = ["", "writer-side board (did the answer use what retrieval found?)"]
        for r in self.rows:
            conveyed = {True: "yes", False: "no", None: "n/a"}[r["conveyed"]]
            lines.append(
                f"  {r['id']}  {r['gold']:<12} verdict={r['verdict']:<8} "
                f"retrieved={'y' if r['retrieved'] else 'n'} "
                f"cited={'y' if r['cited'] else 'n'} conveyed={conveyed}")
        print("\n".join(lines))


if __name__ == "__main__":                           # pragma: no cover
    unittest.main()
