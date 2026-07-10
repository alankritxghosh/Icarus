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


if __name__ == "__main__":
    unittest.main()
