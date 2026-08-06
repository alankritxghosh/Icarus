# evals/test_index_evidence_wiring.py
"""The index chunk reaching the WRITER, without disturbing anything measured.

Three properties, in descending order of how badly a regression would hurt:

1. The board is untouched. `retrieved[:k]` drives recall@k on every eval number
   in the repo, so the index ref is APPENDED, never prepended -- prepending
   would push a real ref out of the top-k window and silently re-baseline the
   board while looking like an improvement.
2. The writer actually sees it, and the gate can ground a citation to it.
3. It can never launder an unrecorded "why". gate.py's (b) guard must still
   force abstention when the only grounded evidence is a file listing.
"""

import json
import unittest

from .corpus import Chunk
from .index_facts import INDEX_REF
from .provider import StaticProvider
from .retriever import LexicalRetriever
from .pipeline import GatedPipeline

CHUNKS = [
    Chunk("code:llm/utils.py#L1-L9", "code", "import os"),
    Chunk("code:src/app.tsx", "code", "export const A = () => {}"),
    Chunk("pr:7", "pr", "we switched to typescript"),
    Chunk("doc:README.md", "doc", "the cli tool"),
]


class _PromptSpy:
    private_safe = True

    def __init__(self, response):
        self._response = response
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        return self._response


def _pipe(provider, chunks=CHUNKS):
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


class IndexReachesTheWriterTests(unittest.TestCase):
    def test_the_writer_sees_the_index_chunk(self):
        spy = _PromptSpy(json.dumps({"verdict": "unknown"}))
        _pipe(spy).answer("what languages is this written in?")
        self.assertIn(INDEX_REF, spy.prompts[0])

    def test_a_citation_to_the_index_is_grounded(self):
        raw = json.dumps({"verdict": "answer",
                          "answer": "Indexed files are Python and TypeScript.",
                          "citations": [INDEX_REF]})
        r = _pipe(StaticProvider(raw)).answer("what languages is this written in?")
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, [INDEX_REF])

    def test_explain_also_carries_it(self):
        spy = _PromptSpy(json.dumps({"verdict": "unknown"}))
        _pipe(spy).explain("llm/utils.py", 1, 5)
        self.assertIn(INDEX_REF, spy.prompts[0])

    def test_explain_with_neighbours_off_gets_no_index_either(self):
        # `neighbors=False` means "answer from the addressed location ALONE" --
        # the guarantee the onboarding tour's README step rests on, after a live
        # bug where a neighbouring commit was cited as this repo's conventions.
        # The index is context like any other, so it must be withheld too.
        spy = _PromptSpy(json.dumps({"verdict": "unknown"}))
        r = _pipe(spy).explain("llm/utils.py", 1, 5, neighbors=False)
        self.assertNotIn(INDEX_REF, spy.prompts[0])
        self.assertNotIn(INDEX_REF, r.retrieved)

    def test_explain_on_an_unresolvable_location_stays_unknown(self):
        # The index must never be able to turn "that location isn't indexed"
        # into an answer about the repository at large.
        r = _pipe(StaticProvider(json.dumps({"verdict": "answer", "answer": "x",
                                             "citations": [INDEX_REF]}))) \
            .explain("does/not/exist.py", 1, 5, neighbors=False)
        self.assertEqual(r.verdict, "unknown")


class BoardIsUntouchedTests(unittest.TestCase):
    def test_index_ref_is_appended_last_so_recall_at_k_is_unchanged(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("typescript")
        self.assertEqual(r.retrieved[-1], INDEX_REF,
                         "index ref must be LAST -- prepending re-baselines recall@k")
        self.assertNotIn(INDEX_REF, r.retrieved[:-1])

    def test_real_retrieval_order_is_otherwise_preserved(self):
        without_index = [r for r in
                         _pipe(StaticProvider(json.dumps({"verdict": "unknown"})))
                         .answer("typescript").retrieved if r != INDEX_REF]
        # Same pipeline, same query: the real refs and their order must be
        # exactly what the retriever produced, untouched.
        expected = LexicalRetriever(CHUNKS).search("typescript", 20)
        self.assertEqual(without_index, expected)


class AnswerAudienceWiringTests(unittest.TestCase):
    """`answer(question, audience=...)` reaches the writer prompt, and does not
    leak into .explain(), which has no audience concept of its own."""

    def test_answer_passes_audience_through_to_the_prompt(self):
        spy = _PromptSpy(json.dumps({"verdict": "unknown"}))
        _pipe(spy).answer("what happened here?", audience="plain")
        self.assertIn("non-technical", spy.prompts[0].lower())

    def test_default_answer_call_is_unaffected(self):
        spy = _PromptSpy(json.dumps({"verdict": "unknown"}))
        _pipe(spy).answer("what happened here?")
        self.assertNotIn("non-technical", spy.prompts[0].lower())

    def test_explain_ignores_audience_it_was_never_given(self):
        # explain() has no audience parameter; this just pins that its prompt
        # is unaffected by anything answer() does elsewhere.
        spy = _PromptSpy(json.dumps({"verdict": "unknown"}))
        _pipe(spy).explain("llm/utils.py", 1, 5)
        self.assertNotIn("non-technical", spy.prompts[0].lower())


class IndexCannotLaunderAnUnrecordedWhyTests(unittest.TestCase):
    def test_a_why_grounded_only_on_the_index_is_forced_to_unknown(self):
        raw = json.dumps({"verdict": "answer",
                          "answer": "TypeScript was chosen for type safety.",
                          "citations": [INDEX_REF]})
        r = _pipe(StaticProvider(raw)).answer("why was TypeScript chosen for this project?")
        self.assertEqual(r.verdict, "unknown",
                         "a file listing is not a recorded reason")


if __name__ == "__main__":
    unittest.main()
