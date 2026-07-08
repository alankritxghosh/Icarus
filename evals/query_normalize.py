# evals/query_normalize.py
"""Query-understanding layer (Brick Q): a thin, stdlib-only normalization pass
that runs BEFORE retrieval so a misspelled/mistyped question still matches the
vocabulary actually used in the codebase.

Design (locked in the plan doc, docs/plans/2026-07-06-tester-feedback-deeper-
comprehension.md, "Brick Q"): embeddings (Brick C) already absorb most
paraphrase/synonym variation; this layer targets what embeddings do NOT
reliably fix -- individual misspelled tokens (e.g. "fuction" for "function").
No new dependency: stdlib difflib fuzzy matching against a vocabulary built
FROM THE CORPUS ITSELF, so a "correction" is always a real term that actually
appears in this codebase, never a guess from an external dictionary.

This module is retrieval-only preprocessing. The ORIGINAL question text is
still what a writer answers from and what a user sees -- only the text used to
SEARCH gets normalized (see evals/retriever.py's NormalizingRetriever, which
wraps a retriever rather than touching the pipeline/writer at all).
"""

import difflib
import re
from typing import Iterable

from .corpus import Chunk
from .retriever import tokenize

# Common short English words normalize_query never "corrects" -- without this,
# a legitimate short word could get fuzzy-matched into an unrelated corpus
# token purely by edit-distance coincidence. Deliberately small, stdlib-only,
# and orthogonal to the corpus vocabulary (never removed/tuned per-repo).
COMMON_SHORT_WORDS = frozenset({
    "a", "an", "as", "at", "by", "do", "he", "if", "in", "is", "it",
    "of", "on", "or", "the", "to", "we", "so", "up",
})

# Matches retriever.tokenize()'s own splitting EXACTLY (same character class,
# case-insensitively) -- this must stay in lockstep with how the vocabulary
# itself is built. An earlier version kept dotted filenames ("tools.py") as
# one compound token, which backfired: retriever.tokenize() splits on the
# period too, so that compound token could never exist in the vocabulary
# verbatim, forcing every filename reference through fuzzy-matching against a
# vocabulary of single (non-dotted) words -- which silently corrupted real
# filenames (e.g. "templates.py" -> "templates", losing the extension) and
# measurably regressed already-correct clean-phrasing recall. Splitting
# identically to tokenize() means a real word (e.g. "templates", "py") is
# almost always present in the vocabulary verbatim and passes straight
# through unmangled.
_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def build_vocabulary(chunks: Iterable[Chunk]) -> frozenset:
    """The set of real tokens that appear in this codebase's corpus, lowercased
    -- reuses retriever.tokenize so the vocabulary matches exactly what BM25
    already indexes. Corrections only ever land on a word genuinely present in
    THIS codebase, never an arbitrary dictionary term."""
    vocab = set()
    for c in chunks:
        vocab.update(tokenize(c.text))
    return frozenset(vocab)


def normalize_query(text: str, vocabulary, cutoff: float = 0.8) -> str:
    """Best-effort spelling correction toward `vocabulary`, for RETRIEVAL only.

    Each word already in the vocabulary (or a common short word) passes
    through unchanged. Every other word is fuzzy-matched (stdlib difflib)
    against the vocabulary; a close-enough match (score >= cutoff) replaces
    it, otherwise the original word is kept as-is -- a low-confidence guess is
    worse than leaving the word alone (the retriever still has BM25 partial
    credit + semantic similarity to fall back on).
    """
    words = _WORD_RE.findall(text)
    if not words:
        return ""
    vocab_set = vocabulary if isinstance(vocabulary, (set, frozenset)) else set(vocabulary)
    # No candidate ordering/sorting needed for determinism: difflib.get_close_
    # matches ranks candidates as (score, candidate_string) tuples and its
    # internal nlargest selection compares those tuples directly, so a tie on
    # score is ALREADY broken deterministically by the candidate string itself
    # -- independent of the iteration order we hand it (verified empirically
    # across repeated frozenset instances with varied insertion order; see
    # test_query_normalize.py's determinism test for the proof case).
    out = []
    for w in words:
        lw = w.lower()
        if lw in vocab_set or lw in COMMON_SHORT_WORDS:
            out.append(w)
            continue
        match = difflib.get_close_matches(lw, vocab_set, n=1, cutoff=cutoff)
        out.append(match[0] if match else w)
    return " ".join(out)
