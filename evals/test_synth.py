# evals/test_synth.py
import json
import unittest

from .corpus import Chunk
from .synth import build_prompt


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

    def test_truncates_very_long_chunks(self):
        big = Chunk("pr:2", "pr", "x" * 5000)
        self.assertLess(len(build_prompt("q", [big])), 4000)

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
