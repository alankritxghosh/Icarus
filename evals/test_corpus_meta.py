# evals/test_corpus_meta.py
import json
import tempfile
import unittest
from pathlib import Path

from .corpus_meta import CORPUS_FORMAT_VERSION, corpus_version, write_meta, load_meta


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

    def test_truncated_field_round_trips_and_defaults_false(self):
        # Brick 2a: a partial corpus (a size cap stopped the walk) must be
        # recorded, and default to False for callers that omit it.
        with tempfile.TemporaryDirectory() as d:
            p, q = Path(d) / "a.json", Path(d) / "b.json"
            write_meta(p, repo="o/r", commit="c", code_dir=".",
                       counts={"code": 0}, truncated=True)
            self.assertTrue(load_meta(p)["truncated"])
            write_meta(q, repo="o/r", commit="c", code_dir=".", counts={"code": 0})
            self.assertFalse(load_meta(q)["truncated"])

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


class CorpusFormatVersionTests(unittest.TestCase):
    """A corpus is stale when the ingest OUTPUT SHAPE has changed, not only
    when the code chunker has. `chunking` cannot carry that: the discussion
    fix (2026-07-28) left it byte-identical, so without a version every
    already-connected repo would have kept serving title+body PR chunks and
    the fix would have been live and inert."""

    def test_write_meta_stamps_the_current_version(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "meta.json"
            write_meta(p, repo="o/r", commit="abc", code_dir=".", counts={})
            self.assertEqual(load_meta(p)["corpus_version"], CORPUS_FORMAT_VERSION)

    def test_a_pre_versioned_corpus_reads_as_version_one(self):
        self.assertEqual(corpus_version({"repo": "o/r"}), 1)

    def test_a_pre_versioned_corpus_is_older_than_current(self):
        # The whole point: an existing on-disk corpus must compare as stale.
        self.assertLess(corpus_version({"repo": "o/r"}), CORPUS_FORMAT_VERSION)

    def test_a_hand_edited_non_integer_reads_as_stale_not_current(self):
        # Fail toward re-ingesting, never toward serving an unknown shape.
        for junk in ("2", None, True, [2], {}):
            self.assertEqual(corpus_version({"corpus_version": junk}), 1, junk)

    def test_a_current_corpus_is_not_stale(self):
        self.assertEqual(corpus_version({"corpus_version": CORPUS_FORMAT_VERSION}),
                         CORPUS_FORMAT_VERSION)
