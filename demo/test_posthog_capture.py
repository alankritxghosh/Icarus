# demo/test_posthog_capture.py
"""capture()'s contract: no-ops with no token (never opens a connection),
posts the right shape with one, and a failing opener never raises into the
caller -- analytics must not be able to break a real request."""

import io
import json
import os
import threading
import unittest
from unittest import mock

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


class ConfigurationTimingTests(unittest.TestCase):
    """Configuration is read when capture RUNS, not when the module imports.

    `demo/server.py` imports this module near the top but loads `.env` inside
    `serve()`. Reading the token into a module global at import therefore left
    it permanently empty for the documented local `.env` setup: analytics
    silently disabled, and a custom `POSTHOG_HOST` silently ignored.
    Shell/PaaS-injected variables worked, which is why it went unnoticed.
    """

    def test_a_token_set_after_import_is_used(self):
        captured = {}
        with mock.patch.dict(os.environ,
                             {"POSTHOG_PROJECT_TOKEN": "from-env"},
                             clear=False):
            def opener(request, timeout=None):
                captured["body"] = json.loads(request.data.decode())
                return _Resp(b"")
            thread = capture("ev", "me", {"x": 1}, opener=opener)
            self.assertIsNotNone(thread)
            thread.join(2)
        self.assertEqual(captured["body"]["api_key"], "from-env")

    def test_a_host_set_after_import_is_used(self):
        captured = {}
        with mock.patch.dict(os.environ,
                             {"POSTHOG_PROJECT_TOKEN": "t",
                              "POSTHOG_HOST": "https://eu.example/"},
                             clear=False):
            def opener(request, timeout=None):
                captured["url"] = request.full_url
                return _Resp(b"")
            capture("ev", "me", opener=opener).join(2)
        self.assertEqual(captured["url"], "https://eu.example/i/v0/e/")

    def test_no_token_in_the_environment_still_no_ops(self):
        calls = []
        with mock.patch.dict(os.environ, {"POSTHOG_PROJECT_TOKEN": ""}, clear=False):
            self.assertIsNone(capture("ev", "me", opener=lambda *a, **k: calls.append(1)))
        self.assertEqual(calls, [])


class NeverBlocksTheResponseTests(unittest.TestCase):
    """`demo/server.py` calls capture BEFORE writing the response, so anything
    escaping capture() stops the real answer from being sent."""

    def test_a_thread_that_cannot_start_is_contained(self):
        # Reproduces the real failure: thread creation/start sat OUTSIDE the
        # exception guard, so `RuntimeError: cannot start new thread` -- a
        # plausible outcome of one-thread-per-event under load -- propagated
        # into the request being served.
        with mock.patch("demo.posthog_capture.threading.Thread") as thread_cls:
            thread_cls.return_value.start.side_effect = RuntimeError(
                "can't start new thread")
            self.assertIsNone(capture("ev", "me", token="t",
                                      opener=lambda *a, **k: None))

    def test_a_thread_that_cannot_be_created_is_contained(self):
        with mock.patch("demo.posthog_capture.threading.Thread",
                        side_effect=RuntimeError("no")):
            self.assertIsNone(capture("ev", "me", token="t",
                                      opener=lambda *a, **k: None))

    def test_events_are_dropped_rather_than_stacking_threads_without_bound(self):
        """The cause, not just the symptom: unbounded thread-per-event is what
        reaches the RuntimeError above in the first place."""
        import demo.posthog_capture as pc
        released = threading.Event()

        def blocking_opener(*_a, **_k):
            released.wait(5)
            return _Resp(b"")

        threads = [capture("ev", "me", token="t", opener=blocking_opener)
                   for _ in range(pc._MAX_IN_FLIGHT)]
        try:
            self.assertTrue(all(t is not None for t in threads))
            # One past the ceiling is refused, and refused WITHOUT raising.
            self.assertIsNone(capture("ev", "me", token="t", opener=blocking_opener))
        finally:
            released.set()
            for t in threads:
                if t is not None:
                    t.join(5)
        # The counter is returned, so a burst does not poison every later event.
        self.assertEqual(pc._in_flight, 0)
        self.assertIsNotNone(capture("ev", "me", token="t",
                                     opener=lambda *a, **k: _Resp(b"")))
