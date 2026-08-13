# demo/test_posthog_capture.py
"""capture()'s contract: no-ops with no token (never opens a connection),
posts the right shape with one, and a failing opener never raises into the
caller -- analytics must not be able to break a real request."""

import io
import json
import unittest

from .posthog_capture import capture


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class CaptureTests(unittest.TestCase):
    def test_noop_without_token(self):
        calls = []
        thread = capture("ev", "me", {"x": 1}, opener=lambda *a, **k: calls.append(1), token="")
        self.assertIsNone(thread)
        self.assertEqual(calls, [])

    def test_posts_expected_shape(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data)
            captured["content_type"] = request.get_header("Content-type")
            return _Resp(b"")

        thread = capture("question_asked", "user-1", {"surface": "mcp"},
                          opener=opener, token="phc_test")
        thread.join(timeout=2)

        self.assertTrue(captured["url"].endswith("/i/v0/e/"))
        self.assertEqual(captured["content_type"], "application/json")
        self.assertEqual(captured["body"], {
            "api_key": "phc_test",
            "event": "question_asked",
            "distinct_id": "user-1",
            "properties": {"surface": "mcp"},
        })

    def test_missing_distinct_id_falls_back_to_anonymous(self):
        captured = {}

        def opener(request, timeout):
            captured["body"] = json.loads(request.data)
            return _Resp(b"")

        capture("ev", None, token="phc_test", opener=opener).join(timeout=2)
        self.assertEqual(captured["body"]["distinct_id"], "anonymous")

    def test_opener_failure_never_raises(self):
        def opener(request, timeout):
            raise OSError("network is down")

        thread = capture("ev", "me", token="phc_test", opener=opener)
        thread.join(timeout=2)  # would have raised into this test if unswallowed


if __name__ == "__main__":
    unittest.main()
