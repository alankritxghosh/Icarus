# demo/test_structure.py
"""Structural comprehension's contract, written before the implementation.

The tests that matter here are the NEGATIVE ones. A dependency graph is the
easiest claim in this product to make confidently and wrongly: a first probe
pass over ten real repositories produced a `pkg -> demo` edge spanning 566
files in jesseduffield/lazygit, which was pure fiction -- Go's
`.../pkg/config` resolved onto an unrelated `demo/config.yml` by bare-name
match. It looked exactly like the true edges beside it.

So most of what is pinned below is what must NOT be emitted.
"""

import builtins
import socket
import unittest
from unittest import mock

from evals.corpus import Chunk

from .structure import build_structure


def code(path, text, window=None):
    ref = f"code:{path}" + (f"#{window}" if window else "")
    return Chunk(ref=ref, source="code", text=text)


class PythonResolutionTests(unittest.TestCase):
    def test_absolute_package_import_becomes_an_edge(self):
        chunks = [
            code("app/api.py", "from app.store import save\n"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        result = build_structure(chunks)
        self.assertIn(("app/api.py", "app/store.py"), result["file_edges"])

    def test_relative_import_resolves_against_the_importing_file(self):
        chunks = [
            code("app/api.py", "from .store import save\n"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        self.assertIn(("app/api.py", "app/store.py"),
                      build_structure(chunks)["file_edges"])

    def test_src_layout_package_resolves(self):
        chunks = [
            code("src/pkg/cli.py", "from pkg.core import run\n"),
            code("src/pkg/core.py", "def run():\n    pass\n"),
        ]
        self.assertIn(("src/pkg/cli.py", "src/pkg/core.py"),
                      build_structure(chunks)["file_edges"])

    def test_package_import_resolves_to_its_init(self):
        chunks = [
            code("app/cli.py", "from app.store import save\n"),
            code("app/store/__init__.py", "def save():\n    pass\n"),
        ]
        self.assertIn(("app/cli.py", "app/store/__init__.py"),
                      build_structure(chunks)["file_edges"])

    def test_third_party_import_is_never_an_edge(self):
        chunks = [
            code("app/api.py", "import httpx\nfrom click import group\n"),
            code("app/store.py", "pass\n"),
        ]
        result = build_structure(chunks)
        self.assertEqual(result["file_edges"], [])
        self.assertGreater(result["unresolved_import_count"], 0)


class FabricationGuardTests(unittest.TestCase):
    """The regression suite for the false-edge class found by the probe."""

    def test_bare_name_never_resolves_to_an_unrelated_directory(self):
        # The exact live fabrication, reduced: `.../pkg/config` must not land
        # on an unrelated `demo/config/` just because the final segment
        # matches. In lazygit that one bare-name match invented a `pkg -> demo`
        # dependency across 566 files, indistinguishable from the true edges
        # beside it.
        #
        # The decoy is deliberately a GO file: an earlier version of this test
        # used `demo/config.yml`, which the language filter rejected before the
        # segment rule was ever reached -- so it passed with the bug present
        # and proved nothing.
        chunks = [
            code("pkg/app/app.go",
                 'import (\n\t"github.com/o/r/pkg/config"\n)\n'),
            code("demo/config/settings.go", "package config\n"),
        ]
        result = build_structure(chunks)
        self.assertEqual(result["package_edges"], [])

    def test_a_non_code_file_is_never_an_import_target(self):
        chunks = [
            code("pkg/app/app.go",
                 'import (\n\t"github.com/o/r/pkg/config"\n)\n'),
            Chunk(ref="config:demo/config.yml", source="config", text="theme: dark\n"),
        ]
        self.assertEqual(build_structure(chunks)["package_edges"], [])

    def test_an_edge_never_names_an_unindexed_file(self):
        chunks = [code("app/api.py", "from app.missing import thing\n")]
        result = build_structure(chunks)
        self.assertEqual(result["file_edges"], [])

    def test_python_import_never_resolves_to_another_language(self):
        chunks = [
            code("app/api.py", "from app.store import save\n"),
            code("app/store.go", "package store\n"),
        ]
        self.assertEqual(build_structure(chunks)["file_edges"], [])

    def test_a_file_never_depends_on_itself(self):
        chunks = [code("app/api.py", "from app.api import thing\n")]
        self.assertEqual(build_structure(chunks)["file_edges"], [])

    def test_import_quoted_inside_a_pr_body_is_not_structure(self):
        chunks = [
            Chunk(ref="pr:42", source="pr",
                  text="PR 42\n\nfrom app.store import save\n"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        self.assertEqual(build_structure(chunks)["file_edges"], [])

    def test_no_imports_anywhere_yields_no_components_rather_than_a_guess(self):
        # A flat single-package Go repo (spf13/cobra: 25 of 36 files at the
        # root) has NO internal import edges by construction -- same-package
        # Go files never import each other. Measured, not hypothesised.
        chunks = [
            code("command.go", "package cobra\n\nfunc Execute() {}\n"),
            code("args.go", "package cobra\n\nfunc Args() {}\n"),
        ]
        result = build_structure(chunks)
        self.assertEqual(result["file_edges"], [])
        self.assertEqual(result["package_edges"], [])
        self.assertEqual(result["components"], [])


class JavaScriptResolutionTests(unittest.TestCase):
    def test_relative_import_with_extension_resolves(self):
        chunks = [
            code("index.js", "import {run} from './lib/run.js';\n"),
            code("lib/run.js", "export function run() {}\n"),
        ]
        self.assertIn(("index.js", "lib/run.js"),
                      build_structure(chunks)["file_edges"])

    def test_parent_relative_import_resolves(self):
        chunks = [
            code("lib/a/one.js", "import x from '../two.js';\n"),
            code("lib/two.js", "export default 1;\n"),
        ]
        self.assertIn(("lib/a/one.js", "lib/two.js"),
                      build_structure(chunks)["file_edges"])

    def test_require_resolves(self):
        chunks = [
            code("index.js", "const run = require('./lib/run');\n"),
            code("lib/run.js", "module.exports = {};\n"),
        ]
        self.assertIn(("index.js", "lib/run.js"),
                      build_structure(chunks)["file_edges"])

    def test_bare_specifier_is_a_dependency_not_an_edge(self):
        chunks = [
            code("index.js", "import execa from 'execa';\n"),
            code("lib/execa.js", "export default 1;\n"),
        ]
        self.assertEqual(build_structure(chunks)["file_edges"], [])


class GoResolutionTests(unittest.TestCase):
    def test_module_path_resolves_to_the_package_directory(self):
        chunks = [
            code("cmd/main.go", 'import (\n\t"github.com/o/r/pkg/gui"\n)\n'),
            code("pkg/gui/gui.go", "package gui\n"),
        ]
        self.assertIn(("cmd/main.go", "pkg/gui"),
                      build_structure(chunks)["package_edges"])

    def test_a_go_package_import_never_becomes_a_file_level_edge(self):
        # Caught by verifying emitted edges against the real source of ten
        # repositories: 19 of 20 sampled cobra edges and 12 of 12 glow edges
        # named a file the importer never mentions. A Go import names a
        # PACKAGE, so resolving it to one file inside that package meant
        # picking the alphabetically-first one and stating it as fact --
        # `active_help.go` in cobra, `config_cmd.go` in glow. The component
        # edge was right the whole time; the file-level claim was invented.
        chunks = [
            code("cmd/main.go", 'import (\n\t"github.com/o/r/pkg/gui"\n)\n'),
            code("pkg/gui/aaa.go", "package gui\n"),
            code("pkg/gui/zzz.go", "package gui\n"),
        ]
        result = build_structure(chunks)
        self.assertEqual(result["file_edges"], [])
        self.assertEqual(result["package_edges"], [("cmd/main.go", "pkg/gui")])

    def test_top_level_package_directory_resolves(self):
        # Found by running this over charmbracelet/glow, not by unit test: a
        # suffix WALK could not reach a one-segment package directory, so a
        # repo whose packages sit at the root scored zero. The module path is
        # host/owner/repo, so the repo-relative part is what follows segment 3
        # -- an exact match, which is both higher recall and stricter than the
        # walk it replaces.
        chunks = [
            code("main.go", 'import (\n\t"github.com/charmbracelet/glow/ui"\n)\n'),
            code("ui/ui.go", "package ui\n"),
        ]
        self.assertIn(("main.go", "ui"),
                      build_structure(chunks)["package_edges"])

    def test_repository_root_package_resolves(self):
        # spf13/cobra: `doc/` imports the root package as the bare module path.
        chunks = [
            code("doc/man_docs.go", 'import (\n\t"github.com/spf13/cobra"\n)\n'),
            code("command.go", "package cobra\n"),
        ]
        self.assertIn(("doc/man_docs.go", "."),
                      build_structure(chunks)["package_edges"])

    def test_standard_library_import_is_never_an_edge(self):
        chunks = [
            code("cmd/main.go", 'import (\n\t"path/filepath"\n)\n'),
            code("pkg/filepath/x.go", "package filepath\n"),
        ]
        self.assertEqual(build_structure(chunks)["package_edges"], [])


class ComponentTests(unittest.TestCase):
    def test_components_are_directories_not_top_level_buckets(self):
        # Measured on lazygit: grouping by TOP-LEVEL directory collapses 1,591
        # real file edges into 2 component edges, because the whole project
        # lives under `pkg/`. The directory a file sits in is the unit a
        # developer actually reasons about.
        chunks = [
            code("pkg/gui/gui.go", 'import (\n\t"github.com/o/r/pkg/commands"\n)\n'),
            code("pkg/commands/git.go", "package commands\n"),
        ]
        components = {c["path"]: c for c in build_structure(chunks)["components"]}
        self.assertIn("pkg/gui", components)
        self.assertIn("pkg/commands", components)
        self.assertEqual(components["pkg/gui"]["depends_on"], ["pkg/commands"])

    def test_every_component_edge_carries_an_indexed_evidence_ref(self):
        chunks = [
            code("app/api.py", "from app.store import save\n", "L1-L50"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        result = build_structure(chunks)
        refs = {c.ref for c in chunks}
        for component in result["components"]:
            for ref in component["evidence_refs"]:
                self.assertIn(ref, refs)

    def test_components_are_sorted_most_depended_on_first(self):
        chunks = [
            code("a/one.py", "from core.x import y\n"),
            code("b/two.py", "from core.x import y\n"),
            code("core/x.py", "y = 1\n"),
        ]
        result = build_structure(chunks)
        self.assertEqual(result["components"][0]["path"], "core")
        self.assertEqual(result["components"][0]["depended_on_by"], ["a", "b"])

    def test_output_is_deterministic_under_reordered_input(self):
        chunks = [
            code("a/one.py", "from core.x import y\n"),
            code("b/two.py", "from core.x import y\n"),
            code("core/x.py", "y = 1\n"),
        ]
        self.assertEqual(build_structure(chunks), build_structure(list(reversed(chunks))))

    def test_no_score_or_rank_field_is_published(self):
        chunks = [
            code("app/api.py", "from app.store import save\n"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        result = build_structure(chunks)
        for component in result["components"]:
            self.assertNotIn("score", component)
            self.assertNotIn("rank", component)
            self.assertNotIn("importance", component)


class CoreFileTests(unittest.TestCase):
    """The component view alone is not an answer for a single-package repo.

    Measured on the ten probe repositories: 77 of psf/requests' 105 edges sit
    INSIDE one component, so the component graph shows `src/requests`, `tests`
    and `docs` and hides everything a reader actually wants. The file-level
    in-degree is the real arrangement there -- and it recovers exactly the
    modules a maintainer would name (`models.py`, `compat.py`, `structures.py`).
    """

    def test_the_most_depended_on_files_are_reported_with_their_counts(self):
        chunks = [
            code("app/a.py", "from app.core import x\n"),
            code("app/b.py", "from app.core import x\n"),
            code("app/c.py", "from app.a import y\n"),
            code("app/core.py", "x = 1\n"),
        ]
        core = build_structure(chunks)["most_depended_on_files"]
        self.assertEqual(core[0]["path"], "app/core.py")
        self.assertEqual(core[0]["depended_on_by_count"], 2)

    def test_each_core_file_carries_an_indexed_evidence_ref(self):
        chunks = [
            code("app/a.py", "from app.core import x\n"),
            code("app/core.py", "x = 1\n"),
        ]
        refs = {c.ref for c in chunks}
        for entry in build_structure(chunks)["most_depended_on_files"]:
            self.assertIn(entry["evidence_ref"], refs)

    def test_a_file_nothing_imports_is_not_listed(self):
        chunks = [
            code("app/a.py", "from app.core import x\n"),
            code("app/core.py", "x = 1\n"),
            code("app/orphan.py", "y = 2\n"),
        ]
        listed = {e["path"] for e in build_structure(chunks)["most_depended_on_files"]}
        self.assertNotIn("app/orphan.py", listed)

    def test_no_core_files_when_nothing_resolves(self):
        self.assertEqual(build_structure([])["most_depended_on_files"], [])


class HonestyTests(unittest.TestCase):
    def test_unresolved_imports_are_counted_not_hidden(self):
        chunks = [code("app/api.py", "import httpx\nimport click\nimport os\n")]
        self.assertEqual(build_structure(chunks)["unresolved_import_count"], 3)

    def test_limitations_are_always_published(self):
        self.assertTrue(build_structure([])["limitations"])

    def test_the_unresolved_count_is_explained_as_mostly_third_party(self):
        # Measured on the committed simonw/llm corpus: 4,706 "unresolved"
        # imports, nearly all of them httpx/click/dataclasses and the rest of
        # the standard library. A bare number that large reads as "Icarus
        # failed to understand this codebase" when it means the opposite --
        # those imports resolved to nothing INTERNAL because they are not
        # internal. The count stays (it is a real observation) and the
        # limitation says what it counts.
        text = " ".join(build_structure([])["limitations"]).lower()
        self.assertIn("third-party", text)

    def test_an_unanalysed_language_is_named_not_silently_ignored(self):
        # Rust, Java, Ruby and the rest have no resolver here. Reporting zero
        # structure for a Rust repository without saying WHY reads as "this
        # project has no internal structure", which is false and is the
        # over-claim this module exists to avoid. Found on rust-lang/mdBook,
        # which produced 0 edges and only 1 unresolved import -- the count
        # implied it had looked, and it had not.
        chunks = [
            code("src/main.rs", "use crate::book::Book;\n"),
            code("src/book.rs", "pub struct Book;\n"),
        ]
        result = build_structure(chunks)
        self.assertIn("Rust", result["unanalysed_languages"])

    def test_an_analysed_language_is_not_listed_as_unanalysed(self):
        chunks = [
            code("app/api.py", "from app.store import save\n"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        self.assertEqual(build_structure(chunks)["unanalysed_languages"], [])

    def test_empty_corpus_yields_empty_structure_not_an_error(self):
        result = build_structure([])
        self.assertEqual(result["file_edges"], [])
        self.assertEqual(result["components"], [])

    def test_is_pure_no_file_or_socket_access(self):
        chunks = [
            code("app/api.py", "from app.store import save\n"),
            code("app/store.py", "def save():\n    pass\n"),
        ]
        with mock.patch.object(builtins, "open",
                               side_effect=AssertionError("opened a file")), \
             mock.patch.object(socket, "socket",
                               side_effect=AssertionError("opened a socket")):
            build_structure(chunks)


if __name__ == "__main__":
    unittest.main()
