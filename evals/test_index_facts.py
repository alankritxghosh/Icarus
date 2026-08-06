# evals/test_index_facts.py
"""`index:overview` -- Icarus's own index offered to the writer AS EVIDENCE.

Why this exists (live, 2026-08-06, muxinc/media-chrome): asked "what coding
languages does the codebase contain", Icarus answered "No one wrote this down"
-- while its own `/map` had already computed the languages from the files it
read, and the tour rendered them two steps earlier. The ask path could only
search text a PERSON wrote, and nobody writes "this project is in TypeScript"
in a document; it is a fact about the FILES. The question's word "languages"
lexically matched `docs/src/languages.ts` (an i18n file about HUMAN languages),
so retrieval returned nothing an answer could be inferred from.

The same question against the single-language simonw/llm board ANSWERED, which
is what made this hard to see: on a pure-Python repo every retrieved chunk is
Python, so the writer can infer the answer by accident. The defect only shows
on a repo where retrieval misses -- i.e. exactly the repos a user connects.

This is deliberately NOT a keyword router ("if the question says 'languages',
call the map"). That is the permutations problem again, one branch at a time.
The index is simply made available as ordinary evidence, so any phrasing that
retrieval routes to it can be answered from it, and cited.
"""

import unittest
from unittest import mock

from .corpus import Chunk
from .index_facts import INDEX_REF, build_index_chunk, language_for


class LanguageForTests(unittest.TestCase):
    def test_maps_known_extensions(self):
        self.assertEqual(language_for("llm/utils.py"), "Python")
        self.assertEqual(language_for("src/app.tsx"), "TypeScript")
        self.assertEqual(language_for("ios/Thing.mm"), "Objective-C++")

    def test_unknown_extension_falls_back_to_the_extension_itself(self):
        self.assertEqual(language_for("a/b.zig"), ".zig")

    def test_no_extension_is_named_not_guessed(self):
        self.assertEqual(language_for("Makefile"), "(no extension)")


class BuildIndexChunkTests(unittest.TestCase):
    CHUNKS = [
        Chunk("code:llm/utils.py#L1-L9", "code", "import os"),
        Chunk("code:llm/utils.py#L10-L20", "code", "def f(): pass"),   # same FILE
        Chunk("code:src/app.tsx", "code", "export const A = () => {}"),
        Chunk("doc:README.md", "doc", "# hi"),
        Chunk("pr:1", "pr", "did a thing"),
        Chunk("issue:2", "issue", "broken"),
    ]

    def setUp(self):
        self.chunk = build_index_chunk(self.CHUNKS)

    def test_has_the_reserved_ref_and_its_own_source(self):
        self.assertEqual(self.chunk.ref, INDEX_REF)
        self.assertEqual(self.chunk.source, "index")

    def test_counts_distinct_files_not_chunks(self):
        # utils.py made two chunks but is ONE file.
        self.assertIn("3 ", self.chunk.text)          # utils.py, app.tsx, README.md
        self.assertNotIn("4 distinct", self.chunk.text)

    def test_reports_languages_by_file_count(self):
        self.assertIn("Python 1", self.chunk.text)
        self.assertIn("TypeScript 1", self.chunk.text)
        self.assertIn("Markdown 1", self.chunk.text)

    def test_reports_evidence_counts_by_source(self):
        self.assertIn("pr", self.chunk.text)
        self.assertIn("issue", self.chunk.text)

    def test_says_plainly_that_it_is_measured_not_written_by_a_person(self):
        # The whole honesty point: this evidence is Icarus reporting what it
        # READ. A citation to it must never read as "a human documented this".
        low = self.chunk.text.lower()
        self.assertIn("icarus", low)
        self.assertIn("read", low)

    def test_never_reads_as_a_recorded_rationale(self):
        # Checked against gate.py's REAL marker list, not a hand-copied subset:
        # an earlier draft ended "...they say nothing about intent", and the
        # substring "intent" made a DISCLAIMER of intent register as a
        # STATEMENT of one -- so "why was TypeScript chosen?" could have been
        # grounded on a file listing. A hand-written word list would not have
        # caught it; importing the real one does, and stays correct if the
        # marker list grows.
        from .gate import _states_reason
        self.assertFalse(_states_reason(self.chunk.text),
                         "index text trips gate.py's rationale detector")

    def test_the_index_is_not_a_rationale_SOURCE_either(self):
        # Belt and braces: even if the text were reworded, `index` must never
        # join pr/issue/doc/commit as a source that inherently records a reason.
        from .gate import _source
        self.assertNotIn(_source(INDEX_REF), ("pr", "issue", "doc", "commit"))

    def test_is_deterministic_under_reordered_input(self):
        a = build_index_chunk(self.CHUNKS).text
        b = build_index_chunk(list(reversed(self.CHUNKS))).text
        self.assertEqual(a, b)

    def test_empty_corpus_yields_nothing_rather_than_an_empty_claim(self):
        self.assertIsNone(build_index_chunk([]))

    def test_is_pure_no_file_or_socket(self):
        with mock.patch("builtins.open", side_effect=AssertionError("opened a file")), \
             mock.patch("socket.socket", side_effect=AssertionError("opened a socket")):
            build_index_chunk(self.CHUNKS)


if __name__ == "__main__":
    unittest.main()
