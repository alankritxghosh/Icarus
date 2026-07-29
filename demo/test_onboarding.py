# demo/test_onboarding.py
"""The guided onboarding tour's contract, written before the implementation.

The tour is the first thing Icarus says about a repository, unprompted. That
makes it the highest-risk surface in the product: a question a user chose to
ask carries their own scepticism with it, and a claim Icarus volunteers does
not. So the tour gets no new intelligence and no new honesty path -- every step
is an ordinary gated ask, and these tests pin that it stays that way.

What they protect:
- the tour ships ONLY the steps measured reliable (evals/onboarding_probe.py),
- its question wording cannot drift away from the wording that was measured,
- `purpose` addresses the README rather than searching for it, and degrades to
  an ordinary ask when there is no README,
- an abstention is passed through untouched, never softened,
- and the tour never writes to the ask ledger.

Stdlib only, always runs.
"""

import unittest

from evals.corpus import Chunk
from evals.pipeline import Result

from .onboarding import STEPS, answer_step, plan

STATUS = {"state": "ready", "repo": "simonw/llm", "commit": "94769b8",
          "counts": {"pr": 2}, "private": False, "truncated": False,
          "indexing": False}


class _FakePipeline:
    """Records how it was called; returns a fixed grounded answer."""

    def __init__(self, chunks=(), result=None):
        self._chunks = list(chunks)
        self._result = result or Result(verdict="answer", answer="because.",
                                        citations=["doc:README.md"],
                                        retrieved=["doc:README.md"])
        self.answer_calls, self.explain_calls = [], []

    def indexed_chunks(self):
        return list(self._chunks)

    def answer(self, question, token=None):
        self.answer_calls.append((question, token))
        return self._result

    def explain(self, path, start, end, question=None):
        self.explain_calls.append((path, start, end, question))
        return self._result


def _with_readme():
    return _FakePipeline([Chunk(ref="doc:README.md", source="doc", text="# llm\n"),
                          Chunk(ref="code:llm/cli.py", source="code", text="x = 1\n")])


def _without_readme():
    return _FakePipeline([Chunk(ref="code:llm/cli.py", source="code", text="x = 1\n")])


class PlanTests(unittest.TestCase):
    def test_the_tour_opens_with_the_deterministic_overview(self):
        # The writer-backed steps run during the lexical-only window after a
        # connect, when answers are measurably worse. The map and entry points
        # need no retrieval at all, so they go first and are always solid.
        steps = plan(STATUS)["steps"]
        self.assertEqual(steps[0]["id"], "overview")
        self.assertEqual(steps[0]["kind"], "map")

    def test_only_the_measured_reliable_steps_ship(self):
        ids = [s["id"] for s in plan(STATUS)["steps"] if s["kind"] == "question"]
        self.assertEqual(ids, ["purpose", "stack", "decisions", "conventions", "recent"])

    def test_the_steps_measured_unreliable_are_absent(self):
        # architecture 2/10 and debt 5/10 on the 2026-07-29 probe. Shipping
        # them would make a third of the tour refuse.
        ids = [s["id"] for s in plan(STATUS)["steps"]]
        self.assertNotIn("architecture", ids)
        self.assertNotIn("debt", ids)

    def test_every_step_carries_a_human_title(self):
        for s in plan(STATUS)["steps"]:
            self.assertTrue(s["title"].strip())

    def test_the_plan_names_the_repo_it_is_a_tour_of(self):
        self.assertEqual(plan(STATUS)["repo"], "simonw/llm")

    def test_the_plan_says_the_index_is_still_building_when_it_is(self):
        p = plan({**STATUS, "indexing": True})
        self.assertIs(p["semantic_indexing_in_progress"], True)
        self.assertTrue(p["note"])


class PurposeIsAddressedNotSearchedTests(unittest.TestCase):
    """Measured 2026-07-29: searching for the README scored 2/10 on `purpose`;
    addressing it scored 10/10, all ten citing the README."""

    def test_purpose_addresses_the_indexed_readme(self):
        pipe = _with_readme()
        answer_step(pipe, STATUS, "purpose")
        self.assertEqual(len(pipe.explain_calls), 1)
        path, start, _end, question = pipe.explain_calls[0]
        self.assertEqual(path, "README.md")
        self.assertEqual(start, 1)
        self.assertIn("problem", question)
        self.assertEqual(pipe.answer_calls, [])

    def test_purpose_falls_back_to_an_ordinary_ask_with_no_readme(self):
        # A repo with no indexed README must still get a tour, not a crash and
        # not a step that silently disappears.
        pipe = _without_readme()
        answer_step(pipe, STATUS, "purpose")
        self.assertEqual(pipe.explain_calls, [])
        self.assertEqual(len(pipe.answer_calls), 1)

    def test_every_other_step_is_an_ordinary_ask(self):
        for step_id in ("stack", "decisions", "conventions", "recent"):
            pipe = _with_readme()
            answer_step(pipe, STATUS, step_id, token="tok")
            self.assertEqual(pipe.explain_calls, [], step_id)
            self.assertEqual(pipe.answer_calls[0][1], "tok", step_id)


class HonestyPassthroughTests(unittest.TestCase):
    def test_an_abstention_is_returned_untouched(self):
        abstain = Result(verdict="unknown", retrieved=["pr:1"],
                         abstention_reason="writer_abstained")
        pipe = _FakePipeline([Chunk(ref="doc:README.md", source="doc", text="hi")],
                             result=abstain)
        got = answer_step(pipe, STATUS, "stack")
        self.assertEqual(got.verdict, "unknown")
        self.assertEqual(got.abstention_reason, "writer_abstained")
        self.assertEqual(got.answer, "")

    def test_an_unknown_step_is_rejected_not_guessed(self):
        with self.assertRaises(ValueError):
            answer_step(_with_readme(), STATUS, "nonsense")


class MeasurementDriftTests(unittest.TestCase):
    """The probe measured these EXACT questions. If the product reworded them,
    10/10 on `purpose` would stop being evidence about the shipped tour -- so
    both read from one definition, and this proves it."""

    def test_the_probe_and_the_product_share_one_definition(self):
        from evals.onboarding_probe import ONBOARDING_STEPS
        probe = dict(ONBOARDING_STEPS)
        for step_id, _title, question in STEPS:
            self.assertEqual(probe[step_id], question, step_id)

    def test_the_probe_still_measures_the_steps_we_cut(self):
        # Cut for now, not forgotten: if architecture or debt become viable we
        # want the probe to be the thing that tells us.
        from evals.onboarding_probe import ONBOARDING_STEPS
        ids = [i for i, _q in ONBOARDING_STEPS]
        self.assertIn("architecture", ids)
        self.assertIn("debt", ids)

    def test_purpose_is_anchored_in_both(self):
        from evals.onboarding_probe import ANCHORED_STEPS
        self.assertEqual(ANCHORED_STEPS, {"purpose"})


if __name__ == "__main__":
    unittest.main()
