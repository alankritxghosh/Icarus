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

    def test_truncates_very_long_chunks(self):
        big = Chunk("pr:2", "pr", "x" * 5000)
        self.assertLess(len(build_prompt("q", [big])), 4000)


if __name__ == "__main__":
    unittest.main()
