# evals/test_investigation_eval.py
"""The live investigation board: the REAL pipeline, corpus, retriever and writer.

Self-skips without `GEMINI_PAID_API_KEY` (and without fastembed or the committed
corpus), exactly like `evals/test_paid_writer_eval.py`. It is the only test here
that costs money, and it is the only one that can tell us whether the
investigation engine is any GOOD rather than merely correct.

Run it deliberately:

    GEMINI_PAID_API_KEY=... python3 -m unittest evals.test_investigation_eval -v

The regression test at the bottom needs no key and always runs: `/ask`'s own
behaviour must be byte-identical after all of this, and that is worth checking
on every single run rather than only when someone remembers to pay for one.
"""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .entities import build_entity_index
from .investigation import Budget
from .investigation_grader import format_board, gates_hold, grade_investigations
from .investigator import conclude, investigate
from .pipeline import GatedPipeline
from .provider import make_provider
from .retriever import HybridRetriever, LexicalRetriever, SemanticRetriever
from .query_normalize import build_vocabulary

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus" / "chunks.jsonl"
QUESTIONS = ROOT / "investigation_questions.json"


def _load_questions():
    return json.loads(QUESTIONS.read_text())["questions"]


def _semantic_available():
    try:
        import fastembed  # noqa: F401
    except Exception:
        return False
    return True


@unittest.skipUnless(os.environ.get("GEMINI_PAID_API_KEY"),
                     "needs GEMINI_PAID_API_KEY (the one production writer)")
@unittest.skipUnless(CORPUS.exists(), "needs the committed corpus")
class LiveInvestigationBoardTests(unittest.TestCase):
    """Every dimension in the brief that needs a real model to mean anything."""

    @classmethod
    def setUpClass(cls):
        from .provider import make_embedding_provider
        from .retriever import NormalizingRetriever
        cls.chunks = load_chunks(CORPUS)
        lexical = LexicalRetriever(cls.chunks)
        if _semantic_available():
            embedder = make_embedding_provider("local")
            retriever = HybridRetriever(lexical, SemanticRetriever(cls.chunks, embedder))
        else:
            retriever = lexical
        retriever = NormalizingRetriever(retriever, build_vocabulary(cls.chunks))
        cls.provider = make_provider("gemini-paid")
        cls.pipeline = GatedPipeline(retriever, cls.chunks, cls.provider)
        cls.entities = build_entity_index(cls.chunks)

    def _run(self, question):
        texts = {}
        inv = investigate(question["question"], self.pipeline, self.entities,
                          self.provider, budget=Budget(max_steps=10, max_writer_calls=10),
                          texts=texts)
        return inv, conclude(inv, self.provider, texts=texts), texts

    def test_the_board_holds_every_gate(self):
        board = grade_investigations(_load_questions(), self._run)
        print("\n" + format_board(board))
        self.assertTrue(gates_hold(board), board["gates"])

    def test_an_unrecorded_reason_is_still_an_honest_unknown(self):
        # An investigation has strictly MORE ways to talk itself into an answer
        # than a single retrieval does -- more evidence, more rounds, a
        # synthesis step. This is the question that proves the extra machinery
        # did not buy helpfulness with a bluff.
        for q in _load_questions():
            if q["label"] != "unanswerable":
                continue
            _inv, result, _texts = self._run(q)
            self.assertEqual(result.verdict, "unknown", q["question"])

    def test_evidence_several_relationships_away_is_actually_reached(self):
        # The distributed-evidence case from the brief: PR -> issue -> code ->
        # a later PR. A single retrieval cannot do this by construction; if the
        # investigation cannot either, the engine has not earned its cost.
        question = next(q for q in _load_questions() if q["dimension"] == "multi_hop")
        inv, _result, _texts = self._run(question)
        reached = [h for h in question["hops"] if h in inv.evidence]
        self.assertGreater(len(reached), 1,
                           f"only reached {reached} of {question['hops']}")

    def test_it_does_not_wander(self):
        board = grade_investigations(_load_questions(), self._run)
        self.assertEqual(board["efficiency"]["duplicate_steps"], 0)
        self.assertLessEqual(board["efficiency"]["max_steps"], 10)

    def test_a_conversation_holds_one_subject_and_compounds(self):
        # The four-turn conversation, through the real engine rather than the
        # HTTP layer (demo/test_investigate_endpoint.py covers that).
        first = investigate("Talk to me about PR #1525.", self.pipeline,
                            self.entities, self.provider, budget=Budget(max_steps=8))
        self.assertEqual(first.subject, ["pr:1525"])
        established = [c for c in first.claims if c.verified]
        self.assertTrue(established, "the opening turn established nothing")

        carried = established
        for follow_up in ("Why did it change?",
                          "What implications did it have on the codebase?",
                          "Why do you think it was applied inside this codebase?"):
            turn = investigate(follow_up, self.pipeline, self.entities, self.provider,
                               subject=list(first.subject), objective=first.objective,
                               carried=carried, budget=Budget(max_steps=8))
            self.assertEqual(turn.subject, ["pr:1525"], follow_up)
            texts = {c["text"] for c in turn.summary()["claims"]}
            for prior in carried:
                self.assertIn(prior.text, texts,
                              f"{follow_up!r} dropped an established finding")
            carried = [c for c in turn.claims if c.verified]


class RegressionTests(unittest.TestCase):
    """No key needed, and deliberately so: this is the check that the whole
    investigation engine changed nothing about the product that already
    worked."""

    @unittest.skipUnless(CORPUS.exists(), "needs the committed corpus")
    def test_ask_is_untouched_by_everything_the_engine_added(self):
        from .provider import StaticProvider
        chunks = load_chunks(CORPUS)
        pipeline = GatedPipeline(LexicalRetriever(chunks), chunks,
                                 StaticProvider(json.dumps(
                                     {"verdict": "answer",
                                      "answer": "Because other plugins import it.",
                                      "citations": ["pr:1435"]})))
        result = pipeline.answer("Why the Responses API as a new class?")
        self.assertEqual(result.verdict, "answer")
        self.assertEqual(result.citations, ["pr:1435"])
        # The read-only accessors the investigation layer added must not have
        # become a second way to reach the corpus that disagrees with the first.
        self.assertEqual(pipeline.chunk_for("pr:1435").ref, "pr:1435")
        self.assertEqual(pipeline.search_refs("responses api", 3),
                         LexicalRetriever(chunks).search("responses api", 3))

    def test_the_labelled_set_is_internally_consistent(self):
        for q in _load_questions():
            if q["label"] == "answerable":
                self.assertTrue(q.get("citations"), q["id"])
            else:
                # An unanswerable question with gold citations would be a
                # contradiction in the labelling, not a hard question.
                self.assertFalse(q.get("citations"), q["id"])
                self.assertFalse(q.get("hops"), q["id"])

    def test_every_gold_ref_exists_in_the_committed_corpus(self):
        # Labelling drift: a gold ref that no longer exists would quietly make
        # citation correctness unachievable and look like a quality regression.
        if not CORPUS.exists():
            self.skipTest("needs the committed corpus")
        refs = {c.ref for c in load_chunks(CORPUS)}
        for q in _load_questions():
            for ref in list(q.get("citations") or ()) + list(q.get("hops") or ()):
                self.assertIn(ref, refs, f"{q['id']} names a ref that is not indexed")


if __name__ == "__main__":
    unittest.main()
