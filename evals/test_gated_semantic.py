# evals/test_gated_semantic.py
"""Honesty-gate proof for the SEMANTIC/HYBRID retrieval path (Brick C).

The comprehension eval (test_retrieval_eval.py) proves semantic retrieval
*retrieves* better. This proves the other, non-negotiable half: the
deterministic honesty gate (evals/gate.py, exercised via GatedPipeline with a
real writer) still fires correctly when the evidence pool comes from SEMANTIC or
HYBRID retrieval rather than BM25 -- i.e. Brick C did not open a bluff path.

Deliberately uses a deterministic StaticEmbeddingProvider (offline, no fastembed)
so it ALWAYS runs and is not a live/skippable test: the point here is gate
behavior on the semantic path, not embedding quality. Mirrors
test_gated_pipeline.py (which covers the lexical path) so the two together show
the gate is retriever-agnostic."""

import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever, SemanticRetriever, HybridRetriever
from .provider import StaticProvider, StaticEmbeddingProvider
from .pipeline import GatedPipeline

CHUNKS = [
    Chunk("pr:1", "pr", "We mock with MSW because stubbing fetch broke on transport switches"),
    Chunk("pr:2", "pr", "bump version"),
]

QUERY = "why MSW instead of stubbing fetch"


def _embed(text):
    # Deterministic 2-D vectors keyed on topic words, so SemanticRetriever
    # surfaces pr:1 for an MSW/fetch query (and never pr:2) -- exercising the
    # real semantic cosine path without needing a downloaded model.
    t = text.lower()
    return [
        1.0 if any(w in t for w in ("msw", "stub", "fetch", "mock")) else 0.0,
        1.0 if any(w in t for w in ("version", "bump")) else 0.0,
    ]


def _semantic():
    return SemanticRetriever(CHUNKS, StaticEmbeddingProvider(_embed))


def _semantic_pipe(provider):
    return GatedPipeline(_semantic(), CHUNKS, provider)


def _hybrid_pipe(provider):
    return GatedPipeline(HybridRetriever(LexicalRetriever(CHUNKS), _semantic()), CHUNKS, provider)


class GatedSemanticPathTests(unittest.TestCase):
    def test_semantic_retrieval_surfaces_the_relevant_chunk(self):
        # Precondition for the gate tests: semantic retrieval actually returns
        # pr:1 (and drops the irrelevant pr:2) for this query.
        got = _semantic().search(QUERY, 5)
        self.assertIn("pr:1", got)
        self.assertNotIn("pr:2", got)

    def test_grounded_answer_passes_gate_on_semantic_evidence(self):
        raw = json.dumps({"verdict": "answer", "answer": "Because fetch stubbing broke.", "citations": ["pr:1"]})
        r = _semantic_pipe(StaticProvider(raw)).answer(QUERY)
        self.assertEqual(r.verdict, "answer")
        self.assertIn("pr:1", r.citations)

    def test_grounded_answer_passes_gate_on_hybrid_evidence(self):
        raw = json.dumps({"verdict": "answer", "answer": "Because fetch stubbing broke.", "citations": ["pr:1"]})
        r = _hybrid_pipe(StaticProvider(raw)).answer(QUERY)
        self.assertEqual(r.verdict, "answer")
        self.assertIn("pr:1", r.citations)

    def test_bluff_citation_forced_unknown_on_semantic_evidence(self):
        # Writer cites a ref semantic retrieval never surfaced -> the gate MUST
        # force abstention. This is the honesty-gate proof for the semantic path.
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        self.assertEqual(_semantic_pipe(StaticProvider(raw)).answer(QUERY).verdict, "unknown")

    def test_bluff_citation_forced_unknown_on_hybrid_evidence(self):
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        self.assertEqual(_hybrid_pipe(StaticProvider(raw)).answer(QUERY).verdict, "unknown")

    def test_writer_abstention_stays_unknown_on_semantic_evidence(self):
        r = _semantic_pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer(QUERY)
        self.assertEqual(r.verdict, "unknown")


if __name__ == "__main__":
    unittest.main()
