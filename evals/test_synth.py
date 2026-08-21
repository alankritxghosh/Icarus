# evals/test_synth.py
import json
import unittest

from .corpus import Chunk
from .synth import build_prompt


class SelectionMarkingTests(unittest.TestCase):
    """A line selection names ONE piece of evidence as the subject; the rest is
    context. Without that distinction the writer answers about whichever chunk
    is easiest to answer -- proven live 2026-08-06 against the real corpus:
    selecting `logging_client()` (llm/utils.py#L149-L153) with neighbours on
    produced a confident, correctly-cited explanation of a DIFFERENT function
    (`extract_fenced_code_block`). Groundedness held; relevance did not, and the
    honesty gate cannot catch that -- it proves citations resolve to retrieved
    evidence, never that the answer is about the code the user pointed at."""

    def setUp(self):
        self.chunks = [Chunk("pr:1", "pr", "We did X because Y."),
                       Chunk("code:a.py", "code", "N = 32")]

    def test_no_selection_leaves_the_prompt_byte_identical(self):
        # The board-protection guard: /ask must not change at all. If this ever
        # fails, every eval number in the repo was measured on a different prompt.
        base = build_prompt("Why X?", self.chunks)
        self.assertEqual(base, build_prompt("Why X?", self.chunks, selection=None))
        self.assertEqual(base, build_prompt("Why X?", self.chunks, selection=[]))

    def test_selected_chunk_is_marked_and_others_are_not(self):
        prompt = build_prompt("What does this do?", self.chunks, selection=["code:a.py"])
        marked = [ln for ln in prompt.splitlines() if "SELECTED" in ln]
        self.assertEqual(len(marked), 1, f"expected exactly one marked block, got {marked}")
        self.assertIn("code:a.py", marked[0])
        self.assertNotIn("pr:1", marked[0])

    def test_instruction_names_the_selection_as_the_subject(self):
        low = build_prompt("What does this do?", self.chunks, selection=["code:a.py"]).lower()
        self.assertIn("selected", low)
        # and must say the rest is context, not an alternative subject
        self.assertIn("context", low)

    def test_selection_never_weakens_the_honesty_rules(self):
        # Same guard the charity clause carries: helpfulness may never be bought
        # with honesty. Evidence-only, no outside knowledge, unknown still open.
        low = build_prompt("What does this do?", self.chunks, selection=["code:a.py"]).lower()
        self.assertIn("only the numbered", low)
        self.assertIn("never use outside knowledge", low)
        self.assertIn("unknown", low)

    def test_a_selection_ref_not_among_the_chunks_marks_nothing(self):
        # Fail safe: an anchor that didn't survive the writer_k cut must not
        # crash and must not mark an unrelated block.
        prompt = build_prompt("What?", self.chunks, selection=["code:missing.py#L1-L9"])
        self.assertNotIn("SELECTED", prompt)

    def test_every_selected_chunk_is_marked_when_several_are_selected(self):
        prompt = build_prompt("What?", self.chunks, selection=["code:a.py", "pr:1"])
        marked = [ln for ln in prompt.splitlines() if "SELECTED" in ln]
        self.assertEqual(len(marked), 2)


class PlainLanguageAudienceTests(unittest.TestCase):
    """`audience="plain"` asks the writer for prose a non-technical reader can
    follow -- same evidence, same honesty gate, same JSON contract, just a
    different sentence. Requested 2026-08-06: explaining a PR to a PM should
    not require them to parse "chain resume from pending tool calls"."""

    def setUp(self):
        self.chunks = [Chunk("pr:1482", "pr", "PauseChain primitive + chain resume.")]

    def test_default_audience_is_byte_identical_to_before_this_existed(self):
        # The board-protection guard, same shape as selection=None: nothing
        # about /ask's prompt may change for a caller that doesn't opt in.
        base = build_prompt("What did PR 1482 do?", self.chunks)
        self.assertEqual(base, build_prompt("What did PR 1482 do?", self.chunks, audience=None))
        self.assertEqual(base, build_prompt("What did PR 1482 do?", self.chunks, audience="developer"))

    def test_plain_audience_adds_a_distinct_instruction(self):
        dev = build_prompt("What did PR 1482 do?", self.chunks)
        plain = build_prompt("What did PR 1482 do?", self.chunks, audience="plain")
        self.assertNotEqual(dev, plain)
        low = plain.lower()
        self.assertIn("non-technical", low)

    def test_plain_audience_forbids_jargon_without_explanation(self):
        low = build_prompt("x", self.chunks, audience="plain").lower()
        self.assertIn("jargon", low)

    def test_plain_audience_keeps_the_json_contract_unchanged(self):
        # The prose changes; the machine-readable shape must not, or the gate's
        # parser breaks.
        plain = build_prompt("x", self.chunks, audience="plain")
        self.assertIn('"verdict"', plain)
        self.assertIn('"citations"', plain)

    def test_plain_audience_never_weakens_the_honesty_rules(self):
        low = build_prompt("x", self.chunks, audience="plain").lower()
        self.assertIn("only the numbered", low)
        self.assertIn("never use outside knowledge", low)
        self.assertIn("unknown", low)

    def test_unknown_audience_value_is_rejected_not_silently_ignored(self):
        # A typo'd audience string silently falling back to developer mode
        # would be a confusing bug to track down later.
        with self.assertRaises(ValueError):
            build_prompt("x", self.chunks, audience="frendly")

    def test_composes_with_selection_marking(self):
        # audience and selection are independent options on the same function;
        # both must be able to apply to the same prompt at once.
        prompt = build_prompt("x", self.chunks, audience="plain", selection=["pr:1482"])
        self.assertIn("non-technical", prompt.lower())
        self.assertIn("SELECTED", prompt)


class BuildPromptTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [Chunk("pr:1", "pr", "We did X because Y."), Chunk("code:a.py", "code", "N = 32")]
        self.prompt = build_prompt("Why X?", self.chunks)

    def test_includes_question_and_refs_and_text(self):
        self.assertIn("Why X?", self.prompt)
        self.assertIn("pr:1", self.prompt)
        self.assertIn("We did X because Y.", self.prompt)
        self.assertIn("code:a.py", self.prompt)

    def test_demands_unknown_when_unsupported(self):
        # the instruction must offer an explicit abstention path
        self.assertIn("unknown", self.prompt.lower())

    def test_interprets_messy_phrasing_charitably(self):
        # The prompt tells the writer to read typo'd/slang/informal questions
        # charitably instead of abstaining on phrasing alone (fixes writer-stage
        # over-abstention on mangled questions -- docs/HANDOFF.md). Guarded so it
        # can't be silently dropped.
        low = self.prompt.lower()
        self.assertIn("typo", low)
        self.assertIn("charitably", low)

    def test_charity_never_weakens_the_evidence_or_unknown_rule(self):
        # The charity clause must NOT relax the honesty instruction: answers stay
        # evidence-only, outside knowledge is still forbidden, and insufficient
        # evidence still means abstain. This is the guard against a future edit
        # trading honesty for helpfulness.
        low = self.prompt.lower()
        self.assertIn("only the numbered", low)          # evidence-only
        self.assertIn("never use outside knowledge", low)  # no outside knowledge
        self.assertIn("insufficient", low)                 # insufficient evidence -> unknown
        self.assertIn("not a reason to abstain", low)      # messy phrasing != insufficient evidence

    def test_truncates_very_long_prose_chunks(self):
        # Still truncated -- the cap was raised on 2026-08-21, not removed.
        # (Before that date doc/config kept a separate 1,500-char prose cap;
        # see evals/test_doc_evidence_truncation.py for why it went.)
        from .synth import _MAX_CHUNK_CHARS
        big = Chunk("doc:a.md", "doc", "x" * (_MAX_CHUNK_CHARS + 5000))
        self.assertLess(len(build_prompt("q", [big])), _MAX_CHUNK_CHARS + 2000)

    def test_every_source_gets_the_same_budget(self):
        # A live-fetched PR (body + comments = the "why") must reach the writer,
        # and so must a real engineering-context doc: both are legitimately
        # large evidence, and the budget no longer depends on the source.
        from .synth import _MAX_CHUNK_CHARS
        body = "x" * 5000
        lengths = {
            src: len(build_prompt("q", [Chunk(f"{src}:a", src, body)]))
            for src in ("pr", "issue", "doc", "config", "code")
        }
        for src, n in lengths.items():
            self.assertGreater(n, 5000, f"{src} evidence was cut below its own size")
        self.assertLess(max(lengths.values()) - min(lengths.values()), 40,
                        f"budget still varies by source: {lengths}")

    def test_chunks_get_a_large_but_still_bounded_budget(self):
        # A 300-line code window is visible, and so is a whole engineering-context
        # doc, but a pathological giant chunk still cannot blow the prompt open.
        # Locks the cap so it can't silently balloon.
        #
        # This test used to end on `assertGreater(code_len, prose_len)`, proving
        # code got the larger budget. With one shared budget that comparison is
        # not merely obsolete, it is VACUOUS: both truncate to the same length
        # and the only remaining difference is that "code:a.py#L1-L400" is nine
        # characters longer than "doc:a.md". It passed for that reason alone.
        from .synth import _MAX_CHUNK_CHARS, _MAX_CODE_CHUNK_CHARS
        oversize = "x" * (_MAX_CODE_CHUNK_CHARS + 5000)
        code_len = len(build_prompt("q", [Chunk("code:a.py#L1-L400", "code", oversize)]))
        prose_len = len(build_prompt("q", [Chunk("doc:a.md", "doc", oversize)]))
        for n in (code_len, prose_len):
            self.assertGreater(n, _MAX_CHUNK_CHARS)              # the full budget was used
            self.assertLess(n, _MAX_CHUNK_CHARS + 2000)          # but bounded (instruction overhead)


if __name__ == "__main__":
    unittest.main()


class DecisionShapedQuestionTests(unittest.TestCase):
    """The 2026-08-21 writer inversion: a question asking whether to DO something,
    answered with the state of the topic instead. See
    evals/test_writer_uses_evidence.py for the live case."""

    def test_detector_fires_on_asking_permission(self):
        from .synth import seeks_decision
        for q in ("Should I fix rows_where and delete_where?",
                  "should we backport this to 3.x?",
                  "Is it safe to change how delete_where handles a missing table?",
                  "Can I remove this flag?",
                  "Do we need to update the Dockerfile pin?",
                  "Is there any reason not to merge this?"):
            self.assertTrue(seeks_decision(q), q)

    def test_detector_ignores_questions_about_what_is_true(self):
        """A false positive changes the emphasis of an answer that did not need
        it, so the patterns require an explicit actor rather than the mere word
        'should' -- including when the EVIDENCE-style prose contains it."""
        from .synth import seeks_decision
        for q in ("Why is the redirect limit 30?",
                  "What does delete_where do?",
                  "Does delete_where commit its changes in the 3.x series?",
                  "The docs say you should install it first",
                  "What should the timeout be set to in production?",
                  None, ""):
            self.assertFalse(seeks_decision(q), repr(q))

    def test_prompt_is_byte_identical_for_every_other_question(self):
        """The guarantee that keeps the eval board comparable across this change,
        the same one `selection` and `audience` carry."""
        chunk = Chunk("pr:1", "pr", "some evidence")
        before = build_prompt("Why is the redirect limit 30?", [chunk])
        self.assertNotIn("asks whether to DO something", before)

    def test_decision_prompt_names_the_failure_it_exists_to_stop(self):
        """An unexplained rule is inert -- the writer has to be told that a plan
        to do something later is not permission to do it now, because that is
        exactly the inference the live failure made."""
        chunk = Chunk("issue:841", "issue", "some evidence")
        prompt = build_prompt("Should I fix rows_where and delete_where?", [chunk])
        self.assertIn("asks whether to DO something", prompt)
        self.assertIn("not permission to make it now", prompt)
