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


if __name__ == "__main__":
    unittest.main()
