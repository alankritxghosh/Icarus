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

    def __init__(self, chunks: List[Chunk], provider):
        self.chunks = chunks
        # Keyed by ref, not a list parallel to `chunks` -- `chunks` is a public
        # attribute (matching LexicalRetriever's convention), so a caller (e.g.
        # a future hybrid ranker) mutating/reordering it post-construction must
        # never silently pair the wrong vector with the wrong ref.
        self._vectors = {c.ref: provider.embed(c.text) for c in chunks}
        self._provider = provider

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
