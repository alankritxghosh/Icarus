"""A named commit SHA is an exact-identifier LOOKUP, not a search.

Commits are deliberately not indexed (a real repo has 10k-1M of them), so
"what did commit abc123 change?" used to have zero evidence and always
abstained. These tests prove the on-demand anchor path: the SHA is fetched
live, reaches the writer, and grounds a citation -- while a fetch failure
still fails safe to an honest unknown, and hex-shaped English words never
trigger a fetch.
"""

import unittest

from .corpus import Chunk
from .pipeline import GatedPipeline
from .provider import StaticProvider
from .gate import gate


class _Retriever:
    def __init__(self, refs=()):
        self._refs = list(refs)

    def search(self, query, k):
        return self._refs[:k]


_COMMIT = Chunk(
    ref="commit:abc1234def5678",
    source="commit",
    text="Commit abc1234def: raise the embed timeout\n\nmodified evals/library.py (+4/-1)",
)


def _pipeline(fetched, seen):
    def live_commit(sha):
        seen.append(sha)
        return fetched

    provider = StaticProvider([
        '{"verdict": "answer", "answer": "It raised the embed timeout.",'
        ' "citations": ["commit:abc1234def5678"]}'
    ])
    return GatedPipeline(_Retriever(), [], provider, live_commit_fetch=live_commit)


class CommitLookupTests(unittest.TestCase):
    def test_named_sha_is_fetched_and_grounds_the_answer(self):
        seen = []
        r = _pipeline(_COMMIT, seen).answer("What did commit abc1234def5678 change?")
        self.assertEqual(seen, ["abc1234def5678"])
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["commit:abc1234def5678"])

    def test_failed_fetch_falls_back_to_honest_unknown(self):
        seen = []
        r = _pipeline(None, seen).answer("What did commit abc1234def5678 change?")
        self.assertEqual(seen, ["abc1234def5678"])
        self.assertEqual(r.verdict, "unknown")

    def test_hex_shaped_english_word_is_not_fetched(self):
        seen = []
        # "defaced" is 7 chars, all in [0-9a-f], and is not a SHA.
        _pipeline(None, seen).answer("Why was this defaced?")
        self.assertEqual(seen, [])

    def test_bare_sha_without_the_word_commit_still_fetches(self):
        seen = []
        _pipeline(None, seen).answer("What does 9ca9f61 do?")
        self.assertEqual(seen, ["9ca9f61"])

    def test_no_commit_fetcher_configured_is_a_no_op(self):
        # The eval board builds no live fetcher; it must stay fully offline.
        provider = StaticProvider(['{"verdict": "unknown"}'])
        r = GatedPipeline(_Retriever(), [], provider).answer("what did commit abc1234 do?")
        self.assertEqual(r.verdict, "unknown")


class CommitRationaleGateTests(unittest.TestCase):
    def test_commit_message_counts_as_recorded_rationale(self):
        raw = ('{"verdict": "answer", "answer": "To stop large repos timing out.",'
               ' "citations": ["commit:abc1234def5678"]}')
        r = gate(raw, ["commit:abc1234def5678"],
                 question="Why was the embed timeout raised?",
                 evidence={"commit:abc1234def5678": _COMMIT.text})
        self.assertEqual(r.verdict, "answer")


if __name__ == "__main__":
    unittest.main()
