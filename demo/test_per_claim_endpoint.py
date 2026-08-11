"""`per_claim` at the HTTP and MCP boundary.

Weighted toward what must NOT change: a caller that does not ask for the
self-report must get a byte-identical payload, and asking for it must never
alter a verdict. The MCP adapter is the one caller that always asks, because a
coding agent acts on the answer.
"""
import json
import unittest
from unittest import mock

from demo.payload import build_payload
from evals.pipeline import Result


def _result(**kw):
    base = dict(verdict="answer", answer="Paths were made absolute.",
                citations=["pr:100"], retrieved=["pr:100", "issue:200"],
                evidence={"pr:100": "PR #100: because the cache moved."})
    base.update(kw)
    return Result(**base)


class PayloadTests(unittest.TestCase):

    def test_absent_when_no_claims(self):
        """Every existing client sees exactly what it saw before."""
        p = build_payload(_result(), "o/r", "abc123")
        self.assertNotIn("claims", p)

    def test_present_and_shaped_when_claims_exist(self):
        r = _result(claims=[
            {"text": "Paths were made absolute.", "citations": ["pr:100"],
             "label": "quoted"},
            {"text": "Relative paths break across depths.",
             "citations": ["pr:100", "issue:200"], "label": "composed"},
        ])
        p = build_payload(r, "o/r", "abc123")
        self.assertEqual([c["label"] for c in p["claims"]], ["quoted", "composed"])
        self.assertEqual(p["claims"][0]["citations"][0]["ref"], "pr:100")
        # Citations carry a URL, like every other ref a client is shown.
        self.assertIn("github.com", p["claims"][0]["citations"][0]["url"])

    def test_claims_do_not_disturb_the_rest_of_the_payload(self):
        without = build_payload(_result(), "o/r", "abc123")
        with_claims = build_payload(
            _result(claims=[{"text": "x", "citations": ["pr:100"],
                             "label": "quoted"}]), "o/r", "abc123")
        self.assertEqual({k: v for k, v in with_claims.items() if k != "claims"},
                         without)


    def test_rests_on_rejected_surfaces_and_is_absent_otherwise(self):
        """The flag a client acts on must cross the boundary -- and must not
        appear on an ordinary claim, or it stops meaning anything."""
        r = _result(claims=[
            {"text": "Absolute paths are preserved.", "citations": ["pr:100"],
             "label": "quoted", "rests_on_rejected": True},
            {"text": "Paths were made absolute.", "citations": ["pr:100"],
             "label": "quoted"},
        ])
        p = build_payload(r, "o/r", "abc123")
        self.assertTrue(p["claims"][0]["rests_on_rejected"])
        self.assertNotIn("rests_on_rejected", p["claims"][1])

    def test_tool_description_disclaims_closed_means_refused(self):
        """A closed pull request mostly means "already done another way".

        Measured 2026-08-11 across nine surfaced PRs on simonw/llm: eight were
        closed because the same change arrived another way, one was an approach
        genuinely not adopted. The raw signal reads as "this was rejected" and
        that inference is wrong most of the time, so the description has to say
        so -- an agent acts on this.
        """
        from demo.mcp_server import handle_message
        tools = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )["result"]["tools"]
        desc = next(t["description"] for t in tools
                    if t["name"] == "get_change_context")
        self.assertIn("not evidence that the approach was rejected", desc)
        self.assertIn("do not send a duplicate", desc)
        self.assertIn("closure thread", desc)

    def test_mcp_tool_tells_the_agent_what_the_flag_means(self):
        """An unexplained flag is inert -- the same reason `composed` carries
        an instruction rather than just a name."""
        from demo.mcp_server import handle_message
        tools = handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        )["result"]["tools"]
        desc = next(t["description"] for t in tools
                    if t["name"] == "get_change_context")
        self.assertIn("rests_on_rejected", desc)
        # The flag's meaning is "nothing cited shows this LANDED", not "every
        # citation is a closed PR" -- the rule was widened after a measured
        # false negative, and a description promising the old test would send an
        # agent looking for the wrong thing.
        self.assertIn("ever LANDED", desc)
        # The exclusion is as load-bearing as the rule: an agent must know that
        # an UNflagged claim citing a closed PR alongside a merged one is not
        # an oversight.
        self.assertIn("NOT flagged", desc)


class RejectedAttemptsPayloadTests(unittest.TestCase):
    """The refused-attempt signal at the payload boundary."""

    def test_absent_when_none(self):
        self.assertNotIn("rejected_attempts", build_payload(_result(), "o/r", "abc"))

    def test_present_with_url_when_any(self):
        r = _result(rejected_attempts=[{"ref": "pr:20754", "title": "Clean up temp"}])
        p = build_payload(r, "astral-sh/uv", "abc123")
        self.assertEqual(p["rejected_attempts"][0]["ref"], "pr:20754")
        self.assertEqual(p["rejected_attempts"][0]["title"], "Clean up temp")
        self.assertIn("astral-sh/uv/pull/20754", p["rejected_attempts"][0]["url"])

    def test_rest_of_payload_untouched(self):
        without = build_payload(_result(), "o/r", "abc")
        with_it = build_payload(
            _result(rejected_attempts=[{"ref": "pr:1", "title": "t"}]), "o/r", "abc")
        self.assertEqual({k: v for k, v in with_it.items() if k != "rejected_attempts"},
                         without)

    def test_surfaced_on_an_abstention_too(self):
        """The case that matters most: the answer did not rest on it, which is
        exactly when an agent is about to redo the refused work."""
        r = _result(verdict="unknown", answer="", citations=[],
                    rejected_attempts=[{"ref": "pr:1", "title": "t"}])
        self.assertIn("rejected_attempts", build_payload(r, "o/r", "abc"))


class McpRequestTests(unittest.TestCase):
    """The agent interface asks for the self-report on every call."""

    def _capture(self, fn, arguments):
        sent = {}

        def fake_request(path, body):
            sent["path"], sent["body"] = path, body
            return {"repo": "o/r", "verdict": "unknown", "answer": "",
                    "citations": [], "searched": [], "anchored": [],
                    "indexing": False, "reason": None}

        from demo import mcp_server
        with mock.patch.object(mcp_server, "_request", fake_request), \
             mock.patch.object(mcp_server, "_checked_repo", lambda r: "o/r"):
            fn(arguments)
        return sent

    def test_change_context_requests_per_claim(self):
        from demo.mcp_server import _get_change_context
        sent = self._capture(_get_change_context,
                             {"repo": "o/r", "question": "why?"})
        self.assertEqual(sent["path"], "/ask")
        self.assertIs(sent["body"]["per_claim"], True)

    def test_explain_requests_per_claim(self):
        from demo.mcp_server import _explain_code_context
        sent = self._capture(_explain_code_context,
                             {"repo": "o/r", "path": "a.py", "start": 1, "end": 5})
        self.assertEqual(sent["path"], "/explain")
        self.assertIs(sent["body"]["per_claim"], True)

    def test_tool_description_tells_the_agent_what_composed_means(self):
        """An unexplained label is inert -- the agent has to know that
        `composed` is the one to verify."""
        from demo.mcp_server import _TOOLS
        descs = " ".join(t["description"] for t in _TOOLS)
        self.assertIn("composed", descs)
        self.assertIn("verify", descs)

    def test_tool_description_explains_rejected_attempts(self):
        from demo.mcp_server import _TOOLS
        descs = " ".join(t["description"] for t in _TOOLS)
        self.assertIn("rejected_attempts", descs)
        self.assertIn("CLOSED WITHOUT being merged", descs)
        # It must NOT promise a reason -- that is the composed-rationale trap.
        self.assertIn("never why", descs)
        # ...nor imply relevance, which is retrieval's behaviour and degrades
        # measurably on a lexical-only index (docs/experiments/2026-08-10-
        # rejected-attempt-false-positive-rate.md).
        self.assertIn("Judge each entry", descs)


if __name__ == "__main__":
    unittest.main()
