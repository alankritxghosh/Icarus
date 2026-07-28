# evals/test_exact_ref_lookup.py
"""RED failing eval for a live-found bug (benawad/vsinder): asking about a
real, in-corpus GitHub issue/PR by its exact number can retrieve NOTHING for
it at all -- not a false abstention with evidence in hand, a genuine zero-
score retrieval miss. An issue/PR's number lives only in its `ref`
("issue:260"), never automatically in its searchable text, and BM25/semantic
search has no special-casing for "look up ref N by its exact number" -- a
query sharing zero other keywords with that chunk's own text scores it
exactly 0 and it is dropped before the writer or gate ever run.

GatedPipeline.explain() already proves out a working "resolve by exact ref,
not .search()" pattern (self._by_ref, anchor-then-neighbors). This file
proves .answer() needs the same anchor path for a question that names an
issue/PR by number, and that adding it doesn't open any new honesty hole
(citations still only ground through the existing gate() path -- no new
logic there at all)."""

import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline, _premise_notes
from .synth import build_prompt


def _corpus_with_unreachable_issue():
    # Fillers share query vocabulary and would ordinarily fill up `retrieved`;
    # gold shares NONE of it -- empirically verified to score exactly 0 under
    # plain BM25 and be dropped from results entirely, regardless of k.
    fillers = [
        Chunk(f"issue:{i}", "issue", "how the retry queue works and does its job")
        for i in range(1, 6)
    ]
    gold = Chunk("issue:260", "issue", "cannot authenticate; login attempts fail intermittently for some accounts")
    chunks = fillers + [gold]
    return chunks, gold


def _pipe(chunks, provider):
    return GatedPipeline(LexicalRetriever(chunks), chunks, provider)


class ExactRefNeverRetrievedTests(unittest.TestCase):
    """Documents today's bug as a baseline: plain search-based retrieval finds
    nothing at all for the gold ref, on the exact live-reproduced phrasing."""

    def test_plain_search_scores_the_gold_issue_at_zero(self):
        chunks, gold = _corpus_with_unreachable_issue()
        r = LexicalRetriever(chunks).search("how does issue #260 work", k=20)
        self.assertNotIn(gold.ref, r)


class ExactRefAnchorLookupTests(unittest.TestCase):
    """The fix: GatedPipeline.answer() must resolve an explicit "issue/PR #N"
    mention via self._by_ref directly, guaranteeing it reaches `retrieved`
    (and the writer) whenever that exact ref exists in the corpus -- the
    same guarantee .explain() already gives a line-selected anchor."""

    def test_hash_prefixed_number_is_recognized_as_an_anchor(self):
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "Login sometimes fails intermittently.", "citations": [gold.ref]})
        r = _pipe(chunks, StaticProvider(raw)).answer("how does issue #260 work")
        self.assertIn(gold.ref, r.retrieved)
        self.assertEqual(r.verdict, "answer")
        self.assertIn(gold.ref, r.citations)

    def test_bare_number_without_hash_is_also_recognized(self):
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "Login sometimes fails intermittently.", "citations": [gold.ref]})
        r = _pipe(chunks, StaticProvider(raw)).answer("what is issue 260 about")
        self.assertIn(gold.ref, r.retrieved)
        self.assertEqual(r.verdict, "answer")

    def test_pr_number_resolves_to_a_pr_ref_not_an_issue_ref(self):
        chunks = [Chunk("pr:42", "pr", "a fix with no shared vocabulary at all here")]
        r = _pipe(chunks, StaticProvider(json.dumps({
            "verdict": "answer", "answer": "It's PR 42.", "citations": ["pr:42"],
        }))).answer("what does pr #42 do")
        self.assertIn("pr:42", r.retrieved)
        self.assertEqual(r.verdict, "answer")

    def test_no_new_bluff_path_a_fabricated_anchor_citation_still_forced_unknown(self):
        # The anchor path only ever ADDS a genuinely-existing ref to
        # `retrieved` -- it must not let a citation to a ref that doesn't
        # exist in the corpus at all slip through.
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["issue:99999"]})
        r = _pipe(chunks, StaticProvider(raw)).answer("how does issue #260 work")
        self.assertEqual(r.verdict, "unknown")

    def test_mentioning_a_number_with_no_matching_ref_is_a_harmless_no_op(self):
        # A number that doesn't correspond to any real ref in this corpus
        # (e.g. "#9999") must not error or inject a phantom anchor -- the
        # question just falls through to ordinary search, same as today.
        chunks, gold = _corpus_with_unreachable_issue()
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "how does issue #9999 work"
        )
        self.assertNotIn("issue:9999", r.retrieved)

    def test_known_accepted_edge_case_a_coincidental_number_can_still_anchor(self):
        # Documented, accepted low-probability edge case (not a silent gap):
        # a colloquial numeric mention ("the #1 rule") will anchor-inject a
        # real issue:1 if one happens to exist in this corpus, even though
        # the question isn't really about that issue. Harmless (it can only
        # ever ADD a genuinely-existing, genuinely-grounded citation
        # candidate -- never fabricate one), but worth having on record.
        chunks, gold = _corpus_with_unreachable_issue()  # includes a real issue:1
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "the #1 rule here is to always retry"
        )
        self.assertIn("issue:1", r.retrieved)


class LiveRefFetchTests(unittest.TestCase):
    """When a question names a PR/issue #N the corpus never indexed (it caps at
    the most-recent PR_LIMIT/ISSUE_LIMIT), the pipeline fetches that exact ref +
    its comments LIVE and answers -- instead of a useless 'no one wrote this
    down' on, e.g., react/react's ancient PR #400. Fail-safe: a fetch miss, or
    no live_fetch configured (the eval board), abstains exactly as before, and
    an already-indexed ref is served from cache with no network call."""

    def _chunks(self):
        return [Chunk("code:a.py#L1-L5", "code", "def f():\n    return 1")]

    def test_unindexed_pr_is_live_fetched_and_answered(self):
        chunks = self._chunks()  # no pr:400 in corpus
        got = Chunk("pr:400", "pr", "PR #400: Add streaming ingest.\n\nComment: chose streaming to bound memory.")
        calls = []
        raw = json.dumps({"verdict": "answer",
                          "answer": "PR #400 added streaming ingest to bound memory.",
                          "citations": ["pr:400"]})
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, StaticProvider(raw),
                             live_fetch=lambda num: (calls.append(num) or (got if num == 400 else None)))
        r = pipe.answer("talk to me about PR 400")
        self.assertEqual(r.verdict, "answer")
        self.assertIn("pr:400", r.citations)
        self.assertEqual(calls, [400])          # the miss triggered exactly one live fetch

    def test_indexed_ref_uses_cache_without_live_fetch(self):
        chunks = [Chunk("pr:400", "pr", "PR #400: Add streaming ingest.")]
        called = []
        raw = json.dumps({"verdict": "answer", "answer": "It adds streaming.", "citations": ["pr:400"]})
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, StaticProvider(raw),
                             live_fetch=lambda num: (called.append(num) or None))
        r = pipe.answer("talk about PR 400")
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(called, [])            # already indexed -> never fetched

    def test_live_fetch_miss_still_abstains(self):
        chunks = self._chunks()
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:999"]})
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, StaticProvider(raw),
                             live_fetch=lambda num: None)   # ref genuinely not found
        self.assertEqual(pipe.answer("talk about PR 999").verdict, "unknown")

    def test_no_live_fetch_configured_is_backcompat(self):
        chunks = self._chunks()
        raw = json.dumps({"verdict": "answer", "answer": "y", "citations": ["pr:400"]})
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, StaticProvider(raw))  # board default
        self.assertEqual(pipe.answer("talk about PR 400").verdict, "unknown")


class FetchRefDetailTests(unittest.TestCase):
    """`fetch_ref_detail` builds one Chunk (title + body + comments) for a single
    PR/issue, tries PR then issue, and fails safe to None."""

    def test_builds_pr_chunk_with_comments(self):
        from unittest import mock
        from evals import ingest
        def fake(args, token=None):
            self.assertEqual(args[:2], ["pr", "view"])
            return {"number": 400, "title": "Add streaming", "body": "Bound memory.",
                    "comments": [{"body": "why: it OOM'd"}, {"body": ""}]}
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            ch = ingest.fetch_ref_detail("o/r", 400)
        self.assertEqual((ch.ref, ch.source), ("pr:400", "pr"))
        self.assertIn("Add streaming", ch.text)
        self.assertIn("why: it OOM'd", ch.text)     # comment discussion is included

    def test_falls_back_to_issue_when_not_a_pr(self):
        import subprocess as sp
        from unittest import mock
        from evals import ingest
        def fake(args, token=None):
            if args[0] == "pr":
                raise sp.CalledProcessError(1, "gh")   # N is an issue, not a PR
            return {"number": 400, "title": "A bug", "body": "desc", "comments": []}
        with mock.patch.object(ingest, "_gh_json", side_effect=fake):
            ch = ingest.fetch_ref_detail("o/r", 400)
        self.assertEqual((ch.ref, ch.source), ("issue:400", "issue"))

    def test_returns_none_on_total_failure(self):
        import subprocess as sp
        from unittest import mock
        from evals import ingest
        with mock.patch.object(ingest, "_gh_json", side_effect=sp.CalledProcessError(1, "gh")):
            self.assertIsNone(ingest.fetch_ref_detail("o/r", 400))


if __name__ == "__main__":
    unittest.main()


class NamedSourceTypeWinsTests(unittest.TestCase):
    """When a question names the KIND of reference, honour it.

    GitHub shares one number sequence between issues and pull requests, so
    `issue:1481` and `pr:1481` can both exist. The anchor resolved them with
    `next(... for s in ("issue", "pr"))`, so ISSUE always won the tie no matter
    what the question said -- asking what "PR 1481" changed anchored to the
    issue. Found 2026-07-28 while root-causing a live report.
    """

    def _chunks(self):
        return [
            Chunk(ref="issue:1481", source="issue", text="ISSUE #1481: a bug report about tool ids"),
            Chunk(ref="pr:1481", source="pr", text="PR #1481: synthesize tool_call_id for providers"),
        ]

    def _anchor_for(self, question):
        chunks = self._chunks()
        p = GatedPipeline(LexicalRetriever(chunks), chunks,
                          StaticProvider(['{"verdict": "unknown"}'] * 4))
        return p.answer(question).retrieved

    def test_pr_phrasing_anchors_the_pr_not_the_issue(self):
        self.assertEqual(self._anchor_for("What did PR 1481 change?")[0], "pr:1481")

    def test_issue_phrasing_anchors_the_issue(self):
        self.assertEqual(self._anchor_for("What is issue 1481 about?")[0], "issue:1481")

    def test_pull_request_spelling_also_anchors_the_pr(self):
        self.assertEqual(self._anchor_for("What did pull request 1481 do?")[0], "pr:1481")

    def test_bare_hash_keeps_the_existing_behaviour(self):
        # "#1481" names no kind, so the previous precedence is preserved rather
        # than silently changed.
        self.assertEqual(self._anchor_for("Tell me about #1481")[0], "issue:1481")


class PremiseNoteTests(unittest.TestCase):
    """A question can be wrong about its own subject, and the pipeline can know.

    "What did PR 6952 change?" when #6952 is an ISSUE used to answer "no one
    wrote this down" -- which reads as "nobody documented it" when the truth is
    "you asked about the wrong kind of thing, and the evidence says so". Found
    live 2026-07-28; it sent the reader hunting a retrieval bug that did not
    exist.

    Derived in code from the ref that actually resolved, never from the model, so
    correcting the premise stays a GROUNDED answer. A prompt RULE was tried first
    and rejected: wording strong enough to work also biased the writer between
    issue:N and pr:N elsewhere and dropped board citation correctness to 83.3%.
    """

    def test_note_when_a_pr_is_really_an_issue(self):
        notes = _premise_notes("What did PR 6952 change?", ["issue:6952"])
        self.assertEqual(len(notes), 1)
        self.assertIn("#6952 is an issue", notes[0])
        self.assertIn("not a pull request", notes[0])

    def test_note_when_an_issue_is_really_a_pr(self):
        notes = _premise_notes("What is issue 1481 about?", ["pr:1481"])
        self.assertIn("#1481 is a pull request", notes[0])

    def test_no_note_when_the_question_is_right(self):
        self.assertEqual(_premise_notes("What did PR 1481 change?", ["pr:1481"]), [])
        self.assertEqual(_premise_notes("What is issue 42 about?", ["issue:42"]), [])

    def test_no_note_for_a_bare_number_naming_no_kind(self):
        # "#123" claims nothing about what it is, so there is nothing to correct.
        self.assertEqual(_premise_notes("Tell me about #123", ["issue:123"]), [])

    def test_no_note_for_a_different_number(self):
        self.assertEqual(_premise_notes("What did PR 10 change?", ["issue:99"]), [])

    def test_prompt_omits_the_facts_block_when_there_is_nothing_to_correct(self):
        # The board's questions generate no notes, so their prompts must be
        # byte-identical to before -- that is why this fix costs nothing there.
        c = [Chunk(ref="pr:1", source="pr", text="body")]
        self.assertEqual(build_prompt("plain question", c),
                         build_prompt("plain question", c, notes=[]))
        self.assertNotIn("ESTABLISHED FACTS", build_prompt("plain question", c))

    def test_prompt_states_a_note_when_there_is_one(self):
        c = [Chunk(ref="issue:6952", source="issue", text="body")]
        p = build_prompt("What did PR 6952 change?", c,
                         notes=["#6952 is an issue (issue:6952), not a pull request."])
        self.assertIn("ESTABLISHED FACTS", p)
        self.assertIn("#6952 is an issue", p)


class AnchoredIsReportedTests(unittest.TestCase):
    """`Result.anchored` exists so a reader can see that the thing they NAMED
    was looked up, rather than reading a flat 20-ref list and concluding the
    question was ignored (live complaint, 2026-07-28). Display only -- it is
    carried alongside the honesty decision, never into it."""

    def test_named_ref_is_reported_as_anchored(self):
        chunks, gold = _corpus_with_unreachable_issue()
        raw = json.dumps({"verdict": "answer", "answer": "Login fails intermittently.",
                          "citations": [gold.ref]})
        r = _pipe(chunks, StaticProvider(raw)).answer("how does issue #260 work")
        self.assertEqual(r.anchored, [gold.ref])
        self.assertEqual(r.retrieved[0], gold.ref, "anchored must stay a prefix of retrieved")

    def test_anchored_survives_an_abstention(self):
        # THE case from the live report: the anchor resolved correctly and the
        # writer still had nothing to say. Losing it here is what made a correct
        # refusal look like a blind one.
        chunks, gold = _corpus_with_unreachable_issue()
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "what did issue #260 change")
        self.assertEqual(r.verdict, "unknown")
        self.assertEqual(r.anchored, [gold.ref])

    def test_a_question_naming_nothing_anchors_nothing(self):
        chunks, _ = _corpus_with_unreachable_issue()
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "how does the retry queue work")
        self.assertEqual(r.anchored, [])

    def test_an_unresolvable_number_anchors_nothing(self):
        chunks, _ = _corpus_with_unreachable_issue()
        r = _pipe(chunks, StaticProvider(json.dumps({"verdict": "unknown"}))).answer(
            "how does issue #9999 work")
        self.assertEqual(r.anchored, [])

    def test_explain_reports_the_selected_lines_as_the_anchor(self):
        chunks = [Chunk("code:llm/x.py#L1-L20", "code", "def go():\n    return 1")]
        r = GatedPipeline(LexicalRetriever(chunks), chunks,
                          StaticProvider(json.dumps({"verdict": "unknown"}))
                          ).explain("llm/x.py", 3, 5)
        self.assertEqual(r.anchored, ["code:llm/x.py#L1-L20"])
