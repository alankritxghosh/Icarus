# evals/retriever.py
"""BM25 lexical retriever over corpus chunks. Stdlib only.

BM25 is the standard keyword-ranking baseline: it scores a chunk by how often
the query's terms appear in it, weighting rare terms higher (idf) and damping
long chunks. Good enough to surface gold PRs whose descriptions share the
question's vocabulary. Embeddings come later, only if this plateaus.
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
