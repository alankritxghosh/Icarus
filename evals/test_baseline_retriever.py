# evals/test_baseline_retriever.py
"""GrepBaselineRetriever: the honest 'what does a developer get by grepping
the repo today, with none of Icarus's ranking or semantics' yardstick -- used
to measure how much Icarus's retrieval is actually worth, not shipped as a
retrieval technique itself."""

import unittest

from evals.corpus import Chunk
from evals.baseline_retriever import GrepBaselineRetriever


class GrepBaselineRetrieverTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            Chunk("code:a#L1-L2", "code", "def authenticate(user): return verify(user.token)"),
            Chunk("code:b#L1-L2", "code", "def bump_version(): pkg.version += 1"),
            Chunk("code:c#L1-L2", "code", "def authenticate_admin(user): return verify(user, admin=True)"),
        ]
        self.r = GrepBaselineRetriever(self.chunks)

    def test_matches_chunk_containing_a_query_keyword(self):
        hits = self.r.search("how does authenticate work", k=5)
        self.assertIn("code:a#L1-L2", hits)
        self.assertNotIn("code:b#L1-L2", hits)  # no keyword overlap at all

    def test_ranks_by_count_of_distinct_matched_keywords(self):
        # "authenticate" AND "admin" both literally appear in chunk c but only
        # "authenticate" appears in chunk a -- grep-style keyword-count ranking
        # (no semantics, no term-frequency weighting like BM25) puts c first.
        hits = self.r.search("authenticate admin", k=5)
        self.assertEqual(hits[0], "code:c#L1-L2")

    def test_case_insensitive(self):
        hits = self.r.search("AUTHENTICATE", k=5)
        self.assertIn("code:a#L1-L2", hits)

    def test_no_match_returns_empty(self):
        self.assertEqual(self.r.search("completely unrelated banana", k=5), [])

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.r.search("", k=5), [])

    def test_query_of_only_common_words_returns_empty(self):
        # A real grep search needs at least one real keyword -- "what does the
        # do" has nothing a developer would actually grep for.
        self.assertEqual(self.r.search("what does the do", k=5), [])

    def test_truncates_to_k(self):
        chunks = [Chunk(f"code:{i}#L1-L2", "code", "authenticate") for i in range(10)]
        r = GrepBaselineRetriever(chunks)
        self.assertEqual(len(r.search("authenticate", k=3)), 3)

    def test_ties_break_by_ref_ascending(self):
        chunks = [
            Chunk("code:z#L1-L2", "code", "authenticate"),
            Chunk("code:a#L1-L2", "code", "authenticate"),
        ]
        r = GrepBaselineRetriever(chunks)
        self.assertEqual(r.search("authenticate", k=5), ["code:a#L1-L2", "code:z#L1-L2"])

    def test_no_ranking_signal_beyond_keyword_presence_count(self):
        # Deliberately dumb: a chunk mentioning "authenticate" 50 times ranks
        # THE SAME as one mentioning it once -- no term-frequency weighting,
        # unlike BM25. This is what distinguishes it as a fair "grep" baseline
        # rather than an accidental second BM25 implementation.
        #
        # Refs are deliberately chosen so ref-ascending order and frequency-
        # descending order DISAGREE ("aaa_once" < "zzz_many" alphabetically,
        # but "zzz_many" has far more raw occurrences) -- an earlier version
        # used refs ("code:once"/"code:many") where the two orderings
        # coincidentally agreed, so a term-frequency-weighted (buggy)
        # implementation would have produced the identical expected output and
        # this test could not have told the difference. Verified: mutating the
        # implementation to `text_lower.count(w)` (frequency-weighted) makes
        # this exact assertion fail, where the old fixture did not.
        chunks = [
            Chunk("code:aaa_once#L1-L2", "code", "authenticate"),
            Chunk("code:zzz_many#L1-L2", "code", " ".join(["authenticate"] * 50)),
        ]
        r = GrepBaselineRetriever(chunks)
        # Both match on the same single keyword -> tie -> ref-ascending order
        # ("aaa_once" first), NOT frequency order (which would put "zzz_many",
        # the 50-occurrence chunk, first).
        self.assertEqual(
            r.search("authenticate", k=5),
            ["code:aaa_once#L1-L2", "code:zzz_many#L1-L2"],
        )


if __name__ == "__main__":
    unittest.main()
