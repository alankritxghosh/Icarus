# evals/test_investigator.py
"""The investigation loop's contract. Offline: no network, no real model.

The tests that matter most here are the ones proving a model CANNOT do the
things it must not do -- run a step outside the vocabulary, assert a claim it
cannot cite, declare its own hypothesis true, or keep the loop running past its
budget. A scripted provider stands in for the writer so each of those can be
attempted deliberately.
"""

import json
import unittest

from .corpus import Chunk
from .entities import build_entity_index
from .investigation import (
    Budget, Claim, HYPOTHESIS_SUPPORTED, STOP_BUDGET, STOP_DIMINISHING,
    SUPPORT_EXPLICIT, SUPPORT_WEAK,
)
from .investigator import (
    _anchor_refs, _seed_steps, _validate_step, conclude, investigate,
)
from .investigation import Step
from .probes import MAX_RETRIEVE_K, ProbeContext, retrieve
from .test_probes import FakePipeline

PR = Chunk(ref="pr:400", source="pr",
           text=("PR #400: new chunking strategy\n\n[MERGED by ana]\n\n"
                 "This exists because retrieval quality degraded on large "
                 "repositories. Closes #372.\n\n"
                 "Files changed (1): llm/cli.py (+10/-2)"))
ISSUE = Chunk(ref="issue:372", source="issue",
              text=("ISSUE #372: retrieval degrades on large repositories\n\n"
                    "Search returns unrelated files once a repo passes ~5k files."))
CODE = Chunk(ref="code:llm/cli.py#L1-L300", source="code", text="WINDOW = 300")
COMMIT = Chunk(ref="commit:abc123", source="commit",
               text="COMMIT abc123: new chunking strategy (#400)")
CHUNKS = [PR, ISSUE, CODE, COMMIT]


class ScriptedProvider:
    """Answers by which prompt it is looking at, so a test can script a whole
    investigation without depending on call order."""

    def __init__(self, plan=None, read=None, synthesis=None):
        self.plan = plan or {"hypotheses": [], "steps": []}
        self.read = read or {"claims": []}
        self.synthesis = synthesis or {"verdict": "unknown"}
        self.prompts = []

    def complete(self, prompt):
        self.prompts.append(prompt)
        if "planning an investigation" in prompt:
            body = self.plan
        elif "reading evidence gathered" in prompt:
            body = self.read(prompt) if callable(self.read) else self.read
        else:
            body = self.synthesis
        return json.dumps(body)


def pipeline(chunks=CHUNKS, **kw):
    return FakePipeline(list(chunks), **kw)


def entities(chunks=CHUNKS):
    return build_entity_index(list(chunks))


CITED_READ = {"claims": [{"text": "PR #400 introduced a new chunking strategy.",
                          "citations": ["pr:400"], "hypothesis": None,
                          "supports": True}]}


class SubjectBindingTests(unittest.TestCase):
    def test_a_named_pull_request_binds_deterministically(self):
        self.assertEqual(_anchor_refs("talk to me about PR #400", pipeline()),
                         ["pr:400"])

    def test_the_named_KIND_wins_over_precedence(self):
        chunks = CHUNKS + [Chunk(ref="issue:400", source="issue", text="ISSUE #400: x")]
        self.assertEqual(_anchor_refs("what did PR 400 change?", pipeline(chunks)),
                         ["pr:400"])
        self.assertEqual(_anchor_refs("what is issue 400 about?", pipeline(chunks)),
                         ["issue:400"])

    def test_a_hex_shaped_english_word_is_not_a_commit(self):
        self.assertEqual(_anchor_refs("why was this defaced?", pipeline()), [])

    def test_a_question_naming_nothing_binds_nothing(self):
        self.assertEqual(_anchor_refs("why is retrieval slow?", pipeline()), [])

    def test_seeds_read_the_subject_before_following_anything(self):
        steps = _seed_steps(["pr:400"], "why?")
        self.assertEqual((steps[0].primitive, steps[0].args), ("inspect", {"ref": "pr:400"}))
        self.assertEqual({s.args["edge"] for s in steps[1:]},
                         {"linked_issues", "changed_files", "commits", "subsequent_prs"})

    def test_with_no_subject_the_opening_move_is_to_search_for_one(self):
        steps = _seed_steps([], "why is retrieval slow?")
        self.assertEqual(steps[0].primitive, "retrieve")


class StepValidationTests(unittest.TestCase):
    def test_a_well_formed_step_is_accepted(self):
        step = _validate_step({"primitive": "trace",
                               "args": {"ref": "pr:400", "edge": "commits"},
                               "reason": "what it did"})
        self.assertEqual(step.primitive, "trace")

    def test_a_primitive_outside_the_vocabulary_is_refused(self):
        for primitive in ("shell", "write_file", "ask_the_internet", "verify"):
            self.assertIsNone(_validate_step({"primitive": primitive,
                                              "args": {"ref": "pr:400"}}), primitive)

    def test_a_smuggled_argument_REJECTS_the_step_rather_than_being_stripped(self):
        # Stripping ran the step anyway. Rejecting is stronger: an argument the
        # primitive cannot take means the planner mis-specified the call, and a
        # bounded budget should not be spent on a guess at what it meant.
        self.assertIsNone(_validate_step({"primitive": "inspect",
                                          "args": {"ref": "pr:400", "cmd": "rm -rf /",
                                                   "url": "http://x"}}))
        # ...and the well-formed call it was trying to smuggle into still works.
        self.assertEqual(_validate_step({"primitive": "inspect",
                                         "args": {"ref": "pr:400"}}).args,
                         {"ref": "pr:400"})

    def test_a_step_with_no_usable_argument_is_refused(self):
        self.assertIsNone(_validate_step({"primitive": "inspect", "args": {}}))
        self.assertIsNone(_validate_step({"primitive": "inspect", "args": "pr:400"}))
        self.assertIsNone(_validate_step("inspect"))


class StepArgumentBoundsTests(unittest.TestCase):
    """A planned step is UNTRUSTED model output. Its arguments reach the
    production retriever, so they are bounded here or nowhere."""

    def test_an_absurd_k_is_bounded_not_forwarded(self):
        # k=1e9 reached search_refs unchanged and every returned chunk was
        # retained before the evidence budget was consulted.
        step = _validate_step({"primitive": "retrieve",
                               "args": {"query": "x", "k": 1_000_000_000}})
        self.assertIsNotNone(step)
        self.assertLessEqual(step.args["k"], MAX_RETRIEVE_K)

    def test_a_boolean_k_is_refused_because_bool_is_an_int_in_python(self):
        step = _validate_step({"primitive": "retrieve",
                               "args": {"query": "x", "k": True}})
        self.assertNotIn("k", (step.args if step else {}))

    def test_a_zero_or_negative_k_is_refused(self):
        for bad in (0, -5):
            step = _validate_step({"primitive": "retrieve",
                                   "args": {"query": "x", "k": bad}})
            self.assertNotIn("k", (step.args if step else {}), bad)

    def test_arguments_belonging_to_a_DIFFERENT_primitive_are_refused(self):
        # retrieve takes a query. `ref`/`edge` are trace's, and accepting them
        # produced a step with no query at all.
        self.assertIsNone(_validate_step({"primitive": "retrieve",
                                          "args": {"ref": "pr:9", "edge": "commits"}}))
        self.assertIsNone(_validate_step({"primitive": "trace",
                                          "args": {"ref": "pr:9"}}))
        self.assertIsNone(_validate_step({"primitive": "compare",
                                          "args": {"ref": "pr:9"}}))

    def test_an_unknown_relationship_is_refused_at_validation(self):
        self.assertIsNone(_validate_step({"primitive": "trace",
                                          "args": {"ref": "pr:9", "edge": "caused_by"}}))

    def test_retrieve_bounds_k_even_if_a_step_arrives_unvalidated(self):
        # Defence in depth: the probe is reachable from seeds too.
        c = ProbeContext(pipeline=pipeline(), entities=entities())
        retrieve(c, Step("retrieve", {"query": "chunking", "k": 10_000}))
        self.assertLessEqual(c.pipeline.searched[-1][1], MAX_RETRIEVE_K)


class LoopTests(unittest.TestCase):
    def test_a_scripted_investigation_gathers_evidence_and_verified_claims(self):
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        self.assertEqual(inv.subject, ["pr:400"])
        self.assertIn("pr:400", inv.evidence)
        self.assertTrue(inv.claims)
        self.assertTrue(all(c.verified for c in inv.claims))
        self.assertTrue(inv.performed)

    def test_the_trail_records_every_step_that_ran(self):
        inv = investigate("about PR #400", pipeline(), entities(),
                          ScriptedProvider(read=CITED_READ))
        trail = inv.summary()["trail"]
        self.assertEqual(len(trail), len(inv.performed))
        self.assertIn("inspect", [s["primitive"] for s in trail])

    def test_a_claim_citing_evidence_nobody_retrieved_never_enters_the_state(self):
        # Two independent layers refuse this -- the gate (via probes.verify) and
        # the support classifier -- and either alone is sufficient. The two
        # tests below isolate each, since this one passes with either disabled.
        provider = ScriptedProvider(read={"claims": [
            {"text": "It was a scalability change.", "citations": ["pr:999"],
             "hypothesis": None, "supports": True}]})
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        self.assertEqual(inv.claims, [])

    def test_a_claim_with_no_citation_at_all_never_enters_the_state(self):
        provider = ScriptedProvider(read={"claims": [
            {"text": "Obviously this was for performance.", "citations": [],
             "hypothesis": None, "supports": True}]})
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        self.assertEqual(inv.claims, [])

    def test_the_GATE_layer_alone_refuses_a_claim_the_classifier_would_admit(self):
        # Citations that resolve perfectly, so classify_support is satisfied --
        # only the honesty gate can reject this, on its self-disclaim guard.
        # Proven red by making probes.verify return True unconditionally.
        provider = ScriptedProvider(read={"claims": [
            {"text": "The evidence does not state a reason for this change.",
             "citations": ["pr:400"], "hypothesis": None, "supports": True}]})
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        self.assertEqual(inv.claims, [])

    def test_the_CLASSIFIER_layer_alone_refuses_a_claim_the_gate_would_admit(self):
        # The gate sees this step's own evidence and is satisfied; the claim
        # cites a ref the investigation did not retain, so it could never be
        # shown to a reader. Proven red by dropping the classify_support check.
        provider = ScriptedProvider(read={"claims": [
            {"text": "It closes issue 372.", "citations": ["pr:400"],
             "hypothesis": None, "supports": True}]})
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        self.assertTrue(inv.claims)          # baseline: this one IS admitted
        inv.evidence.clear()
        from .investigation import classify_support, SUPPORT_UNSUPPORTED
        self.assertEqual(classify_support(["pr:400"], inv.evidence),
                         SUPPORT_UNSUPPORTED)

    def test_support_is_classified_in_code_whatever_the_model_says(self):
        provider = ScriptedProvider(read={"claims": [
            {"text": "The window is 300 lines.",
             "citations": ["code:llm/cli.py#L1-L300"], "supports": True,
             "support": "explicit", "confidence": 0.99}]})
        inv = investigate("what is the window size?", pipeline(), entities(), provider)
        self.assertEqual([c.support for c in inv.claims], [SUPPORT_WEAK])

    def test_a_model_cannot_declare_its_own_hypothesis_true(self):
        provider = ScriptedProvider(
            plan={"hypotheses": ["it was a scalability change"],
                  "steps": [], "status": "supported"},
            read=CITED_READ)
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        # It became supported only because a VERIFIED, cited claim was attached
        # to it -- and here none was, since the read claim named no hypothesis.
        self.assertNotEqual(inv.hypotheses[0].status, HYPOTHESIS_SUPPORTED)

    def test_a_hypothesis_becomes_supported_only_through_verified_claims(self):
        provider = ScriptedProvider(
            plan={"hypotheses": ["it fixed retrieval quality"], "steps": []},
            read={"claims": [
                {"text": "PR #400 was made because retrieval degraded on large "
                         "repositories.", "citations": ["pr:400", "issue:372"],
                 "hypothesis": "h1", "supports": True}]})
        inv = investigate("why was PR #400 introduced?", pipeline(), entities(), provider)
        self.assertEqual(inv.hypotheses[0].status, HYPOTHESIS_SUPPORTED)
        self.assertEqual(inv.claims[0].support, SUPPORT_EXPLICIT)

    def test_a_step_the_loop_already_ran_is_never_run_twice(self):
        provider = ScriptedProvider(
            plan={"hypotheses": [], "steps": [
                {"primitive": "inspect", "args": {"ref": "pr:400"}, "reason": "again"}]},
            read=CITED_READ)
        inv = investigate("about PR #400", pipeline(), entities(), provider)
        ids = [s.id for s in inv.performed]
        self.assertEqual(len(ids), len(set(ids)))

    def test_a_traced_relationship_is_actually_READ_not_just_discovered(self):
        # The live-found failure this exists to prevent: an investigation of
        # PR #1525 traced its linked issue, changed file and follow-up pull
        # requests and read NONE of them, scoring 25% hop recall while
        # reporting itself finished. Following a link and never looking at the
        # other end is the whole point of tracing, missed.
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("about PR #400", pipeline(), entities(), provider,
                          budget=Budget(max_steps=12))
        inspected = {s.args.get("ref") for s in inv.performed if s.primitive == "inspect"}
        self.assertIn("issue:372", inspected)
        self.assertIn("issue:372", inv.evidence)

    def test_following_is_bounded_so_one_trace_cannot_eat_the_budget(self):
        prs = [Chunk(ref=f"pr:{n}", source="pr",
                     text=f"PR #{n}: later\n\nFiles changed (1): llm/cli.py (+1/-1)")
               for n in range(500, 520)]
        chunks = CHUNKS + prs
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("about PR #400", pipeline(chunks), entities(chunks), provider,
                          budget=Budget(max_steps=40))
        followed = [s for s in inv.performed
                    if s.primitive == "inspect" and "later" in s.reason]
        self.assertLessEqual(len(followed), 3 * 4)   # _MAX_FOLLOW per trace step

    def test_an_entity_is_read_before_a_file_when_the_budget_is_short(self):
        # A pull request or issue is one bounded document that usually records a
        # reason; a file expands into code that can only ever show WHAT. When
        # the budget cuts the list short it should cut the code, not the reason.
        from .investigator import _follow_order
        self.assertEqual(_follow_order(["llm/cli.py", "issue:372", "docs/x.md",
                                        "commit:abc"]),
                         ["issue:372", "commit:abc", "llm/cli.py", "docs/x.md"])

    def test_live_fetched_evidence_hands_its_TEXT_back_to_the_caller(self):
        # Found live 2026-08-08: the server rebuilt evidence text from the
        # indexed corpus after the run, which silently lost every live-fetched
        # piece -- an unindexed pull request, a commit, a diff. `diff:1525`
        # reached the conclusion with empty text, blanking its excerpt and
        # leaving the gate's entity-presence guard checking an empty string.
        fetched = Chunk(ref="pr:900", source="pr", text="PR #900: later work")
        texts = {}
        investigate("about PR #900", pipeline(live=lambda n, t: fetched),
                    entities(), ScriptedProvider(read=CITED_READ), texts=texts)
        self.assertEqual(texts.get("pr:900"), fetched.text)

    def test_the_diff_fetcher_reaches_a_compare_step(self):
        diff = Chunk(ref="diff:400", source="diff", text="DIFF of PR #400\n\n@@ -1 +1 @@")
        provider = ScriptedProvider(
            plan={"hypotheses": [], "steps": [
                {"primitive": "compare", "args": {"pr": "pr:400"},
                 "reason": "what the code became"}]},
            read=CITED_READ)
        texts = {}
        inv = investigate("what did PR #400 change?", pipeline(), entities(), provider,
                          diff_fetch=lambda n, t=None: diff, texts=texts)
        self.assertIn("diff:400", inv.evidence)
        self.assertIn("@@", texts["diff:400"])

    def test_the_evidence_character_ceiling_is_enforced_BEFORE_evidence_is_kept(self):
        # It was charged AFTER a whole parallel batch had been retained: with
        # max_evidence_chars=1 the run kept 2,000 characters and only then
        # noticed. A ceiling checked after the spend is a counter, not a bound.
        big = [Chunk(ref=f"pr:{n}", source="pr", text="x" * 2000)
               for n in range(400, 410)]
        texts = {}
        budget = Budget(max_evidence_chars=500, max_parallel=4)
        inv = investigate("about PR #400", pipeline(big), entities(big),
                          ScriptedProvider(read=CITED_READ), budget=budget, texts=texts)
        self.assertLessEqual(sum(len(t) for t in texts.values()),
                             budget.max_evidence_chars)
        self.assertLessEqual(budget.evidence_chars_spent, budget.max_evidence_chars)

    def test_clipped_evidence_is_REPORTED_not_silently_dropped(self):
        # Truncating evidence and saying nothing would let a conclusion rest on
        # a partial read while reading as a complete one.
        big = [Chunk(ref=f"pr:{n}", source="pr", text="x" * 2000)
               for n in range(400, 410)]
        inv = investigate("about PR #400", pipeline(big), entities(big),
                          ScriptedProvider(read=CITED_READ),
                          budget=Budget(max_evidence_chars=500, max_parallel=4))
        self.assertTrue(any("evidence" in u.lower() for u in inv.unknowns),
                        f"nothing disclosed the clip: {inv.unknowns}")

    def test_a_generous_budget_keeps_every_piece_of_evidence(self):
        # The bound must not bite in ordinary use.
        texts = {}
        investigate("about PR #400", pipeline(), entities(),
                    ScriptedProvider(read=CITED_READ), texts=texts)
        self.assertIn("pr:400", texts)
        self.assertEqual(texts["pr:400"], PR.text)

    def test_the_budget_is_a_hard_ceiling_on_steps(self):
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("about PR #400", pipeline(), entities(), provider,
                          budget=Budget(max_steps=2, max_parallel=1))
        self.assertLessEqual(len(inv.performed), 2)
        self.assertEqual(inv.stopped_because, STOP_BUDGET)

    def test_the_budget_is_a_hard_ceiling_on_billed_writer_calls(self):
        provider = ScriptedProvider(read=CITED_READ)
        investigate("about PR #400", pipeline(), entities(), provider,
                    budget=Budget(max_writer_calls=2, max_parallel=1))
        self.assertLessEqual(len(provider.prompts), 2)

    def test_the_writer_budget_covers_SYNTHESIS_too(self):
        # conclude() spent a writer call unconditionally, so a run capped at 2
        # made 3. The ceiling has to cover the whole request, not just the
        # gathering half -- synthesis is the one call a user always pays for.
        provider = ScriptedProvider(
            read=CITED_READ,
            synthesis={"verdict": "answer", "answer": "x", "citations": ["pr:400"]})
        budget = Budget(max_writer_calls=2, max_parallel=1)
        inv = investigate("about PR #400", pipeline(), entities(), provider, budget=budget)
        conclude(inv, provider, texts={"pr:400": PR.text})
        self.assertLessEqual(budget.writer_calls_spent, budget.max_writer_calls)
        self.assertLessEqual(len(provider.prompts), 2)

    def test_a_synthesis_slot_is_RESERVED_so_a_conclusion_is_still_possible(self):
        # Reserving beats refusing: an investigation that gathered evidence and
        # then had no budget left to say anything would be a worse product than
        # one that gathered slightly less.
        provider = ScriptedProvider(
            read=CITED_READ,
            synthesis={"verdict": "answer", "answer": "x", "citations": ["pr:400"]})
        budget = Budget(max_writer_calls=3, max_parallel=1)
        inv = investigate("about PR #400", pipeline(), entities(), provider, budget=budget)
        self.assertTrue(inv.claims, "nothing was gathered at all")
        result = conclude(inv, provider, texts={"pr:400": PR.text})
        self.assertEqual(result.verdict, "answer")
        self.assertLessEqual(budget.writer_calls_spent, budget.max_writer_calls)

    def test_a_planner_returning_nonsense_ends_the_run_rather_than_improvising(self):
        provider = ScriptedProvider(plan={"steps": [{"primitive": "curl"}]})
        inv = investigate("why is retrieval slow?", pipeline(), entities(), provider)
        self.assertIsNotNone(inv.stopped_because)
        self.assertLessEqual(len(inv.performed), 1)

    def test_a_run_that_stops_learning_ends_on_diminishing_returns(self):
        # Every step re-finds the same single chunk, so no round adds a new ref.
        provider = ScriptedProvider(
            plan={"hypotheses": [], "steps": [
                {"primitive": "retrieve", "args": {"query": "chunking"}},
                {"primitive": "retrieve", "args": {"query": "chunk strategy"}},
                {"primitive": "retrieve", "args": {"query": "chunk window"}}]},
            read={"claims": []})
        inv = investigate("why?", pipeline(chunks=[PR], ranking=["pr:400"]),
                          entities([PR]), provider, budget=Budget(max_parallel=1))
        self.assertIn(inv.stopped_because, (STOP_DIMINISHING, STOP_BUDGET))

    def test_a_step_that_finds_nothing_is_kept_as_an_unknown_not_dropped(self):
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("about PR #400", pipeline(chunks=[PR]), entities([PR]),
                          provider)
        self.assertTrue(any("nothing recorded" in u for u in inv.unknowns))

    def test_a_caller_supplied_subject_is_used_instead_of_re_deriving_it(self):
        # The follow-up path: "why did IT change?" names nothing.
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("why did it change?", pipeline(), entities(), provider,
                          subject=["pr:400"], objective="why was PR #400 introduced?")
        self.assertEqual(inv.subject, ["pr:400"])
        self.assertIn("pr:400", inv.evidence)

    def test_the_callers_token_reaches_a_live_fetch_and_is_not_retained(self):
        seen = []
        p = pipeline(live=lambda n, t: seen.append(t))
        inv = investigate("about PR #900", p, entities(), ScriptedProvider(),
                          token="gho_secret")
        self.assertEqual(seen, ["gho_secret"])
        self.assertNotIn("gho_secret", json.dumps(inv.summary()))


class ConcludeTests(unittest.TestCase):
    TEXTS = {"pr:400": PR.text, "issue:372": ISSUE.text}

    def _investigated(self, read=CITED_READ):
        provider = ScriptedProvider(read=read)
        return investigate("why was PR #400 introduced?", pipeline(), entities(),
                           provider)

    def test_an_investigation_with_no_findings_abstains(self):
        inv = investigate("why?", pipeline(), entities(),
                          ScriptedProvider(read={"claims": []}))
        result = conclude(inv, ScriptedProvider())
        self.assertEqual(result.verdict, "unknown")
        self.assertIsNotNone(result.abstention_reason)

    def test_a_grounded_conclusion_is_an_ordinary_Result(self):
        inv = self._investigated()
        provider = ScriptedProvider(synthesis={
            "verdict": "answer",
            "answer": "PR #400 introduced a new chunking strategy because "
                      "retrieval degraded on large repositories.",
            "citations": ["pr:400"]})
        result = conclude(inv, provider, texts=self.TEXTS)
        self.assertEqual(result.verdict, "answer")
        self.assertEqual(result.citations, ["pr:400"])
        self.assertEqual(result.anchored, ["pr:400"])

    def test_a_conclusion_citing_unretrieved_evidence_is_forced_to_unknown(self):
        inv = self._investigated()
        provider = ScriptedProvider(synthesis={
            "verdict": "answer", "answer": "It was a scalability migration.",
            "citations": ["pr:999"]})
        self.assertEqual(conclude(inv, provider, texts=self.TEXTS).verdict, "unknown")

    def test_the_final_answer_faces_the_FULL_gate_not_a_weaker_one(self):
        # A "why" concluded only from a bare code constant must abstain, even
        # though that claim was legitimately verified mid-run for groundedness.
        provider = ScriptedProvider(read={"claims": [
            {"text": "The window is 300 lines.",
             "citations": ["code:llm/cli.py#L1-L300"], "supports": True}]})
        inv = investigate("why is the chunk window 300 lines?", pipeline(),
                          entities(), provider)
        self.assertTrue(inv.claims)          # the finding survived the run...
        out = conclude(inv, ScriptedProvider(synthesis={
            "verdict": "answer", "answer": "Because the window is 300 lines.",
            "citations": ["code:llm/cli.py#L1-L300"]}),
            texts={"code:llm/cli.py#L1-L300": CODE.text})
        self.assertEqual(out.verdict, "unknown")   # ...but cannot answer the why

    def test_the_synthesis_prompt_carries_findings_unknowns_and_conflicts(self):
        inv = self._investigated()
        inv.unknowns.append("whether it was part of a larger migration")
        inv.contradictions = [("c1", "c2", "it was a scalability change")]
        provider = ScriptedProvider()
        conclude(inv, provider, texts=self.TEXTS)
        prompt = provider.prompts[-1]
        self.assertIn("FINDINGS:", prompt)
        self.assertIn("whether it was part of a larger migration", prompt)
        self.assertIn("do not resolve it", prompt)

    def test_a_budget_truncated_run_tells_the_writer_to_say_so(self):
        provider = ScriptedProvider(read=CITED_READ)
        inv = investigate("about PR #400", pipeline(), entities(), provider,
                          budget=Budget(max_steps=1, max_parallel=1))
        out = ScriptedProvider()
        conclude(inv, out, texts=self.TEXTS)
        self.assertIn("stopped early", out.prompts[-1])

    def test_evidence_returned_is_the_cited_text_and_nothing_more(self):
        inv = self._investigated()
        provider = ScriptedProvider(synthesis={
            "verdict": "answer", "answer": "It closes issue 372.",
            "citations": ["pr:400"]})
        result = conclude(inv, provider, texts=self.TEXTS)
        self.assertEqual(list(result.evidence), ["pr:400"])


if __name__ == "__main__":
    unittest.main()
