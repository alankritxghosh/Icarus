"""`_gh_json` retries a transient GitHub failure, not a real one.

Live-found 2026-08-28: a large bulk `gh pr list` for cli/cli (~14k PRs)
intermittently 502/504s from GitHub's GraphQL endpoint and succeeds on an
immediate retry, but the base coverage pass had no retry, so one transient blip
killed the whole ingest. These tests drive `evals.ingest.subprocess.run`
directly (the mock-`_gh_json` discussion tests can't see a retry inside
`_gh_json`), with `time.sleep` patched so they stay instant.
"""

import json
import subprocess
import unittest
from unittest import mock

from . import ingest


def _ok(payload="[]"):
    return subprocess.CompletedProcess(["gh"], 0, stdout=payload, stderr="")


def _boom(stderr):
    return subprocess.CalledProcessError(1, ["gh"], output="", stderr=stderr)


class GhJsonRetryTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(ingest.time, "sleep")
        self.addCleanup(patcher.stop)
        patcher.start()

    def test_transient_502_then_success(self):
        seq = [_boom("HTTP 502: Bad Gateway"), _boom("error: 504"), _ok('[{"number": 1}]')]
        with mock.patch.object(ingest.subprocess, "run",
                               side_effect=seq) as run:
            self.assertEqual(ingest._gh_json(["pr", "list"]), [{"number": 1}])
        self.assertEqual(run.call_count, 3)

    def test_timeout_then_success(self):
        seq = [subprocess.TimeoutExpired(["gh"], 900), _ok('[]')]
        with mock.patch.object(ingest.subprocess, "run", side_effect=seq) as run:
            self.assertEqual(ingest._gh_json(["pr", "list"]), [])
        self.assertEqual(run.call_count, 2)

    def test_non_transient_failure_is_not_retried(self):
        err = _boom("Could not resolve to a Repository with the name 'x/y'.")
        with mock.patch.object(ingest.subprocess, "run",
                               side_effect=err) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                ingest._gh_json(["pr", "list"])
        self.assertEqual(run.call_count, 1)

    def test_all_attempts_transient_raises_last(self):
        with mock.patch.object(ingest.subprocess, "run",
                               side_effect=_boom("502 gateway")) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                ingest._gh_json(["pr", "list"])
        self.assertEqual(run.call_count, ingest._GH_RETRY_ATTEMPTS)

    def test_happy_path_calls_once(self):
        with mock.patch.object(ingest.subprocess, "run",
                               return_value=_ok('{"a": 1}')) as run:
            self.assertEqual(ingest._gh_json(["api", "x"]), {"a": 1})
        self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
