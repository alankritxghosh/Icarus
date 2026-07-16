# evals/test_gated_pipeline.py
import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline

CHUNKS = [
    Chunk("pr:1", "pr", "We mock with MSW because stubbing fetch broke on transport switches"),
    Chunk("pr:2", "pr", "bump version"),
]


def _pipe(provider):
    return GatedPipeline(LexicalRetriever(CHUNKS), CHUNKS, provider)


class _SpyProvider:
    """Records the exact prompt it was sent, so a test can assert on what the
    writer actually saw -- not just on the final gate verdict (a canned/fake
    verdict can't distinguish "the writer saw this text" from "the gate
    happens to allow this citation structurally")."""

    def __init__(self):
        self.last_prompt = None

    def complete(self, prompt):
        self.last_prompt = prompt
        return json.dumps({"verdict": "unknown"})


class WriterVisibilityGapTests(unittest.TestCase):
    """Reproduces a live-found bug (saltstack/salt, benawad/vsinder): a gold
    chunk can rank within GatedPipeline.answer()'s recall_n (used for
    `retrieved`/recall measurement) while still ranking beyond writer_k (only
    the top writer_k of those ever reach build_prompt) -- so the gold chunk's
    TEXT never reaches the writer, and an honest-looking "unknown" hides
    evidence that was genuinely retrieved."""

    _MARKER = "GIZMO_MARKER_TOKEN"
    _QUESTION = "why does gizmo retry using exponential backoff automatically"

    def _pipeline_with_buried_gold(self, provider, **kwargs):
        # 8 fillers share every query term (high combined idf) and BM25-outrank
        # a gold chunk that shares only "gizmo" -- empirically verified to put
        # gold at rank 9 of 9 (index 8), beyond both the old and new writer_k.
        fillers = [
            Chunk(f"pr:{i}", "pr", f"{self._QUESTION} filler variant {i}")
            for i in range(1, 9)
        ]
        gold = Chunk("pr:999", "pr", f"gizmo is documented {self._MARKER} as a subsystem name only")
        chunks = fillers + [gold]
        return GatedPipeline(LexicalRetriever(chunks), chunks, provider, **kwargs), gold

    def test_gold_beyond_writer_k_is_still_in_retrieved(self):
        # Recall holds regardless of writer_k -- this is the "evidence was
        # genuinely retrieved" half of the bug report.
        spy = _SpyProvider()
        pipe, gold = self._pipeline_with_buried_gold(spy, writer_k=6)
        r = pipe.answer(self._QUESTION)
        self.assertIn(gold.ref, r.retrieved)

    def test_writer_k_of_6_never_shows_the_writer_the_gold_text(self):
        # Locks in the actual mechanism as a permanent regression guard,
        # independent of whatever the current default is.
        spy = _SpyProvider()
        pipe, _ = self._pipeline_with_buried_gold(spy, writer_k=6)
        pipe.answer(self._QUESTION)
        self.assertNotIn(self._MARKER, spy.last_prompt)

    def test_default_writer_k_now_shows_the_writer_the_gold_text(self):
        # The actual fix: raising GatedPipeline's writer_k default must widen
        # the writer's visibility far enough to include rank 9 of 9.
        spy = _SpyProvider()
        pipe, _ = self._pipeline_with_buried_gold(spy)  # no override -- real default
        pipe.answer(self._QUESTION)
        self.assertIn(self._MARKER, spy.last_prompt)


class GatedPipelineTests(unittest.TestCase):
    def test_emits_grounded_answer(self):
        raw = json.dumps({"verdict": "answer", "answer": "Because fetch stubbing broke.", "citations": ["pr:1"]})
        r = _pipe(StaticProvider(raw)).answer("why MSW instead of stubbing fetch")
        self.assertEqual(r.verdict, "answer")
        self.assertIn("pr:1", r.citations)

    def test_abstains_when_writer_abstains(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("why MSW")
        self.assertEqual(r.verdict, "unknown")

    def test_bluff_with_unretrieved_citation_is_forced_unknown(self):
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        self.assertEqual(_pipe(StaticProvider(raw)).answer("why MSW").verdict, "unknown")

    def test_populates_retrieved_for_recall(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("why MSW instead of stubbing fetch")
        self.assertIn("pr:1", r.retrieved)  # recall@k still measurable even on abstain


if __name__ == "__main__":
    unittest.main()
