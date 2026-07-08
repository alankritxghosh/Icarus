# evals/baseline_retriever.py
"""A third-party comparison point for the comprehension board: what does a
developer already get today by grepping the repo, with none of Icarus's BM25
ranking, semantic retrieval, or query normalization?

This is a YARDSTICK, not a retrieval technique -- it exists to measure how
much Icarus's retrieval is actually worth over the tool every developer
already has, not to be shipped or composed into the real pipeline. Deliberately
dumb: keyword presence only, no term-frequency weighting, no semantics, no
synonym/typo tolerance.

Implemented in pure Python (no subprocess call to an external `grep`/`rg`
binary) so it runs anywhere without requiring ripgrep/grep installed, and so
its behavior is exactly pinned by this file rather than by whatever grep
version/flags happen to be on a given machine -- a fair, reproducible
comparison rather than an environment-dependent one. Emulates
`grep -il -e word1 -e word2 ...`: case-insensitive substring OR-match across
the query's real keywords (common short words are skipped, same as a
developer would skip them when picking a search term), chunks ranked by how
many DISTINCT keywords they contain.
"""

from typing import List

from .corpus import Chunk
from .query_normalize import COMMON_SHORT_WORDS
from .retriever import tokenize


class GrepBaselineRetriever:
    """Same `.search(query, k) -> List[str]` contract as every other retriever
    here, so it drops into the identical `grade()` harness for an apples-to-
    apples comparison -- but it is a comparison baseline, not a component
    meant to be composed into the real pipeline."""

    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks

    def search(self, query: str, k: int = 20) -> List[str]:
        keywords = {w for w in tokenize(query) if w not in COMMON_SHORT_WORDS}
        if not keywords:
            return []
        scored = []
        for c in self.chunks:
            text_lower = c.text.lower()
            hits = sum(1 for w in keywords if w in text_lower)
            if hits > 0:
                scored.append((hits, c.ref))
        # rank by keyword-match count desc, ref asc for determinism (mirrors
        # every other retriever's tie-break convention in this file's family).
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [ref for _, ref in scored[:k]]
