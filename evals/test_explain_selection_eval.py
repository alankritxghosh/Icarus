# evals/test_explain_selection_eval.py
"""Live proof that a line selection is answered ABOUT THE SELECTED LINES.

Found 2026-08-06 against the real serving pipeline (gemini-paid writer, hybrid
+ normalized retrieval, committed simonw/llm corpus). Selecting
`llm/utils.py#L149-L153` -- the five-line `logging_client()` function -- and
clicking "Ask Icarus" with no typed question produced, across repeated runs:

    default compound question, neighbours ON    -> unknown
    "What does this code do?",  neighbours ON   -> unknown (and, on another
                                                   run, an answer about the
                                                   whole file, not the lines)
    "What does this code do?",  neighbours OFF  -> correct, cites the anchor
    "...and how is it used?",   neighbours ON   -> a confident, correctly-cited
                                                   explanation of a DIFFERENT
                                                   function entirely

Two distinct defects, both fixed here, and the second is the dangerous one:
the honesty gate proves every citation resolves to genuinely-retrieved evidence
-- it cannot prove the answer is about the code the user selected. A grounded
answer to the wrong question passes every gate we have.

Deliberately a LIVE test (self-skips without a paid key / fastembed / corpus):
the failure is a property of a real writer choosing among real evidence, and a
StaticProvider cannot reproduce a model's choice. The deterministic half of the
contract -- that the selection is marked and neighbours are not -- is pinned
offline in test_synth.SelectionMarkingTests and
test_gated_explain.ExplainMarksTheSelectionTests, which always run.
"""

import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "evals" / "corpus"

# The anchor: `def logging_client() -> httpx.Client: ...`, five lines, no
# docstring, no PR or issue in the corpus explaining why it exists. Exactly the
# "plain code a senior engineer would explain in one sentence" case.
PATH, START, END = "llm/utils.py", 149, 153
ANCHOR_REF = "code:llm/utils.py#L149-L153"


def _skip_reason():
    from evals.env_file import load_env_file
    load_env_file(REPO_ROOT / ".env")
    if not os.environ.get("GEMINI_PAID_API_KEY"):
        return "GEMINI_PAID_API_KEY not set"
    if not (CORPUS_DIR / "chunks.jsonl").exists():
        return "committed corpus missing"
    try:
        import fastembed  # noqa: F401
    except Exception:
        return "fastembed not installed (serving uses hybrid retrieval)"
    return None


class ExplainAnswersAboutTheSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        reason = _skip_reason()
        if reason:
            raise unittest.SkipTest(reason)
        from demo.library import _build_gated_pipeline
        cls.pipe = _build_gated_pipeline(str(CORPUS_DIR))

    def test_bare_click_explains_the_selected_lines_with_neighbours_on(self):
        """The shipping path: select lines, click "Ask Icarus", type nothing.

        Neighbours stay ON -- narrowing them to fix this would throw away the
        "how is it used in this codebase" context that is the whole reason to
        ask Icarus rather than read the function.
        """
        r = self.pipe.explain(PATH, START, END)
        self.assertEqual(r.verdict, "answer",
                         "a bare line selection over plain code must never abstain: "
                         "the code IS the evidence")
        self.assertIn(ANCHOR_REF, r.citations,
                      f"answered without citing the selected lines; cited {r.citations}")
        self.assertIn("logging_client", r.answer,
                      f"answer is not about the selected function: {r.answer!r}")

    def test_a_typed_question_about_the_selection_is_answered_about_it(self):
        """The typed path -- the one that must be promoted in the UI, since it
        measurably feeds better neighbour evidence (see pipeline.explain)."""
        r = self.pipe.explain(PATH, START, END,
                              question="What does this function return?")
        self.assertEqual(r.verdict, "answer")
        self.assertIn(ANCHOR_REF, r.citations,
                      f"answered without citing the selected lines; cited {r.citations}")

    def test_an_unrecorded_why_still_abstains_honestly(self):
        """The honesty property must SURVIVE the fix. Asking why this design was
        chosen -- which nothing in the corpus records -- must still come back
        unknown. If this ever goes green with an answer, the fix bought
        helpfulness with a bluff and must be reverted."""
        r = self.pipe.explain(PATH, START, END,
                              question="Why was this approach chosen over the alternatives?")
        self.assertEqual(r.verdict, "unknown",
                         f"invented a rationale nothing records: {r.answer!r}")


if __name__ == "__main__":
    unittest.main()
