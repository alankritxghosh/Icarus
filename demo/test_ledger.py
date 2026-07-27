# demo/test_ledger.py
"""The per-repo ask ledger: what a team asked, and -- the part that matters --
what it turned out nobody had written down.

Offline and pure: a temp directory, no server, no network.
"""

import json
import tempfile
import threading
import unittest
from pathlib import Path

from .ledger import Ledger


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "ledger"
        self.led = Ledger(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_records_and_reads_back(self):
        self.led.record("acme/app", user="1001", question="why is the retry limit 5?",
                        verdict="answer", citations=["pr:12"])
        got = self.led.entries("acme/app")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["question"], "why is the retry limit 5?")
        self.assertEqual(got[0]["verdict"], "answer")
        self.assertEqual(got[0]["citations"], ["pr:12"])
        self.assertEqual(got[0]["user"], "1001")
        self.assertIn("ts", got[0])

    def test_entries_are_per_repo(self):
        # A company's questions must not leak into another company's notebook --
        # the ledger is per-repo for the same reason the corpus is.
        self.led.record("acme/app", user="1", question="acme question", verdict="unknown")
        self.led.record("other/app", user="2", question="other question", verdict="unknown")
        acme = json.dumps(self.led.entries("acme/app"))
        self.assertIn("acme question", acme)
        self.assertNotIn("other question", acme)

    def test_unknowns_only_filters_to_the_gaps(self):
        # This is the artifact the whole feature exists for: everything the team
        # needed to know that nobody had ever recorded.
        self.led.record("acme/app", user="1", question="answered one", verdict="answer",
                        citations=["pr:1"])
        self.led.record("acme/app", user="1", question="undocumented one", verdict="unknown")
        gaps = self.led.entries("acme/app", unknowns_only=True)
        self.assertEqual([e["question"] for e in gaps], ["undocumented one"])

    def test_survives_a_new_process(self):
        # The ledger is the accumulating asset; it cannot live in memory.
        self.led.record("acme/app", user="1", question="q", verdict="unknown")
        fresh = Ledger(self.root)
        self.assertEqual(len(fresh.entries("acme/app")), 1)

    def test_most_recent_first_and_limited(self):
        for i in range(5):
            self.led.record("acme/app", user="1", question=f"q{i}", verdict="unknown")
        got = self.led.entries("acme/app", limit=2)
        self.assertEqual([e["question"] for e in got], ["q4", "q3"])

    def test_unknown_repo_reads_empty_rather_than_raising(self):
        self.assertEqual(self.led.entries("never/asked"), [])

    def test_concurrent_writes_all_land_and_stay_parseable(self):
        # The server is threaded, so two people asking at once is the normal
        # case, not an edge one. A torn line would corrupt the record silently.
        def worker(n):
            for i in range(20):
                self.led.record("acme/app", user=str(n), question=f"q{n}-{i}",
                                verdict="unknown")
        threads = [threading.Thread(target=worker, args=(n,)) for n in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        got = self.led.entries("acme/app", limit=1000)
        self.assertEqual(len(got), 100, "every append must land")

    def test_hostile_repo_name_cannot_escape_the_ledger_root(self):
        # Repo names are validated at the HTTP edge, but the ledger must not
        # depend on that being the only guard.
        for bad in ("../../etc/passwd", "a/../../b", "/abs/path", ".."):
            with self.assertRaises(ValueError):
                self.led.record(bad, user="1", question="q", verdict="unknown")

    def test_writes_land_under_the_ledger_root_only(self):
        # The ledger MUST NOT live inside a corpus directory: registry ingest
        # publishes a corpus with os.replace(), which swaps the whole directory
        # and would silently delete a team's entire question history on the next
        # re-index.
        self.led.record("acme/app", user="1", question="q", verdict="unknown")
        written = list(self.root.rglob("*.jsonl"))
        self.assertTrue(written)
        for p in written:
            self.assertIn(self.root, p.parents)
