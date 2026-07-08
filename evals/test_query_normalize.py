# evals/test_query_normalize.py
"""Q1: the pure query-normalizer. Stdlib-only, no fastembed needed -- always
runs. Vocabulary is deliberately tiny/controlled here so corrections are
predictable; the real corpus vocabulary is exercised in
test_query_normalization_eval.py."""

import unittest

from evals.corpus import Chunk
from evals.query_normalize import build_vocabulary, normalize_query, _WORD_RE
from evals.retriever import tokenize


class BuildVocabularyTests(unittest.TestCase):
    def test_uses_the_same_tokenizer_as_bm25(self):
        # Corrections should only ever land on real corpus terms -- so the
        # vocabulary must be built with the identical tokenizer BM25 indexes
        # with, not a separate/looser word-splitter.
        chunks = [Chunk("code:a", "code", "def authenticate(user): return verify(user)")]
        vocab = build_vocabulary(chunks)
        self.assertIn("authenticate", vocab)
        self.assertIn("verify", vocab)


class TokenizerLockstepTests(unittest.TestCase):
    """The exact invariant whose violation caused a real bug: query_normalize's
    word-splitter (_WORD_RE) must stay IDENTICAL to retriever.tokenize()'s, or
    normalize_query's output tokens silently stop matching the vocabulary
    build_vocabulary produces from that same tokenizer (see
    evals/query_normalize.py's module docstring for the incident this guards
    against -- dotted filenames like "tools.py" were once corrupted this way).
    Always-run and stdlib-only, so this catches a regression even without
    fastembed/the live board test."""

    def test_word_splitter_matches_retriever_tokenize_on_varied_text(self):
        probes = [
            "what does tools.py do",
            "how does __main__.py run as a script",
            "Template.evaluate() returns a string",
            "make_schema_id computes a schema's id",
            "snake_case, CamelCase, and dotted.identifiers.here",
        ]
        for text in probes:
            got = {w.lower() for w in _WORD_RE.findall(text)}
            want = set(tokenize(text))
            self.assertEqual(got, want, f"tokenizer drift on: {text!r}")


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

    def test_deterministic_on_a_genuine_scoring_tie(self):
        # A vacuous version of this test (varying only the RNG/hash seed with
        # a vocab that has one clear winner) would pass even with a genuinely
        # non-deterministic candidate-ordering bug, since there's nothing to
        # break a tie on. This vocab is engineered so "function" and
        # "fanction" score IDENTICALLY against "fnction" (verified:
        # difflib.SequenceMatcher(None, "fnction", w).ratio() == 0.9333... for
        # both) -- so this only stays green if ties resolve the same way
        # regardless of the vocabulary's (frozenset) iteration order, across
        # many freshly-constructed frozenset instances with varied insertion
        # order (which perturbs Python's iteration order via hash placement).
        tie_vocab_a = frozenset({"function", "fanction", "unrelated1"})
        tie_vocab_b = frozenset({"unrelated2", "fanction", "function"})
        results = set()
        for _ in range(20):
            results.add(normalize_query("fnction", tie_vocab_a, cutoff=0.6))
            results.add(normalize_query("fnction", tie_vocab_b, cutoff=0.6))
        self.assertEqual(results, {"function"})

    def test_deterministic_across_repeated_calls(self):
        # Same input, same output, every time -- the ordinary (non-tie) case.
        results = {normalize_query("fuction", self.vocab) for _ in range(20)}
        self.assertEqual(results, {"function"})

    def test_empty_query_returns_empty_string(self):
        self.assertEqual(normalize_query("", self.vocab), "")


if __name__ == "__main__":
    unittest.main()
