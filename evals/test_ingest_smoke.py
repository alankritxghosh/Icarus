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
from demo.links import ref_to_url

SMOKE_REPO = "simonw/json-flatten"  # tiny pure-Python repo

# Tiny, stable, genuinely non-Python public repo (Task A5): 16 tracked files
# (verified live), plain JavaScript source (index.js, browser.js, test.js,
# etc.) plus a readme.md and a .github/workflows/main.yml, so a single ingest
# exercises all three source tags (code/doc/config) without any .py in sight.
# Maintained by a prolific, long-tenured npm-package author (sindresorhus) with
# 1300+ stars and a decade of history -- unlikely to be deleted, renamed, or
# made private.
NON_PYTHON_SMOKE_REPO = "sindresorhus/is-online"


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

    def test_ingests_a_tiny_non_python_repo(self):
        """Whole-codebase ingest must genuinely handle a non-Python repo: real
        .js source chunks (not just "some chunks exist"), proven by checking
        the actual refs in chunks.jsonl for a non-.py path."""
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "chunks.jsonl"
            meta = Path(d) / "meta.json"
            with mock.patch.object(ingest, "OUT", out), mock.patch.object(ingest, "META", meta):
                ingest.main(["--repo", NON_PYTHON_SMOKE_REPO, "--code-dir", "."])
            lines = [l for l in out.read_text().splitlines() if l.strip()]
            self.assertTrue(lines, "no chunks written")

            m = load_meta(meta)
            self.assertEqual(m["repo"], NON_PYTHON_SMOKE_REPO)
            self.assertTrue(m["counts"]["code"] >= 1)  # the repo's .js files
            self.assertTrue(m["counts"].get("doc", 0) >= 1)  # readme.md

            refs = [json.loads(l)["ref"] for l in lines]
            non_python_code_refs = [
                r for r in refs
                if r.startswith("code:") and not r.split("#", 1)[0].endswith(".py")
            ]
            self.assertTrue(non_python_code_refs, f"expected a non-.py code ref, got: {refs}")

            # Chain a real non-Python ref through to a real rendered citation
            # link (demo/links.py) -- proves classify_file -> chunk_text ->
            # fetch_code -> ref_to_url actually connects end to end, not just
            # each half in isolation.
            ref = non_python_code_refs[0]
            path, hash_sep, line_range = ref[len("code:"):].partition("#")
            url = ref_to_url(ref, NON_PYTHON_SMOKE_REPO, m["commit"])
            self.assertIsNotNone(url)
            self.assertIn(NON_PYTHON_SMOKE_REPO, url)
            self.assertIn(path, url)
            if hash_sep:
                self.assertTrue(url.endswith(f"#{line_range}"))


if __name__ == "__main__":
    unittest.main()
