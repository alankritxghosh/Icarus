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
        # doc/config keep the small prose cap.
        big = Chunk("doc:a.md", "doc", "x" * 5000)
        self.assertLess(len(build_prompt("q", [big])), 4000)

    def test_pr_issue_discussion_gets_the_larger_budget(self):
        # A live-fetched PR (body + comments = the "why") must reach the writer,
        # not be cut at the small prose cap.
        from .synth import _MAX_CHUNK_CHARS
        pr = Chunk("pr:400", "pr", "x" * 5000)
        self.assertGreater(len(build_prompt("q", [pr])), _MAX_CHUNK_CHARS + 2000)

    def test_code_chunks_get_a_larger_but_still_bounded_budget(self):
        # Code chunks get _MAX_CODE_CHUNK_CHARS (so a 300-line window is visible),
        # more than the prose cap but STILL bounded -- a pathological giant chunk
        # can't blow the prompt open. Locks the cap so it can't silently balloon.
        from .synth import _MAX_CHUNK_CHARS, _MAX_CODE_CHUNK_CHARS
        oversize = "x" * (_MAX_CODE_CHUNK_CHARS + 5000)   # bigger than the code cap
        code_len = len(build_prompt("q", [Chunk("code:a.py#L1-L400", "code", oversize)]))
        prose_len = len(build_prompt("q", [Chunk("doc:a.md", "doc", oversize)]))
        # code was truncated to the code cap (not the full oversize length)...
        self.assertGreater(code_len, _MAX_CODE_CHUNK_CHARS)          # got the larger code budget
        self.assertLess(code_len, _MAX_CODE_CHUNK_CHARS + 2000)      # but bounded (instruction overhead only)
        # ...and prose of the SAME size got only the small cap
        self.assertLess(prose_len, _MAX_CHUNK_CHARS + 2000)
        self.assertGreater(code_len, prose_len)                     # code budget strictly larger


if __name__ == "__main__":
    unittest.main()
