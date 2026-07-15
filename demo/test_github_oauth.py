# demo/test_github_oauth.py
"""The server-side GitHub OAuth flow: pure URL building, offline token exchange,
and the single-use state/session lifecycle. No network."""

import json
import unittest

from .github_oauth import authorize_url, exchange_code, OAuthFlow, new_state


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _opener(payload):
    def _open(req, timeout):
        return _FakeResp(payload)
    return _open


class AuthorizeUrlTests(unittest.TestCase):
    def test_includes_all_params(self):
        url = authorize_url("cid123", "http://127.0.0.1:8000/auth/github/callback", "st8", scope="repo")
        self.assertTrue(url.startswith("https://github.com/login/oauth/authorize?"))
        self.assertIn("client_id=cid123", url)
        self.assertIn("state=st8", url)
        self.assertIn("scope=repo", url)
        self.assertIn("127.0.0.1", url)

    def test_default_scope_grants_private_repo_read(self):
        # Private repos are the product: the default login scope must be `repo`
        # so the caller's token can read/clone their own private repositories.
        # (Classic OAuth has no read-only private scope; the per-repo GitHub App
        # is the roadmap replacement -- see authorize_url's docstring.)
        url = authorize_url("cid123", "http://127.0.0.1:8000/auth/github/callback", "st8")
        self.assertIn("scope=repo", url)


class ExchangeCodeTests(unittest.TestCase):
    def test_parses_access_token(self):
        token = exchange_code("thecode", client_id="c", client_secret="s",
                              redirect_uri="r", opener=_opener({"access_token": "gho_abc"}))
        self.assertEqual(token, "gho_abc")

    def test_error_body_raises(self):
        with self.assertRaises(RuntimeError):
            exchange_code("bad", client_id="c", client_secret="s", redirect_uri="r",
                          opener=_opener({"error": "bad_verification_code"}))


class OAuthFlowTests(unittest.TestCase):
    def _flow(self):
        # Fake exchanger: any code → a token derived from it (offline, deterministic).
        def fake_exchange(code, *, client_id, client_secret, redirect_uri):
            return f"token-for-{code}"
        return OAuthFlow("cid", "secret", "http://127.0.0.1:8000/auth/github/callback",
                         exchanger=fake_exchange)

    def test_configured(self):
        self.assertTrue(self._flow().configured)
        self.assertFalse(OAuthFlow("cid", "", "r").configured)

    def test_begin_complete_redeem_happy_path(self):
        flow = self._flow()
        state, url = flow.begin()
        self.assertIn(f"state={state}", url)
        session, mode, target = flow.complete(state, "CODE1")
        self.assertEqual(mode, "app")
        self.assertIsNone(target)
        self.assertEqual(flow.redeem(session), "token-for-CODE1")

    def test_begin_defaults_to_app_mode(self):
        flow = self._flow()
        state, _ = flow.begin()
        session, mode, target = flow.complete(state, "CODE_A")
        self.assertEqual(mode, "app")
        self.assertIsNone(target)
        self.assertEqual(flow.redeem(session), "token-for-CODE_A")

    def test_begin_web_mode_flows_through_complete(self):
        flow = self._flow()
        state, _ = flow.begin("web")
        session, mode, target = flow.complete(state, "CODE_W")
        self.assertEqual(mode, "web")
        self.assertIsNone(target)
        self.assertEqual(flow.redeem(session), "token-for-CODE_W")

    # --- Brick D: extension mode (chrome.identity.launchWebAuthFlow) ---

    _EXT_TARGET = "https://" + "a" * 32 + ".chromiumapp.org/"

    def test_begin_extension_mode_carries_the_redirect_target_through_complete(self):
        flow = self._flow()
        state, _ = flow.begin("extension", redirect_target=self._EXT_TARGET)
        session, mode, target = flow.complete(state, "CODE_E")
        self.assertEqual(mode, "extension")
        self.assertEqual(target, self._EXT_TARGET)
        self.assertEqual(flow.redeem(session), "token-for-CODE_E")

    def test_begin_extension_mode_without_a_target_is_rejected(self):
        # Meaningless/unsafe to proceed: nowhere to send the user back to.
        with self.assertRaises(ValueError):
            self._flow().begin("extension")

    def test_begin_extension_mode_rejects_a_non_chromiumapp_target(self):
        # The open-redirect guard: a caller must not be able to make the
        # server redirect a real logged-in session anywhere it likes after a
        # successful GitHub login -- only a genuine chrome-extension redirect
        # target (https://<32 a-p letters>.chromiumapp.org/) is accepted.
        with self.assertRaises(ValueError):
            self._flow().begin("extension", redirect_target="https://evil.example.com/steal")

    def test_begin_extension_mode_rejects_a_malformed_chromiumapp_id(self):
        # Right domain, wrong id shape (extension ids are exactly 32 chars in
        # a-p) -- still refused, not just a bare substring/suffix check.
        with self.assertRaises(ValueError):
            self._flow().begin("extension", redirect_target="https://short.chromiumapp.org/")

    def test_app_and_web_modes_ignore_a_redirect_target_if_somehow_supplied(self):
        # redirect_target is only meaningful for "extension" -- passing one to
        # another mode must not be silently honored (it's never used for the
        # actual redirect for those modes), so complete() must still report
        # None for them regardless.
        flow = self._flow()
        state, _ = flow.begin("web", redirect_target=self._EXT_TARGET)
        _, mode, target = flow.complete(state, "CODE_IGNORED")
        self.assertEqual(mode, "web")
        self.assertIsNone(target)

    def test_unknown_state_rejected(self):
        with self.assertRaises(ValueError):
            self._flow().complete("never-issued", "CODE")

    def test_redeem_is_single_use(self):
        flow = self._flow()
        state, _ = flow.begin()
        session, _, _ = flow.complete(state, "CODE2")
        self.assertEqual(flow.redeem(session), "token-for-CODE2")
        self.assertIsNone(flow.redeem(session))  # second time: gone

    def test_state_is_single_use(self):
        flow = self._flow()
        state, _ = flow.begin()
        flow.complete(state, "CODE3")
        with self.assertRaises(ValueError):
            flow.complete(state, "CODE3")  # state consumed

    def test_expired_state_rejected(self):
        def fake_exchange(code, **kw):
            return "t"
        flow = OAuthFlow("cid", "secret", "r", ttl=0.0, exchanger=fake_exchange)
        state, _ = flow.begin()
        with self.assertRaises(ValueError):
            flow.complete(state, "CODE")  # ttl=0 → already expired


if __name__ == "__main__":
    unittest.main()
