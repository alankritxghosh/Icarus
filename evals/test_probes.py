# evals/test_probes.py
"""The five primitives' contract. Offline: no network, no model, no corpus.

What is pinned hardest is that a probe stays a THIN adapter -- it may not rank,
resolve, or decide. A probe that quietly re-implemented retrieval or the gate
would give the investigation loop a second, weaker standard of truth, and the
weaker one always wins in the end.
"""

import unittest

from .corpus import Chunk
from .entities import build_entity_index
from .investigation import Step
from .probes import (
    ProbeContext, compare, inspect, retrieve, run_round, run_step, trace, verify,
)


class FakePipeline:
    """Only the read-only surface probes are allowed to touch."""

    def __init__(self, chunks, ranking=None, live=None, live_commit=None):
        self._by_ref = {c.ref: c for c in chunks}
        self._ranking = ranking if ranking is not None else [c.ref for c in chunks]
        self._live, self._live_commit = live, live_commit
        self.searched = []

    def chunk_for(self, ref):
        return self._by_ref.get(ref)

    def search_refs(self, query, k):
        self.searched.append((query, k))
        return self._ranking[:k]

    def fetchers(self):
        return self._live, self._live_commit


PR = Chunk(ref="pr:400", source="pr",
           text=("PR #400: chunking\n\nCloses #372.\n\n"
                 "Files changed (1): llm/cli.py (+10/-2)"))
ISSUE = Chunk(ref="issue:372", source="issue",
              text="ISSUE #372: retrieval degrades on large repositories")
CODE = Chunk(ref="code:llm/cli.py#L1-L300", source="code", text="WINDOW = 300")
COMMIT = Chunk(ref="commit:abc123", source="commit",
               text="COMMIT abc123: Improve chunking (#400)")


def ctx(chunks=(PR, ISSUE, CODE, COMMIT), **kw):
    pipeline = FakePipeline(list(chunks), **kw)
    return ProbeContext(pipeline=pipeline, entities=build_entity_index(list(chunks)))


class RetrieveTests(unittest.TestCase):
    def test_delegates_to_the_pipelines_own_retriever(self):
        # Not a second ranking. An investigation that retrieved differently from
        # /ask would answer differently from it on the same evidence.
        c = ctx()
        out = retrieve(c, Step("retrieve", {"query": "chunking", "k": 2}))
        self.assertEqual(c.pipeline.searched, [("chunking", 2)])
        self.assertEqual(list(out.evidence), ["pr:400", "issue:372"])

    def test_evidence_carries_its_text_and_the_step_that_found_it(self):
        step = Step("retrieve", {"query": "chunking", "k": 1})
        out = retrieve(ctx(), step)
        self.assertEqual(out.texts["pr:400"], PR.text)
        self.assertEqual(out.evidence["pr:400"].via, step.id)

    def test_a_ranked_ref_with_no_chunk_is_skipped_not_invented(self):
        c = ctx(ranking=["pr:400", "pr:999"])
        out = retrieve(c, Step("retrieve", {"query": "x", "k": 5}))
        self.assertEqual(list(out.evidence), ["pr:400"])

    def test_an_empty_query_finds_nothing_and_says_so(self):
        out = retrieve(ctx(), Step("retrieve", {"query": "  "}))
        self.assertEqual(out.evidence, {})
        self.assertTrue(out.note)

    def test_nothing_matching_is_reported_rather_than_silent(self):
        out = retrieve(ctx(ranking=[]), Step("retrieve", {"query": "zzz"}))
        self.assertIn("zzz", out.note)


class InspectTests(unittest.TestCase):
    def test_an_indexed_ref_is_read_from_memory_without_fetching(self):
        calls = []
        c = ctx(live=lambda n, t: calls.append(n))
        out = inspect(c, Step("inspect", {"ref": "pr:400"}))
        self.assertEqual(out.texts, {"pr:400": PR.text})
        self.assertEqual(calls, [])

    def test_an_unindexed_ref_is_live_fetched(self):
        fetched = Chunk(ref="pr:900", source="pr", text="PR #900: later work")
        c = ctx(live=lambda n, t: fetched if n == 900 else None)
        out = inspect(c, Step("inspect", {"ref": "pr:900"}))
        self.assertEqual(out.texts, {"pr:900": fetched.text})

    def test_the_fetch_decides_the_KIND_not_the_request(self):
        # GitHub shares one number sequence: asking for pr:6952 can return the
        # issue. Recording it under the requested ref would make every later
        # citation point at something that does not exist.
        real = Chunk(ref="issue:6952", source="issue", text="ISSUE #6952: x")
        c = ctx(live=lambda n, t: real)
        out = inspect(c, Step("inspect", {"ref": "pr:6952"}))
        self.assertEqual(list(out.evidence), ["issue:6952"])

    def test_the_callers_token_is_passed_to_the_fetch(self):
        seen = []
        c = ctx(live=lambda n, t: seen.append(t))
        c.token = "gho_secret"
        inspect(c, Step("inspect", {"ref": "pr:900"}))
        self.assertEqual(seen, ["gho_secret"])

    def test_a_failed_fetch_reports_a_gap_rather_than_raising(self):
        def boom(n, t):
            raise RuntimeError("network")
        out = inspect(ctx(live=boom), Step("inspect", {"ref": "pr:900"}))
        self.assertEqual(out.evidence, {})
        self.assertIn("could not be read", out.note)

    def test_with_no_fetcher_wired_an_unindexed_ref_is_simply_unread(self):
        out = inspect(ctx(), Step("inspect", {"ref": "pr:900"}))
        self.assertEqual(out.evidence, {})
        self.assertTrue(out.note)

    def test_a_bare_path_reads_that_files_windows(self):
        out = inspect(ctx(), Step("inspect", {"ref": "llm/cli.py"}))
        self.assertEqual(list(out.evidence), ["code:llm/cli.py#L1-L300"])

    def test_a_many_windowed_file_is_bounded_and_the_bound_is_reported(self):
        chunks = [Chunk(ref=f"code:big.py#L{i}-L{i+9}", source="code", text="x")
                  for i in range(1, 100, 10)]
        out = inspect(ctx(chunks), Step("inspect", {"ref": "big.py"}))
        self.assertEqual(len(out.evidence), 3)
        self.assertIn("first 3", out.note)

    def test_an_unindexed_path_is_reported_as_not_indexed(self):
        out = inspect(ctx(), Step("inspect", {"ref": "nope.py"}))
        self.assertIn("not indexed", out.note)


class TraceTests(unittest.TestCase):
    def test_evidence_is_the_chunk_that_PROVES_the_edge(self):
        out = trace(ctx(), Step("trace", {"ref": "pr:400", "edge": "linked_issues"}))
        self.assertEqual(list(out.evidence), ["pr:400"])

    def test_targets_are_DISCOVERED_not_read(self):
        # The whole point of separating discovery from reading: a trace that
        # pulled in every target's text would spend the evidence budget on
        # material nobody has decided is relevant yet.
        out = trace(ctx(), Step("trace", {"ref": "pr:400", "edge": "linked_issues"}))
        self.assertEqual(out.discovered, ["issue:372"])
        self.assertNotIn("issue:372", out.texts)

    def test_an_unknown_relationship_is_refused_not_guessed(self):
        out = trace(ctx(), Step("trace", {"ref": "pr:400", "edge": "caused_by"}))
        self.assertEqual(out.evidence, {})
        self.assertIn("caused_by", out.note)

    def test_no_recorded_relationship_is_stated_as_such(self):
        out = trace(ctx(), Step("trace", {"ref": "pr:400", "edge": "dependents"}))
        self.assertIn("nothing recorded", out.note)

    def test_a_truncated_edge_list_is_disclosed(self):
        pr = Chunk(ref="pr:401", source="pr",
                   text=("PR #401: sweep\n\nFiles changed (40): a.py (+1/-1) · "
                         "… and 39 more files"))
        code = Chunk(ref="code:a.py#L1-L300", source="code", text="x")
        out = trace(ctx([pr, code]),
                    Step("trace", {"ref": "pr:401", "edge": "changed_files"}))
        self.assertIn("not everything", out.note)


class CompareDiffTests(unittest.TestCase):
    """Route 1: the pull request's own diff, which depends on no convention."""

    def test_the_real_diff_is_preferred_over_reconstructing_from_commits(self):
        diff = Chunk(ref="diff:400", source="diff",
                     text="DIFF of PR #400\n\n@@ -1,3 +1,4 @@\n+WINDOW = 300")
        c = ctx()
        c.diff_fetch = lambda n, t: diff if n == 400 else None
        out = compare(c, Step("compare", {"pr": "pr:400"}))
        self.assertEqual(list(out.evidence), ["diff:400"])
        self.assertIn("@@", out.texts["diff:400"])

    def test_the_callers_token_is_passed_to_the_diff_fetch(self):
        seen = []
        c = ctx()
        c.token = "gho_secret"
        c.diff_fetch = lambda n, t: seen.append(t)
        compare(c, Step("compare", {"pr": "pr:400"}))
        self.assertEqual(seen, ["gho_secret"])

    def test_a_failed_diff_fetch_falls_back_to_the_commits(self):
        def boom(n, t):
            raise RuntimeError("network")
        c = ctx()
        c.diff_fetch = boom
        out = compare(c, Step("compare", {"pr": "pr:400"}))
        self.assertEqual(list(out.evidence), ["commit:abc123"])

    def test_a_repo_with_no_diff_and_no_commit_link_reports_an_honest_gap(self):
        c = ctx([PR, CODE])
        c.diff_fetch = lambda n, t: None
        out = compare(c, Step("compare", {"pr": "pr:400"}))
        self.assertEqual(out.evidence, {})
        self.assertIn("cannot be read", out.note)


class CompareTests(unittest.TestCase):
    def test_reads_real_diffs_from_the_pull_requests_commits(self):
        diff = Chunk(ref="commit:abc123", source="commit",
                     text="COMMIT abc123: Improve chunking\n\nmodified llm/cli.py\n@@ -1 +1 @@")
        c = ctx(live_commit=lambda sha, t: diff if sha == "abc123" else None)
        out = compare(c, Step("compare", {"pr": "pr:400"}))
        self.assertIn("@@", out.texts["commit:abc123"])

    def test_without_live_access_the_indexed_message_is_used_not_nothing(self):
        out = compare(ctx(), Step("compare", {"pr": "pr:400"}))
        self.assertEqual(out.texts, {"commit:abc123": COMMIT.text})

    def test_a_repo_recording_no_commit_link_yields_an_honest_gap(self):
        out = compare(ctx([PR, CODE]), Step("compare", {"pr": "pr:400"}))
        self.assertEqual(out.evidence, {})
        self.assertIn("cannot be read", out.note)

    def test_compare_refuses_anything_that_is_not_a_pull_request(self):
        out = compare(ctx(), Step("compare", {"pr": "issue:372"}))
        self.assertIn("needs a pull request", out.note)

    def test_the_commit_bound_is_reported(self):
        prc = Chunk(ref="pr:500", source="pr", text="PR #500: many")
        commits = [Chunk(ref=f"commit:sha{i}", source="commit",
                         text=f"COMMIT sha{i}: work (#500)") for i in range(6)]
        out = compare(ctx([prc] + commits), Step("compare", {"pr": "pr:500"}))
        self.assertEqual(len(out.evidence), 4)
        self.assertIn("first 4", out.note)


class VerifyTests(unittest.TestCase):
    TEXTS = {"pr:400": PR.text, "issue:372": ISSUE.text}

    def test_a_grounded_claim_is_supported(self):
        self.assertTrue(verify("It closes issue 372.", ["pr:400"], self.TEXTS))

    def test_a_claim_citing_unretrieved_evidence_is_not(self):
        self.assertFalse(verify("Something else happened.", ["pr:999"], self.TEXTS))

    def test_a_claim_citing_nothing_is_not(self):
        self.assertFalse(verify("It was for scalability.", [], self.TEXTS))

    def test_it_is_the_real_gate_including_the_self_disclaim_guard(self):
        # Proves this is gate() and not a re-implementation of groundedness:
        # prose that admits it does not know is refused even though its citation
        # resolves perfectly.
        self.assertFalse(verify("The evidence does not state a reason for this.",
                                ["pr:400"], self.TEXTS))

    def test_the_rationale_guard_applies_only_when_a_question_is_given(self):
        code_texts = {"code:llm/cli.py#L1-L300": CODE.text}
        self.assertTrue(verify("The window is 300 lines.",
                               ["code:llm/cli.py#L1-L300"], code_texts))
        self.assertFalse(verify("The window is 300 lines.",
                                ["code:llm/cli.py#L1-L300"], code_texts,
                                question="why is the window 300 lines?"))


class RunnerTests(unittest.TestCase):
    def test_an_unsupported_primitive_is_refused_not_executed(self):
        out = run_step(ctx(), Step("delete_everything", {"ref": "pr:400"}))
        self.assertEqual(out.evidence, {})
        self.assertIn("unsupported", out.note)

    def test_a_round_returns_results_in_STEP_order(self):
        c = ctx()
        steps = [Step("inspect", {"ref": "issue:372"}),
                 Step("inspect", {"ref": "pr:400"}),
                 Step("inspect", {"ref": "code:llm/cli.py#L1-L300"})]
        results = run_round(c, steps)
        self.assertEqual([list(r.evidence)[0] for r in results],
                         ["issue:372", "pr:400", "code:llm/cli.py#L1-L300"])

    def test_one_failing_step_does_not_take_the_round_down(self):
        def boom(n, t):
            raise RuntimeError("network")
        c = ctx(live=boom)
        results = run_round(c, [Step("inspect", {"ref": "pr:900"}),
                                Step("inspect", {"ref": "pr:400"})])
        self.assertEqual(results[0].evidence, {})
        self.assertEqual(list(results[1].evidence), ["pr:400"])

    def test_an_empty_round_is_not_an_error(self):
        self.assertEqual(run_round(ctx(), []), [])


if __name__ == "__main__":
    unittest.main()
