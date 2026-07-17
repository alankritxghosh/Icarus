# evals/test_corpus_meta.py
import json
import tempfile
import unittest
from pathlib import Path

from .corpus_meta import write_meta, load_meta


class CorpusMetaTests(unittest.TestCase):
    def test_round_trips(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "meta.json"
            write_meta(p, repo="o/r", commit="abc123", code_dir="src",
                       counts={"pr": 5, "issue": 2, "code": 10})
            m = load_meta(p)
            self.assertEqual(m["repo"], "o/r")
            self.assertEqual(m["commit"], "abc123")
            self.assertEqual(m["code_dir"], "src")
            self.assertEqual(m["counts"]["code"], 10)
            self.assertIn("generated_at", m)

    def test_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(load_meta(Path(d) / "nope.json"))

    def test_chunking_field_round_trips(self):
        # T6 of docs/plans/2026-07-17-ast-chunking-all-languages.md: records
        # which chunking scheme produced this corpus, read by
        # demo/library.py's staleness check.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "meta.json"
            write_meta(p, repo="o/r", commit="abc123", code_dir="src",
                       counts={"pr": 0, "issue": 0, "code": 0}, chunking="ast")
            self.assertEqual(load_meta(p)["chunking"], "ast")

    def test_chunking_defaults_to_chunk_text_for_callers_that_omit_it(self):
        # Every corpus written before this field existed was chunk_text --
        # existing callers (most tests) that don't pass `chunking` at all
        # must not need updating just because this field was added.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "meta.json"
            write_meta(p, repo="o/r", commit="abc123", code_dir="src",
                       counts={"pr": 0, "issue": 0, "code": 0})
            self.assertEqual(load_meta(p)["chunking"], "chunk_text")


if __name__ == "__main__":
    unittest.main()
