# evals/test_ingest_repo.py
"""ingest_repo writes chunks.jsonl + meta.json into any target dir and returns
counts. Offline: the network fetches are monkeypatched."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import ingest
from .corpus_meta import load_meta


class IngestRepoTests(unittest.TestCase):
    def test_writes_corpus_and_meta_to_target_dir(self):
        prs = ([{"ref": "pr:1", "source": "pr", "text": "why X"}], {7})
        issues = [{"ref": "issue:7", "source": "issue", "text": "ctx"}]
        code = [{"ref": "code:a.py", "source": "code", "text": "x=1"}]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", return_value=issues), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            counts = ingest.ingest_repo("octo/repo", d, commit="abc123", code_dir=".")
            chunks = [json.loads(l) for l in (Path(d) / "chunks.jsonl").read_text().splitlines() if l.strip()]
            self.assertEqual([c["ref"] for c in chunks], ["pr:1", "issue:7", "code:a.py"])
            self.assertEqual(counts, {"pr": 1, "issue": 1, "code": 1})
            m = load_meta(Path(d) / "meta.json")
            self.assertEqual(m["repo"], "octo/repo")
            self.assertEqual(m["commit"], "abc123")


if __name__ == "__main__":
    unittest.main()
