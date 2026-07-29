# demo/test_entry_points.py
"""Entry-point detection's contract, written before the implementation.

"Where do I start reading?" is the second question anyone has about an
unfamiliar repo, and it is the first one Icarus could only answer by guessing.
So the whole design is rules-only, and these tests pin that:

- every detected entry point names the RULE that produced it and the indexed
  ref that is its EVIDENCE,
- a rule may only name a file that is actually in the indexed corpus,
- when no rule fires the answer is an empty list -- never a ranked guess,
- and nothing here scores, weights or ranks anything.

Stdlib only, always runs. No model call, no network, no filesystem.
"""

import unittest

from evals.corpus import Chunk

from .entry_points import detect_entry_points


def _c(ref, text="", source=None):
    return Chunk(ref=ref, source=source or ref.split(":", 1)[0], text=text)


PYPROJECT = """
[project]
name = "llm"

[project.scripts]
llm = "llm.runner:main"
"""


class RuleFiringTests(unittest.TestCase):
    """Each rule fires on a real positive case and names itself."""

    def test_a_declared_console_script_resolves_to_its_indexed_module(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT), _c("code:llm/runner.py", "def main(): ...")]
        found = detect_entry_points(chunks)
        self.assertEqual([e["path"] for e in found], ["llm/runner.py"])
        rule = found[0]["rules"][0]
        self.assertEqual(rule["rule"], "pyproject-console-script")
        self.assertEqual(rule["evidence_ref"], "config:pyproject.toml")
        self.assertIn("llm", rule["detail"])

    def test_a_src_layout_console_script_resolves_too(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT), _c("code:src/llm/runner.py", "def main(): ...")]
        self.assertEqual([e["path"] for e in detect_entry_points(chunks)], ["src/llm/runner.py"])

    def test_a_package_module_console_script_resolves_to_its_init(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT), _c("code:llm/runner/__init__.py", "x = 1")]
        self.assertEqual([e["path"] for e in detect_entry_points(chunks)], ["llm/runner/__init__.py"])

    def test_a_python_main_guard_is_an_entry_point(self):
        chunks = [_c("code:tool.py", 'if __name__ == "__main__":\n    main()\n')]
        found = detect_entry_points(chunks)
        self.assertEqual(found[0]["path"], "tool.py")
        self.assertEqual(found[0]["rules"][0]["rule"], "python-main-guard")

    def test_a_single_quoted_main_guard_counts_too(self):
        chunks = [_c("code:tool.py", "if __name__ == '__main__':\n    main()\n")]
        self.assertEqual(len(detect_entry_points(chunks)), 1)

    def test_a_file_that_merely_QUOTES_the_guard_is_not_an_entry_point(self):
        # Found by running the rules over this repo: demo/entry_points.py
        # matched itself, because it contains the guard as a string literal.
        # Same class as evals/pipeline.py's "a hex-shaped English word is not
        # a commit SHA" guard -- a substring match on source code will
        # eventually match the code that describes it.
        quoted = '_MAIN_GUARDS = (\'if __name__ == "__main__"\',)\n'
        self.assertEqual(detect_entry_points([_c("code:rules.py", quoted)]), [])

    def test_an_indented_guard_inside_a_function_still_counts(self):
        chunks = [_c("code:tool.py", "def run():\n    if __name__ == '__main__':\n        go()\n")]
        self.assertEqual([e["path"] for e in detect_entry_points(chunks)], ["tool.py"])

    def test_a_test_files_main_guard_is_not_an_application_entry_point(self):
        # Found by running the rules over this repo: `if __name__ ==
        # "__main__": unittest.main()` is boilerplate in EVERY test file --
        # 60+ of them here. Each one is genuinely runnable, so the rule was
        # not wrong; it was answering a different question than the one a new
        # engineer is asking. A list of 70 "entry points" is no more useful
        # than none, and it buries the four that matter.
        for path in ("evals/test_gate.py", "pkg/gate_test.py", "tests/smoke.py",
                     "src/tests/helpers/run.py"):
            with self.subTest(path=path):
                chunks = [_c(f"code:{path}", 'if __name__ == "__main__":\n    unittest.main()\n')]
                self.assertEqual(detect_entry_points(chunks), [])

    def test_a_non_test_main_guard_is_still_an_entry_point(self):
        chunks = [_c("code:evals/run.py", 'if __name__ == "__main__":\n    main()\n')]
        self.assertEqual([e["path"] for e in detect_entry_points(chunks)], ["evals/run.py"])

    def test_committed_fixtures_are_not_entry_points(self):
        # Found by running the tour on this repo, 2026-07-29: two of the five
        # entry points offered were `evals/fixtures/ast_chunking_eval/llm/
        # __main__.py` and `.../cli.py` -- committed COPIES of someone else's
        # project, kept as test data. Nobody starts reading there, and "where
        # do I start?" is the one claim a newcomer acts on immediately.
        for path in ("evals/fixtures/ast_chunking_eval/llm/__main__.py",
                     "evals/fixtures/ast_chunking_eval/llm/cli.py",
                     "pkg/fixture/main.py", "internal/testdata/run.py",
                     "src/__fixtures__/app.py"):
            with self.subTest(path=path):
                chunks = [_c(f"code:{path}", 'if __name__ == "__main__":\n    main()\n')]
                self.assertEqual(detect_entry_points(chunks), [])

    def test_a_real_module_named_like_a_fixture_word_is_still_an_entry_point(self):
        # The rule is a PATH SEGMENT, not a substring: a real module whose name
        # merely contains "fixture" is the project's code, not test data.
        chunks = [_c("code:app/fixtures.py", 'if __name__ == "__main__":\n    main()\n')]
        self.assertEqual([e["path"] for e in detect_entry_points(chunks)], ["app/fixtures.py"])

    def test_a_test_file_is_still_excluded_when_named_conventionally(self):
        # tests/main.py is a test helper, not the application's entry point.
        chunks = [_c("code:tests/main.py", "x = 1\n")]
        self.assertEqual(detect_entry_points(chunks), [])

    def test_a_go_main_function_needs_both_package_main_and_func_main(self):
        chunks = [_c("code:cmd/serve/main.go", "package main\n\nfunc main() {\n}\n")]
        found = detect_entry_points(chunks)
        self.assertEqual(found[0]["rules"][0]["rule"], "go-main-function")

    def test_a_go_library_package_is_not_an_entry_point(self):
        chunks = [_c("code:pkg/util/util.go", "package util\n\nfunc mainish() {\n}\n")]
        self.assertEqual(detect_entry_points(chunks), [])

    def test_a_rust_main_file_is_an_entry_point(self):
        chunks = [_c("code:src/main.rs", "fn main() {}\n")]
        found = detect_entry_points(chunks)
        self.assertEqual(found[0]["rules"][0]["rule"], "rust-main-file")

    def test_a_conventional_filename_is_an_entry_point(self):
        chunks = [_c("code:app/__main__.py", "print(1)\n")]
        found = detect_entry_points(chunks)
        self.assertEqual(found[0]["rules"][0]["rule"], "conventional-filename")
        self.assertIn("__main__.py", found[0]["rules"][0]["detail"])


class OnlyIndexedFilesTests(unittest.TestCase):
    """The groundedness guard: a rule may only name a file Icarus indexed.

    A console script pointing at a module that was never indexed is a real
    situation (an excluded extension, a size cap, a src layout we don't
    understand) and the honest response is silence, not a path we cannot show.
    """

    def test_a_console_script_pointing_at_an_unindexed_module_yields_nothing(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT)]  # no llm/runner.py indexed
        self.assertEqual(detect_entry_points(chunks), [])

    def test_every_named_path_is_an_indexed_path(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT), _c("code:llm/cli.py", ""),
                  _c("code:tool.py", 'if __name__ == "__main__": pass'),
                  _c("code:src/main.rs", "fn main(){}"), _c("pr:1", "main.go")]
        indexed = {c.ref.split(":", 1)[1].split("#")[0] for c in chunks
                   if c.source in ("code", "doc", "config")}
        for e in detect_entry_points(chunks):
            self.assertIn(e["path"], indexed)

    def test_a_pr_body_mentioning_main_never_produces_an_entry_point(self):
        # PR/issue/commit chunks have no file path at all -- they must never
        # be mistaken for one.
        chunks = [_c("pr:12", 'package main\n\nfunc main() {}\nif __name__ == "__main__":')]
        self.assertEqual(detect_entry_points(chunks), [])


class NoGuessingTests(unittest.TestCase):
    """When no rule fires, the answer is nothing."""

    def test_an_ordinary_library_repo_yields_no_entry_points(self):
        chunks = [_c("code:llm/models.py", "class Model: pass\n"),
                  _c("doc:README.md", "# llm\nRun `llm` to start.\n")]
        self.assertEqual(detect_entry_points(chunks), [])

    def test_an_empty_corpus_yields_no_entry_points(self):
        self.assertEqual(detect_entry_points([]), [])

    def test_nothing_is_ranked_or_scored(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT), _c("code:llm/cli.py", ""),
                  _c("code:tool.py", 'if __name__ == "__main__": pass')]
        for e in detect_entry_points(chunks):
            self.assertEqual(set(e), {"path", "rules"})
            for rule in e["rules"]:
                self.assertEqual(set(rule), {"rule", "evidence_ref", "detail"})


class MalformedInputTests(unittest.TestCase):
    """A rule that cannot read its evidence stays silent."""

    def test_an_unparseable_pyproject_is_skipped_not_guessed(self):
        chunks = [_c("config:pyproject.toml", "[project.scripts\nllm = broken"),
                  _c("code:llm/runner.py", "")]
        self.assertEqual(detect_entry_points(chunks), [])

    def test_a_windowed_partial_pyproject_is_skipped_not_guessed(self):
        # A >300-line manifest chunks into windows, and half a TOML file does
        # not parse. Silence beats a half-read manifest.
        chunks = [_c("config:pyproject.toml#L301-L600", 'llm = "llm.runner:main"\n'),
                  _c("code:llm/runner.py", "")]
        self.assertEqual(detect_entry_points(chunks), [])

    def test_a_pyproject_with_no_scripts_table_yields_nothing(self):
        chunks = [_c("config:pyproject.toml", '[project]\nname = "llm"\n'),
                  _c("code:llm/runner.py", "")]
        self.assertEqual(detect_entry_points(chunks), [])


class GroupingAndDeterminismTests(unittest.TestCase):
    def test_two_rules_on_one_file_group_into_one_entry(self):
        # Otherwise "4 entry points" would mean 2 files -- the same
        # chunks-versus-files inflation the map already refuses.
        chunks = [_c("config:pyproject.toml",
                     '[project.scripts]\nllm = "llm.cli:cli"\n'),
                  _c("code:llm/cli.py", 'if __name__ == "__main__": pass')]
        found = detect_entry_points(chunks)
        self.assertEqual(len(found), 1)
        self.assertEqual([r["rule"] for r in found[0]["rules"]],
                         ["conventional-filename", "pyproject-console-script", "python-main-guard"])

    def test_a_file_split_into_windows_is_named_once(self):
        chunks = [_c("code:tool.py#L1-L300", "x = 1\n"),
                  _c("code:tool.py#L261-L560", 'if __name__ == "__main__": pass')]
        found = detect_entry_points(chunks)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["rules"][0]["evidence_ref"], "code:tool.py#L261-L560")

    def test_detection_is_deterministic_and_order_independent(self):
        chunks = [_c("config:pyproject.toml", PYPROJECT), _c("code:llm/cli.py", ""),
                  _c("code:tool.py", 'if __name__ == "__main__": pass'),
                  _c("code:src/main.rs", "fn main(){}")]
        first = detect_entry_points(chunks)
        self.assertEqual(first, detect_entry_points(chunks))
        self.assertEqual(first, detect_entry_points(list(reversed(chunks))))

    def test_paths_are_sorted(self):
        chunks = [_c("code:z.py", 'if __name__ == "__main__": pass'),
                  _c("code:a.py", 'if __name__ == "__main__": pass')]
        self.assertEqual([e["path"] for e in detect_entry_points(chunks)], ["a.py", "z.py"])


class PurityTests(unittest.TestCase):
    def test_detect_takes_only_chunks(self):
        import inspect
        self.assertEqual(set(inspect.signature(detect_entry_points).parameters), {"chunks"})

    def test_detect_never_touches_the_network_or_disk(self):
        import builtins
        import socket
        real_open, real_socket = builtins.open, socket.socket

        def _no(*a, **k):
            raise AssertionError("detect_entry_points must not read files or open sockets")

        builtins.open, socket.socket = _no, _no
        try:
            detect_entry_points([_c("config:pyproject.toml", PYPROJECT), _c("code:llm/cli.py", "")])
        finally:
            builtins.open, socket.socket = real_open, real_socket


if __name__ == "__main__":
    unittest.main()
