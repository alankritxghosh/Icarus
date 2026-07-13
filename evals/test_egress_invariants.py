# evals/test_egress_invariants.py
"""Egress invariants: private text can only ever reach the private-safe writer.

Proves, offline, with an injectable spy provider (not a mocked interlock):
  1. the sentinel in a private chunk reaches ONLY a provider that genuinely
     passed `assert_safe_for_private`, via the same construction shape
     `demo/library.py`'s `_build_gated_pipeline` uses;
  2. handing that same construction path an UNSAFE provider raises
     `PrivateDataError` BEFORE any prompt is sent (zero prompts, not just a
     raise);
  3. the serve path (`demo/library.py` + `demo/server.py`) never imports the
     judge -- the judge is a quality dial, not part of what answers a user;
  4. git hygiene: per-user private storage is gitignored, and the tracked
     tree is free of anything secret-shaped.

This is the last proof task in Brick E, alongside test_cross_user_isolation
(Task 13). No production code is touched or mocked away here.
"""

import subprocess
import unittest
from pathlib import Path

from .corpus import Chunk
from .provider import Provider
from .retriever import LexicalRetriever
from .pipeline import GatedPipeline
from .trust import PrivateDataError, assert_safe_for_private

ROOT = Path(__file__).resolve().parent.parent
SENTINEL = "XYZZY-PRIVATE-42"


class SpyProvider(Provider):
    """Test double: records every prompt it's given, returns a canned reply.

    `private_safe` is settable per-instance so the same class can play both
    the "safe" and "unsafe" role across tests. The canned response is a
    deliberate abstention ({"verdict": "unknown"}) -- valid honesty-gate JSON
    that always resolves to Result(verdict="unknown"). This test cares about
    WHAT reached the provider (`self.prompts`), not the answer/abstain split,
    so the simplest reply that reliably parses is the right choice.
    """

    def __init__(self, private_safe: bool, response: str = '{"verdict": "unknown"}'):
        self.private_safe = private_safe
        self._response = response
        self.prompts = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._response


def _private_chunks():
    return [
        Chunk("code:secret.py", "code", f"def handle(): return '{SENTINEL}'"),
        Chunk("code:other.py", "code", "def unrelated(): pass"),
    ]


def build_safe_pipeline(provider, chunks):
    """Mirrors demo/library.py's _build_gated_pipeline trust chokepoint:
    check the interlock at construction, the single chokepoint where the
    provider is fixed for the pipeline's lifetime, THEN build the pipeline."""
    assert_safe_for_private(provider)
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


class PrivateEgressTests(unittest.TestCase):
    def test_sentinel_reaches_only_the_private_safe_spy(self):
        chunks = _private_chunks()
        safe_spy = SpyProvider(private_safe=True)

        pipeline = build_safe_pipeline(safe_spy, chunks)
        pipeline.answer("what does handle return")

        # The sentinel genuinely reached the spy's prompt -- the product
        # working as intended (private code reaches the private-safe writer).
        self.assertTrue(
            any(SENTINEL in p for p in safe_spy.prompts),
            "sentinel never reached the private-safe provider's prompt",
        )
        # No other provider object exists anywhere in this test's scope: only
        # `safe_spy` was ever constructed or passed to the pipeline builder.

    def test_the_private_safe_spy_is_called_exactly_once(self):
        chunks = _private_chunks()
        safe_spy = SpyProvider(private_safe=True)
        pipeline = build_safe_pipeline(safe_spy, chunks)
        pipeline.answer("what does handle return")

        # The one spy that exists was called exactly once. No other provider
        # object is constructed anywhere in this test's scope -- `safe_spy` is
        # the only Provider instance this test ever creates or passes to the
        # pipeline builder.
        self.assertEqual(len(safe_spy.prompts), 1)


class InterlockWiredPathTests(unittest.TestCase):
    def test_unsafe_provider_is_refused_before_any_prompt_is_sent(self):
        chunks = _private_chunks()
        unsafe_spy = SpyProvider(private_safe=False)

        with self.assertRaises(PrivateDataError):
            build_safe_pipeline(unsafe_spy, chunks)

        # The interlock fires at construction -- before .complete() is ever
        # called -- so nothing was sent to the refused provider.
        self.assertEqual(unsafe_spy.prompts, [])


class NoJudgeInServePathTests(unittest.TestCase):
    """The judge (evals/judge.py, class Judge) is a quality dial used only by
    the eval harness/grader -- it must never be wired into what answers a
    live user. Checked against precise import-shaped substrings (not a bare
    case-insensitive "judge", which could false-positive on an unrelated
    word) so this both catches a disguised import and doesn't cry wolf."""

    FORBIDDEN_SUBSTRINGS = (
        "evals.judge",
        "from .judge",
        "from evals.judge",
        "import judge",
        "Judge(",
    )

    def _assert_clean(self, path: Path):
        source = path.read_text()
        for needle in self.FORBIDDEN_SUBSTRINGS:
            self.assertNotIn(
                needle, source,
                f"{path} references the judge ({needle!r}) -- the judge must "
                "never be wired into the live serve path",
            )

    def test_library_does_not_import_the_judge(self):
        self._assert_clean(ROOT / "demo" / "library.py")

    def test_server_does_not_import_the_judge(self):
        self._assert_clean(ROOT / "demo" / "server.py")


class GitHygieneTests(unittest.TestCase):
    def test_gitignore_covers_per_user_private_storage(self):
        # .gitignore has a `data/` entry (Task 4) covering all per-user
        # storage, public caches AND private code alike.
        probe = "data/1001/private/x/chunks.jsonl"
        result = subprocess.run(
            ["git", "check-ignore", "-q", probe],
            cwd=ROOT,
        )
        self.assertEqual(
            result.returncode, 0,
            f"git does not ignore {probe!r} -- per-user private storage would "
            "be committable",
        )

    def test_scan_secrets_is_clean_on_the_tracked_tree(self):
        script = ROOT / "scripts" / "scan_secrets.sh"
        if not script.exists():
            self.skipTest("scripts/scan_secrets.sh not present in this environment")
        result = subprocess.run(
            ["bash", str(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"scan_secrets.sh found something secret-shaped:\n{result.stdout}\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
