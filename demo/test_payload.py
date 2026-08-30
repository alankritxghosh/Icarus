# demo/test_payload.py
import unittest

from evals.pipeline import Result
from . import payload
from .payload import build_payload

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"


class BuildPayloadTests(unittest.TestCase):
    def test_answer_carries_prose_and_citation_urls(self):
        r = Result(verdict="answer", answer="Because Y.",
                   citations=["pr:1435"], retrieved=["pr:1435", "code:llm/x.py"])
        p = build_payload(r, REPO, COMMIT)
        self.assertEqual(p["verdict"], "answer")
        self.assertEqual(p["answer"], "Because Y.")
        self.assertEqual(p["citations"], [{"ref": "pr:1435", "url": "https://github.com/simonw/llm/pull/1435", "excerpt": ""}])
        self.assertEqual(p["searched"], ["pr:1435", "code:llm/x.py"])

    def test_unknown_is_empty_answer_no_citations_but_shows_searched(self):
        r = Result(verdict="unknown", retrieved=["code:llm/x.py", "code:llm/y.py"])
        p = build_payload(r, REPO, COMMIT)
        self.assertEqual(p["verdict"], "unknown")
        self.assertEqual(p["answer"], "")
        self.assertEqual(p["citations"], [])
        self.assertEqual(p["searched"], ["code:llm/x.py", "code:llm/y.py"])

    def test_citations_preserve_order(self):
        r = Result(verdict="answer", answer="a", citations=["pr:2", "pr:1"],
                   retrieved=["pr:2", "pr:1"])
        self.assertEqual([c["ref"] for c in build_payload(r, REPO, COMMIT)["citations"]], ["pr:2", "pr:1"])

    def test_citation_without_url_still_appears(self):
        r = Result(verdict="answer", answer="a", citations=["slack:9"], retrieved=["slack:9"])
        self.assertEqual(build_payload(r, REPO, COMMIT)["citations"], [{"ref": "slack:9", "url": None, "excerpt": ""}])


class AnchoredTests(unittest.TestCase):
    """The named ref has to survive to the renderer. Without it a refusal that
    looked up exactly what was asked is indistinguishable from one that ignored
    the question -- the live complaint this field exists to fix (2026-07-28)."""

    def test_unknown_still_reports_what_the_question_named(self):
        r = Result(verdict="unknown", retrieved=["issue:6952", "code:a.py", "code:b.py"],
                   anchored=["issue:6952"])
        p = build_payload(r, REPO, COMMIT)
        self.assertEqual(p["anchored"], ["issue:6952"])
        # Still listed in `searched` too: "all of them shown" must stay true.
        self.assertEqual(p["searched"], ["issue:6952", "code:a.py", "code:b.py"])

    def test_answer_reports_the_anchor_as_well(self):
        r = Result(verdict="answer", answer="a", citations=["pr:1435"],
                   retrieved=["pr:1435", "code:a.py"], anchored=["pr:1435"])
        self.assertEqual(build_payload(r, REPO, COMMIT)["anchored"], ["pr:1435"])

    def test_a_question_naming_nothing_anchors_nothing(self):
        r = Result(verdict="unknown", retrieved=["code:a.py"])
        self.assertEqual(build_payload(r, REPO, COMMIT)["anchored"], [])


if __name__ == "__main__":
    unittest.main()

class ExcerptTests(unittest.TestCase):
    """The excerpt is PROOF shown inline, so its bounds and its truncation
    marking are correctness, not cosmetics: an unmarked clip misrepresents the
    evidence."""

    def test_short_evidence_is_shown_whole_and_unmarked(self):
        self.assertEqual(payload.excerpt("const maxRetries = 3"), "const maxRetries = 3")

    def test_blank_lines_are_dropped(self):
        self.assertEqual(payload.excerpt("a\n\n\nb"), "a\nb")

    def test_extra_lines_are_clipped_and_marked(self):
        out = payload.excerpt("l1\nl2\nl3\nl4\nl5\nl6")
        self.assertEqual(out.splitlines()[:4], ["l1", "l2", "l3", "l4"])
        self.assertTrue(out.endswith("…"), "a clipped excerpt must be marked")

    def test_one_enormous_line_is_bounded_and_marked(self):
        # A machine-generated file can hold a single ~250k-char line; a line cap
        # alone never trips on it.
        out = payload.excerpt("x" * 250_000)
        self.assertLess(len(out), 200)
        self.assertIn("…", out)

    def test_no_evidence_yields_empty_string(self):
        self.assertEqual(payload.excerpt(""), "")

    def test_payload_carries_the_excerpt_for_each_citation(self):
        r = Result(verdict="answer", answer="Because of the restart window.",
                   citations=["code:sched/retry.go#L1-L40"],
                   retrieved=["code:sched/retry.go#L1-L40"],
                   evidence={"code:sched/retry.go#L1-L40": "// 5 masked a dead node\nconst maxRetries = 3"})
        out = payload.build_payload(r, "acme/sched", "abc1234")
        self.assertEqual(out["citations"][0]["excerpt"],
                         "// 5 masked a dead node\nconst maxRetries = 3")

    def test_unknown_verdict_carries_no_citations_and_no_excerpts(self):
        r = Result(verdict="unknown", retrieved=["code:a.py#L1-L10"],
                   evidence={"code:a.py#L1-L10": "should not leak"})
        out = payload.build_payload(r, "acme/sched", "abc1234")
        self.assertEqual(out["citations"], [])
        self.assertNotIn("should not leak", str(out))

    def test_agents_can_opt_in_to_retrieved_evidence_on_an_unknown(self):
        r = Result(
            verdict="unknown",
            retrieved=["issue:112", "issue:850"],
            evidence={
                "issue:112": "Add retry support for transient failures.",
                "issue:850": "Retries remain an open feature request.",
            },
        )
        out = payload.build_payload(
            r, "simonw/llm", "abc1234", include_evidence=True)

        self.assertEqual(out["verdict"], "unknown")
        self.assertEqual(out["citations"], [])
        self.assertEqual(
            out["evidence"],
            [
                {
                    "ref": "issue:112",
                    "url": "https://github.com/simonw/llm/issues/112",
                    "excerpt": "Add retry support for transient failures.",
                },
                {
                    "ref": "issue:850",
                    "url": "https://github.com/simonw/llm/issues/850",
                    "excerpt": "Retries remain an open feature request.",
                },
            ],
        )

    def test_payload_identifies_the_exact_corpus_that_answered(self):
        out = payload.build_payload(Result(verdict="unknown"), REPO, COMMIT)
        self.assertEqual(out["repo"], REPO)
        self.assertEqual(out["commit"], COMMIT)



class IndexingCaveatTests(unittest.TestCase):
    """An abstention while the index is still building means "I have not
    finished reading", NOT "no one wrote this down". Only the second is a claim
    about the repository, and it is the product's whole promise -- so the two
    must never render the same. Measured live 2026-07-28: the same question
    abstained 3/3 mid-build and answered 3/3 once the embed finished, on an
    identical corpus with an identical anchor and writer."""

    def test_an_abstention_mid_index_is_marked(self):
        r = Result(verdict="unknown", retrieved=["code:a.py"])
        self.assertTrue(build_payload(r, REPO, COMMIT, indexing=True)["indexing"])

    def test_a_complete_index_is_not_marked(self):
        r = Result(verdict="unknown", retrieved=["code:a.py"])
        self.assertFalse(build_payload(r, REPO, COMMIT, indexing=False)["indexing"])

    def test_the_field_defaults_to_false_for_existing_callers(self):
        r = Result(verdict="unknown", retrieved=[])
        self.assertFalse(build_payload(r, REPO, COMMIT)["indexing"])

    def test_marking_never_alters_the_verdict_or_citations(self):
        # The flag is a caveat on the ANSWER's completeness, never an input to
        # the honesty decision -- it must not touch what was emitted.
        r = Result(verdict="answer", answer="Because Y.", citations=["pr:1435"],
                   retrieved=["pr:1435"])
        plain = build_payload(r, REPO, COMMIT, indexing=False)
        mid = build_payload(r, REPO, COMMIT, indexing=True)
        self.assertEqual(plain["verdict"], mid["verdict"])
        self.assertEqual(plain["citations"], mid["citations"])
        self.assertEqual(plain["answer"], mid["answer"])

class EvidenceExcerptsOnAnUnknownTests(unittest.TestCase):
    """The agent-facing evidence list must carry TEXT, not just refs.

    Measured 2026-08-21 across two independent Claude Code sessions on
    firecrawl/firecrawl. Both received `verdict: unknown` with ~21 evidence
    refs and EVERY excerpt empty, and both discarded the list as noise. One of
    them later found commit 4d2f303e by hand -- the precedent that became PR
    #4382 -- and it had been in that first evidence list all along.

    The cause is a seam, not a retrieval failure: `pipeline` populates
    `Result.evidence` for CITED refs only, while `build_payload` builds its
    evidence list over `retrieved`. On an answer the two mostly overlap; on an
    UNKNOWN there are no citations, so every excerpt is "" -- the list is
    emptiest exactly when it is the only thing the caller gets.

    The tool description promises "an unknown verdict can still include related
    evidence". A bare ref is not evidence; it is a pointer to evidence.
    """

    def _unknown_result(self):
        r = Result(verdict="unknown", answer="", citations=[],
                   retrieved=["commit:4d2f303e", "issue:4054"])
        # What the writer actually saw, for every ref shown -- not just cited.
        r.shown = {"commit:4d2f303e": "fix(api/monitor): accept origin field in create/update body",
                   "issue:4054": "[OPEN] dify Create Monitor error type: HTTPError"}
        return r

    def test_unknown_verdict_still_carries_excerpts(self):
        payload = build_payload(self._unknown_result(), "o/r", "abc123",
                                include_evidence=True)
        excerpts = [e["excerpt"] for e in payload["evidence"]]
        self.assertTrue(all(excerpts),
                        f"evidence arrived as bare refs with no text: {payload['evidence']}")
        self.assertIn("accept origin field", excerpts[0])

    def test_every_retrieved_ref_appears(self):
        payload = build_payload(self._unknown_result(), "o/r", "abc123",
                                include_evidence=True)
        self.assertEqual(["commit:4d2f303e", "issue:4054"],
                         [e["ref"] for e in payload["evidence"]])

    def test_excerpts_are_still_bounded_and_marked(self):
        """The cap is not negotiable -- an unmarked clip misrepresents proof."""
        r = Result(verdict="unknown", answer="", citations=[], retrieved=["code:a.py"])
        r.shown = {"code:a.py": "\n".join(f"line {i}" for i in range(200))}
        payload = build_payload(r, "o/r", "abc123", include_evidence=True)
        text = payload["evidence"][0]["excerpt"]
        self.assertLess(len(text), 400)
        self.assertIn("…", text)

    def test_cited_evidence_is_unchanged(self):
        """The citations block keeps reading from `evidence`, the cited-only map
        the gate and writer saw. This change adds a display path, it does not
        widen what counts as grounded."""
        r = Result(verdict="answer", answer="Because X.", citations=["pr:1"],
                   retrieved=["pr:1", "pr:2"])
        r.evidence = {"pr:1": "the cited chunk"}
        payload = build_payload(r, "o/r", "abc123")
        self.assertIn("the cited chunk", payload["citations"][0]["excerpt"])
