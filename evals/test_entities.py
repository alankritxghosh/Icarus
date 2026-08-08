# evals/test_entities.py
"""The entity index's contract, weighted toward what must NOT be emitted.

A wrong relationship is worse than a missing one: it is a confident claim about
the reader's own repository, indistinguishable from the true edges beside it
(see demo/structure.py's lazygit finding). So most of what is pinned here is
absence -- a foreign reference, a bare number, a quoted commit subject, an
unindexed target -- rather than presence.
"""

import unittest
from unittest import mock

from .corpus import Chunk
from .entities import (
    EDGE_CHANGED_FILES, EDGE_COMMITS, EDGE_DEPENDENCIES, EDGE_DEPENDENTS,
    EDGE_LINKED_ISSUES, EDGE_MENTIONED_BY, EDGE_SUBSEQUENT_PRS,
    build_entity_index,
)


def pr(n, text):
    return Chunk(ref=f"pr:{n}", source="pr", text=text)


def issue(n, text="ISSUE #%s: something"):
    return Chunk(ref=f"issue:{n}", source="issue", text=text)


def code(path, text="x = 1", window="#L1-L300"):
    return Chunk(ref=f"code:{path}{window}", source="code", text=text)


class LinkedIssueTests(unittest.TestCase):
    def test_body_mention_links_an_indexed_issue_both_ways(self):
        idx = build_entity_index([
            pr(400, "PR #400: chunking\n\nCloses #372, which broke large repos."),
            issue(372),
        ])
        self.assertEqual(idx.targets("pr:400", EDGE_LINKED_ISSUES), ["issue:372"])
        self.assertEqual(idx.targets("issue:372", EDGE_MENTIONED_BY), ["pr:400"])

    def test_edge_names_the_chunk_that_proves_it(self):
        idx = build_entity_index([pr(400, "PR #400: x\n\nCloses #372."), issue(372)])
        edge = idx.edges("pr:400", EDGE_LINKED_ISSUES)[0]
        self.assertEqual(edge.evidence_ref, "pr:400")

    def test_foreign_repository_reference_is_not_a_local_link(self):
        # "upstream/lib#372" is another project's issue. Matching the bare number
        # would attach an unrelated local issue to this PR.
        idx = build_entity_index([
            pr(400, "PR #400: x\n\nMirrors upstream/lib#372 in spirit."),
            issue(372),
        ])
        self.assertEqual(idx.targets("pr:400", EDGE_LINKED_ISSUES), [])

    def test_unindexed_number_produces_no_edge(self):
        # #999 might be a PR, a foreign ref, or outside the indexed slice.
        # Nothing about it is provable, so nothing is emitted.
        idx = build_entity_index([pr(400, "PR #400: x\n\nSee #999.")])
        self.assertEqual(idx.targets("pr:400", EDGE_LINKED_ISSUES), [])

    def test_a_pr_restating_its_own_number_does_not_link_to_itself(self):
        idx = build_entity_index([pr(372, "PR #372: x\n\nThis is #372."), issue(372)])
        self.assertEqual(idx.targets("pr:372", EDGE_LINKED_ISSUES), [])

    def test_repeated_mention_yields_one_edge(self):
        idx = build_entity_index([
            pr(400, "PR #400: x\n\nFixes #372. Really, #372. Again #372."), issue(372)])
        self.assertEqual(len(idx.edges("pr:400", EDGE_LINKED_ISSUES)), 1)


class ChangedFileTests(unittest.TestCase):
    LINE = ("PR #400: chunking\n\n[MERGED by ana]\n\nBody.\n\n"
            "Files changed (2): llm/cli.py (+10/-2) · llm/models.py (+3/-0)")

    def test_changed_files_are_paths_and_expand_to_chunks_on_request(self):
        idx = build_entity_index([pr(400, self.LINE),
                                  code("llm/cli.py"), code("llm/models.py")])
        self.assertEqual(idx.targets("pr:400", EDGE_CHANGED_FILES),
                         ["llm/cli.py", "llm/models.py"])
        self.assertEqual(idx.chunks_for("llm/cli.py"), ["code:llm/cli.py#L1-L300"])

    def test_unindexed_path_is_kept_but_marked_not_indexed(self):
        idx = build_entity_index([pr(400, self.LINE), code("llm/cli.py")])
        by_target = {e.target: e.indexed for e in idx.edges("pr:400", EDGE_CHANGED_FILES)}
        self.assertIs(by_target["llm/cli.py"], True)
        self.assertIs(by_target["llm/models.py"], False)
        # ...and a caller asking only for things it can go and read gets only those.
        self.assertEqual(idx.targets("pr:400", EDGE_CHANGED_FILES), ["llm/cli.py"])
        self.assertEqual(idx.chunks_for("llm/models.py"), [])

    def test_a_many_windowed_file_is_named_ONCE_not_once_per_window(self):
        # Fanning file edges across windows is what turned 30 real import edges
        # into 56,056 emitted ones on the committed corpus, and buries "1 file
        # changed" under near-duplicate refs.
        idx = build_entity_index([
            pr(400, "PR #400: x\n\nFiles changed (1): llm/cli.py (+1/-1)"),
            code("llm/cli.py", window="#L1-L300"), code("llm/cli.py", window="#L261-L560")])
        self.assertEqual(idx.targets("pr:400", EDGE_CHANGED_FILES), ["llm/cli.py"])
        self.assertEqual(len(idx.chunks_for("llm/cli.py")), 2)

    def test_truncated_file_list_is_reported(self):
        idx = build_entity_index([
            pr(400, "PR #400: x\n\nFiles changed (35): a.py (+1/-1) · "
                    "b.py (+2/-0) · … and 33 more files"),
            code("a.py"), code("b.py")])
        self.assertTrue(idx.is_truncated("pr:400", EDGE_CHANGED_FILES))

    def test_complete_file_list_is_not_reported_as_truncated(self):
        idx = build_entity_index([
            pr(400, "PR #400: x\n\nFiles changed (1): a.py (+1/-1)"), code("a.py")])
        self.assertFalse(idx.is_truncated("pr:400", EDGE_CHANGED_FILES))

    def test_a_comment_quoting_a_WELL_FORMED_line_mid_line_yields_nothing(self):
        # The quoted text is byte-identical to a real Files changed line, so
        # only the line ANCHOR can reject it. An earlier version of this test
        # appended " list was wrong", which _FILE_ENTRY rejected on its own --
        # it passed with the anchor deliberately removed, i.e. it tested
        # nothing. Proven red by dropping the ^ from _FILES_LINE.
        idx = build_entity_index([
            pr(400, "PR #400: x\n\nComment by bo: I copied it here -- "
                    "Files changed (1): a.py (+1/-1)"),
            code("a.py")])
        self.assertEqual(idx.targets("pr:400", EDGE_CHANGED_FILES), [])

    def test_an_issue_is_never_a_source_of_changed_files(self):
        idx = build_entity_index([
            Chunk(ref="issue:9", source="issue",
                  text="ISSUE #9: x\n\nFiles changed (1): a.py (+1/-1)"),
            code("a.py")])
        self.assertEqual(idx.targets("issue:9", EDGE_CHANGED_FILES), [])


class CommitTests(unittest.TestCase):
    def test_squash_subject_attaches_the_commit_to_its_pr(self):
        idx = build_entity_index([
            pr(400, "PR #400: chunking"),
            Chunk(ref="commit:abc123", source="commit",
                  text="COMMIT abc123: Improve chunking (#400)\n\n[ana on 2026-01-01]")])
        self.assertEqual(idx.targets("pr:400", EDGE_COMMITS), ["commit:abc123"])

    def test_a_pr_number_quoted_in_the_commit_BODY_is_not_membership(self):
        # A commit body routinely cites other PRs as context. Treating those as
        # "this commit belongs to that PR" invents history.
        idx = build_entity_index([
            pr(400, "PR #400: chunking"),
            Chunk(ref="commit:abc123", source="commit",
                  text="COMMIT abc123: Unrelated fix\n\n[ana]\n\nFollow-up to (#400)")])
        self.assertEqual(idx.targets("pr:400", EDGE_COMMITS), [])

    def test_subject_naming_an_unindexed_pr_yields_nothing(self):
        idx = build_entity_index([
            Chunk(ref="commit:abc123", source="commit",
                  text="COMMIT abc123: Improve chunking (#400)")])
        self.assertEqual(idx.targets("pr:400", EDGE_COMMITS), [])


class SubsequentPrTests(unittest.TestCase):
    CHUNKS = [
        pr(400, "PR #400: x\n\nFiles changed (1): llm/cli.py (+1/-1)"),
        pr(412, "PR #412: y\n\nFiles changed (1): llm/cli.py (+2/-2)"),
        pr(390, "PR #390: earlier\n\nFiles changed (1): llm/cli.py (+3/-3)"),
        pr(420, "PR #420: elsewhere\n\nFiles changed (1): other.py (+1/-1)"),
        code("llm/cli.py"), code("other.py"),
    ]

    def test_only_later_prs_touching_a_shared_file(self):
        idx = build_entity_index(self.CHUNKS)
        self.assertEqual(idx.targets("pr:400", EDGE_SUBSEQUENT_PRS), ["pr:412"])

    def test_the_earlier_pr_sees_the_later_ones(self):
        idx = build_entity_index(self.CHUNKS)
        self.assertEqual(idx.targets("pr:390", EDGE_SUBSEQUENT_PRS), ["pr:400", "pr:412"])

    def test_a_pr_is_never_subsequent_to_itself(self):
        idx = build_entity_index(self.CHUNKS)
        self.assertNotIn("pr:400", idx.targets("pr:400", EDGE_SUBSEQUENT_PRS))


class StructureDelegationTests(unittest.TestCase):
    def test_import_edges_become_dependency_edges_both_ways(self):
        idx = build_entity_index(
            [code("a.py", text="import b"), code("b.py")],
            structure={"file_edges": [("a.py", "b.py")]})
        self.assertEqual(idx.targets("a.py", EDGE_DEPENDENCIES), ["b.py"])
        self.assertEqual(idx.targets("b.py", EDGE_DEPENDENTS), ["a.py"])

    def test_a_caller_holding_a_chunk_ref_may_traverse_with_it(self):
        idx = build_entity_index(
            [code("a.py", text="import b"), code("b.py")],
            structure={"file_edges": [("a.py", "b.py")]})
        self.assertEqual(idx.targets("code:a.py#L1-L300", EDGE_DEPENDENCIES), ["b.py"])

    def test_the_proof_is_the_window_that_actually_names_the_import(self):
        # structure.py resolves the edge but returns path pairs with no chunk.
        # Citing the file's FIRST window would point a reader at lines holding
        # no import at all.
        idx = build_entity_index(
            [code("a.py", text="x = 1", window="#L1-L300"),
             code("a.py", text="import b", window="#L261-L560"), code("b.py")],
            structure={"file_edges": [("a.py", "b.py")]})
        self.assertEqual(idx.edges("a.py", EDGE_DEPENDENCIES)[0].evidence_ref,
                         "code:a.py#L261-L560")

    def test_an_import_no_indexed_window_shows_is_dropped_not_mis_cited(self):
        idx = build_entity_index(
            [code("a.py", text="x = 1"), code("b.py")],
            structure={"file_edges": [("a.py", "b.py")]})
        self.assertEqual(idx.targets("a.py", EDGE_DEPENDENCIES), [])

    def test_without_structure_dependencies_are_empty_and_said_to_be(self):
        idx = build_entity_index([code("a.py")])
        self.assertEqual(idx.targets("a.py", EDGE_DEPENDENCIES), [])
        self.assertTrue(any("nothing looked" in l for l in idx.limitations))

    def test_an_import_edge_to_an_unindexed_file_is_dropped(self):
        idx = build_entity_index([code("a.py", text="import gone")],
                                 structure={"file_edges": [("a.py", "gone.py")]})
        self.assertEqual(idx.targets("a.py", EDGE_DEPENDENCIES), [])


class DisciplineTests(unittest.TestCase):
    CHUNKS = [
        pr(400, "PR #400: x\n\nCloses #372.\n\nFiles changed (1): a.py (+1/-1)"),
        pr(410, "PR #410: y\n\nFiles changed (1): a.py (+1/-1)"),
        issue(372), code("a.py"),
        Chunk(ref="commit:abc", source="commit", text="COMMIT abc: x (#400)"),
    ]

    def _all(self, idx):
        return sorted((e.kind, e.source_ref, e.target)
                      for bucket in idx._by_source.values() for e in bucket)

    def test_deterministic_under_reordered_input(self):
        a = build_entity_index(self.CHUNKS)
        b = build_entity_index(list(reversed(self.CHUNKS)))
        self.assertEqual(self._all(a), self._all(b))

    def test_every_edge_names_an_indexed_chunk_as_its_proof(self):
        refs = {c.ref for c in self.CHUNKS}
        idx = build_entity_index(self.CHUNKS)
        for bucket in idx._by_source.values():
            for edge in bucket:
                self.assertIn(edge.evidence_ref, refs, edge)

    def test_no_edge_carries_a_score_or_rank(self):
        idx = build_entity_index(self.CHUNKS)
        edge = idx.edges("pr:400", EDGE_LINKED_ISSUES)[0]
        for banned in ("score", "rank", "confidence", "weight"):
            self.assertFalse(hasattr(edge, banned))

    def test_unknown_edge_kind_raises_rather_than_returning_empty(self):
        idx = build_entity_index(self.CHUNKS)
        with self.assertRaises(ValueError):
            idx.edges("pr:400", "caused_by")

    def test_pure_opens_no_file_and_no_socket(self):
        import builtins
        import socket
        with mock.patch.object(builtins, "open", side_effect=AssertionError("opened a file")), \
             mock.patch.object(socket, "socket", side_effect=AssertionError("opened a socket")):
            build_entity_index(self.CHUNKS)

    def test_empty_corpus_yields_an_index_that_answers_honestly(self):
        idx = build_entity_index([])
        self.assertEqual(idx.targets("pr:1", EDGE_LINKED_ISSUES), [])
        self.assertTrue(idx.limitations)


if __name__ == "__main__":
    unittest.main()
