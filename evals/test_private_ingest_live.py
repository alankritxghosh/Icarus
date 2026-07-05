# evals/test_private_ingest_live.py
"""Live end-to-end proof of the private-repo pipeline (network + real paid API
calls; needs a real private repo + tokens nobody has typed in yet). Proves,
against the real classes (not fakes):

1. the caller-scoped access check (evals.github_access.repo_info) really reads
   a real private repo with a real token;
2. a real authed ingest_repo() clone + a real GatedPipeline(..., PaidGeminiProvider())
   answers (or honestly abstains) without breaking the honesty gate;
3. the trust interlock (assert_safe_for_private) genuinely refuses a real FREE
   provider instance, exercised in the same live run as (2) for a stronger
   end-to-end signal than the unit tests in evals/test_trust.py alone.

Default-skips (mirrors evals/test_ingest_smoke.py's opt-in-flag pattern):
requires RUN_PRIVATE_INGEST=1 PLUS all of ICARUS_TEST_PRIVATE_REPO,
GITHUB_TOKEN, GEMINI_PAID_API_KEY. Partial configuration still skips cleanly --
this test clones a real repo and spends real paid-API quota, so it must never
run by accident.

GITHUB_TOKEN needs the "repo" scope (classic PAT) or equivalent private-repo
read access -- see docs/plans/2026-07-04-private-repos-per-user-isolation.md."""

import os
import tempfile
import unittest
from pathlib import Path

from . import github_access
from . import ingest
from .corpus import load_chunks
from .pipeline import GatedPipeline
from .provider import GeminiProvider, make_provider
from .retriever import LexicalRetriever
from .trust import PrivateDataError, assert_safe_for_private

REPO = os.environ.get("ICARUS_TEST_PRIVATE_REPO")
TOKEN = os.environ.get("GITHUB_TOKEN")
PAID_KEY = os.environ.get("GEMINI_PAID_API_KEY")

_READY = (
    os.environ.get("RUN_PRIVATE_INGEST") == "1"
    and bool(REPO)
    and bool(TOKEN)
    and bool(PAID_KEY)
)


@unittest.skipUnless(
    _READY,
    "set RUN_PRIVATE_INGEST=1 plus ICARUS_TEST_PRIVATE_REPO, GITHUB_TOKEN, "
    "GEMINI_PAID_API_KEY (needs a real private repo + network + paid API quota)",
)
class PrivateIngestLiveTests(unittest.TestCase):
    def test_access_check_confirms_real_private_repo(self):
        info = github_access.repo_info(REPO, TOKEN)
        self.assertIsNotNone(info, "repo_info returned None -- token can't read this repo")
        self.assertEqual(
            info, {"private": True},
            f"{REPO} is not private per GitHub -- misconfigured ICARUS_TEST_PRIVATE_REPO?",
        )

    def test_real_ingest_and_paid_answer_hold_the_honesty_gate(self):
        with tempfile.TemporaryDirectory() as d:
            counts = ingest.ingest_repo(REPO, d, code_dir=".", token=TOKEN)
            self.assertGreater(sum(counts.values()), 0, "ingest wrote zero chunks")
            chunks_path = Path(d) / "chunks.jsonl"
            meta_path = Path(d) / "meta.json"
            self.assertTrue(chunks_path.exists(), "chunks.jsonl was not written")
            self.assertTrue(meta_path.exists(), "meta.json was not written")

            chunks = load_chunks(chunks_path)
            self.assertTrue(chunks, "no chunks loaded from the live-ingested corpus")

            provider = make_provider("gemini-paid")
            assert_safe_for_private(provider)  # the real chokepoint, real provider
            pipeline = GatedPipeline(LexicalRetriever(chunks), chunks, provider)

            result = pipeline.answer("What does this repository do?")
            self.assertIn(result.verdict, ("answer", "unknown"))
            if result.verdict == "unknown":
                print("WARNING: pipeline abstained -- the citations-subset assertion path "
                      "was NOT exercised this run. Consider a repo with more substantive "
                      "README/docs content, or a more specific question.")
            if result.verdict == "answer":
                self.assertTrue(result.citations, "answer verdict with no citations")
                self.assertTrue(
                    set(result.citations).issubset(set(result.retrieved)),
                    "citations must be a subset of retrieved evidence",
                )

    def test_interlock_refuses_a_real_free_provider(self):
        free_provider = GeminiProvider()  # never private_safe -- see evals/provider.py
        with self.assertRaises(PrivateDataError):
            assert_safe_for_private(free_provider)


if __name__ == "__main__":
    unittest.main()
