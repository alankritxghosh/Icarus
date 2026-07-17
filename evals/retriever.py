# evals/retriever.py
"""Retrievers over corpus chunks: BM25 (lexical) and cosine (semantic). Stdlib only.

BM25 is the standard keyword-ranking baseline: it scores a chunk by how often
the query's terms appear in it, weighting rare terms higher (idf) and damping
long chunks. Good enough to surface gold PRs whose descriptions share the
question's vocabulary -- but it cannot match a paraphrase that shares no terms
with the target text (Brick C's fatal case: "how does login work" vs. a chunk
that says "validates a user's credentials and issues a session cookie").

SemanticRetriever closes that gap: it ranks chunks by cosine similarity between
an embedded query and embedded chunk text (via the EmbeddingProvider
abstraction in evals/provider.py), so meaning-close text ranks together even
with zero keyword overlap. Same .search(query, k) -> List[str] contract as
LexicalRetriever -- a drop-in replacement, not a new interface.
"""

import math
import re
import time
from collections import Counter
from typing import List

from .corpus import Chunk

_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN.findall(text.lower())


class LexicalRetriever:
    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self._doc_tokens = [tokenize(c.text) for c in chunks]
        self._doc_len = [len(t) for t in self._doc_tokens]
        self._avgdl = (sum(self._doc_len) / len(self._doc_len)) if self._doc_len else 0.0
        self._tf = [Counter(t) for t in self._doc_tokens]
        df: Counter = Counter()
        for toks in self._doc_tokens:
            for term in set(toks):
                df[term] += 1
        n_docs = len(chunks)
        self._idf = {t: math.log(1 + (n_docs - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def _score(self, q_tokens: List[str], i: int) -> float:
        tf, dl, score = self._tf[i], self._doc_len[i], 0.0
        for term in q_tokens:
            freq = tf.get(term, 0)
            if not freq:
                continue
            denom = freq + self.k1 * (1 - self.b + self.b * dl / (self._avgdl or 1))
            score += self._idf.get(term, 0.0) * (freq * (self.k1 + 1)) / denom
        return score

    def search(self, query: str, k: int = 20) -> List[str]:
        q_tokens = tokenize(query)
        scored = [(self._score(q_tokens, i), self.chunks[i].ref) for i in range(len(self.chunks))]
        # rank by score desc, ref asc for determinism; drop zero-score chunks
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [ref for s, ref in scored[:k] if s > 0]


def _cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors, stdlib-only.

    Returns 0.0 for a zero-magnitude vector rather than raising ZeroDivisionError.
    0.0 is cosine's own "orthogonal / no relationship" value, so a degenerate
    all-zero embedding (which carries no directional information at all) sorts
    exactly where an unrelated chunk would -- never first, but also never
    poisoning the whole search with a crash.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticRetriever:
    """Ranks chunks by cosine similarity between embedded query and chunk text.

    Drop-in replacement for LexicalRetriever: same constructor shape (chunks
    first) and the exact same `.search(query, k) -> List[str]` contract,
    including the ref-ascending tie-break convention. `provider` is duck-typed
    -- anything with `.embed(text: str) -> list` works (EmbeddingProvider or
    StaticEmbeddingProvider in tests); we don't import the class here since we
    never need to construct or isinstance-check it.
    """

    def __init__(self, chunks: List[Chunk], provider, vectors=None, timeout=None, on_progress=None):
        self.chunks = chunks
        # Keyed by ref, not a list parallel to `chunks` -- `chunks` is a public
        # attribute (matching LexicalRetriever's convention), so a caller (e.g.
        # a future hybrid ranker) mutating/reordering it post-construction must
        # never silently pair the wrong vector with the wrong ref.
        #
        # `vectors` lets a caller supply precomputed chunk embeddings (e.g. from
        # an on-disk cache) to skip the expensive embed-every-chunk pass. It MUST
        # cover every chunk's ref (search() indexes self._vectors[c.ref]); the
        # caller owns that guarantee. The provider is still kept for embedding
        # the QUERY at search time, so a real embedder is always required.
        if vectors is not None:
            missing = {c.ref for c in chunks} - set(vectors)
            if missing:
                # Fail LOUD at construction rather than KeyError at query time:
                # search() indexes self._vectors[c.ref] for every chunk.
                raise ValueError(
                    f"vectors missing {len(missing)} of {len(chunks)} chunk ref(s)"
                )
            self._vectors = vectors
        else:
            self._vectors = self._embed_all(chunks, provider, timeout, on_progress)
        self._provider = provider

    @staticmethod
    def _embed_all(chunks, provider, timeout, on_progress):
        """Embed every chunk sequentially -- one `.embed()` call per chunk, NOT
        batched into a single call (measured: batching all-at-once was ~10x
        SLOWER for this workload, not faster -- fastembed's internal batch
        path evidently doesn't help here, so don't "optimize" this into a
        single provider.embed(texts) call).

        `timeout` (seconds, wall-clock) bounds the whole loop so a
        pathologically slow embedder -- e.g. a CPU-throttled host -- fails
        loudly instead of hanging forever with zero signal. This is not
        theoretical: a private-repo connect on Render's free tier ran 35+
        minutes with no way to tell if it was almost done or truly stuck
        (docs/HANDOFF.md). None (the default) preserves the old unbounded
        behavior exactly, for every caller that doesn't pass it.

        `on_progress(done, total)`, if given, is called after every chunk so
        a slow embed is at least OBSERVABLE (e.g. in server logs) instead of
        a silent black box."""
        start = time.monotonic()
        total = len(chunks)
        vectors = {}
        for i, c in enumerate(chunks):
            if timeout is not None and time.monotonic() - start > timeout:
                raise TimeoutError(
                    f"embedding timed out after {timeout:.0f}s ({i}/{total} chunks done)"
                )
            vectors[c.ref] = provider.embed(c.text)
            if on_progress is not None:
                on_progress(i + 1, total)
        return vectors

    @property
    def vectors(self):
        """The {ref: embedding} map -- exposed so a caller can persist it to a
        cache after construction (see demo/library.py's vector cache)."""
        return self._vectors

    def search(self, query: str, k: int = 20) -> List[str]:
        q_vec = self._provider.embed(query)
        scored = [(_cosine(q_vec, self._vectors[c.ref]), c.ref) for c in self.chunks]
        # rank by similarity desc, ref asc for determinism (mirrors LexicalRetriever).
        # Cosine's natural range is [-1, 1], where 0 means "no relationship" and
        # negative means "opposite" -- both are non-matches, so "> 0" (not ">=
        # some positive threshold") is the right cutoff: it drops orthogonal and
        # opposite chunks while keeping anything with a genuine positive lean
        # toward the query, exactly mirroring BM25's "no evidence at all" cutoff.
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [ref for s, ref in scored[:k] if s > 0]


class HybridRetriever:
    """Fuses two ranked retrievers via Reciprocal Rank Fusion (RRF).

    BM25 scores and cosine similarities live on completely different, mutually
    incomparable scales -- there's no principled way to add or normalize them
    directly. RRF sidesteps that by throwing away the raw score entirely and
    combining retrievers using only RANK POSITION: for a ref at 1-indexed rank
    `r` in a list, its contribution from that list is `1 / (rrf_constant + r)`.
    A ref's final score is the SUM of that contribution across every list it
    appears in -- so a ref both retrievers rank highly gets boosted (it earns
    two decent contributions), while a ref only one retriever found still gets
    a fair non-zero score from that one list, rather than being penalized to
    zero for the other list's silence.

    `rrf_constant = 60` is the standard default from the original RRF paper/
    practice (it dampens the influence of very top ranks so rank 1 vs. rank 2
    doesn't dominate the fused score disproportionately); we use it as a
    sensible off-the-shelf default rather than tuning it.

    `semantic_weight`/`lexical_weight` (both default 1.0, i.e. plain
    unweighted RRF -- the ORIGINAL contract, unchanged) scale each list's
    contribution before summing. Found live 2026-07-17 (T7 of
    docs/plans/2026-07-17-ast-chunking-all-languages.md), AFTER AST chunking
    fixed the embedder's 512-token truncation: on the real comprehension
    board, semantic alone hit 84.6% recall@5 while equal-weight RRF fusion
    hit only 69.2% -- worse than either retriever needed to be. Root cause is
    a structural property of RRF, not a bug: it rewards CONSENSUS (moderate
    rank in both lists) over a single retriever's excellent rank, so once
    semantic dominates, BM25's noisy also-ran candidates can out-accumulate a
    semantically-excellent, lexically-invisible gold chunk purely by also
    showing up (mediocrely) in BOTH lists. Confirmed directly: on that same
    board, BM25 rescued ZERO questions semantic alone missed -- every lexical
    hit was already a semantic hit (small-N evidence, board-specific, not a
    universal claim that lexical search never helps). Sweeping `rrf_constant`
    alone had NO effect (a ref absent from BM25's own top-20 gets zero
    contribution regardless of the constant -- the constant only reweights
    ranks within a list a ref already appears in). Sweeping semantic_weight
    at lexical_weight=1 showed a clean plateau: recall recovers to
    semantic-alone's exact ceiling (84.6%) starting at weight=15 and stays
    flat through weight=100 -- see demo/library.py's `_build_retriever` for
    the production weighting chosen from that plateau. Kept as an explicit,
    optional parameter (not baked into the default) so this file's own
    extensive existing test suite (evals/test_retriever.py), which
    hand-computes exact unweighted RRF scores, needed zero changes.

    Takes two ALREADY-CONSTRUCTED objects, each implementing `.search(query,
    k) -> List[str]` -- duck-typed, not hardcoded to LexicalRetriever/
    SemanticRetriever, so any two compatible retrievers (including test
    fakes) can be fused.
    """

    def __init__(self, lexical, semantic, rrf_constant: int = 60,
                semantic_weight: float = 1.0, lexical_weight: float = 1.0):
        self.lexical = lexical
        self.semantic = semantic
        self.rrf_constant = rrf_constant
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight

    def search(self, query: str, k: int = 20) -> List[str]:
        # Pull a generous recall pool from each underlying retriever -- more
        # than the final `k` we'll return -- so RRF has enough candidates to
        # fuse from (a ref ranked, say, 15th by one retriever and 2nd by the
        # other should still be able to surface near the top of the fused
        # list, which requires actually seeing it in both pools). `max(k, 20)`
        # keeps the pool at least the standard default recall depth used
        # elsewhere in this file (both retrievers' own `k` default is 20),
        # while still growing with a caller-requested larger `k`.
        recall_n = max(k, 20)
        lexical_ranked = self.lexical.search(query, recall_n)
        semantic_ranked = self.semantic.search(query, recall_n)

        scores: dict = {}
        for ranked, weight in ((lexical_ranked, self.lexical_weight),
                               (semantic_ranked, self.semantic_weight)):
            # A ref repeating WITHIN one list is a bug in that retriever (a
            # legitimate retriever never returns the same ref twice) -- since
            # HybridRetriever accepts ANY .search()-compatible object, not
            # just our two trusted concrete classes, we can't assume that
            # holds. Track refs already credited from THIS list so a
            # duplicate is silently ignored rather than double-counted; a ref
            # appearing in both the lexical AND semantic lists is fine and
            # intentional (that's two separate lists, each contributing once).
            seen_in_this_list: set = set()
            for rank, ref in enumerate(ranked, start=1):
                if ref in seen_in_this_list:
                    continue
                seen_in_this_list.add(ref)
                scores[ref] = scores.get(ref, 0.0) + weight / (self.rrf_constant + rank)

        fused = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return [ref for ref, _ in fused[:k]]


class NormalizingRetriever:
    """Wraps any `.search(query, k) -> List[str]`-compatible retriever, running
    Brick Q's stdlib fuzzy-spelling normalization (evals/query_normalize.py) on
    the query BEFORE delegating -- "wire ahead of the retriever" per the plan.

    Duck-typed like every other retriever here, so it composes freely, e.g.
    `NormalizingRetriever(HybridRetriever(lexical, semantic), vocabulary)`.
    Only the text used to SEARCH is normalized; the caller's original question
    (e.g. what GatedPipeline hands to the writer) is untouched -- this class
    never sees or returns anything but retrieval results.
    """

    def __init__(self, retriever, vocabulary, cutoff: float = 0.8):
        self._retriever = retriever
        self._vocabulary = vocabulary
        self._cutoff = cutoff

    def search(self, query: str, k: int = 20) -> List[str]:
        from .query_normalize import normalize_query  # local: avoids a circular
        # import (query_normalize imports retriever.tokenize at module level).
        normalized = normalize_query(query, self._vocabulary, self._cutoff)
        return self._retriever.search(normalized, k)
