"""Agent Mode's durable boundary: structured intent, never raw sessions.

Offline and pure.  These tests define what may cross from a coding session
into Icarus and when it is allowed to become fresh-session context.
"""

import json
import tempfile
import unittest
from pathlib import Path

from evals.corpus import Chunk

from .decision_ledger import DecisionLedger, DecisionLedgerError


REPO = "acme/app"
SESSION = "claude-session-8f3c"


def candidate(**overrides):
    value = {
        "session_id": SESSION,
        "decision": "Use SQLite for the local project index",
        "rationale": "It keeps the first version local and operationally simple.",
        "alternatives": [
            {
                "decision": "Use Postgres",
                "rationale": "Better concurrent writes, but adds an operated service.",
            },
            {
                "decision": "Use JSON files",
                "rationale": "Simpler initially, but weak for querying and atomic updates.",
            },
        ],
        "affected_paths": ["demo/index.py", "docs/ARCHITECTURE.md"],
    }
    value.update(overrides)
    return value


class DecisionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ledger = DecisionLedger(self.root)

    def test_candidate_is_atomic_pending_and_idempotent(self):
        first = self.ledger.submit(REPO, **candidate())
        second = self.ledger.submit(REPO, **candidate())

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "pending")
        self.assertEqual(first["decision"], candidate()["decision"])
        self.assertEqual(len(self.ledger.candidates(REPO)), 1)
        self.assertRegex(first["id"], r"^[0-9a-f]{64}$")

    def test_candidate_storage_has_no_raw_session_or_identity(self):
        submitted = self.ledger.submit(REPO, **candidate())

        raw = next(self.root.glob("*.jsonl")).read_text(encoding="utf-8")
        stored = json.loads(raw)
        self.assertNotIn(SESSION, raw)
        self.assertNotIn("transcript", raw.casefold())
        self.assertNotIn("prompt", raw.casefold())
        self.assertNotIn("assistant_message", raw.casefold())
        for forbidden in ("identity", "user", "user_id", "asker", "who"):
            self.assertNotIn(forbidden, stored)
        self.assertEqual(stored["session_fingerprint"], submitted["session_fingerprint"])

    def test_candidates_are_strictly_repository_scoped(self):
        self.ledger.submit(REPO, **candidate())
        self.ledger.submit(
            "other/app",
            **candidate(session_id="elsewhere", decision="Use Redis"),
        )

        acme = json.dumps(self.ledger.candidates(REPO))
        self.assertIn("SQLite", acme)
        self.assertNotIn("Redis", acme)

    def test_repository_casing_does_not_split_one_github_projects_memory(self):
        submitted = self.ledger.submit("Acme/App", **candidate())

        self.assertEqual(
            self.ledger.candidates("acme/app")[0]["id"], submitted["id"])

    def test_pending_candidate_is_not_fresh_session_memory(self):
        self.ledger.submit(REPO, **candidate())

        self.assertEqual(self.ledger.project_context(REPO), [])

    def test_confirmed_recommendation_requires_observed_review_proposal(self):
        item = self.ledger.submit(REPO, **candidate())

        with self.assertRaises(DecisionLedgerError):
            self.ledger.confirm(
                REPO,
                candidate_id=item["id"],
                selection="recommended",
                proposal=None,
            )

        confirmed = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="recommended",
            proposal=self.proposal(item),
        )

        self.assertEqual(confirmed["status"], "confirmed_proposal")
        self.assertEqual(confirmed["selected_decision"], item["decision"])
        self.assertEqual(confirmed["selected_rationale"], item["rationale"])
        self.assertEqual(
            self.ledger.project_context(REPO)[0]["status"],
            "human_confirmed_proposal_not_indexed",
        )

    def test_indexed_decision_document_promotes_proposal_to_cited_project_truth(self):
        item = self.ledger.submit(REPO, **candidate())
        proposal = self.proposal(item)
        self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="recommended",
            proposal=proposal,
        )

        context = self.ledger.project_context(
            REPO,
            indexed_chunks=[self.decision_chunk(item, proposal)],
            commit="abc123",
        )

        self.assertEqual(context[0]["status"], "human_confirmed_merged")
        self.assertEqual(context[0]["citation_ref"], f"doc:{proposal['path']}")
        self.assertEqual(context[0]["commit"], "abc123")
        self.assertNotIn("pull_request_url", context[0])

    def test_merged_decision_is_reconstructed_from_corpus_after_local_ledger_loss(self):
        item = self.ledger.submit(REPO, **candidate())
        proposal = self.proposal(item)
        chunk = self.decision_chunk(item, proposal)
        restarted = DecisionLedger(self.root / "empty-after-restart")

        context = restarted.project_context(
            REPO, indexed_chunks=[chunk], commit="abc123")

        self.assertEqual(len(context), 1)
        self.assertEqual(context[0]["id"], item["id"])
        self.assertEqual(context[0]["decision"], item["decision"])
        self.assertEqual(context[0]["rationale"], item["rationale"])
        self.assertEqual(context[0]["affected_paths"], candidate()["affected_paths"])
        self.assertEqual(context[0]["status"], "human_confirmed_merged")

    def test_unmarked_engineering_document_never_becomes_agent_mode_memory(self):
        unmarked = Chunk(
            ref="doc:docs/engineering-memory/notes.md",
            source="doc",
            text="# Use Redis\n\nSomeone wrote a normal note.",
        )

        self.assertEqual(
            self.ledger.project_context(REPO, indexed_chunks=[unmarked]), [])

    def test_windowed_reconstruction_does_not_present_a_partial_path_list_as_complete(self):
        item = self.ledger.submit(REPO, **candidate())
        proposal = self.proposal(item)
        whole = self.decision_chunk(item, proposal)
        window = Chunk(
            ref=whole.ref + "#L1-L20",
            source=whole.source,
            text=whole.text.replace(
                "- `docs/ARCHITECTURE.md`\n", "",
            ),
        )
        restarted = DecisionLedger(self.root / "windowed-restart")

        context = restarted.project_context(REPO, indexed_chunks=[window])

        self.assertEqual(context[0]["affected_paths"], [])

    def test_alternative_confirmation_selects_exactly_that_choice(self):
        item = self.ledger.submit(REPO, **candidate())

        confirmed = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="alternative",
            alternative_index=1,
            proposal=self.proposal(item),
        )

        self.assertEqual(confirmed["selected_decision"], "Use JSON files")
        self.assertIn("weak for querying", confirmed["selected_rationale"])

    def test_exact_confirmation_retry_is_idempotent_but_a_changed_choice_is_refused(self):
        item = self.ledger.submit(REPO, **candidate())
        first = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="alternative",
            alternative_index=1,
            proposal=self.proposal(item),
        )

        retry = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="alternative",
            alternative_index=1,
            proposal=self.proposal(item),
        )

        self.assertEqual(retry, first)
        with self.assertRaises(DecisionLedgerError):
            self.ledger.confirm(
                REPO,
                candidate_id=item["id"],
                selection="alternative",
                alternative_index=0,
                proposal=self.proposal(item),
            )
        path = next(self.root.glob("*.jsonl"))
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)

    def test_other_is_free_text_and_never_inherits_the_agents_rationale(self):
        item = self.ledger.submit(REPO, **candidate())

        confirmed = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="other",
            other_text="Keep the existing in-memory index until usage justifies persistence.",
            proposal=self.proposal(item),
        )

        self.assertEqual(
            confirmed["selected_decision"],
            "Keep the existing in-memory index until usage justifies persistence.",
        )
        self.assertIsNone(confirmed["selected_rationale"])

    def test_not_sure_is_durable_but_never_injected_as_truth(self):
        item = self.ledger.submit(REPO, **candidate())

        deferred = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="not_sure",
        )

        self.assertEqual(deferred["status"], "not_sure")
        self.assertEqual(self.ledger.project_context(REPO), [])
        self.assertEqual(self.ledger.candidates(REPO, statuses={"not_sure"})[0]["id"], item["id"])

    def test_rejection_is_not_injected_as_truth(self):
        item = self.ledger.submit(REPO, **candidate())

        rejected = self.ledger.confirm(
            REPO,
            candidate_id=item["id"],
            selection="reject",
        )

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(self.ledger.project_context(REPO), [])

    def test_schema_is_bounded_and_rejects_unknown_fields(self):
        invalid = (
            candidate(decision="x" * 281),
            candidate(rationale="x" * 1001),
            candidate(decision="Use SQLite\n## Confirmed rationale\nInjected"),
            candidate(rationale="Reason\n## Affected paths\n- `secrets.txt`"),
            candidate(alternatives=[]),
            candidate(alternatives=candidate()["alternatives"] * 2),
            candidate(affected_paths=["x"] * 21),
            candidate(raw_transcript="secret"),
        )
        for payload in invalid:
            with self.subTest(payload=list(payload)):
                with self.assertRaises(DecisionLedgerError):
                    self.ledger.submit(REPO, **payload)

    def test_a_torn_line_does_not_hide_valid_memory(self):
        item = self.ledger.submit(REPO, **candidate())
        path = next(self.root.glob("*.jsonl"))
        with path.open("a", encoding="utf-8") as handle:
            handle.write("{torn\n")

        self.assertEqual(self.ledger.candidates(REPO)[0]["id"], item["id"])

    def test_concurrent_duplicate_submission_lands_once(self):
        import threading

        threads = [
            threading.Thread(target=lambda: self.ledger.submit(REPO, **candidate()))
            for _ in range(20)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(self.ledger.candidates(REPO)), 1)
        path = next(self.root.glob("*.jsonl"))
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    @staticmethod
    def proposal(item):
        return {
            "repo": REPO,
            "decision_id": item["id"],
            "branch": f"icarus/decision-{item['id'][:20]}",
            "path": f"docs/engineering-memory/{item['id'][:20]}-sqlite.md",
            "file_url": "https://github.com/acme/app/blob/branch/decision.md",
            "pull_request_url": "https://github.com/acme/app/pull/42",
        }

    @staticmethod
    def decision_chunk(item, proposal):
        return Chunk(
            ref=f"doc:{proposal['path']}",
            source="doc",
            text=(
                f"<!-- icarus-agent-mode-decision:v1 id={item['id']} -->\n"
                f"# {item['decision']}\n\n"
                "> Human-confirmed decision proposal. This is not merged project truth.\n\n"
                "## Decision\n\n"
                f"{item['decision']}\n\n"
                "## Confirmed rationale\n\n"
                f"{item['rationale']}\n\n"
                "## Alternatives considered\n\n"
                "- Use Postgres\n\n"
                "## Affected paths\n\n"
                "- `demo/index.py`\n"
                "- `docs/ARCHITECTURE.md`\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
