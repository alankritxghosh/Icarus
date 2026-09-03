# demo/test_ratelimit.py
import unittest

from .ratelimit import RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_rejects_non_positive_configuration(self):
        for limit, window in ((0, 60), (-1, 60), (1, 0), (1, -1)):
            with self.subTest(limit=limit, window=window):
                with self.assertRaises(ValueError):
                    RateLimiter(limit, window)

    def test_allows_up_to_the_limit(self):
        rl = RateLimiter(3, 60, _now=lambda: 1000.0)
        for _ in range(3):
            self.assertTrue(rl.allow("alice"))

    def test_blocks_the_call_past_the_limit_in_the_same_window(self):
        rl = RateLimiter(3, 60, _now=lambda: 1000.0)
        for _ in range(3):
            self.assertTrue(rl.allow("alice"))
        self.assertFalse(rl.allow("alice"))

    def test_a_different_key_is_unaffected_by_another_keys_usage(self):
        rl = RateLimiter(1, 60, _now=lambda: 1000.0)
        self.assertTrue(rl.allow("alice"))
        self.assertFalse(rl.allow("alice"))  # alice is exhausted
        self.assertTrue(rl.allow("bob"))  # bob has his own budget
        self.assertFalse(rl.allow("bob"))  # and bob's budget is independent too

    def test_window_sliding_allows_again_after_it_elapses(self):
        clock = {"t": 1000.0}
        rl = RateLimiter(2, 60, _now=lambda: clock["t"])
        self.assertTrue(rl.allow("alice"))
        self.assertTrue(rl.allow("alice"))
        self.assertFalse(rl.allow("alice"))  # at the limit

        clock["t"] += 59  # still inside the window
        self.assertFalse(rl.allow("alice"))

        clock["t"] += 2  # now past the window for the first hit (61s later)
        self.assertTrue(rl.allow("alice"))

    def test_retry_after_reports_when_the_oldest_hit_expires(self):
        clock = {"t": 1000.0}
        rl = RateLimiter(2, 60, _now=lambda: clock["t"])
        self.assertTrue(rl.allow("alice"))
        clock["t"] += 10
        self.assertTrue(rl.allow("alice"))

        self.assertEqual(rl.retry_after("alice"), 50)
        self.assertEqual(rl.retry_after("bob"), 0)

        clock["t"] += 49.1
        self.assertEqual(rl.retry_after("alice"), 1)

        clock["t"] += 0.9
        self.assertEqual(rl.retry_after("alice"), 0)

    def test_retry_after_does_not_consume_the_budget(self):
        rl = RateLimiter(1, 60, _now=lambda: 1000.0)
        self.assertEqual(rl.retry_after("alice"), 0)
        self.assertTrue(rl.allow("alice"))
        self.assertEqual(rl.retry_after("alice"), 60)
        self.assertFalse(rl.allow("alice"))

    def test_default_clock_is_real_time_when_not_injected(self):
        # Behavior for real callers (no _now override) is unchanged: it should
        # still allow calls under the limit using the real wall clock.
        rl = RateLimiter(2, 60)
        self.assertTrue(rl.allow("alice"))
        self.assertTrue(rl.allow("alice"))
        self.assertFalse(rl.allow("alice"))


if __name__ == "__main__":
    unittest.main()
