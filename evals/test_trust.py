# evals/test_trust.py
"""The trust interlock: private code may only reach a private-safe provider.
Deterministic and auditable, in the same spirit as the honesty gate."""

import unittest

from .provider import (GeminiProvider, GroqProvider, OpenRouterProvider,
                       PaidGeminiProvider, StaticProvider)
from .trust import PrivateDataError, assert_safe_for_private


class InterlockTests(unittest.TestCase):
    def test_refuses_every_free_provider(self):
        for p in (GeminiProvider(), GroqProvider(), OpenRouterProvider()):
            with self.assertRaises(PrivateDataError):
                assert_safe_for_private(p)

    def test_passes_private_safe_providers(self):
        assert_safe_for_private(PaidGeminiProvider())   # must not raise
        assert_safe_for_private(StaticProvider("x"))

    def test_absent_flag_is_refused_not_assumed(self):
        class Bare:  # a provider that never declared itself
            pass
        with self.assertRaises(PrivateDataError):
            assert_safe_for_private(Bare())


if __name__ == "__main__":
    unittest.main()
