"""The anonymous public demo path: one question, no login, default repo only.

Built for a Show HN. The measured problem it fixes: `POST /ask` returned
401 "sign in with GitHub to continue", so a stranger could not see the product
answer anything without handing over a GitHub account first.

The tests are weighted toward what must NOT open. Letting a caller in without
a credential is a hole by construction, so every boundary that still has to
hold is pinned here: only /ask, only the built-in repo, a GLOBAL budget rather
than a per-caller one (an anonymous caller has no identity to meter), no ledger
pollution, and no effect on authenticated callers.
"""
import json
import unittest
import unittest.mock
import urllib.error
import urllib.request

from .auth import StaticTokenVerifier
from .ratelimit import RateLimiter
from .test_server import _ServerFixture, _StubLibrary, _StubRegistry


class _RecordingRegistry(_StubRegistry):
    pass


class _StubLedger:
    def __init__(self):
        self.records = []

    def record(self, repo, **kwargs):
        self.records.append((repo, kwargs))

    def gaps(self, repo, include_resolved=False):
        return []


def _ask(base, question="Why the Responses API as a new class?", token=None):
    data = json.dumps({"question": question}).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(base + "/ask", data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read() or b"{}")
        e.close()
        return e.code, body


class PublicDemoOffTests(unittest.TestCase):
    """The guard that must stay green: default behaviour is unchanged."""

    def setUp(self):
        self.fx = _ServerFixture(_StubLibrary(), require_auth=True,
                                 verifier=StaticTokenVerifier({"good"}))
        self.addCleanup(self.fx.close)

    def test_anonymous_ask_is_still_refused_when_the_demo_is_off(self):
        code, body = _ask(self.fx.base)
        self.assertEqual(code, 401)
        self.assertIn("sign in", body["error"])


class PublicDemoOnTests(unittest.TestCase):

    def setUp(self):
        self.ledger = _StubLedger()
        self.registry = _RecordingRegistry(_StubLibrary())
        self.fx = _ServerFixture(
            self.registry, require_auth=True,
            verifier=StaticTokenVerifier({"good"}),
            public_demo=True, ledger=self.ledger,
            demo_limiter=RateLimiter(3, 3600))
        self.addCleanup(self.fx.close)

    def test_a_stranger_gets_a_real_answer_with_no_credential(self):
        code, body = _ask(self.fx.base)
        self.assertEqual(code, 200)
        self.assertEqual(body["verdict"], "answer")
        self.assertEqual(body["repo"], "simonw/llm")

    def test_the_demo_uses_the_shared_anonymous_library_not_a_forged_identity(self):
        _ask(self.fx.base)
        self.assertEqual(self.registry.seen[-1], None)

    def test_connect_stays_closed_to_anonymous_callers(self):
        data = json.dumps({"repo": "owner/name"}).encode()
        req = urllib.request.Request(self.fx.base + "/connect", data=data,
                                     headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 401)
        cm.exception.close()

    def test_the_budget_is_global_because_there_is_no_identity_to_meter(self):
        for _ in range(3):
            self.assertEqual(_ask(self.fx.base)[0], 200)
        code, body = _ask(self.fx.base)
        self.assertEqual(code, 429)
        self.assertIn("demo", body["error"].lower())

    def test_an_exhausted_demo_budget_does_not_block_a_signed_in_caller(self):
        for _ in range(4):
            _ask(self.fx.base)
        self.assertEqual(_ask(self.fx.base, token="good")[0], 200)

    def test_demo_questions_are_not_written_to_the_ledger(self):
        _ask(self.fx.base, question="Why the Responses API as a new class?")
        self.assertEqual(self.ledger.records, [])

    def test_a_signed_in_question_is_still_written_to_the_ledger(self):
        _ask(self.fx.base, question="Why the Responses API as a new class?", token="good")
        self.assertEqual(len(self.ledger.records), 1)

    def test_analytics_marks_the_surface_so_demo_traffic_is_separable(self):
        with unittest.mock.patch("demo.server.posthog_capture.capture") as capture:
            _ask(self.fx.base)
        surfaces = [c.args[2].get("surface") for c in capture.call_args_list
                    if c.args[0] == "question_asked"]
        self.assertEqual(surfaces, ["public_demo"])


if __name__ == "__main__":
    unittest.main()
