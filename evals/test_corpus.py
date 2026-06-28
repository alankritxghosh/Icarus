# evals/test_corpus.py
import json
import unittest
from pathlib import Path
import tempfile

from .corpus import Chunk, load_chunks


class CorpusLoaderTests(unittest.TestCase):
    def test_loads_jsonl_into_chunks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "chunks.jsonl"
            p.write_text(
                json.dumps({"ref": "pr:1", "source": "pr", "text": "hello"}) + "\n"
                + "\n"  # blank line tolerated
                + json.dumps({"ref": "code:a.py", "source": "code", "text": "x=1"}) + "\n"
            )
            chunks = load_chunks(p)
            self.assertEqual([c.ref for c in chunks], ["pr:1", "code:a.py"])
            self.assertIsInstance(chunks[0], Chunk)
            self.assertEqual(chunks[0].source, "pr")


if __name__ == "__main__":
    unittest.main()
