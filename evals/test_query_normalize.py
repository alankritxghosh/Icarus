# evals/test_query_normalize.py
"""Q1: the pure query-normalizer. Stdlib-only, no fastembed needed -- always
runs. Vocabulary is deliberately tiny/controlled here so corrections are
predictable; the real corpus vocabulary is exercised in
test_query_normalization_eval.py."""

import unittest

from evals.corpus import Chunk
from evals.query_normalize import build_vocabulary, normalize_query


class BuildVocabularyTests(unittest.TestCase):
    def test_uses_the_same_tokenizer_as_bm25(self):
        # Corrections should only ever land on real corpus terms -- so the
        # vocabulary must be built with the identical tokenizer BM25 indexes
        # with, not a separate/looser word-splitter.
        chunks = [Chunk("code:a", "code", "def authenticate(user): return verify(user)")]
        vocab = build_vocabulary(chunks)
        self.assertIn("authenticate", vocab)
        self.assertIn("verify", vocab)


class NormalizeQueryTests(unittest.TestCase):
    def setUp(self):
        self.vocab = frozenset({
            "function", "authenticate", "schema", "return", "compute",
            "tools.py", "__main__.py",
        })

    def test_corrects_a_known_typo(self):
        self.assertEqual(normalize_query("fuction", self.vocab), "function")

    def test_leaves_correct_words_alone(self):
        self.assertEqual(
            normalize_query("function authenticate", self.vocab),
            "function authenticate",
        )

    def test_splits_dotted_filenames_matching_bm25s_own_tokenization(self):
        # MUST match retriever.tokenize()'s splitting exactly: BM25 also splits
        # "tools.py" into "tools" + "py" (its tokenizer has no dot handling).
        # An earlier version kept dotted filenames as one compound token, which
        # backfired -- that compound never exists in a vocabulary built from
        # tokenize(), so it always missed and got spuriously "corrected"
        # against unrelated single words (see evals/query_normalize.py's
        # docstring). Splitting identically means "tools"/"py" -- both real
        # vocabulary words here -- pass through untouched, uncorrupted.
        vocab = frozenset({"tools", "py"})
        got = normalize_query("what does tools.py do", vocab)
        self.assertEqual(got.split()[-3:], ["tools", "py", "do"])

    def test_leaves_unmatched_word_unchanged_when_no_close_match(self):
        # No close match in this vocab -- must NOT force a wrong "correction";
        # a low-confidence guess is worse than leaving the original word.
        self.assertIn("banana", normalize_query("banana", self.vocab).split())

    def test_skips_correction_for_common_short_words(self):
        # Short common English words must never get fuzzy-matched into an
        # unrelated vocabulary word.
        self.assertEqual(normalize_query("is a function", self.vocab), "is a function")

    def test_multiple_typos_in_one_query_all_corrected(self):
        got = normalize_query("fuction to compue a schemas", self.vocab, cutoff=0.7)
        words = got.split()
        self.assertIn("function", words)
        self.assertIn("compute", words)

    def test_cutoff_controls_correction_strictness(self):
        # A near-miss typo corrects at a moderate cutoff...
        self.assertEqual(normalize_query("fnction", self.vocab, cutoff=0.6), "function")
        # ...but at a very strict cutoff the same typo is too far and is left
        # alone rather than guessed.
        self.assertEqual(normalize_query("fnction", self.vocab, cutoff=0.99), "fnction")

    def test_deterministic_across_repeated_calls(self):
        # Guards against a set/frozenset-iteration-order flake: same input must
        # give the same output every time.
        results = {normalize_query("fuction", self.vocab) for _ in range(20)}
        self.assertEqual(results, {"function"})

    def test_empty_query_returns_empty_string(self):
        self.assertEqual(normalize_query("", self.vocab), "")


if __name__ == "__main__":
    unittest.main()
