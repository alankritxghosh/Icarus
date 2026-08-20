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
        self.led.record("acme/app", question="why is the retry limit 5?",
                        verdict="answer", citations=["pr:12"])
        got = self.led.entries("acme/app")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["question"], "why is the retry limit 5?")
        self.assertEqual(got[0]["verdict"], "answer")
        self.assertEqual(got[0]["citations"], ["pr:12"])
        self.assertIn("ts", got[0])

    def test_who_asked_is_never_recorded(self):
        # Decided 2026-07-27: the ledger maps what an ORGANISATION has not
        # written down. It does not track which employee asked what. Keeping the
        # asker would make "Alice asked about auth fourteen times" a query this
        # system can answer, which is a different product -- surveillance of a
        # team rather than memory for it.
        #
        # The cost is real and accepted: gaps can be ranked by how OFTEN they
        # were hit, but not by how many DISTINCT people hit them.
        self.led.record("acme/app", question="q", verdict="unknown")
        raw = (self.root / "acme__app.jsonl").read_text()
        entry = self.led.entries("acme/app")[0]
        for field in ("user", "user_id", "identity", "asker"):
            self.assertNotIn(field, entry)
        self.assertNotIn("1001", raw)

    def test_entries_are_per_repo(self):
        # A company's questions must not leak into another company's notebook --
        # the ledger is per-repo for the same reason the corpus is.
        self.led.record("acme/app", question="acme question", verdict="unknown")
        self.led.record("other/app", question="other question", verdict="unknown")
        acme = json.dumps(self.led.entries("acme/app"))
        self.assertIn("acme question", acme)
        self.assertNotIn("other question", acme)

    def test_unknowns_only_filters_to_the_gaps(self):
        # This is the artifact the whole feature exists for: everything the team
        # needed to know that nobody had ever recorded.
        self.led.record("acme/app", question="answered one", verdict="answer",
                        citations=["pr:1"])
        self.led.record("acme/app", question="undocumented one", verdict="unknown")
        gaps = self.led.entries("acme/app", unknowns_only=True)
        self.assertEqual([e["question"] for e in gaps], ["undocumented one"])

    def test_survives_a_new_process(self):
        # The ledger is the accumulating asset; it cannot live in memory.
        self.led.record("acme/app", question="q", verdict="unknown")
        fresh = Ledger(self.root)
        self.assertEqual(len(fresh.entries("acme/app")), 1)

    def test_most_recent_first_and_limited(self):
        for i in range(5):
            self.led.record("acme/app", question=f"q{i}", verdict="unknown")
        got = self.led.entries("acme/app", limit=2)
        self.assertEqual([e["question"] for e in got], ["q4", "q3"])

    def test_unknown_repo_reads_empty_rather_than_raising(self):
        self.assertEqual(self.led.entries("never/asked"), [])

    def test_concurrent_writes_all_land_and_stay_parseable(self):
        # The server is threaded, so two people asking at once is the normal
        # case, not an edge one. A torn line would corrupt the record silently.
        def worker(n):
            for i in range(20):
                self.led.record("acme/app", question=f"q{n}-{i}", verdict="unknown")
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
                self.led.record(bad, question="q", verdict="unknown")

    def test_writes_land_under_the_ledger_root_only(self):
        # The ledger MUST NOT live inside a corpus directory: registry ingest
        # publishes a corpus with os.replace(), which swaps the whole directory
        # and would silently delete a team's entire question history on the next
        # re-index.
        self.led.record("acme/app", question="q", verdict="unknown")
        written = list(self.root.rglob("*.jsonl"))
        self.assertTrue(written)
        for p in written:
            self.assertIn(self.root, p.parents)


class AbstentionReasonTests(unittest.TestCase):
    """The ledger records WHY the gate abstained, so the unknowns map is a real
    map of documentation debt rather than a pile of everything that failed.

    Without it, "nobody wrote this down" and "you asked about something that
    does not exist here" are indistinguishable, and a typo inflates a team's
    apparent debt."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name))

    def test_the_reason_round_trips(self):
        self.ledger.record("o/r", question="why 30?", verdict="unknown",
                           reason="no_recorded_reason")
        self.assertEqual(self.ledger.entries("o/r")[0]["reason"], "no_recorded_reason")

    def test_the_two_buckets_stay_distinguishable_on_disk(self):
        self.ledger.record("o/r", question="why 30?", verdict="unknown",
                           reason="no_recorded_reason")
        self.ledger.record("o/r", question="how does Xyzzy work?", verdict="unknown",
                           reason="entity_absent")
        reasons = {e["question"]: e["reason"] for e in self.ledger.entries("o/r")}
        self.assertEqual(reasons["why 30?"], "no_recorded_reason")
        self.assertEqual(reasons["how does Xyzzy work?"], "entity_absent")

    def test_an_answer_records_no_reason(self):
        self.ledger.record("o/r", question="why?", verdict="answer",
                           citations=["pr:1"])
        self.assertIsNone(self.ledger.entries("o/r")[0]["reason"])

    def test_the_field_is_optional_for_existing_callers(self):
        self.ledger.record("o/r", question="q", verdict="unknown")
        self.assertIsNone(self.ledger.entries("o/r")[0]["reason"])

    def test_recording_a_reason_still_stores_no_identity(self):
        # The privacy property must survive the new field.
        self.ledger.record("o/r", question="q", verdict="unknown",
                           reason="entity_absent")
        entry = self.ledger.entries("o/r")[0]
        for forbidden in ("user", "user_id", "asker", "identity", "who"):
            self.assertNotIn(forbidden, entry)


class MemoryGapLifecycleTests(unittest.TestCase):
    """The closed loop: an honest unknown opens a gap; a later cited answer
    resolves it. Nothing weaker is allowed to claim the team's ignorance was
    repaired."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name))

    def test_a_later_cited_answer_resolves_the_exact_gap(self):
        self.ledger.record(
            "o/r", question="Why is auth synchronous?", verdict="unknown",
            reason="no_recorded_reason",
        )
        self.ledger.record(
            "o/r", question="  why is AUTH synchronous?  ", verdict="answer",
            citations=["doc:docs/engineering-memory/auth-synchronous.md#L1-L18"],
        )

        gaps = self.ledger.gaps("o/r", include_resolved=True)

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["status"], "resolved")
        self.assertEqual(gaps[0]["unknown_count"], 1)
        self.assertEqual(
            gaps[0]["resolution_citations"],
            ["doc:docs/engineering-memory/auth-synchronous.md#L1-L18"],
        )

    def test_an_answer_without_a_citation_does_not_resolve_a_gap(self):
        self.ledger.record(
            "o/r", question="Why is auth synchronous?", verdict="unknown",
            reason="no_recorded_reason",
        )
        self.ledger.record(
            "o/r", question="Why is auth synchronous?", verdict="answer",
            citations=[],
        )

        self.assertEqual(self.ledger.gaps("o/r")[0]["status"], "open")

    def test_entity_absent_is_visible_but_not_recordable_memory_debt(self):
        self.ledger.record(
            "o/r", question="Why does Xyzzy authenticate?", verdict="unknown",
            reason="entity_absent",
        )

        gap = self.ledger.gaps("o/r")[0]

        self.assertFalse(gap["actionable"])
        self.assertEqual(gap["kind"], "not_in_repo")

    def test_only_genuine_recorded_reason_absence_is_actionable(self):
        for reason in (None, "writer_abstained", "self_disclaimed", "no_evidence"):
            self.ledger.record(
                "o/r", question=f"question {reason}", verdict="unknown",
                reason=reason,
            )

        self.assertFalse(any(g["actionable"] for g in self.ledger.gaps("o/r")))

    def test_a_writer_declining_a_why_is_recordable_debt(self):
        """The reason the loop was unreachable in practice until 2026-08-08.

        `writer_found_no_reason` is the writer's own judgement that a
        rationale-seeking question has no recorded answer -- the ONLY
        classification real-world abstentions produced (onboarding_probe:
        24/70, every one of them). It has to be actionable or the whole
        record-engineering-memory path is dead code. It stays a distinct
        REASON from the code-proven `no_recorded_reason` so the ledger can
        still tell proof from judgement.
        """
        self.ledger.record(
            "o/r", question="Why is auth synchronous?", verdict="unknown",
            reason="writer_found_no_reason",
        )

        gap = self.ledger.gaps("o/r")[0]

        self.assertTrue(gap["actionable"])
        self.assertEqual(gap["kind"], "undocumented")

    def test_open_filter_excludes_resolved_but_preserves_recurring_counts(self):
        for _ in range(3):
            self.ledger.record(
                "o/r", question="Why Redis?", verdict="unknown",
                reason="no_recorded_reason",
            )
        self.ledger.record(
            "o/r", question="Why Redis?", verdict="answer", citations=["pr:42"],
        )
        self.ledger.record(
            "o/r", question="Why billing isolated?", verdict="unknown",
            reason="no_recorded_reason",
        )

        self.assertEqual(
            [g["question"] for g in self.ledger.gaps("o/r")],
            ["Why billing isolated?"],
        )
        resolved = self.ledger.gaps("o/r", include_resolved=True)
        redis = next(g for g in resolved if g["question"] == "Why Redis?")
        self.assertEqual(redis["unknown_count"], 3)

    def test_gap_records_never_contain_an_asker(self):
        self.ledger.record(
            "o/r", question="Why billing isolated?", verdict="unknown",
            reason="no_recorded_reason",
        )

        raw = json.dumps(self.ledger.gaps("o/r"))
        for forbidden in ("user", "user_id", "identity", "asker", "who"):
            self.assertNotIn(forbidden, raw)

    def test_unicode_casefold_identity_is_shared_by_listing_and_recording(self):
        for question in ("Why Straße?", "WHY STRASSE?"):
            self.ledger.record(
                "o/r", question=question, verdict="unknown",
                reason="no_recorded_reason",
            )

        gaps = self.ledger.gaps("o/r")

        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["unknown_count"], 2)
        self.assertRegex(gaps[0]["id"], r"^[0-9a-f]{64}$")

    def test_proposal_survives_later_unknowns_until_a_cited_answer_resolves_it(self):
        question = "Why is auth synchronous?"
        self.ledger.record(
            "o/r", question=question, verdict="unknown",
            reason="no_recorded_reason",
        )
        gap = self.ledger.gaps("o/r")[0]
        proposal = {
            "repo": "o/r",
            "question": question,
            "branch": f"icarus/memory-{gap['id'][:20]}",
            "path": "docs/engineering-memory/auth.md",
            "file_url": "https://github.com/o/r/blob/branch/auth.md",
            "pull_request_url": "https://github.com/o/r/pull/42",
        }

        self.ledger.record_proposal(
            "o/r", gap_id=gap["id"], question=question, result=proposal,
        )
        self.ledger.record(
            "o/r", question=question, verdict="unknown",
            reason="no_recorded_reason",
        )

        proposed = self.ledger.gaps("o/r")[0]
        self.assertEqual(proposed["status"], "proposed")
        self.assertFalse(proposed["actionable"])
        self.assertEqual(proposed["proposal"], proposal)
        self.assertEqual(proposed["unknown_count"], 2)

        self.ledger.record(
            "o/r", question=question, verdict="answer",
            citations=["doc:docs/engineering-memory/auth.md#L1-L12"],
        )
        resolved = self.ledger.gaps("o/r", include_resolved=True)[0]
        self.assertEqual(resolved["status"], "resolved")
