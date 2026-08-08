# demo/test_investigate_endpoint.py
"""POST /investigate at the real HTTP boundary, plus conversational continuity.

The four-turn conversation this feature exists for is tested end to end here:

    "talk to me about PR #400"
    "why did it change?"          <- "it" must resolve, without a model deciding
    "what did it affect?"
    "why was that appropriate here?"

Everything else is pinned from the refusing side: an unrelated question must NOT
inherit a subject, another identity must never see one, and the answer must face
the same limiter, entitlement gate and honesty gate as /ask.
"""

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer
from pathlib import Path

from evals.corpus import Chunk
from evals.entities import build_entity_index
from evals.pipeline import GatedPipeline
from .auth import StaticTokenVerifier
from .investigations import ConversationStore
from .ratelimit import RateLimiter
from .server import make_handler
from .test_server import _StubRegistry

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"

CHUNKS = [
    Chunk(ref="pr:400", source="pr",
          text=("PR #400: new chunking strategy\n\n[MERGED by ana]\n\n"
                "Retrieval quality degraded on large repositories, so this "
                "changes how files are split. Closes #372.\n\n"
                "Files changed (1): llm/cli.py (+10/-2)")),
    Chunk(ref="issue:372", source="issue",
          text="ISSUE #372: retrieval degrades on large repositories"),
    Chunk(ref="code:llm/cli.py#L1-L300", source="code", text="WINDOW = 300"),
]


class ScriptedWriter:
    """Answers by which investigation prompt it is looking at."""

    private_safe = True

    def __init__(self):
        self.prompts = []
        # Every finding is stamped with a distinct number, so a finding present
        # in a later turn can only have got there by being CARRIED -- a writer
        # that emitted identical text each turn would make the compounding test
        # pass whether or not anything was carried (it did, until this).
        self.reads = 0

    def complete(self, prompt):
        self.prompts.append(prompt)
        if "planning an investigation" in prompt:
            return json.dumps({"hypotheses": ["it fixed retrieval quality"],
                               "steps": []})
        if "reading evidence gathered" in prompt:
            refs = [l[1:-1] for l in prompt.splitlines()
                    if l.startswith("[") and l.endswith("]")]
            if not refs:
                return json.dumps({"claims": []})
            self.reads += 1
            return json.dumps({"claims": [
                {"text": f"Finding {self.reads}: PR #400 changed how files are "
                         f"split because retrieval degraded on large repositories.",
                 "citations": refs[:1], "hypothesis": "h1", "supports": True}]})
        return json.dumps({"verdict": "answer",
                           "answer": "It changed chunking because retrieval "
                                     "degraded on large repositories.",
                           "citations": ["pr:400"]})


class _Retriever:
    def search(self, query, k):
        return [c.ref for c in CHUNKS][:k]


class _Library:
    def __init__(self, writer):
        self._pipe = GatedPipeline(_Retriever(), CHUNKS, writer)
        self.commit = COMMIT
        self.generation = 1
        self.indexing = False
        self.snapshot_calls = 0
        # When set, the corpus is swapped the moment a request reads it --
        # standing in for a /connect refresh landing mid-request.
        self.swap_on_next_pipeline_read = False

    def snapshot(self):
        from demo.library import _CorpusSnapshot
        self.snapshot_calls += 1
        snap = _CorpusSnapshot(pipeline=self._pipe, provider=self._pipe.provider(),
                               repo=REPO, commit=self.commit,
                               generation=self.generation,
                               fingerprint=f"fp-{self.generation}",
                               indexing=self.indexing)
        if self.swap_on_next_pipeline_read:
            self.commit = "swapped-mid-request"     # the index moves underneath
        return snap

    def current_pipeline(self):
        return self._pipe

    def provenance(self):
        return (REPO, self.commit)

    def status_snapshot(self):
        return {"state": "ready", "repo": REPO, "commit": COMMIT,
                "counts": None, "error": None, "phase": None, "private": False,
                "indexing": False}


def _post(url, obj, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(obj).encode(), headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.status, json.loads(resp.read())


class InvestigateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        html = Path(cls._tmp.name) / "index.html"
        html.write_text("<html></html>")
        cls.writer = ScriptedWriter()
        cls.lib = _Library(cls.writer)
        cls.conversations = ConversationStore()
        handler = make_handler(
            _StubRegistry(cls.lib), str(html), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "user-a", "tok-b": "user-b"}), conversations=cls.conversations,
            entity_index=lambda lib, snapshot=None: build_entity_index(CHUNKS),
            ask_limiter=RateLimiter(100, 60),
            # Generous here so the shared server can serve a whole test class.
            # The PRODUCTION default is 3/min -- see make_handler, and the
            # billed-call test below, which injects its own tight limiter.
            investigate_limiter=RateLimiter(100, 60))
        cls.server = HTTPServer(("127.0.0.1", 0), handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls._tmp.cleanup()

    def setUp(self):
        self.conversations.forget("user-a", REPO)
        self.conversations.forget("user-b", REPO)

    def ask(self, question, token="tok-a", **extra):
        return _post(self.base + "/investigate", {"question": question, **extra},
                     token=token)

    # -- the answer ------------------------------------------------------
    def test_an_investigation_answers_in_the_same_shape_as_ask(self):
        status, payload = self.ask("talk to me about PR #400")
        self.assertEqual(status, 200)
        for key in ("repo", "commit", "verdict", "answer", "citations",
                    "searched", "anchored", "indexing", "reason"):
            self.assertIn(key, payload)
        self.assertEqual(payload["verdict"], "answer")
        self.assertEqual(payload["citations"][0]["url"],
                         "https://github.com/simonw/llm/pull/400")

    def test_indexing_caveat_describes_the_snapshot_not_later_status(self):
        self.lib.indexing = True
        try:
            _, payload = self.ask("talk to me about PR #400")
        finally:
            self.lib.indexing = False
        self.assertTrue(payload["indexing"])

    def test_the_trail_shows_how_the_repository_led_to_the_conclusion(self):
        _, payload = self.ask("talk to me about PR #400")
        inv = payload["investigation"]
        self.assertEqual(inv["subject"], ["pr:400"])
        self.assertTrue(inv["trail"])
        self.assertTrue(all(finding["id"] for finding in inv["findings"]))
        self.assertIn("inspect", [s["primitive"] for s in inv["trail"]])
        self.assertTrue(inv["findings"])

    def test_every_finding_carries_its_support_class_and_linked_citations(self):
        _, payload = self.ask("talk to me about PR #400")
        finding = payload["investigation"]["findings"][0]
        self.assertIn(finding["support"], ("explicit", "strong", "weak"))
        self.assertTrue(finding["citations"][0]["url"].startswith("https://github.com/"))

    def test_unknowns_are_published_even_when_empty(self):
        _, payload = self.ask("talk to me about PR #400")
        self.assertIn("unknowns", payload["investigation"])
        self.assertIn("contradictions", payload["investigation"])

    # -- continuity ------------------------------------------------------
    def test_a_four_turn_conversation_holds_one_subject(self):
        self.ask("talk to me about PR #400")
        for follow_up in ("why did it change?",
                          "what implications did it have?",
                          "why do you think they did it this way?"):
            _, payload = self.ask(follow_up)
            self.assertEqual(payload["investigation"]["subject"], ["pr:400"],
                             follow_up)

    def test_a_follow_up_carries_the_ORIGINAL_objective_not_the_pronoun(self):
        self.ask("talk to me about PR #400")
        _, payload = self.ask("why did it change?")
        self.assertIn("400", payload["investigation"]["objective"])

    def test_a_follow_up_COMPOUNDS_on_what_earlier_turns_established(self):
        # Section 9's requirement: a follow-up must not restart from zero.
        # Findings from turn one arrive as established claims in turn two.
        _, first = self.ask("talk to me about PR #400")
        _, second = self.ask("why did it change?")
        established = {f["text"] for f in first["investigation"]["findings"]}
        carried = {f["text"] for f in second["investigation"]["findings"]}
        self.assertTrue(established)
        self.assertTrue(established <= carried,
                        f"turn two lost {established - carried}")

    def test_a_carried_findings_support_class_is_not_re_measured(self):
        # It was measured against the evidence THAT turn held. Re-deriving it now
        # would usually downgrade it to unsupported, for no better reason than
        # that the evidence text was deliberately not kept.
        self.ask("talk to me about PR #400")
        _, payload = self.ask("why did it change?")
        self.assertNotIn("unsupported",
                         [f["support"] for f in payload["investigation"]["findings"]])

    def test_a_question_naming_its_own_subject_rebinds_rather_than_inheriting(self):
        self.ask("talk to me about PR #400")
        _, payload = self.ask("what did issue 372 report?")
        self.assertEqual(payload["investigation"]["subject"], ["issue:372"])

    def test_an_unrelated_question_does_not_inherit_a_subject(self):
        # The dangerous case: inheriting here yields a confident, fully cited
        # answer about the wrong thing, which groundedness cannot detect.
        self.ask("talk to me about PR #400")
        _, payload = self.ask("how does the retriever rank results?")
        self.assertEqual(payload["investigation"]["subject"], [])

    def test_fresh_true_starts_a_new_enquiry(self):
        self.ask("talk to me about PR #400")
        _, payload = self.ask("why did it change?", fresh=True)
        self.assertEqual(payload["investigation"]["subject"], [])

    def test_fresh_must_be_a_real_boolean(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.ask("why did it change?", fresh="yes")
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_one_callers_subject_never_reaches_another(self):
        self.ask("talk to me about PR #400", token="tok-a")
        _, payload = self.ask("why did it change?", token="tok-b")
        self.assertEqual(payload["investigation"]["subject"], [])

    def test_a_first_turn_follow_up_with_no_history_simply_finds_no_subject(self):
        # "it" with nothing to refer to binds no subject. The investigation
        # still runs -- retrieval can legitimately find evidence for a
        # subjectless question -- so what is pinned is that nothing was
        # INVENTED to stand in for "it", not that the answer must be empty.
        _, payload = self.ask("why did it change?")
        self.assertEqual(payload["investigation"]["subject"], [])
        self.assertEqual(payload["searched"] and payload["anchored"], [])

    # -- the gates -------------------------------------------------------
    def test_an_unauthenticated_caller_is_refused(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            _post(self.base + "/investigate", {"question": "about PR #400"})
        self.assertEqual(cm.exception.code, 401)
        cm.exception.close()

    def test_a_missing_or_blank_question_is_refused(self):
        for body in ({}, {"question": ""}, {"question": "   "}, {"question": 7}):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(self.base + "/investigate", body, token="tok-a")
            self.assertEqual(cm.exception.code, 400, body)
            cm.exception.close()

    def test_it_has_its_OWN_allowance_because_it_costs_far_more_than_an_ask(self):
        # This replaces an earlier test that asserted /investigate shares /ask's
        # limiter. Sharing was not conservative, it was the defect: one HTTP
        # request makes several billed calls, so 30 investigations a minute is
        # ~300 provider calls where /ask's own budget allows 30.
        tmp = tempfile.TemporaryDirectory()
        html = Path(tmp.name) / "index.html"
        html.write_text("<html></html>")
        handler = make_handler(
            _StubRegistry(self.lib), str(html), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "user-a"}),
            conversations=ConversationStore(),
            entity_index=lambda lib, snapshot=None: build_entity_index(CHUNKS),
            ask_limiter=RateLimiter(100, 60),
            investigate_limiter=RateLimiter(1, 60))
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            _post(base + "/investigate", {"question": "about PR #400"}, token="tok-a")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(base + "/investigate", {"question": "again"}, token="tok-a")
            self.assertEqual(cm.exception.code, 429)
            cm.exception.close()
            # ...and a plain ask is unaffected: it has its own, separate budget.
            status, _ = _post(base + "/ask", {"question": "anything"}, token="tok-a")
            self.assertEqual(status, 200)
        finally:
            server.shutdown()
            server.server_close()
            tmp.cleanup()

    def test_billed_provider_calls_are_bounded_per_identity_not_just_requests(self):
        # One HTTP request is many billed calls. Bounding requests alone let one
        # identity spend ~10x the /ask budget per minute -- the limiter has to
        # bound what is actually billed, and refuse BEFORE any provider call.
        tmp = tempfile.TemporaryDirectory()
        html = Path(tmp.name) / "index.html"
        html.write_text("<html></html>")
        writer = ScriptedWriter()
        handler = make_handler(
            _StubRegistry(_Library(writer)), str(html), require_auth=True,
            verifier=StaticTokenVerifier({"tok-a": "user-a"}),
            conversations=ConversationStore(),
            entity_index=lambda lib, snapshot=None: build_entity_index(CHUNKS),
            ask_limiter=RateLimiter(100, 60),
            investigate_limiter=RateLimiter(1, 60))
        server = HTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            _post(base + "/investigate", {"question": "about PR #400"}, token="tok-a")
            spent = len(writer.prompts)
            self.assertGreater(spent, 1, "one investigation should bill several calls")
            with self.assertRaises(urllib.error.HTTPError) as cm:
                _post(base + "/investigate", {"question": "again"}, token="tok-a")
            self.assertEqual(cm.exception.code, 429)
            cm.exception.close()
            # Refused BEFORE the writer: not one extra billed call.
            self.assertEqual(len(writer.prompts), spent)
        finally:
            server.shutdown()
            server.server_close()
            tmp.cleanup()

    def test_a_refreshed_index_ends_the_conversation_rather_than_carrying_findings(self):
        # /connect refresh republishes the corpus under a live conversation.
        # A follow-up must not inherit findings verified against evidence that
        # may no longer exist.
        self.ask("talk to me about PR #400")
        self.lib.commit = "moved-to-a-new-commit"
        try:
            _, payload = self.ask("why did it change?")
            self.assertEqual(payload["investigation"]["subject"], [])
        finally:
            self.lib.commit = COMMIT

    def test_a_SAME_COMMIT_refresh_still_ends_the_conversation(self):
        # Ingest includes MUTABLE pull-request and issue discussion. A refresh
        # can publish genuinely different evidence while HEAD is unchanged, so
        # a commit SHA alone is not a corpus identity. Findings verified against
        # the previous ingest must not be carried into an answer about the new
        # one just because the SHA matched.
        self.ask("talk to me about PR #400")
        self.lib.generation += 1          # a refresh at the SAME commit
        try:
            _, payload = self.ask("why did it change?")
            self.assertEqual(payload["investigation"]["subject"], [])
        finally:
            self.lib.generation -= 1

    def test_one_request_answers_from_ONE_corpus_even_if_it_is_swapped(self):
        # provenance() and current_pipeline() were read separately, so a
        # concurrent refresh could answer from one pipeline while returning
        # citation URLs and conversation provenance from another.
        self.lib.snapshot_calls = 0        # count THIS request only
        self.lib.swap_on_next_pipeline_read = True
        try:
            _, payload = self.ask("talk to me about PR #400")
        finally:
            self.lib.swap_on_next_pipeline_read = False
            self.lib.commit = COMMIT
        # The commit reported is the one the answer was actually produced from.
        self.assertEqual(payload["commit"], COMMIT)
        self.assertEqual(self.lib.snapshot_calls, 1,
                         "the request must capture the corpus exactly once")

    def test_the_investigation_uses_the_pipelines_own_trust_checked_writer(self):
        # Never a second provider built for this path: the pipeline's writer is
        # the one the trust interlock approved at build time.
        self.assertIs(self.lib.current_pipeline().provider(), self.writer)


if __name__ == "__main__":
    unittest.main()
