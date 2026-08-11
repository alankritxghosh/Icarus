"""The writer's per-sentence self-report, and the deterministic check on it.

Weighted toward what must NOT happen: the prompt must be byte-identical when the
feature is off (every number on the eval board was measured on the unmodified
prompt), and the self-report must never be able to move a verdict.

Stdlib only, no model, always runs.
"""
import unittest

from evals.corpus import Chunk
from evals.gate import (attribute_claims, gate, extract_json,
                        CLAIM_QUOTED, CLAIM_COMPOSED, CLAIM_UNSUPPORTED)
from evals.pipeline import GatedPipeline
from evals.provider import StaticProvider
from evals.synth import build_prompt

CHUNKS = [
    Chunk(ref="pr:100", source="pr", text="PR #100: we made paths absolute because "
          "the cache moved between machines."),
    Chunk(ref="issue:200", source="issue", text="ISSUE #200: relative paths break "
          "when the project is checked out at a different depth."),
    Chunk(ref="code:a.py#L1-L50", source="code", text="def f():\n    return 1\n"),
]
RETRIEVED = [c.ref for c in CHUNKS]


class PromptUnchangedWhenOffTests(unittest.TestCase):
    """The guarantee that lets this ship without re-baselining the board."""

    def test_default_prompt_is_byte_identical(self):
        before = build_prompt("why?", CHUNKS)
        after = build_prompt("why?", CHUNKS, per_claim=False)
        self.assertEqual(before, after)
        self.assertNotIn("claims", before)

    def test_per_claim_adds_the_rule_and_keeps_json_tail_last(self):
        on = build_prompt("why?", CHUNKS, per_claim=True)
        self.assertIn('"claims"', on)
        self.assertIn("one entry per sentence", on)
        # The closing instruction must remain the final line of the instruction
        # block, or the writer is told to reply with JSON and then given more rules.
        head = on.split("\n\nQUESTION:")[0]
        self.assertTrue(head.rstrip().endswith("Reply with JSON and nothing else."))

    def test_per_claim_only_adds(self):
        off = build_prompt("why?", CHUNKS)
        on = build_prompt("why?", CHUNKS, per_claim=True)
        self.assertGreater(len(on), len(off))
        # Everything after the instruction block (question + evidence) is untouched.
        self.assertEqual(off.split("\n\nQUESTION:")[1], on.split("\n\nQUESTION:")[1])


class AttributeClaimsTests(unittest.TestCase):

    def test_one_resolving_ref_is_quoted(self):
        parsed = {"claims": [{"text": "Paths were made absolute.",
                              "citations": ["pr:100"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual([c["label"] for c in out], [CLAIM_QUOTED])
        self.assertEqual(out[0]["citations"], ["pr:100"])

    def test_two_resolving_refs_is_composed(self):
        parsed = {"claims": [{"text": "Absolute paths were chosen because relative "
                                      "ones break across depths.",
                              "citations": ["pr:100", "issue:200"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_COMPOSED)
        self.assertEqual(out[0]["citations"], ["pr:100", "issue:200"])

    def test_unretrieved_ref_is_dropped_not_trusted(self):
        """The whole point: a self-report is evidence, not proof. A ref nobody
        retrieved may only ever move a claim TOWARD unsupported."""
        parsed = {"claims": [{"text": "A rule nobody wrote.",
                              "citations": ["pr:999"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_UNSUPPORTED)
        self.assertEqual(out[0]["citations"], [])

    def test_partial_drop_downgrades_composed_to_quoted(self):
        parsed = {"claims": [{"text": "x", "citations": ["pr:100", "pr:999"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_QUOTED)

    def test_duplicate_refs_are_not_corroboration(self):
        """One source cited twice is one source -- the same rule
        investigation.classify_support applies."""
        parsed = {"claims": [{"text": "x", "citations": ["pr:100", "pr:100"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_QUOTED)

    def test_reformatted_citation_resolves_like_any_other(self):
        """Claim citations go through the gate's own _resolve, so the same
        tolerated reformatting applies -- and no more."""
        parsed = {"claims": [{"text": "x", "citations": ["[a.py#L20]"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_QUOTED)
        self.assertEqual(out[0]["citations"], ["code:a.py#L1-L50"])

    def test_out_of_window_citation_does_not_resolve(self):
        parsed = {"claims": [{"text": "x", "citations": ["a.py#L900"]}]}
        out = attribute_claims(parsed, RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_UNSUPPORTED)

    def test_missing_or_malformed_input_never_raises(self):
        for parsed in ({}, {"claims": "nope"}, {"claims": [None, 3, "x"]},
                       {"claims": [{"citations": ["pr:100"]}]},   # no text
                       {"claims": [{"text": "   ", "citations": []}]},  # blank text
                       None, "not a dict", []):
            self.assertEqual(attribute_claims(parsed, RETRIEVED), [])

    def test_non_list_citations_are_tolerated(self):
        out = attribute_claims({"claims": [{"text": "x", "citations": "pr:100"}]},
                               RETRIEVED)
        self.assertEqual(out[0]["label"], CLAIM_UNSUPPORTED)

    def test_absent_claims_key_is_inert(self):
        """Every caller that never asked for a self-report gets nothing, so this
        cannot affect an existing path."""
        raw = '{"verdict": "answer", "answer": "a", "citations": ["pr:100"]}'
        self.assertEqual(attribute_claims(extract_json(raw), RETRIEVED), [])


class NeverTouchesTheVerdictTests(unittest.TestCase):

    def _reply(self, claims):
        import json
        return json.dumps({"verdict": "answer", "answer": "Paths were made absolute.",
                           "citations": ["pr:100"], "claims": claims})

    def test_verdict_identical_with_hostile_claims(self):
        """A writer reporting garbage claims alongside a properly grounded answer
        must still get its answer through: the gate decides, this only describes."""
        good = gate('{"verdict":"answer","answer":"Paths were made absolute.",'
                    '"citations":["pr:100"]}', RETRIEVED)
        with_claims = gate(self._reply([{"text": "junk", "citations": ["pr:999"]}]),
                           RETRIEVED)
        self.assertEqual(with_claims.verdict, good.verdict)
        self.assertEqual(with_claims.citations, good.citations)

    def test_ungrounded_answer_still_abstains_however_good_the_claims_look(self):
        raw = ('{"verdict":"answer","answer":"x","citations":["pr:999"],'
               '"claims":[{"text":"x","citations":["pr:100"]}]}')
        self.assertEqual(gate(raw, RETRIEVED).verdict, "unknown")


class PipelineWiringTests(unittest.TestCase):

    def _pipeline(self, reply):
        from evals.retriever import LexicalRetriever
        return GatedPipeline(LexicalRetriever(CHUNKS), CHUNKS, StaticProvider([reply]))

    REPLY = ('{"verdict":"answer","answer":"Paths were made absolute.",'
             '"citations":["pr:100"],'
             '"claims":[{"text":"Paths were made absolute.","citations":["pr:100"]},'
             '{"text":"Relative paths break across depths.",'
             '"citations":["pr:100","issue:200"]}]}')

    def test_claims_empty_by_default(self):
        r = self._pipeline(self.REPLY).answer("why are paths absolute?")
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.claims, [])

    def test_claims_populated_when_requested(self):
        p = self._pipeline(self.REPLY)
        r = p._answer_from("why are paths absolute?", CHUNKS, RETRIEVED, per_claim=True)
        self.assertEqual([c["label"] for c in r.claims],
                         [CLAIM_QUOTED, CLAIM_COMPOSED])

    def test_verdict_unchanged_by_the_flag(self):
        off = self._pipeline(self.REPLY)._answer_from(
            "why?", CHUNKS, RETRIEVED, per_claim=False)
        on = self._pipeline(self.REPLY)._answer_from(
            "why?", CHUNKS, RETRIEVED, per_claim=True)
        self.assertEqual((off.verdict, off.citations, off.answer),
                         (on.verdict, on.citations, on.answer))


class RestsOnRejectedTests(unittest.TestCase):
    """A sentence resting only on REFUSED pull requests is marked as such.

    Reproduces the real shape found 2026-08-11 (docs/experiments/
    2026-08-11-fabrication-recheck-per-claim.md): the fabricated sentence cited
    ONE closed-unmerged PR, so `label` was `quoted` -- the label an agent is
    told to trust -- while that same PR sat in `rejected_attempts`.
    """

    CHUNKS = [
        # Closed WITHOUT merging -- a proposal, not shipped behaviour.
        Chunk(ref="pr:17122", source="pr",
              text="PR #17122: preserve absolute paths when find-links is absolute\n"
                   "[CLOSED by someone]\nAbsolute paths should survive locking."),
        # Merged -- shipped behaviour, must never be marked.
        Chunk(ref="pr:18176", source="pr",
              text="PR #18176: preserve absolute/relative paths in lockfiles\n"
                   "[MERGED by someone]\nRelative stays relative."),
    ]
    RETRIEVED = [c.ref for c in CHUNKS]

    def _run(self, claims_json):
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"Paths are preserved.",'
                 '"citations":["pr:17122"],"claims":' + claims_json + '}')
        p = GatedPipeline(LexicalRetriever(self.CHUNKS), self.CHUNKS,
                          StaticProvider([reply]))
        return p._answer_from("what is preserved?", self.CHUNKS, self.RETRIEVED,
                              per_claim=True)

    def test_claim_citing_only_a_refused_pr_is_marked(self):
        r = self._run('[{"text":"Absolute paths are preserved.",'
                      '"citations":["pr:17122"]}]')
        claim = r.claims[0]
        # The label is unchanged -- this is a second axis, not a fourth label.
        self.assertEqual(claim["label"], CLAIM_QUOTED)
        self.assertTrue(claim["rests_on_rejected"])
        self.assertIn("pr:17122", [a["ref"] for a in r.rejected_attempts])

    def test_claim_citing_a_merged_pr_is_not_marked(self):
        r = self._run('[{"text":"Relative paths stay relative.",'
                      '"citations":["pr:18176"]}]')
        self.assertNotIn("rests_on_rejected", r.claims[0])

    def test_one_live_source_is_enough_to_not_mark(self):
        """Marked only when EVERY citation is refused: a sentence that also
        rests on shipped evidence is not a restatement of a refusal."""
        r = self._run('[{"text":"Paths are preserved.",'
                      '"citations":["pr:17122","pr:18176"]}]')
        self.assertEqual(r.claims[0]["label"], CLAIM_COMPOSED)
        self.assertNotIn("rests_on_rejected", r.claims[0])

    def test_unsupported_claim_is_not_marked(self):
        """No citations means nothing to be resting ON -- vacuous all() must
        not mark it."""
        r = self._run('[{"text":"Paths are preserved.","citations":["pr:999"]}]')
        self.assertEqual(r.claims[0]["label"], CLAIM_UNSUPPORTED)
        self.assertNotIn("rests_on_rejected", r.claims[0])


if __name__ == "__main__":
    unittest.main()
