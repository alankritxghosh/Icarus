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


class LoginScopeByModeTests(unittest.TestCase):
    """The consent screen must match what the user is actually doing right now.

    `repo` grants read AND WRITE on every private repository a person owns.
    Until 2026-08-11 the Mac app asked for it on the FIRST launch, before the
    user had seen Icarus answer anything -- an unnotarized alpha demanding
    write access to everything, which is the largest single obstacle between a
    stranger and trying it.

    Now every first sign-in asks for identity only, and `repo` is requested in
    its own consent screen at the moment somebody connects a private
    repository. This narrows what is REQUESTED, never what is enforced: a token
    without `repo` cannot read a private repo, so github_access.repo_info
    refuses it regardless.

    `web` stopped being identity-only on 2026-09-03: the web Agent Mode
    decision graph writes real pull requests with the caller's own token
    (the exact `GitHubMemoryWriter.record_decision` flow the native apps
    already use), and `read:user` cannot create a branch or a PR -- GitHub
    rejects the write. `public_repo` is the smallest scope that makes it
    real, and stays strictly narrower than `app-private`'s `repo` (public
    only, never private). `app`/`extension` are UNCHANGED -- still identity
    alone, since neither of them writes to GitHub on sign-in.
    """

    def _flow(self):
        def fake_exchange(code, *, client_id, client_secret, redirect_uri):
            return f"token-for-{code}"
        return OAuthFlow("cid", "secret", "http://127.0.0.1:8000/auth/github/callback",
                         exchanger=fake_exchange)

    def test_first_sign_in_asks_for_identity_only_on_app_and_extension(self):
        for mode, target in (("app", None),
                             ("extension",
                              "https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/")):
            with self.subTest(mode=mode):
                _state, url = self._flow().begin(mode, target) if target \
                    else self._flow().begin(mode)
                self.assertIn("scope=read%3Auser", url)
                self.assertNotIn("scope=repo", url)
                self.assertNotIn("scope=public_repo", url)

    def test_web_mode_asks_for_public_repo_write_access(self):
        # Not identity-only (it writes real PRs now), and not the native
        # surfaces' full `repo` either (public repos only, matching web's own
        # "never connects a private repo" boundary elsewhere in this file).
        _state, url = self._flow().begin("web")
        self.assertIn("scope=public_repo", url)
        self.assertNotIn("scope=read%3Auser", url)
        # A bare `assertNotIn("scope=repo", url)` would be VACUOUSLY true here
        # for the wrong reason: "repo" IS a substring of "public_repo", so
        # that check passes no matter what. Anchor on the delimiter instead --
        # "scope=repo&" cannot appear inside "scope=public_repo&" (there is no
        # "scope=repo&" substring once "public_" sits between "=" and "repo").
        self.assertNotIn("scope=repo&", url)

    def test_private_mode_is_the_only_one_that_asks_for_repo(self):
        _state, url = self._flow().begin("app-private")
        self.assertIn("scope=repo", url)

    def test_default_mode_is_identity_only(self):
        # No mode = the Mac app's ordinary sign-in. It must be the SAFE default:
        # a caller that forgets to say what it wants gets the least privilege.
        _state, url = self._flow().begin()
        self.assertIn("scope=read%3Auser", url)
        self.assertNotIn("scope=repo", url)

    def test_private_mode_uses_the_native_callback(self):
        # app-private differs from app ONLY in scope. If it ever stopped being
        # treated as a native login, the callback would redirect somewhere the
        # Mac app is not listening and the upgrade would silently never finish.
        flow = self._flow()
        state, _url = flow.begin("app-private")
        _session, mode, target = flow.complete(state, "code-1")
        self.assertEqual(mode, "app-private")
        self.assertIsNone(target)


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
