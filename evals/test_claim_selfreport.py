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
        self.assertTrue(claim["rests_on_unlanded"])
        self.assertIn("pr:17122", [a["ref"] for a in r.rejected_attempts])

    def test_claim_citing_a_merged_pr_is_not_marked(self):
        r = self._run('[{"text":"Relative paths stay relative.",'
                      '"citations":["pr:18176"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    def test_one_live_source_is_enough_to_not_mark(self):
        """Marked only when EVERY citation is refused: a sentence that also
        rests on shipped evidence is not a restatement of a refusal."""
        r = self._run('[{"text":"Paths are preserved.",'
                      '"citations":["pr:17122","pr:18176"]}]')
        self.assertEqual(r.claims[0]["label"], CLAIM_COMPOSED)
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    # --- the two REAL cases from Experiment C2, which decide this rule -------
    # (docs/experiments/2026-08-11-agent-mode-exp-c2-results.md)

    C2_CHUNKS = [
        Chunk(ref="pr:1549", source="pr",
              text="PR #1549: Fix fragment filter SQL broken by SQLite 3.51.0\n"
                   "[CLOSED by ikatyal2110]\nSQLite 3.51.0 broke correlated EXISTS."),
        Chunk(ref="issue:1511", source="issue",
              text="ISSUE #1511: llm logs -f fragment filter returns no results\n"
                   "[CLOSED by Cyrus580529]\nThe fragment filter builds SQL like this."),
        Chunk(ref="pr:1588", source="pr",
              text="PR #1588: Fix llm openai endpoint ignoring --schema\n"
                   "[MERGED by simonw]\nMatches the pattern used everywhere else."),
        Chunk(ref="pr:1584", source="pr",
              text="PR #1584: Fix template schema_object overriding --schema\n"
                   "[CLOSED by simonw]\nDuplicate."),
    ]

    def _c2(self, claims_json):
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"x.","citations":["pr:1549"],'
                 '"claims":' + claims_json + '}')
        refs = [c.ref for c in self.C2_CHUNKS]
        p = GatedPipeline(LexicalRetriever(self.C2_CHUNKS), self.C2_CHUNKS,
                          StaticProvider([reply]))
        return p._answer_from("q?", self.C2_CHUNKS, refs, per_claim=True)

    def test_refused_pr_plus_issue_is_marked(self):
        """C2 task 2's real false negative: Icarus called a REFUSED pull
        request's approach "the accepted fix", citing that PR plus the issue
        that reported the bug. Nothing cited shows the change ever landed --
        an issue reports a problem, it does not record an adoption -- so this
        must be marked. The original every-citation rule stayed silent here.
        """
        r = self._c2('[{"text":"The accepted fix is to replace the UNION.",'
                     '"citations":["pr:1549","issue:1511"]}]')
        self.assertTrue(r.claims[0].get("rests_on_unlanded"))

    def test_refused_pr_plus_merged_pr_is_not_marked(self):
        """C2 task 3, the case that must STAY silent: the claim cites a closed
        PR alongside a MERGED one. The merged PR is proof the approach landed,
        so the sentence is standing on solid ground and flagging it would be
        noise -- this is the case a naive any-citation rule would get wrong.
        """
        r = self._c2('[{"text":"The command-line schema should win.",'
                     '"citations":["pr:1584","pr:1588"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    def test_unsupported_claim_is_not_marked(self):
        """No citations means nothing to be resting ON -- vacuous all() must
        not mark it."""
        r = self._run('[{"text":"Paths are preserved.","citations":["pr:999"]}]')
        self.assertEqual(r.claims[0]["label"], CLAIM_UNSUPPORTED)
        self.assertNotIn("rests_on_unlanded", r.claims[0])


class AnIssueIsNotEvidenceOfWorkTests(unittest.TestCase):
    """An issue records a REQUEST or a REPORT. It never records that anything
    was built, attempted, or decided.

    Two measured cases, both on `meilisearch-swift`:

    - docs/experiments/2026-08-14-dogfood-meilisearch-swift-two-issues.md:
      "adding new fields like indexSize/usedIndexSize has been attempted
      before", citing `issue:531` -- the issue REQUESTING those fields. The
      issue restating its own existence was read as evidence of a prior
      attempt.
    - Reproduced live while fixing that, unprompted: asked whether index size
      reporting had been added, Icarus answered "Yes, issue #531 tracks the
      addition of ...", citing `issue:531` alone and labelled `quoted`.

    The pipeline already stated this principle -- "an issue reports a problem;
    it never records an adoption, so it cannot rescue the claim" -- but only
    applied it when a pull request was cited alongside. A claim resting on
    issues ALONE was the one arrangement where nothing checked.
    """

    CHUNKS = [
        Chunk(ref="issue:531", source="issue",
              text="ISSUE #531: Add indexSize and usedIndexSize to stats\n\n"
                   "[OPEN by curquiza]\n\nThe engine now returns these fields."),
        Chunk(ref="code:Sources/MeiliSearch/Stats.swift", source="code",
              text="public struct Stat {\n  public let numberOfDocuments: Int\n}"),
        Chunk(ref="pr:400", source="pr",
              text="PR #400: stats work\n\n[MERGED by curquiza]\n\nShipped."),
    ]

    def _run(self, claims_json):
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"a.","citations":["issue:531"],'
                 '"claims":' + claims_json + '}')
        refs = [c.ref for c in self.CHUNKS]
        p = GatedPipeline(LexicalRetriever(self.CHUNKS), self.CHUNKS,
                          StaticProvider([reply]))
        return p._answer_from("has this been added?", self.CHUNKS, refs,
                              per_claim=True)

    def test_a_claim_resting_only_on_an_issue_is_marked(self):
        r = self._run('[{"text":"Yes, issue #531 tracks the addition of these '
                      'fields.","citations":["issue:531"]}]')
        claim = r.claims[0]
        # `quoted` again -- it faithfully restates one chunk. The chunk simply
        # is not evidence of the thing the sentence implies.
        self.assertEqual(claim["label"], CLAIM_QUOTED)
        self.assertTrue(claim["rests_on_unlanded"])

    def test_two_issues_are_not_corroboration_of_a_landing(self):
        chunks = self.CHUNKS + [
            Chunk(ref="issue:99", source="issue",
                  text="ISSUE #99: same request\n\n[OPEN by someone]\n\nPlease add.")]
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"a.","citations":["issue:531"],'
                 '"claims":[{"text":"This has been attempted before.",'
                 '"citations":["issue:531","issue:99"]}]}')
        p = GatedPipeline(LexicalRetriever(chunks), chunks, StaticProvider([reply]))
        r = p._answer_from("q?", chunks, [c.ref for c in chunks], per_claim=True)
        self.assertEqual(r.claims[0]["label"], CLAIM_COMPOSED)
        self.assertTrue(r.claims[0]["rests_on_unlanded"])

    def test_the_code_itself_is_still_solid_ground(self):
        """The guard against turning this into noise: an issue cited ALONGSIDE
        the shipped file is a sentence standing on something real."""
        r = self._run('[{"text":"Stat holds document counts.",'
                      '"citations":["issue:531",'
                      '"code:Sources/MeiliSearch/Stats.swift"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    def test_a_merged_pr_is_still_solid_ground(self):
        r = self._run('[{"text":"Stats shipped earlier.",'
                      '"citations":["issue:531","pr:400"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    def test_a_claim_with_no_citations_is_still_not_marked(self):
        """Unchanged: nothing to be resting ON. Dropping the pull-request
        anchor must not make the all() vacuously true."""
        r = self._run('[{"text":"Something.","citations":["issue:999"]}]')
        self.assertEqual(r.claims[0]["label"], CLAIM_UNSUPPORTED)
        self.assertNotIn("rests_on_unlanded", r.claims[0])


class OpenPullRequestIsNotCurrentStateTests(unittest.TestCase):
    """An OPEN pull request describes PROPOSED code, not the file today.

    The measured case (docs/experiments/2026-08-14-dogfood-meilisearch-swift-
    two-issues.md): asked to re-check a finished diff, Icarus stated "the
    existing `Stat` model ... already uses this `SizeValue` type" -- false. It
    had read `pr:522`, an OPEN and approved but unmerged pull request, as a
    description of `main`. Every citation resolved, so the honesty gate passed
    it; groundedness proves a citation is real, never that it describes the
    present.

    `rests_on_unlanded` could not fire: #522 is not closed, so it was not in
    `rejected_attempts` at all. The predicate the code always wanted --
    "nothing cited shows this LANDED" -- was written narrower than its own
    comment, covering closed-unmerged only. An open PR fails that test exactly
    as a closed one does.
    """

    CHUNKS = [
        # Open, approved, unmerged: the real #522 shape.
        Chunk(ref="pr:522", source="pr",
              text="PR #522: Add SizeValue and sizeFormat to stats\n\n"
                   "[OPEN by mvanhorn]\n\nReview: approved\n\n"
                   "Introduces a SizeValue type used by Stat."),
        # Shipped: the file as it actually is.
        Chunk(ref="code:Sources/MeiliSearch/Stats.swift", source="code",
              text="public struct Stat {\n  public let numberOfDocuments: Int\n}"),
        Chunk(ref="pr:400", source="pr",
              text="PR #400: earlier stats work\n\n[MERGED by curquiza]\n\nShipped."),
    ]

    def _run(self, claims_json, cite="pr:522"):
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"Stat uses SizeValue.",'
                 '"citations":["' + cite + '"],"claims":' + claims_json + '}')
        refs = [c.ref for c in self.CHUNKS]
        p = GatedPipeline(LexicalRetriever(self.CHUNKS), self.CHUNKS,
                          StaticProvider([reply]))
        return p._answer_from("does Stat use SizeValue?", self.CHUNKS, refs,
                              per_claim=True)

    def test_a_claim_resting_only_on_an_open_pr_is_marked(self):
        r = self._run('[{"text":"Stat already uses this SizeValue type.",'
                      '"citations":["pr:522"]}]')
        claim = r.claims[0]
        # Still `quoted` -- it does restate one chunk faithfully. That is the
        # whole danger: the trusted label with a proposal underneath it.
        self.assertEqual(claim["label"], CLAIM_QUOTED)
        self.assertTrue(claim["rests_on_unlanded"])

    def test_an_open_pr_is_never_a_rejected_attempt(self):
        """Nobody refused #522 -- it is open and approved. The `risks` list
        must not gain it just because the claim flag now covers it; these are
        two different questions about the same pull request."""
        r = self._run('[{"text":"Stat already uses this SizeValue type.",'
                      '"citations":["pr:522"]}]')
        self.assertNotIn("pr:522", [a["ref"] for a in r.rejected_attempts])

    def test_a_current_state_citation_alongside_it_silences_the_flag(self):
        """The suppression rule, stated as what it actually is.

        A citation to current code means the sentence does not rest SOLELY on
        proposals. It does not mean the code supports the sentence -- this is a
        source-SHAPE heuristic, and the flag has no way to check entailment
        without becoming a model, which AGENTS.md rules out.
        """
        r = self._run(
            '[{"text":"Stat is a struct of stat fields.",'
            '"citations":["pr:522","code:Sources/MeiliSearch/Stats.swift"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    def test_KNOWN_LIMITATION_a_contradicting_code_citation_also_silences_it(self):
        """Raised in review, and recorded rather than papered over.

        This is the ORIGINAL false sentence -- "Stat already uses SizeValue" --
        citing the open proposal AND the current `Stats.swift`, which actually
        DISPROVES it. The flag stays silent, because the rule reads source
        shape and `Stats.swift` is current-state evidence.

        So the flag catches this defect only in the arrangement it was measured
        in (the proposal cited ALONE). Detecting the contradiction needs
        semantic entailment between a sentence and a chunk, which is exactly
        what `evals/gate.py` refuses to attempt and what the per-claim
        `composed`/`quoted` labels exist to hand to the reader instead.

        Asserted, not just commented, so the limitation cannot quietly change
        without someone deciding to change it.
        """
        r = self._run(
            '[{"text":"Stat already uses this SizeValue type.",'
            '"citations":["pr:522","code:Sources/MeiliSearch/Stats.swift"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])
        # What the reader DOES still get: the sentence rests on two chunks
        # taken together, which is the label they are told to verify.
        self.assertEqual(r.claims[0]["label"], CLAIM_COMPOSED)

    def test_a_merged_pr_alongside_it_is_solid_ground(self):
        r = self._run('[{"text":"Stats have shipped before.",'
                      '"citations":["pr:522","pr:400"]}]')
        self.assertNotIn("rests_on_unlanded", r.claims[0])

    def test_an_unmerged_prs_diff_is_marked_too(self):
        """The same session's other instance: a `diff:` ref is the PROPOSED
        hunks. It carries no state of its own, so it is judged by the pull
        request it belongs to -- unlanded here."""
        chunks = self.CHUNKS + [
            Chunk(ref="diff:522", source="diff",
                  text="+++ Stats.swift\n+  public let indexSize: SizeValue")]
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"x.","citations":["diff:522"],'
                 '"claims":[{"text":"Stat has an indexSize field.",'
                 '"citations":["diff:522"]}]}')
        p = GatedPipeline(LexicalRetriever(chunks), chunks,
                          StaticProvider([reply]))
        r = p._answer_from("q?", chunks, [c.ref for c in chunks], per_claim=True)
        self.assertTrue(r.claims[0]["rests_on_unlanded"])

    def test_a_diff_whose_pull_request_merged_is_not_marked(self):
        """And the mapping has to work the other way, or every diff would be
        flagged regardless of what happened to it."""
        chunks = self.CHUNKS + [
            Chunk(ref="diff:400", source="diff", text="+++ x\n+ shipped")]
        from evals.retriever import LexicalRetriever
        reply = ('{"verdict":"answer","answer":"x.","citations":["diff:400"],'
                 '"claims":[{"text":"That change shipped.",'
                 '"citations":["diff:400"]}]}')
        p = GatedPipeline(LexicalRetriever(chunks), chunks,
                          StaticProvider([reply]))
        r = p._answer_from("q?", chunks, [c.ref for c in chunks], per_claim=True)
        self.assertNotIn("rests_on_unlanded", r.claims[0])


if __name__ == "__main__":
    unittest.main()
