# evals/test_ingest_smoke.py
"""Real end-to-end ingest of a tiny public repo (network; needs gh + git).
Writes to a temp path so it never touches the committed corpus. Default-skips;
run with RUN_INGEST_SMOKE=1."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import ingest
from .corpus_meta import load_meta

SMOKE_REPO = "simonw/json-flatten"  # tiny pure-Python repo


@unittest.skipUnless(os.environ.get("RUN_INGEST_SMOKE") == "1", "set RUN_INGEST_SMOKE=1 (needs gh+git+network)")
class IngestSmokeTests(unittest.TestCase):
    def test_ingests_a_tiny_public_repo(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "chunks.jsonl"
            meta = Path(d) / "meta.json"
            with mock.patch.object(ingest, "OUT", out), mock.patch.object(ingest, "META", meta):
                ingest.main(["--repo", SMOKE_REPO, "--code-dir", "."])
            lines = [l for l in out.read_text().splitlines() if l.strip()]
            self.assertTrue(lines, "no chunks written")
            m = load_meta(meta)
            self.assertEqual(m["repo"], SMOKE_REPO)
            self.assertTrue(m["counts"]["code"] >= 1)  # the repo's .py files


if __name__ == "__main__":
    unittest.main()
