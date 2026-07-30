# demo/test_visits.py
"""Returning-user state's contract, written before the implementation.

The decision this implements is
`docs/decisions/2026-07-30-returning-user-state.md`, and the tests that matter
most are the ones proving what is NOT stored. Icarus was strictly stateless
about people until now; the ask ledger was built specifically so that WHO
ASKED is never recorded. This store records identity, so the safety property
is that the two can never be joined into a per-person question history.

Four fields, and no fifth: user identity, repository identity, last-seen
commit, last-visit timestamp.
"""

import json
import tempfile
import unittest
from pathlib import Path

from .visits import VisitStore


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class VisitStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.clock = _Clock()
        self.store = VisitStore(self.root, now=self.clock)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_first_visit_has_no_record(self):
        self.assertIsNone(self.store.last_visit("1001", "o/r"))

    def test_a_recorded_visit_reads_back(self):
        self.store.record("1001", "o/r", "abc")
        self.assertEqual(self.store.last_visit("1001", "o/r"),
                         {"commit": "abc", "at": 1000.0})

    def test_a_later_visit_overwrites_rather_than_appends(self):
        # An append-only trail of timestamps IS an activity log, however
        # harmless each row looks. The decision doc forbids one.
        self.store.record("1001", "o/r", "abc")
        self.clock.t = 2000.0
        self.store.record("1001", "o/r", "def")
        self.assertEqual(self.store.last_visit("1001", "o/r"),
                         {"commit": "def", "at": 2000.0})

    def test_repos_are_tracked_separately(self):
        self.store.record("1001", "o/one", "abc")
        self.store.record("1001", "o/two", "def")
        self.assertEqual(self.store.last_visit("1001", "o/one")["commit"], "abc")
        self.assertEqual(self.store.last_visit("1001", "o/two")["commit"], "def")

    def test_one_users_state_is_invisible_to_another(self):
        self.store.record("1001", "o/r", "abc")
        self.assertIsNone(self.store.last_visit("1002", "o/r"))


class NothingElseIsStoredTests(unittest.TestCase):
    """The decision doc's exclusions, enforced rather than promised."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = VisitStore(self.root, now=_Clock())

    def tearDown(self):
        self._tmp.cleanup()

    def _raw(self, user="1001"):
        return json.loads((self.root / user / "visits.json").read_text())

    def test_exactly_the_four_approved_fields_reach_disk(self):
        self.store.record("1001", "o/r", "abc")
        raw = self._raw()
        self.assertEqual(set(raw), {"o/r"})               # repository identity
        self.assertEqual(set(raw["o/r"]), {"commit", "at"})  # commit + timestamp
        # user identity is the DIRECTORY, not a field -- so it cannot be
        # copied out of the file by accident.

    def test_the_record_interface_accepts_no_question_or_answer(self):
        # A signature that cannot take a question is a stronger guarantee than
        # a policy that says we won't pass one.
        import inspect
        params = set(inspect.signature(self.store.record).parameters)
        for forbidden in ("question", "answer", "citations", "verdict", "count"):
            self.assertNotIn(forbidden, params)

    def test_no_visit_count_or_streak_is_derived(self):
        for _ in range(5):
            self.store.record("1001", "o/r", "abc")
        raw = self._raw()["o/r"]
        self.assertEqual(set(raw), {"commit", "at"})
        for value in raw.values():
            self.assertNotIsInstance(value, list)


class DurabilityAndSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.store = VisitStore(self.root, now=_Clock())

    def tearDown(self):
        self._tmp.cleanup()

    def test_state_survives_a_new_store_object(self):
        # The whole point: `LibraryRegistry._last_repo` is in-process memory
        # and does not survive a deploy, which is why this brick needed a real
        # store rather than another dict.
        self.store.record("1001", "o/r", "abc")
        self.assertEqual(VisitStore(self.root).last_visit("1001", "o/r")["commit"], "abc")

    def test_it_lives_under_the_users_own_isolated_directory(self):
        # The same directory `LibraryRegistry.disconnect` deletes, so
        # "deletable, and actually deleted" needs no second mechanism.
        self.store.record("1001", "o/r", "abc")
        self.assertTrue((self.root / "1001" / "visits.json").exists())

    def test_a_hostile_user_id_cannot_escape_the_root(self):
        for bad in ("../evil", "a/b", "..", "", None):
            with self.assertRaises(ValueError):
                self.store.record(bad, "o/r", "abc")

    def test_a_hostile_repo_name_is_refused(self):
        for bad in ("../../etc/passwd", "no-slash", ""):
            with self.assertRaises(ValueError):
                self.store.record("1001", bad, "abc")

    def test_a_corrupt_file_reads_as_no_record_rather_than_raising(self):
        # Never on the answering path: a damaged file must degrade to "first
        # visit", never take a request down.
        (self.root / "1001").mkdir(parents=True)
        (self.root / "1001" / "visits.json").write_text("{ not json")
        self.assertIsNone(self.store.last_visit("1001", "o/r"))

    def test_a_failed_write_never_raises(self):
        # An asset, not a dependency -- the same rule the ask ledger holds to.
        store = VisitStore(self.root / "nonexistent" / "\0bad", now=_Clock())
        store.record("1001", "o/r", "abc")  # must not raise

    def test_a_corrupt_file_is_replaced_by_the_next_write(self):
        (self.root / "1001").mkdir(parents=True)
        (self.root / "1001" / "visits.json").write_text("{ not json")
        self.store.record("1001", "o/r", "abc")
        self.assertEqual(self.store.last_visit("1001", "o/r")["commit"], "abc")


if __name__ == "__main__":
    unittest.main()
