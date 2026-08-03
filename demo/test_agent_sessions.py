import unittest

from .agent_sessions import AgentSessionStore


class AgentSessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_000.0
        self.store = AgentSessionStore(
            ttl=600.0,
            clock=lambda: self.now,
        )

    def test_issue_returns_an_opaque_short_lived_token(self):
        token, expires_at = self.store.issue("github-user-42", "simonw/llm")

        self.assertNotIn("github-user-42", token)
        self.assertNotIn("simonw/llm", token)
        self.assertGreaterEqual(len(token), 32)
        self.assertEqual(expires_at, 1_600.0)
        grant = self.store.verify(token)
        self.assertEqual(grant.identity, "github-user-42")
        self.assertEqual(grant.repo, "simonw/llm")

    def test_expired_session_fails_closed(self):
        token, _ = self.store.issue("github-user-42", "simonw/llm")
        self.now = 1_600.0

        self.assertIsNone(self.store.verify(token))

    def test_unknown_or_empty_token_never_resolves(self):
        self.assertIsNone(self.store.verify(""))
        self.assertIsNone(self.store.verify("not-issued-here"))

    def test_sessions_are_distinct_and_identity_scoped(self):
        first, _ = self.store.issue("github-user-1", "one/repo")
        second, _ = self.store.issue("github-user-2", "two/repo")

        self.assertNotEqual(first, second)
        self.assertEqual(self.store.verify(first).identity, "github-user-1")
        self.assertEqual(self.store.verify(first).repo, "one/repo")
        self.assertEqual(self.store.verify(second).identity, "github-user-2")
        self.assertEqual(self.store.verify(second).repo, "two/repo")


if __name__ == "__main__":
    unittest.main()
