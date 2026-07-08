# evals/test_gated_explain.py
"""Brick D's core: GatedPipeline.explain(path, start, end, question=None) --
resolve evidence by LINE LOCATION (a GitHub selection), not a text query, but
go through the IDENTICAL writer -> gate() path as .answer(). Proves no new
honesty path was opened: the same bluff-forcing-abstention behavior holds."""

import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline

CHUNKS = [
    # The anchor: a line-windowed code chunk covering lines 10-40 of tools.py.
    Chunk("code:llm/tools.py#L10-L40", "code", "def llm_time(): return datetime.now()"),
    # A neighbor a text search on the anchor's content should surface.
    Chunk("pr:99", "pr", "Added llm_time() to the tools module for the current timestamp"),
    # Unrelated evidence -- must not appear in a well-scoped explain.
    Chunk("pr:1", "pr", "bump version"),
    # A whole-file chunk (the committed-corpus shape) for a second file.
    Chunk("code:llm/models.py", "code", "class Response: pass"),
]


def _pipe(provider, chunks=CHUNKS):
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


class ExplainResolvesAnchorTests(unittest.TestCase):
    def test_explain_includes_the_anchor_chunk_in_retrieved(self):
        raw = json.dumps({"verdict": "answer", "answer": "It returns the current time.",
                          "citations": ["code:llm/tools.py#L10-L40"]})
        r = _pipe(StaticProvider(raw)).explain("llm/tools.py", 15, 20)
        self.assertIn("code:llm/tools.py#L10-L40", r.retrieved)

    def test_explain_finds_a_neighbor_via_semantic_search_on_anchor_text(self):
        raw = json.dumps({"verdict": "unknown"})
        r = _pipe(StaticProvider(raw)).explain("llm/tools.py", 15, 20)
        # LexicalRetriever alone, searching the anchor's own text (no question
        # supplied -> falls back to it), should surface pr:99 (shares
        # "llm_time"/"tools") over the unrelated pr:1.
        self.assertIn("pr:99", r.retrieved)

    def test_explain_prefers_the_caller_question_for_neighbor_search_when_given(self):
        # Real bug this proves is fixed: an earlier version ALWAYS searched
        # neighbors on the anchor's own code text, even when the caller
        # supplied a real question -- live-verified against the real corpus to
        # measurably find WORSE neighbors than searching the actual question,
        # causing the writer to honestly abstain on a question /ask answers
        # confidently (not a gate bug -- explain() was just feeding it worse
        # evidence). Here: "timestamp format" is a query-specific keyword pr:99
        # doesn't have; a chunk containing it must only surface when the
        # QUESTION (not the anchor's "def llm_time..." text) drives the search.
        chunks = CHUNKS + [Chunk("pr:200", "pr", "Discussed the timestamp format returned by tools")]
        raw = json.dumps({"verdict": "unknown"})
        r = _pipe(StaticProvider(raw), chunks).explain(
            "llm/tools.py", 15, 20, question="what timestamp format does this use"
        )
        self.assertIn("pr:200", r.retrieved)

    def test_whole_file_chunk_resolves_as_anchor_for_any_line(self):
        raw = json.dumps({"verdict": "answer", "answer": "A Response class.",
                          "citations": ["code:llm/models.py"]})
        r = _pipe(StaticProvider(raw)).explain("llm/models.py", 500, 510)
        self.assertIn("code:llm/models.py", r.retrieved)

    def test_no_coverage_for_the_requested_location_is_honest_unknown(self):
        # A file/line combination nothing in the corpus covers -- the gate's
        # ordinary "no evidence" abstention, not a special-cased error.
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:1"]})
        r = _pipe(StaticProvider(raw)).explain("llm/nonexistent.py", 1, 5)
        self.assertEqual(r.verdict, "unknown")


class ExplainHonestyGateTests(unittest.TestCase):
    """The load-bearing proof: explain() opens NO new honesty path."""

    def test_grounded_answer_passes_through(self):
        raw = json.dumps({"verdict": "answer", "answer": "It returns the current time.",
                          "citations": ["code:llm/tools.py#L10-L40"]})
        r = _pipe(StaticProvider(raw)).explain("llm/tools.py", 15, 20)
        self.assertEqual(r.verdict, "answer")
        self.assertIn("code:llm/tools.py#L10-L40", r.citations)

    def test_bluff_with_unretrieved_citation_is_forced_unknown(self):
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        r = _pipe(StaticProvider(raw)).explain("llm/tools.py", 15, 20)
        self.assertEqual(r.verdict, "unknown")

    def test_writer_abstention_stays_unknown(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).explain("llm/tools.py", 15, 20)
        self.assertEqual(r.verdict, "unknown")


class ExplainQuestionTests(unittest.TestCase):
    def test_uses_a_sensible_default_question_when_none_supplied(self):
        seen = []

        class _Spy:
            def complete(self, prompt):
                seen.append(prompt)
                return json.dumps({"verdict": "unknown"})

        _pipe(_Spy()).explain("llm/tools.py", 15, 20)
        self.assertEqual(len(seen), 1)
        self.assertIn("do", seen[0].lower())  # the default asks what/why the code does

    def test_uses_the_callers_question_when_supplied(self):
        seen = []

        class _Spy:
            def complete(self, prompt):
                seen.append(prompt)
                return json.dumps({"verdict": "unknown"})

        _pipe(_Spy()).explain("llm/tools.py", 15, 20, question="why does this return UTC?")
        self.assertIn("why does this return UTC?", seen[0])


class AnswerBehaviorUnchangedTests(unittest.TestCase):
    """Regression guard for the .answer_from() refactor: .answer() itself must
    behave EXACTLY as before -- same retrieval, same gate, same Result shape."""

    def test_answer_still_emits_grounded_answers(self):
        raw = json.dumps({"verdict": "answer", "answer": "It returns the current time.",
                          "citations": ["code:llm/tools.py#L10-L40"]})
        r = _pipe(StaticProvider(raw)).answer("what does llm_time return")
        self.assertEqual(r.verdict, "answer")
        self.assertIn("code:llm/tools.py#L10-L40", r.citations)

    def test_answer_still_forces_unknown_on_bluff(self):
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        r = _pipe(StaticProvider(raw)).answer("what does llm_time return")
        self.assertEqual(r.verdict, "unknown")


if __name__ == "__main__":
    unittest.main()
