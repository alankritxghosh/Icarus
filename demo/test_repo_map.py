# demo/test_repo_map.py
"""The repository map's contract, written before the implementation.

The map is the first thing Icarus says about a repo BEFORE anyone asks a
question, so it is the first surface that can over-claim. Every test here
exists to pin one honesty property, not a formatting preference:

- it may only name files it actually indexed,
- it may never present the ingest EXCLUSION RULES as observed excluded files,
- it may never read "not truncated" as "complete",
- and it must be a pure function of refs the corpus already holds -- no model
  call, no network, no re-reading chunks.jsonl.

Stdlib only, always runs.
"""

import unittest

from evals.corpus import Chunk

from .repo_map import build_map


def _chunks(refs, texts=None):
    texts = texts or {}
    return [Chunk(ref=r, source=r.split(":", 1)[0], text=texts.get(r, "")) for r in refs]


def build_map_from_refs(refs, status):
    """Every case in this file is expressed as refs; build_map takes chunks."""
    return build_map(_chunks(refs), status)

# A ref list shaped exactly like a real corpus's: source-prefixed, code/doc/
# config carrying a repo-relative path (optionally line-windowed), pr/issue/
# commit carrying an identifier instead of a path.
REFS = [
    "code:llm/cli.py#L1-L300",
    "code:llm/cli.py#L261-L560",
    "code:llm/embeddings.py",
    "code:llm/default_plugins/openai_models.py",
    "code:setup.py",
    "code:web/app.ts",
    "doc:README.md",
    "doc:docs/plugins.md",
    "config:pyproject.toml",
    "pr:1435",
    "pr:1436",
    "issue:900",
    "commit:c4367f231b5dc54f23f2983828562ce3a7555a8a",
]

STATUS = {"state": "ready", "repo": "simonw/llm", "commit": "94769b8",
          "counts": {"pr": 2, "issue": 1}, "error": None, "phase": None,
          "private": False, "truncated": False, "indexing": False}


def _status(**overrides):
    return {**STATUS, **overrides}


class MapNamesOnlyIndexedFilesTests(unittest.TestCase):
    """Requirement 1: every file the map names exists in the indexed corpus.

    This is the map's version of groundedness. A map that infers a file it did
    not index is the same failure as a citation to evidence that was never
    retrieved -- and it would be far harder to spot, because a plausible file
    tree looks like knowledge.
    """

    def test_every_named_documentation_file_is_an_indexed_ref(self):
        m = build_map_from_refs(REFS, STATUS)
        indexed_paths = {r.split(":", 1)[1].split("#")[0] for r in REFS
                         if r.split(":", 1)[0] in ("code", "doc", "config")}
        for path in m["indexed_documentation"]["files"]:
            self.assertIn(path, indexed_paths)

    def test_the_named_readme_is_an_indexed_ref(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertEqual(m["indexed_documentation"]["readme"], "README.md")

    def test_every_named_directory_came_from_an_indexed_path(self):
        m = build_map_from_refs(REFS, STATUS)
        real_tops = {"llm", "web", "docs", "."}
        self.assertTrue(set(m["indexed_directories"]) <= real_tops)

    def test_file_count_is_distinct_paths_not_chunks(self):
        # llm/cli.py is TWO chunks and ONE file. Reporting 9 files when there
        # are 8 would be a small lie that compounds across every later claim.
        m = build_map_from_refs(REFS, STATUS)
        self.assertEqual(m["indexed_file_count"], 8)

    def test_chunk_counts_are_labelled_as_chunks_not_files(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertEqual(m["indexed_chunks_by_source"]["code"], 6)
        self.assertEqual(m["indexed_chunks_by_source"]["pr"], 2)
        self.assertEqual(m["indexed_chunks_by_source"]["issue"], 1)
        self.assertEqual(m["indexed_chunks_by_source"]["commit"], 1)


class DeterminismTests(unittest.TestCase):
    """Requirement 2: the same corpus always produces the same map."""

    def test_two_builds_of_the_same_refs_are_identical(self):
        self.assertEqual(build_map_from_refs(REFS, STATUS), build_map_from_refs(REFS, STATUS))

    def test_ref_order_does_not_change_the_map(self):
        self.assertEqual(build_map_from_refs(REFS, STATUS), build_map_from_refs(list(reversed(REFS)), STATUS))

    def test_an_empty_corpus_is_zero_not_an_error(self):
        m = build_map_from_refs([], STATUS)
        self.assertEqual(m["indexed_file_count"], 0)
        self.assertEqual(m["indexed_documentation"]["readme"], None)


class HonestAbsenceTests(unittest.TestCase):
    """Requirement 3: a missing README is REPORTED, not silently omitted.

    "No README was indexed" and "I forgot to look" render identically if the
    key simply disappears -- and one of them is a claim about the customer's
    repository.
    """

    def test_a_corpus_with_no_readme_says_so_explicitly(self):
        refs = [r for r in REFS if r != "doc:README.md"]
        m = build_map_from_refs(refs, STATUS)
        self.assertIn("readme", m["indexed_documentation"])
        self.assertIsNone(m["indexed_documentation"]["readme"])

    def test_no_readme_is_never_invented_from_a_similar_file(self):
        m = build_map_from_refs(["doc:docs/plugins.md", "code:a.py"], STATUS)
        self.assertIsNone(m["indexed_documentation"]["readme"])
        self.assertEqual(m["indexed_documentation"]["files"], ["docs/plugins.md"])


class ContributingDocTests(unittest.TestCase):
    """The map resolves the repo's contributing guide, for the same reason it
    resolves the README.

    Measured 2026-07-29: the tour's `conventions` step answered 9/10 but only
    4/9 of those said anything -- every hollow one cited a COMMIT MESSAGE that
    merely mentioned a contributing guide ("added in commit a6ed0f2") rather
    than the guide itself. Seven of the ten repos had the document indexed the
    whole time; retrieval just never reached it. Same failure `purpose` had
    before the README was addressed by path.
    """

    def test_a_root_contributing_file_is_found(self):
        m = build_map_from_refs(["doc:CONTRIBUTING.md", "code:a.py"], STATUS)
        self.assertEqual(m["indexed_documentation"]["contributing"], "CONTRIBUTING.md")

    def test_a_nested_or_dotted_location_is_found(self):
        for path in ("docs/contributing.rst", ".github/CONTRIBUTING.md",
                     "docs/dev/contributing.rst"):
            with self.subTest(path=path):
                m = build_map_from_refs([f"doc:{path}"], STATUS)
                self.assertEqual(m["indexed_documentation"]["contributing"], path)

    def test_the_shallowest_wins_so_a_vendored_copy_cannot_outrank_the_real_one(self):
        # lazygit really does carry pkg/gocui/CONTRIBUTING.md alongside its own.
        m = build_map_from_refs(["doc:pkg/gocui/CONTRIBUTING.md",
                                 "doc:CONTRIBUTING.md"], STATUS)
        self.assertEqual(m["indexed_documentation"]["contributing"], "CONTRIBUTING.md")

    def test_a_code_of_conduct_is_not_a_contributing_guide(self):
        # Adjacent, and not an answer to "what conventions do you expect?".
        m = build_map_from_refs(["doc:CODE_OF_CONDUCT.md"], STATUS)
        self.assertIsNone(m["indexed_documentation"]["contributing"])

    def test_absence_is_reported_not_omitted(self):
        m = build_map_from_refs(["doc:README.md"], STATUS)
        self.assertIn("contributing", m["indexed_documentation"])
        self.assertIsNone(m["indexed_documentation"]["contributing"])

    def test_it_is_always_an_indexed_path(self):
        m = build_map_from_refs(REFS, STATUS)
        c = m["indexed_documentation"]["contributing"]
        if c is not None:
            self.assertIn(c, m["indexed_documentation"]["files"])


class TruncationTests(unittest.TestCase):
    """Requirements 4 and 5: truncation is surfaced, and its ABSENCE is not
    quietly upgraded into a completeness claim."""

    def test_a_truncated_corpus_is_flagged(self):
        m = build_map_from_refs(REFS, _status(truncated=True))
        self.assertIs(m["corpus_truncated"], True)

    def test_truncation_is_also_stated_in_words(self):
        m = build_map_from_refs(REFS, _status(truncated=True))
        self.assertTrue(any("cap" in l.lower() or "truncat" in l.lower()
                            for l in m["limitations"]))

    def test_an_untruncated_corpus_is_never_called_complete(self):
        m = build_map_from_refs(REFS, _status(truncated=False))
        self.assertIs(m["corpus_truncated"], False)
        blob = repr(m).lower()
        for claim in ("complete coverage", "fully indexed", "everything in the repo",
                      "all files", "complete", "total_file"):
            self.assertNotIn(claim, blob)

    def test_the_indexed_only_caveat_is_present_even_when_untruncated(self):
        # The standing limitation is about what a corpus-derived map CAN know,
        # which does not change when nothing was truncated.
        m = build_map_from_refs(REFS, _status(truncated=False))
        self.assertTrue(any("indexed" in l.lower() for l in m["limitations"]))
        self.assertTrue(m["limitations"])


class ExclusionRulesAreRulesTests(unittest.TestCase):
    """Requirement 6: the ingest deny-lists are reported as RULES that were
    applied, never as evidence that particular files were excluded.

    Icarus never observed the files it skipped -- `classify_file` returns None
    and the walk moves on, recording nothing. Publishing an excluded-file count
    or list would be fabricated precision.
    """

    def test_rules_are_present_and_are_plain_descriptions(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertTrue(m["exclusion_rules"])
        for rule in m["exclusion_rules"]:
            self.assertIsInstance(rule, str)

    def test_no_excluded_file_count_or_list_is_published(self):
        m = build_map_from_refs(REFS, STATUS)
        for forbidden in ("excluded_files", "excluded_file_count", "skipped_files",
                          "total_files", "total_file_count", "repository_file_count"):
            self.assertNotIn(forbidden, m)

    def test_the_rules_are_disclaimed_as_unobserved(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertTrue(any("rule" in l.lower() for l in m["limitations"]))

    def test_the_rules_are_derived_from_ingest_not_restated(self):
        # A hand-copied rule list drifts silently the moment ingest changes.
        from evals.ingest import _DENY_DIR_SEGMENTS
        blob = " ".join(build_map_from_refs(REFS, STATUS)["exclusion_rules"])
        for segment in _DENY_DIR_SEGMENTS:
            self.assertIn(segment, blob)


class ReadinessTests(unittest.TestCase):
    """The map must say which SEARCH is live, because during the lexical-only
    window an abstention means "I haven't finished reading", not "nobody wrote
    this down" (demo/library.py's _indexing flag)."""

    def test_semantic_indexing_in_progress_mirrors_the_libraries_flag(self):
        self.assertIs(build_map_from_refs(REFS, _status(indexing=True))["semantic_indexing_in_progress"], True)
        self.assertIs(build_map_from_refs(REFS, _status(indexing=False))["semantic_indexing_in_progress"], False)

    def test_lexical_search_is_ready_whenever_a_corpus_is_loaded(self):
        self.assertIs(build_map_from_refs(REFS, STATUS)["lexical_search_ready"], True)
        self.assertIs(build_map_from_refs([], STATUS)["lexical_search_ready"], False)

    def test_repo_and_commit_come_from_the_status_snapshot(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertEqual(m["repo"], "simonw/llm")
        self.assertEqual(m["commit"], "94769b8")


class LanguageGroupingTests(unittest.TestCase):
    def test_files_are_grouped_by_language_by_distinct_path(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertEqual(m["indexed_languages"]["Python"], 4)  # cli, embeddings, openai_models, setup
        self.assertEqual(m["indexed_languages"]["TypeScript"], 1)
        self.assertEqual(m["indexed_languages"]["Markdown"], 2)

    def test_an_unmapped_extension_falls_back_to_the_extension_itself(self):
        # Better an honest ".fake" than silently dropping the file from the
        # totals, which would make the language counts disagree with
        # indexed_file_count.
        m = build_map_from_refs(["code:weird/thing.fake"], STATUS)
        self.assertEqual(m["indexed_languages"], {".fake": 1})

    def test_language_totals_equal_the_file_count(self):
        m = build_map_from_refs(REFS, STATUS)
        self.assertEqual(sum(m["indexed_languages"].values()), m["indexed_file_count"])


class AuxiliaryTreeTests(unittest.TestCase):
    """Committed test data is LABELLED, never quietly removed from the totals.

    Found by running the tour on this repo: 348 of 500 indexed files sat under
    `evals/fixtures/`, so the map read as an Objective-C++/Kotlin/Swift mobile
    codebase. Every number was true and the impression was false, which is
    worse than either -- the same failure this product exists to avoid, moved
    from answers into a summary.

    Excluding fixtures from the counts would "fix" it by breaking the map's one
    contract: that it describes what Icarus READ. So the totals stay whole and
    the auxiliary share is named beside them.
    """

    AUX = ["code:evals/fixtures/rn/App.tsx", "code:evals/fixtures/rn/Main.kt",
           "code:tests/helpers.py", "code:demo/test_server.py"]
    REAL = ["code:demo/server.py", "code:evals/ingest.py"]

    def test_auxiliary_files_are_counted_and_named(self):
        m = build_map_from_refs(self.AUX + self.REAL, STATUS)
        self.assertEqual(m["indexed_auxiliary"]["file_count"], 4)
        self.assertTrue(m["indexed_auxiliary"]["rule"].strip())

    def test_the_totals_still_include_every_auxiliary_file(self):
        # The honesty property: labelling must not reweight what was indexed.
        m = build_map_from_refs(self.AUX + self.REAL, STATUS)
        self.assertEqual(m["indexed_file_count"], 6)
        self.assertEqual(sum(m["indexed_languages"].values()), 6)
        self.assertEqual(sum(m["indexed_directories"].values()), 6)

    def test_a_corpus_with_no_auxiliary_files_reports_zero_not_silence(self):
        m = build_map_from_refs(self.REAL, STATUS)
        self.assertEqual(m["indexed_auxiliary"]["file_count"], 0)
        self.assertIn("rule", m["indexed_auxiliary"])

    def test_the_auxiliary_rule_matches_the_entry_point_rule(self):
        # One definition, used twice -- otherwise the map could call a file
        # test data while the entry-point list still offers it as a place to
        # start reading.
        from demo.entry_points import is_auxiliary_path
        for ref in self.AUX:
            self.assertTrue(is_auxiliary_path(ref.split(":", 1)[1]), ref)
        for ref in self.REAL:
            self.assertFalse(is_auxiliary_path(ref.split(":", 1)[1]), ref)


class PurityTests(unittest.TestCase):
    """Requirement 7: no model call is required to produce the map."""

    def test_build_map_takes_no_provider_or_pipeline(self):
        import inspect
        params = set(inspect.signature(build_map).parameters)
        self.assertEqual(params, {"chunks", "status"})

    def test_build_map_never_touches_the_network_or_disk(self):
        import builtins
        import socket
        real_open, real_socket = builtins.open, socket.socket

        def _no(*a, **k):
            raise AssertionError("build_map must not read files or open sockets")

        builtins.open, socket.socket = _no, _no
        try:
            build_map_from_refs(REFS, STATUS)
        finally:
            builtins.open, socket.socket = real_open, real_socket


if __name__ == "__main__":
    unittest.main()


class StructureIntegrationTests(unittest.TestCase):
    """The map carries the derived dependency structure (Brick S).

    The map already answers "what did Icarus read". Structure answers "how is
    it arranged" -- the question the onboarding probe measured worst (2 of 10
    real repositories) and the one anchoring to a README provably could not
    fix, because a README says what a project is FOR, not how its code is laid
    out.
    """

    def _map(self, chunks):
        return build_map(chunks, {"repo": "o/r", "commit": "abc"})

    def test_the_map_carries_the_structure_block(self):
        chunks = [
            Chunk(ref="code:app/api.py", source="code",
                  text="from app.store import save\n"),
            Chunk(ref="code:app/store.py", source="code", text="def save():\n    pass\n"),
        ]
        structure = self._map(chunks)["indexed_structure"]
        self.assertEqual(structure["file_edges"], [("app/api.py", "app/store.py")])

    def test_a_repo_with_no_resolvable_imports_reports_empty_structure(self):
        chunks = [Chunk(ref="doc:README.md", source="doc", text="# hi\n")]
        structure = self._map(chunks)["indexed_structure"]
        self.assertEqual(structure["components"], [])
        self.assertTrue(structure["limitations"])

    def test_structure_names_only_files_the_map_also_indexed(self):
        chunks = [
            Chunk(ref="code:app/api.py", source="code",
                  text="from app.store import save\n"),
            Chunk(ref="code:app/store.py", source="code", text="def save():\n    pass\n"),
        ]
        result = self._map(chunks)
        indexed = {c.ref.split(":", 1)[1].split("#", 1)[0] for c in chunks}
        for source, target in result["indexed_structure"]["file_edges"]:
            self.assertIn(source, indexed)
            self.assertIn(target, indexed)

    def test_structure_is_named_indexed_like_every_other_map_field(self):
        # The map's one contract: every field describes what Icarus READ, never
        # what exists in the repository. Structure is derived from indexed
        # chunks only, so it carries the same prefix and the same promise.
        result = self._map([])
        self.assertIn("indexed_structure", result)
