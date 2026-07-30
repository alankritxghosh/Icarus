# demo/test_freshness.py
"""Staleness reporting's contract, written before the implementation.

One honesty property dominates this file: **"I could not check" must never
render as "up to date".** A connected repo drifts silently -- this repo's own
index sat nine commits behind HEAD with nothing anywhere saying so -- and the
fix for that is worthless if a failed network call produces a confident
"current". `up_to_date` is therefore a THREE-valued field: True, False, or
None for unknown, and every failure path lands on None.
"""

import unittest

from .freshness import FreshnessChecker


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _checker(head=None, behind=None, clock=None, record=None):
    def _head(repo, token):
        if record is not None:
            record.append(("head", repo))
        return head

    def _between(repo, base, target, token):
        if record is not None:
            record.append(("between", base, target))
        return behind

    return FreshnessChecker(head_fn=_head, between_fn=_between,
                            now=clock or _Clock(), ttl=600)


class UpToDateTests(unittest.TestCase):
    def test_matching_head_is_up_to_date_with_zero_behind(self):
        result = _checker(head="abc").check("o/r", "abc", None)
        self.assertIs(result["up_to_date"], True)
        self.assertEqual(result["behind_by"], 0)

    def test_a_matching_head_never_costs_a_second_request(self):
        # The common case is "nothing changed". Paying for a compare call on
        # every poll of an unchanged repo would be the whole cost of this
        # feature spent on its least interesting answer.
        record = []
        _checker(head="abc", record=record).check("o/r", "abc", None)
        self.assertEqual([c[0] for c in record], ["head"])

    def test_a_differing_head_reports_how_far_behind(self):
        result = _checker(head="new", behind=9).check("o/r", "old", None)
        self.assertIs(result["up_to_date"], False)
        self.assertEqual(result["behind_by"], 9)
        self.assertEqual(result["head_commit"], "new")

    def test_the_comparison_runs_from_the_indexed_commit_to_head(self):
        record = []
        _checker(head="new", behind=1, record=record).check("o/r", "old", None)
        self.assertIn(("between", "old", "new"), record)


class UnknownIsNeverFreshTests(unittest.TestCase):
    """Every failure path lands on None, not on a reassuring answer."""

    def test_an_unreadable_head_is_unknown_not_up_to_date(self):
        result = _checker(head=None).check("o/r", "abc", None)
        self.assertIsNone(result["up_to_date"])
        self.assertIsNone(result["behind_by"])

    def test_a_failed_comparison_still_reports_that_it_differs(self):
        # We know the shas differ even though the count is unavailable, so
        # `up_to_date` is genuinely False -- only the NUMBER is unknown.
        # Downgrading this to None would hide a fact we actually have.
        result = _checker(head="new", behind=None).check("o/r", "old", None)
        self.assertIs(result["up_to_date"], False)
        self.assertIsNone(result["behind_by"])

    def test_no_indexed_commit_is_unknown(self):
        result = _checker(head="abc").check("o/r", None, None)
        self.assertIsNone(result["up_to_date"])

    def test_no_repo_is_unknown_and_never_calls_out(self):
        record = []
        result = _checker(head="abc", record=record).check(None, "abc", None)
        self.assertIsNone(result["up_to_date"])
        self.assertEqual(record, [])

    def test_a_failed_check_is_retried_rather_than_cached(self):
        # Pinning "unknown" for the whole TTL would make one network blip hide
        # staleness for ten minutes.
        record = []
        checker = _checker(head=None, record=record)
        checker.check("o/r", "abc", None)
        checker.check("o/r", "abc", None)
        self.assertEqual(len(record), 2)

    def test_the_result_always_carries_every_key(self):
        # A client that reads `up_to_date` must never get a KeyError on a
        # failure path and fall back to rendering nothing.
        for checker in (_checker(head=None), _checker(head="a"), _checker(head="b", behind=2)):
            result = checker.check("o/r", "a", None)
            for key in ("up_to_date", "behind_by", "head_commit", "checked_at"):
                self.assertIn(key, result)


class CachingTests(unittest.TestCase):
    """`/status` is polled continuously; the network call is not."""

    def test_a_second_check_inside_the_ttl_is_served_from_cache(self):
        record = []
        checker = _checker(head="abc", record=record)
        checker.check("o/r", "abc", None)
        checker.check("o/r", "abc", None)
        self.assertEqual(len(record), 1)

    def test_the_check_runs_again_once_the_ttl_expires(self):
        record, clock = [], _Clock()
        checker = _checker(head="abc", clock=clock, record=record)
        checker.check("o/r", "abc", None)
        clock.t += 601
        checker.check("o/r", "abc", None)
        self.assertEqual(len(record), 2)

    def test_a_different_repo_is_cached_separately(self):
        record = []
        checker = _checker(head="abc", record=record)
        checker.check("o/r", "abc", None)
        checker.check("o/other", "abc", None)
        self.assertEqual(len(record), 2)

    def test_a_changed_indexed_commit_invalidates_the_cache(self):
        # After a refresh the indexed commit moves. Serving the pre-refresh
        # verdict would tell the user their fresh index is still stale --
        # the exact moment they are looking at the banner to see it clear.
        record = []
        checker = _checker(head="abc", record=record)
        checker.check("o/r", "old", None)   # stale: costs head + compare
        checker.check("o/r", "abc", None)   # refreshed: must not reuse the entry
        self.assertEqual([c for c in record if c[0] == "head"],
                         [("head", "o/r"), ("head", "o/r")])

    def test_the_cache_never_retains_the_callers_token(self):
        checker = _checker(head="abc")
        checker.check("o/r", "abc", "secret-token")
        self.assertNotIn("secret-token", repr(checker.__dict__))


class ReportedTimeTests(unittest.TestCase):
    def test_checked_at_is_the_time_of_the_real_check(self):
        clock = _Clock(1234.0)
        result = _checker(head="abc", clock=clock).check("o/r", "abc", None)
        self.assertEqual(result["checked_at"], 1234.0)

    def test_a_cached_result_reports_when_it_was_actually_checked(self):
        # Not "now" -- a user deciding whether to trust an index needs to know
        # the answer is up to ten minutes old.
        clock = _Clock(1000.0)
        checker = _checker(head="abc", clock=clock)
        checker.check("o/r", "abc", None)
        clock.t += 300
        self.assertEqual(checker.check("o/r", "abc", None)["checked_at"], 1000.0)


if __name__ == "__main__":
    unittest.main()
