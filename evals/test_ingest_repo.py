# evals/test_ingest_repo.py
"""ingest_repo writes chunks.jsonl + meta.json into any target dir and returns
counts. Offline: the network fetches are monkeypatched."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import ingest
from .corpus_meta import load_meta


class IngestRepoTests(unittest.TestCase):
    def test_writes_corpus_and_meta_to_target_dir(self):
        prs = ([{"ref": "pr:1", "source": "pr", "text": "why X"}], {7})
        issues = [{"ref": "issue:7", "source": "issue", "text": "ctx"}]
        code = [{"ref": "code:a.py", "source": "code", "text": "x=1"}]
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest, "fetch_prs", return_value=prs), \
                mock.patch.object(ingest, "fetch_issues", return_value=issues), \
                mock.patch.object(ingest, "fetch_code", return_value=code):
            counts = ingest.ingest_repo("octo/repo", d, commit="abc123", code_dir=".")
            chunks = [json.loads(l) for l in (Path(d) / "chunks.jsonl").read_text().splitlines() if l.strip()]
            self.assertEqual([c["ref"] for c in chunks], ["pr:1", "issue:7", "code:a.py"])
            self.assertEqual(counts, {"pr": 1, "issue": 1, "code": 1})
            m = load_meta(Path(d) / "meta.json")
            self.assertEqual(m["repo"], "octo/repo")
            self.assertEqual(m["commit"], "abc123")


class AuthenticatedIngestTests(unittest.TestCase):
    """The caller's token authenticates git+gh — via ENV ONLY. argv shows in
    `ps`, URLs land in git config: both are leaks."""

    def test_git_env_carries_basic_auth_never_argv(self):
        from evals.ingest import _git_env
        env = _git_env("SECRET-TOKEN")
        self.assertEqual(env["GIT_CONFIG_COUNT"], "1")
        self.assertEqual(env["GIT_CONFIG_KEY_0"], "http.extraHeader")
        self.assertTrue(env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic "))
        self.assertNotIn("SECRET-TOKEN", env["GIT_CONFIG_VALUE_0"])  # b64, not raw
        import base64
        b64 = env["GIT_CONFIG_VALUE_0"].split()[-1]
        self.assertEqual(base64.b64decode(b64).decode(), "x-access-token:SECRET-TOKEN")

    def test_git_env_without_token_is_plain(self):
        import os
        from evals.ingest import _git_env
        self.assertNotIn("GIT_CONFIG_COUNT", set(_git_env(None)) - set(os.environ))

    def test_gh_env_sets_gh_token(self):
        from evals.ingest import _gh_env
        self.assertEqual(_gh_env("SECRET")["GH_TOKEN"], "SECRET")

    def test_token_reaches_subprocess_env_never_args(self):
        """Drive a real ingest_repo(...) call with subprocess.run faked at the
        lowest level (git ls-remote / gh / git clone / git checkout) and prove:
        the token string never appears in any `args` list, and the recorded
        `env` kwarg for git calls carries _git_env's header, for gh calls
        carries GH_TOKEN."""
        token = "SECRET-TOKEN"
        calls = []

        def fake_run(args, **kwargs):
            calls.append({"args": list(args), "env": kwargs.get("env")})
            prog = args[0]
            if prog == "git" and args[1] == "ls-remote":
                return subprocess.CompletedProcess(args, 0, stdout="deadbeef\tHEAD\n")
            if prog == "git" and args[1] == "clone":
                dest = Path(args[-1])
                dest.mkdir(parents=True, exist_ok=True)
                return subprocess.CompletedProcess(args, 0, stdout="")
            if prog == "git" and args[1] == "-C":
                return subprocess.CompletedProcess(args, 0, stdout="")
            if prog == "gh":
                if "pr" in args and "list" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="[]")
                if "issue" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="{}")
                return subprocess.CompletedProcess(args, 0, stdout="[]")
            raise AssertionError(f"unexpected subprocess call: {args}")

        with tempfile.TemporaryDirectory() as d, \
                mock.patch("evals.ingest.subprocess.run", side_effect=fake_run):
            ingest.ingest_repo("octo/private-repo", d, code_dir=".", token=token)

        self.assertTrue(calls, "expected at least one subprocess.run call")
        for call in calls:
            for arg in call["args"]:
                self.assertNotIn(token, str(arg))

        git_calls = [c for c in calls if c["args"][0] == "git"]
        gh_calls = [c for c in calls if c["args"][0] == "gh"]
        self.assertTrue(git_calls)
        self.assertTrue(gh_calls)
        for c in git_calls:
            self.assertEqual(c["env"]["GIT_CONFIG_VALUE_0"],
                              ingest._git_env(token)["GIT_CONFIG_VALUE_0"])
        for c in gh_calls:
            self.assertEqual(c["env"]["GH_TOKEN"], token)


if __name__ == "__main__":
    unittest.main()
