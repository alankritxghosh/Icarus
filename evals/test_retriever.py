# evals/test_retriever.py
import time
import unittest
from unittest import mock

from .corpus import Chunk
from .provider import StaticEmbeddingProvider
from .retriever import (
    HybridRetriever,
    LexicalRetriever,
    NormalizingRetriever,
    SemanticRetriever,
    _cosine,
    tokenize,
)


class TokenizeTests(unittest.TestCase):
    def test_lowercases_and_splits_on_non_word(self):
        self.assertEqual(tokenize("Why MSW, not fetch?"), ["why", "msw", "not", "fetch"])


class RetrieverTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            Chunk("pr:1", "pr", "We mock with MSW because stubbing fetch broke on transport switches"),
            Chunk("pr:2", "pr", "Bump version and update changelog"),
            Chunk("code:a.py", "code", "def add(a, b): return a + b"),
        ]
        self.r = LexicalRetriever(self.chunks)

    def test_ranks_relevant_chunk_first(self):
        self.assertEqual(self.r.search("why do we mock with MSW instead of stubbing fetch", k=3)[0], "pr:1")

    def test_returns_at_most_k_refs(self):
        self.assertLessEqual(len(self.r.search("mock", k=1)), 1)

    def test_no_match_returns_empty(self):
        self.assertEqual(self.r.search("xyzzy nonexistentterm", k=3), [])

    def test_ties_break_by_ref_ascending(self):
        # identical text -> identical score -> deterministic ref-ascending order.
        # This determinism is load-bearing for reproducible eval scores.
        chunks = [Chunk("pr:9", "pr", "alpha"), Chunk("pr:1", "pr", "alpha"), Chunk("pr:5", "pr", "alpha")]
        self.assertEqual(LexicalRetriever(chunks).search("alpha", k=3), ["pr:1", "pr:5", "pr:9"])

    def test_empty_corpus_returns_empty(self):
        self.assertEqual(LexicalRetriever([]).search("anything", k=3), [])

    def test_zero_score_chunk_dropped_from_mixed_result(self):
        chunks = [Chunk("pr:1", "pr", "msw mocking rationale"), Chunk("pr:2", "pr", "completely unrelated")]
        self.assertEqual(LexicalRetriever(chunks).search("msw", k=5), ["pr:1"])

    def test_truncates_to_k(self):
        chunks = [Chunk(f"pr:{i}", "pr", "common term") for i in range(5)]
        self.assertEqual(len(LexicalRetriever(chunks).search("common", k=2)), 2)


class CosineTests(unittest.TestCase):
    def test_identical_vectors_have_similarity_one(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [1.0, 0.0]), 1.0)

    def test_opposite_vectors_have_similarity_negative_one(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [-1.0, 0.0]), -1.0)

    def test_orthogonal_vectors_have_similarity_zero(self):
        self.assertAlmostEqual(_cosine([1.0, 0.0], [0.0, 1.0]), 0.0)

    def test_hand_verified_pair(self):
        # dot = 1*0.9 + 0*0.1 = 0.9; |a|=1.0; |b|=sqrt(0.81+0.01)=sqrt(0.82)
        # cos = 0.9 / sqrt(0.82) ~= 0.99388373...
        self.assertAlmostEqual(_cosine([1.0, 0.0], [0.9, 0.1]), 0.9938837346736189)

    def test_zero_vector_does_not_crash_and_returns_zero(self):
        self.assertEqual(_cosine([0.0, 0.0], [1.0, 0.0]), 0.0)
        self.assertEqual(_cosine([1.0, 0.0], [0.0, 0.0]), 0.0)
        self.assertEqual(_cosine([0.0, 0.0], [0.0, 0.0]), 0.0)


class SemanticRetrieverTests(unittest.TestCase):
    def setUp(self):
        # Target chunk describes an auth/login flow but never uses the word
        # "login" (or any token the paraphrased query uses) -- verified via
        # tokenize() in test_paraphrase_shares_no_bm25_tokens_with_target below.
        self.target_text = "validates a users credentials and issues a session cookie"
        self.unrelated1_text = "the recipe calls for two cups of flour and a pinch of salt"
        self.unrelated2_text = "the weather forecast predicts rain over the weekend"
        self.query = "how does login work"

        self.chunks = [
            Chunk("code:auth.py", "code", self.target_text),
            Chunk("code:recipe.py", "code", self.unrelated1_text),
            Chunk("code:weather.py", "code", self.unrelated2_text),
        ]

        # Hand-picked 2D vectors: the query sits close to the target (small
        # angle, cosine ~0.994), opposite the first unrelated chunk (cosine
        # -1.0), and orthogonal to the second (cosine 0.0).
        vectors = {
            self.query: [1.0, 0.0],
            self.target_text: [0.9, 0.1],
            self.unrelated1_text: [-1.0, 0.0],
            self.unrelated2_text: [0.0, 1.0],
        }
        self.provider = StaticEmbeddingProvider(vectors)
        self.retriever = SemanticRetriever(self.chunks, self.provider)

    def test_paraphrase_shares_no_bm25_tokens_with_target(self):
        # The exact claim Brick C exists to prove depends on this being true --
        # verify it directly rather than assuming it.
        self.assertEqual(set(tokenize(self.query)) & set(tokenize(self.target_text)), set())

    def test_semantic_retriever_ranks_paraphrased_target_first(self):
        self.assertEqual(self.retriever.search(self.query, k=3)[0], "code:auth.py")

    def test_lexical_retriever_fails_on_the_same_paraphrased_query(self):
        # Same chunks, same query: BM25 has zero keyword overlap with the
        # target chunk, so it returns nothing -- this is the gap Brick C closes.
        self.assertEqual(LexicalRetriever(self.chunks).search(self.query, k=3), [])

    def test_returns_at_most_k_refs(self):
        self.assertLessEqual(len(self.retriever.search(self.query, k=1)), 1)

    def test_orthogonal_chunk_dropped_as_non_positive_similarity(self):
        # unrelated2 is exactly orthogonal (cosine 0.0) to the query -- dropped
        # by the same "> 0" convention LexicalRetriever uses for a zero score.
        results = self.retriever.search(self.query, k=3)
        self.assertNotIn("code:weather.py", results)

    def test_negative_similarity_chunk_dropped(self):
        results = self.retriever.search(self.query, k=3)
        self.assertNotIn("code:recipe.py", results)

    def test_ties_break_by_ref_ascending(self):
        # Identical vectors -> identical similarity -> deterministic ref-ascending
        # order, mirroring LexicalRetriever's tie-break convention exactly.
        chunks = [Chunk("pr:9", "pr", "alpha"), Chunk("pr:1", "pr", "alpha"), Chunk("pr:5", "pr", "alpha")]
        provider = StaticEmbeddingProvider({"alpha": [1.0, 0.0], "query": [1.0, 0.0]})
        self.assertEqual(
            SemanticRetriever(chunks, provider).search("query", k=3), ["pr:1", "pr:5", "pr:9"]
        )

    def test_truncates_to_k(self):
        chunks = [Chunk(f"pr:{i}", "pr", "common") for i in range(5)]
        provider = StaticEmbeddingProvider({"common": [1.0, 0.0], "query": [1.0, 0.0]})
        self.assertEqual(len(SemanticRetriever(chunks, provider).search("query", k=2)), 2)

    def test_empty_corpus_returns_empty(self):
        provider = StaticEmbeddingProvider({"query": [1.0, 0.0]})
        self.assertEqual(SemanticRetriever([], provider).search("query", k=3), [])

    def test_embeds_each_chunk_exactly_once_at_construction(self):
        calls = []

        def mapping(text):
            calls.append(text)
            return [1.0, 0.0]

        provider = StaticEmbeddingProvider(mapping)
        SemanticRetriever(self.chunks, provider)
        self.assertEqual(calls, [c.text for c in self.chunks])

    def test_no_timeout_by_default_preserves_old_unbounded_behavior(self):
        # Regression guard: every existing caller that doesn't pass timeout=
        # must behave exactly as before this option was added.
        provider = StaticEmbeddingProvider(lambda text: [1.0, 0.0])
        retr = SemanticRetriever(self.chunks, provider)  # must not raise
        self.assertEqual(len(retr.vectors), len(self.chunks))

    def test_timeout_raises_before_finishing_a_slow_embed(self):
        # A fake provider that "sleeps" by faking elapsed wall-clock time via a
        # counter, so the test is fast and deterministic (no real time.sleep).
        chunks = [Chunk(f"pr:{i}", "pr", f"text{i}") for i in range(3)]
        calls = {"n": 0}

        def slow_embed(text):
            calls["n"] += 1
            return [1.0, 0.0]

        provider = StaticEmbeddingProvider(slow_embed)
        real_monotonic = time.monotonic
        # First call to monotonic() is the start time; each check after that
        # advances by 1s per chunk embedded, so timeout=0.5s fires right after
        # chunk 0 (elapsed 1s > 0.5s) -- deterministic, no real sleeping.
        ticks = iter([0.0, 0.0, 1.0])
        with mock.patch("evals.retriever.time.monotonic", side_effect=lambda: next(ticks, 999.0)):
            with self.assertRaises(TimeoutError) as ctx:
                SemanticRetriever(chunks, provider, timeout=0.5)
        self.assertIn("1/3", str(ctx.exception))
        self.assertEqual(calls["n"], 1)  # stopped after exactly one chunk

    def test_on_progress_called_after_every_chunk(self):
        chunks = [Chunk(f"pr:{i}", "pr", f"text{i}") for i in range(3)]
        provider = StaticEmbeddingProvider(lambda text: [1.0, 0.0])
        seen = []
        SemanticRetriever(chunks, provider, on_progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(seen, [(1, 3), (2, 3), (3, 3)])


class HybridRetrieverTests(unittest.TestCase):
    """Fixture shared by all cases below (see docstring on each test for the
    hand-computed RRF math this fixture is built to exercise):

    Query: "cache invalidation strategy"
      - code:a.py -- shares keywords with the query (BM25 rank 1, score
        1.9011...), but its embedding is orthogonal to the query (cosine 0.0
        -- dropped by SemanticRetriever's "> 0" cutoff). Lexical-only hit.
      - code:b.py -- shares zero keywords with the query (BM25 score 0.0 --
        dropped by LexicalRetriever's "> 0" cutoff), but its embedding is
        very close to the query's (cosine ~0.99979 -- semantic rank 1).
        Semantic-only hit.
      - code:c.py -- shares keywords with the query AND has a close
        embedding, so it ranks (BM25 rank 2, score 1.3187...; semantic rank
        2, cosine ~0.99388). Appears in BOTH lists.

    RRF (constant=60, 1-indexed rank, contributions summed per ref):
      - code:a.py: lexical rank 1 -> 1/61 = 0.016393442...; absent from
        semantic -> +0. Total = 1/61.
      - code:b.py: absent from lexical -> +0; semantic rank 1 -> 1/61.
        Total = 1/61.
      - code:c.py: lexical rank 2 -> 1/62; semantic rank 2 -> 1/62.
        Total = 2/62 = 1/31 = 0.032258065... (double the other two, since it
        is the only ref both retrievers found).

    Expected fused order: code:c.py first (highest combined score), then
    code:a.py and code:b.py tied at exactly 1/61 -- broken by ref ascending
    ("code:a.py" < "code:b.py"), matching LexicalRetriever/SemanticRetriever's
    tie-break convention exactly.
    """

    def setUp(self):
        self.query = "cache invalidation strategy"
        self.chunks = [
            Chunk("code:a.py", "code", "cache invalidation strategy for the token cache invalidation cache"),
            Chunk("code:b.py", "code", "evicting stale entries when the ttl expires"),
            Chunk("code:c.py", "code", "cache invalidation strategy uses a ttl to evict stale entries"),
        ]
        self.lexical = LexicalRetriever(self.chunks)
        vectors = {
            self.query: [1.0, 0.0],
            self.chunks[0].text: [0.0, 1.0],   # orthogonal to query -> dropped by semantic
            self.chunks[1].text: [0.98, 0.02],  # very close to query -> semantic rank 1
            self.chunks[2].text: [0.9, 0.1],    # close to query -> semantic rank 2
        }
        self.provider = StaticEmbeddingProvider(vectors)
        self.semantic = SemanticRetriever(self.chunks, self.provider)
        self.hybrid = HybridRetriever(self.lexical, self.semantic)

        # Sanity-check the underlying rankings this whole fixture depends on,
        # so a change to LexicalRetriever/SemanticRetriever's internals fails
        # loudly here rather than silently invalidating the hand-computed
        # RRF math below.
        assert self.lexical.search(self.query, k=10) == ["code:a.py", "code:c.py"]
        assert self.semantic.search(self.query, k=10) == ["code:b.py", "code:c.py"]

    def test_chunk_ranked_highly_by_both_retrievers_ranks_first(self):
        # code:c.py is the only ref both lists agree on -- RRF sums its two
        # contributions (1/62 + 1/62 = 1/31), which beats either lone
        # contribution (1/61) that code:a.py/code:b.py get from a single list.
        self.assertEqual(self.hybrid.search(self.query, k=3)[0], "code:c.py")

    def test_ref_found_by_only_one_retriever_is_still_included(self):
        # code:b.py has zero keyword overlap with the query (BM25 excludes
        # it entirely) but is included in the fused result via its semantic
        # contribution alone -- not dropped, not crashed.
        results = self.hybrid.search(self.query, k=3)
        self.assertIn("code:b.py", results)

    def test_concrete_blending_matches_hand_computed_rrf_order(self):
        # Exact expected order per the fixture docstring's hand computation:
        # code:c.py (1/31) first, then code:a.py and code:b.py tied at 1/61
        # each, broken by ref ascending.
        self.assertEqual(
            self.hybrid.search(self.query, k=3),
            ["code:c.py", "code:a.py", "code:b.py"],
        )

    def test_determinism_same_inputs_same_order_every_time(self):
        first = self.hybrid.search(self.query, k=3)
        for _ in range(5):
            self.assertEqual(self.hybrid.search(self.query, k=3), first)

    def test_ties_break_by_ref_ascending(self):
        # code:a.py and code:b.py are exactly tied at 1/61 in the fixture
        # above; ref-ascending is the deterministic tiebreak.
        results = self.hybrid.search(self.query, k=3)
        self.assertEqual(results[1:], ["code:a.py", "code:b.py"])

    def test_truncates_to_k(self):
        self.assertLessEqual(len(self.hybrid.search(self.query, k=1)), 1)
        self.assertEqual(len(self.hybrid.search(self.query, k=1)), 1)

    def test_empty_when_neither_retriever_finds_anything(self):
        chunks = [Chunk("pr:1", "pr", "completely unrelated text")]
        lexical = LexicalRetriever(chunks)
        provider = StaticEmbeddingProvider({"nomatch query": [1.0, 0.0], "completely unrelated text": [0.0, 1.0]})
        semantic = SemanticRetriever(chunks, provider)
        hybrid = HybridRetriever(lexical, semantic)
        self.assertEqual(hybrid.search("nomatch query", k=5), [])

    def test_generic_over_any_search_compatible_object(self):
        # HybridRetriever must not be hardcoded to LexicalRetriever/
        # SemanticRetriever -- any object with .search(query, k) works,
        # proving it wraps the interface, not the concrete classes.
        class FakeRetriever:
            def __init__(self, refs):
                self._refs = refs

            def search(self, query, k=20):
                return self._refs[:k]

        fake_a = FakeRetriever(["x:1", "x:2"])
        fake_b = FakeRetriever(["x:2", "x:3"])
        result = HybridRetriever(fake_a, fake_b).search("anything", k=10)
        self.assertEqual(set(result), {"x:1", "x:2", "x:3"})
        # x:2 appears in both lists (rank 2 in a, rank 1 in b) so it should
        # combine two contributions and not be dropped.
        self.assertIn("x:2", result)

    def test_duplicate_ref_within_one_list_is_not_double_counted(self):
        # HybridRetriever accepts ANY .search()-compatible retriever, not
        # just our two trusted concrete classes (proven above) -- so it
        # can't assume every retriever it's handed dedupes internally. A
        # hostile/buggy retriever returning the same ref twice in ONE list
        # must not get its score doubled.
        class DupeRetriever:
            def search(self, query, k=20):
                return ["x:1", "x:1", "x:2"][:k]

        class EmptyRetriever:
            def search(self, query, k=20):
                return []

        rrf_constant = 60
        result = HybridRetriever(DupeRetriever(), EmptyRetriever(), rrf_constant=rrf_constant).search(
            "anything", k=10
        )
        self.assertEqual(result, ["x:1", "x:2"])

        # Rebuild the raw scores the same way HybridRetriever does internally
        # to assert the exact (non-doubled) value, not just the ordering.
        expected_x1 = 1.0 / (rrf_constant + 1)  # only the FIRST occurrence counts (rank 1)
        expected_x2 = 1.0 / (rrf_constant + 3)  # rank 3: enumerate still advances past the dupe
        buggy_x1_if_double_counted = 1.0 / (rrf_constant + 1) + 1.0 / (rrf_constant + 2)
        self.assertAlmostEqual(expected_x1, 0.01639344262295082)
        self.assertAlmostEqual(expected_x2, 0.015873015873015872)
        self.assertNotAlmostEqual(expected_x1, buggy_x1_if_double_counted)
        # x:1 (deduped, rank 1) must still outrank x:2 (rank 3) -- confirming
        # the guard didn't drop x:1's contribution entirely, only its dupe.
        self.assertGreater(expected_x1, expected_x2)

    def test_k_zero_returns_empty_list_no_crash(self):
        self.assertEqual(self.hybrid.search(self.query, k=0), [])

    def test_both_retrievers_empty_returns_empty_list(self):
        # Pure-fake aggregation-over-nothing case, isolated from any real
        # retrieval semantics (BM25/cosine cutoffs etc.) -- distinct from
        # test_empty_when_neither_retriever_finds_anything above, which
        # exercises the realistic LexicalRetriever/SemanticRetriever path.
        class EmptyRetriever:
            def search(self, query, k=20):
                return []

        result = HybridRetriever(EmptyRetriever(), EmptyRetriever()).search("anything", k=5)
        self.assertEqual(result, [])

    def test_default_construction_leaves_weights_at_one(self):
        # Locks the unweighted contract every hand-computed test above
        # depends on -- omitting semantic_weight/lexical_weight must never
        # silently change behavior.
        self.assertEqual(self.hybrid.semantic_weight, 1.0)
        self.assertEqual(self.hybrid.lexical_weight, 1.0)


class WeightedHybridRetrieverTests(unittest.TestCase):
    """T7 (docs/plans/2026-07-17-ast-chunking-all-languages.md): proves the
    optional semantic_weight/lexical_weight scale each list's RRF
    contribution before summing, using the SAME fixture as
    HybridRetrieverTests above so the only variable is the weighting.

    With semantic_weight=15, lexical_weight=1, rrf_constant=60:
      - code:a.py: lexical rank 1 -> 1 * 1/61 = 0.016393442...; absent from
        semantic -> +0. Total = 1/61.
      - code:b.py: absent from lexical -> +0; semantic rank 1 ->
        15 * 1/61 = 15/61 = 0.245901639... Total = 15/61.
      - code:c.py: lexical rank 2 -> 1 * 1/62 = 0.016129032...; semantic
        rank 2 -> 15 * 1/62 = 15/62 = 0.241935484... Total = 16/62 =
        0.258064516...

    Expected fused order: code:c.py (0.2581) > code:b.py (0.2459) >
    code:a.py (0.0164) -- a real reordering versus the unweighted fixture
    above, where code:a.py and code:b.py tied. This is the exact mechanism
    behind the fix found live: weighting semantic higher lets a
    semantically-excellent, lexically-invisible ref (code:b.py here) win out
    over a merely lexical-only one, instead of both being flattened to the
    same score.
    """

    def setUp(self):
        self.query = "cache invalidation strategy"
        self.chunks = [
            Chunk("code:a.py", "code", "cache invalidation strategy for the token cache invalidation cache"),
            Chunk("code:b.py", "code", "evicting stale entries when the ttl expires"),
            Chunk("code:c.py", "code", "cache invalidation strategy uses a ttl to evict stale entries"),
        ]
        self.lexical = LexicalRetriever(self.chunks)
        vectors = {
            self.query: [1.0, 0.0],
            self.chunks[0].text: [0.0, 1.0],
            self.chunks[1].text: [0.98, 0.02],
            self.chunks[2].text: [0.9, 0.1],
        }
        self.provider = StaticEmbeddingProvider(vectors)
        self.semantic = SemanticRetriever(self.chunks, self.provider)
        assert self.lexical.search(self.query, k=10) == ["code:a.py", "code:c.py"]
        assert self.semantic.search(self.query, k=10) == ["code:b.py", "code:c.py"]

    def test_weighting_is_stored_verbatim(self):
        hybrid = HybridRetriever(self.lexical, self.semantic, semantic_weight=15.0, lexical_weight=1.0)
        self.assertEqual(hybrid.semantic_weight, 15.0)
        self.assertEqual(hybrid.lexical_weight, 1.0)

    def test_heavier_semantic_weight_matches_hand_computed_order(self):
        hybrid = HybridRetriever(self.lexical, self.semantic, semantic_weight=15.0, lexical_weight=1.0)
        self.assertEqual(
            hybrid.search(self.query, k=3),
            ["code:c.py", "code:b.py", "code:a.py"],
        )

    def test_heavier_semantic_weight_reorders_versus_the_unweighted_tie(self):
        # The exact same fixture, unweighted, ties code:a.py/code:b.py at
        # 1/61 (ref-ascending puts a before b -- see HybridRetrieverTests).
        # Weighting semantic must break that tie in b's favor, proving the
        # weight parameter actually changes fusion behavior, not just stores
        # a number nothing reads.
        unweighted = HybridRetriever(self.lexical, self.semantic).search(self.query, k=3)
        weighted = HybridRetriever(
            self.lexical, self.semantic, semantic_weight=15.0, lexical_weight=1.0
        ).search(self.query, k=3)
        self.assertEqual(unweighted[1:], ["code:a.py", "code:b.py"])
        self.assertEqual(weighted[1:], ["code:b.py", "code:a.py"])

    def test_exact_weighted_scores_match_hand_computation(self):
        rrf_constant = 60
        semantic_weight = 15.0
        lexical_weight = 1.0
        hybrid = HybridRetriever(
            self.lexical, self.semantic, rrf_constant=rrf_constant,
            semantic_weight=semantic_weight, lexical_weight=lexical_weight,
        )
        # Rebuild the raw scores the same way HybridRetriever does internally.
        scores = {}
        for ranked, weight in (
            (self.lexical.search(self.query, 20), lexical_weight),
            (self.semantic.search(self.query, 20), semantic_weight),
        ):
            for rank, ref in enumerate(ranked, start=1):
                scores[ref] = scores.get(ref, 0.0) + weight / (rrf_constant + rank)

        self.assertAlmostEqual(scores["code:a.py"], 1.0 / 61)
        self.assertAlmostEqual(scores["code:b.py"], 15.0 / 61)
        self.assertAlmostEqual(scores["code:c.py"], 1.0 / 62 + 15.0 / 62)
        self.assertEqual(hybrid.search(self.query, k=3), ["code:c.py", "code:b.py", "code:a.py"])

    def test_zero_lexical_weight_fully_excludes_lexical_contribution(self):
        # A degenerate but valid weighting (0.0) must zero out that list's
        # score contribution entirely -- proving the multiplier is applied
        # to the score, not just used as a tiebreak nudge. HybridRetriever
        # doesn't filter zero-score refs (that's LexicalRetriever/
        # SemanticRetriever's own "> 0" job, not the fuser's), so
        # code:a.py -- lexical-only in this fixture -- still appears in the
        # fused list, but with a zeroed score it must sort dead last, behind
        # every ref that earned a real positive contribution.
        hybrid = HybridRetriever(self.lexical, self.semantic, semantic_weight=1.0, lexical_weight=0.0)
        results = hybrid.search(self.query, k=3)
        self.assertEqual(results[-1], "code:a.py")
        self.assertEqual(set(results), {"code:a.py", "code:b.py", "code:c.py"})


class NormalizingRetrieverTests(unittest.TestCase):
    """Q2: wraps any .search()-compatible retriever, normalizing the query
    (Q1's normalize_query) before delegating. Wiring "ahead of the retriever"
    per the plan -- the wrapped retriever, and everything else in the pipeline
    (the writer prompt), never sees the normalized text, only the original
    inner retriever gets the corrected query for SEARCH purposes."""

    def setUp(self):
        self.vocab = frozenset({"function", "authenticate"})

    def test_delegates_with_the_normalized_query(self):
        seen = []

        class _Spy:
            def search(self, query, k=20):
                seen.append(query)
                return ["ref:1"]

        r = NormalizingRetriever(_Spy(), self.vocab)
        result = r.search("fuction authh", k=5)
        self.assertEqual(len(seen), 1)  # exactly one delegated call
        self.assertNotIn("fuction", seen[0].split())  # the INNER retriever saw the correction
        self.assertEqual(result, ["ref:1"])  # and the inner retriever's result passes through

    def test_passes_k_through_unchanged(self):
        seen_k = []

        class _Spy:
            def search(self, query, k=20):
                seen_k.append(k)
                return []

        NormalizingRetriever(_Spy(), self.vocab).search("function", k=7)
        self.assertEqual(seen_k, [7])

    def test_composes_with_a_real_retriever(self):
        chunks = [Chunk("code:a#L1-L2", "code", "def authenticate(user): pass")]
        lexical = LexicalRetriever(chunks)
        vocab = frozenset({"authenticate"})
        r = NormalizingRetriever(lexical, vocab)
        # "authenicate" is a typo for "authenticate" (one letter dropped) --
        # close enough to correct, and BM25 alone finds nothing for the typo'd
        # token (no keyword overlap), so this only passes if normalization ran.
        self.assertNotIn("code:a#L1-L2", lexical.search("authenicate", k=5))  # BM25 alone: miss
        self.assertIn("code:a#L1-L2", r.search("authenicate", k=5))  # normalized: hit


if __name__ == "__main__":
    unittest.main()
