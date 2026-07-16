# evals/test_exact_ref_lookup.py
"""RED failing eval for a live-found bug (benawad/vsinder): asking about a
real, in-corpus GitHub issue/PR by its exact number can retrieve NOTHING for
it at all -- not a false abstention with evidence in hand, a genuine zero-
score retrieval miss. An issue/PR's number lives only in its `ref`
("issue:260"), never automatically in its searchable text, and BM25/semantic
search has no special-casing for "look up ref N by its exact number" -- a
query sharing zero other keywords with that chunk's own text scores it
exactly 0 and it is dropped before the writer or gate ever run.

GatedPipeline.explain() already proves out a working "resolve by exact ref,
not .search()" pattern (self._by_ref, anchor-then-neighbors). This file
proves .answer() needs the same anchor path for a question that names an
issue/PR by number, and that adding it doesn't open any new honesty hole
(citations still only ground through the existing gate() path -- no new
logic there at all)."""

import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline


def _corpus_with_unreachable_issue():
    # Fillers share query vocabulary and would ordinarily fill up `retrieved`;
    # gold shares NONE of it -- empirically verified to score exactly 0 under
    # plain BM25 and be dropped from results entirely, regardless of k.
    fillers = [
        Chunk(f"issue:{i}", "issue", "how the retry queue works and does its job")
        for i in range(1, 6)
    ]
    gold = Chunk("issue:260", "issue", "cannot authenticate; login attempts fail intermittently for some accounts")
    chunks = fillers + [gold]
    return chunks, gold


def _pipe(chunks, provider):
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


class ExactRefNeverRetrievedTests(unittest.TestCase):
    """Documents today's bug as a baseline: plain search-based retrieval finds
    nothing at all for the gold ref, on the exact live-reproduced phrasing."""

    def test_plain_search_scores_the_gold_issue_at_zero(self):
        chunks, gold = _corpus_with_unreachable_issue()
        r = LexicalRetriever(chunks).search("how does issue #260 work", k=20)
        self.assertNotIn(gold.ref, r)


class ExactRefAnchorLookupTests(unittest.TestCase):
    """The fix: GatedPipeline.answer() must resolve an explicit "issue/PR #N"
    mention via self._by_ref directly, guaranteeing it reaches `retrieved`
    (and the writer) whenever that exact ref exists in the corpus -- the
    same guarantee .explain() already gives a line-selected anchor."""

    def test_hash_prefixed_number_is_recognized_as_an_anchor(self):
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "Login sometimes fails intermittently.", "citations": [gold.ref]})
        r = _pipe(chunks, StaticProvider(raw)).answer("how does issue #260 work")
        self.assertIn(gold.ref, r.retrieved)
        self.assertEqual(r.verdict, "answer")
        self.assertIn(gold.ref, r.citations)

    def test_bare_number_without_hash_is_also_recognized(self):
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "Login sometimes fails intermittently.", "citations": [gold.ref]})
        r = _pipe(chunks, StaticProvider(raw)).answer("what is issue 260 about")
        self.assertIn(gold.ref, r.retrieved)
        self.assertEqual(r.verdict, "answer")

    def test_pr_number_resolves_to_a_pr_ref_not_an_issue_ref(self):
        chunks = [Chunk("pr:42", "pr", "a fix with no shared vocabulary at all here")]
        r = _pipe(chunks, StaticProvider(json.dumps({
            "verdict": "answer", "answer": "It's PR 42.", "citations": ["pr:42"],
        }))).answer("what does pr #42 do")
        self.assertIn("pr:42", r.retrieved)
        self.assertEqual(r.verdict, "answer")

    def test_no_new_bluff_path_a_fabricated_anchor_citation_still_forced_unknown(self):
        # The anchor path only ever ADDS a genuinely-existing ref to
        # `retrieved` -- it must not let a citation to a ref that doesn't
        # exist in the corpus at all slip through.
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["issue:99999"]})
        r = _pipe(chunks, StaticProvider(raw)).answer("how does issue #260 work")
        self.assertEqual(r.verdict, "unknown")

    def test_mentioning_a_number_with_no_matching_ref_is_a_harmless_no_op(self):
        # A number that doesn't correspond to any real ref in this corpus
        # (e.g. "#9999") must not error or inject a phantom anchor -- the
        # question just falls through to ordinary search, same as today.
        chunks, gold = _corpus_with_unreachable_issue()
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "how does issue #9999 work"
        )
        self.assertNotIn("issue:9999", r.retrieved)

    def test_known_accepted_edge_case_a_coincidental_number_can_still_anchor(self):
        # Documented, accepted low-probability edge case (not a silent gap):
        # a colloquial numeric mention ("the #1 rule") will anchor-inject a
        # real issue:1 if one happens to exist in this corpus, even though
        # the question isn't really about that issue. Harmless (it can only
        # ever ADD a genuinely-existing, genuinely-grounded citation
        # candidate -- never fabricate one), but worth having on record.
        chunks, gold = _corpus_with_unreachable_issue()  # includes a real issue:1
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "the #1 rule here is to always retry"
        )
        self.assertIn("issue:1", r.retrieved)


if __name__ == "__main__":
    unittest.main()
