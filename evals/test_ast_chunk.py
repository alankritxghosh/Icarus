"""Unit tests for ast_chunk: the AST-aware code chunker.

Stdlib-only and always-run (no fastembed, no corpus, no network) -- the live
recall proof lives in test_ast_chunking_eval.py and self-skips. These lock the
contract: same shape as chunk_text, honest fallbacks, and chunks that actually
fit the embedder's budget.
"""

import ast
import json
import unittest
from pathlib import Path

from .ast_chunk import _MAX_EMITTED_CHUNK_CHARS, _MAX_WHOLE_CLASS_LINES, ast_chunk
from .ingest import chunk_text

_CORPUS_PATH = Path(__file__).parent / "corpus" / "chunks.jsonl"


class AstChunkContractTests(unittest.TestCase):
    def test_splits_top_level_functions_into_separate_chunks(self):
        src = "def alpha():\n    return 1\n\n\ndef beta():\n    return 2\n"
        chunks = ast_chunk(src, "code:m.py")
        bodies = [c["text"] for c in chunks]
        self.assertEqual(len(chunks), 2)
        self.assertTrue(any("def alpha" in b and "def beta" not in b for b in bodies))
        self.assertTrue(any("def beta" in b and "def alpha" not in b for b in bodies))

    def test_refs_use_chunk_texts_window_format(self):
        # The gate resolves a citation by CONTAINMENT in the retrieved window
        # (evals/gate.py _resolve). An AST chunk must therefore look like any
        # other window, or every citation it produces stops grounding.
        src = "def alpha():\n    return 1\n"
        ref = ast_chunk(src, "code:m.py")[0]["ref"]
        self.assertRegex(ref, r"^code:m\.py#L\d+-L\d+$")

    def test_ref_line_range_matches_the_real_source_lines(self):
        src = "# c\n# c\ndef alpha():\n    return 1\n"
        chunk = next(c for c in ast_chunk(src, "code:m.py") if "def alpha" in c["text"])
        self.assertTrue(chunk["ref"].endswith("#L3-L4"), chunk["ref"])

    def test_no_source_key_matching_chunk_text(self):
        # chunk_text deliberately omits "source"; the caller owns the tag.
        for c in ast_chunk("def a():\n    return 1\n", "code:m.py"):
            self.assertNotIn("source", c)

    def test_small_class_stays_whole(self):
        src = "class Tiny:\n    def a(self):\n        return 1\n\n    def b(self):\n        return 2\n"
        chunks = ast_chunk(src, "code:m.py")
        self.assertEqual(len(chunks), 1)
        self.assertIn("class Tiny", chunks[0]["text"])

    def test_large_class_splits_per_method_with_scope_header(self):
        methods = "".join(
            f"    def m{i}(self):\n        x = {i}\n        return x\n\n"
            for i in range(30)
        )
        src = f"class Big:\n{methods}"
        self.assertGreater(src.count("\n"), _MAX_WHOLE_CLASS_LINES)
        chunks = ast_chunk(src, "code:m.py")
        # 30 methods and nothing else: this class has no docstring or
        # attributes, so there is no class-header chunk to emit -- a chunk
        # holding a bare `class Big:` line would be noise.
        self.assertEqual(len(chunks), 30)
        # Every method chunk names its enclosing class, or a retrieved method
        # is unattributable evidence.
        for c in chunks:
            self.assertIn("in class Big", c["text"])

    def test_split_class_keeps_its_docstring_and_attributes_as_evidence(self):
        # The counterpart to the test above: when the class head DOES carry
        # evidence, it must survive the per-method split under the CLASS's own
        # ref -- not leak into the module-preamble chunk's whole-file ref,
        # which would misattribute it.
        methods = "".join(
            f"    def m{i}(self):\n        x = {i}\n        return x\n\n"
            for i in range(30)
        )
        src = ('class Big:\n    """What Big is for."""\n\n'
               "    MAX_RETRIES = 7\n\n" + methods)
        chunks = ast_chunk(src, "code:m.py")
        head = [c for c in chunks if "MAX_RETRIES = 7" in c["text"]]
        self.assertEqual(len(head), 1, "class attribute must appear exactly once")
        self.assertIn("What Big is for.", head[0]["text"])
        # Filed under the class's own line range, not the whole file.
        self.assertRegex(head[0]["ref"], r"^code:m\.py#L1-L\d+$")
        self.assertNotEqual(head[0]["ref"], "code:m.py")

    def test_module_level_constants_are_not_dropped(self):
        # The board asks about CONVERSATION_NAME_LENGTH, a bare module
        # constant with no AST boundary of its own. Losing it would be a
        # silent evidence regression.
        src = "CONVERSATION_NAME_LENGTH = 32\n\n\ndef alpha():\n    return 1\n"
        chunks = ast_chunk(src, "code:m.py")
        self.assertTrue(any("CONVERSATION_NAME_LENGTH = 32" in c["text"] for c in chunks))

    def test_imports_appear_as_scope_header_on_each_chunk(self):
        src = "import os\nfrom pathlib import Path\n\n\ndef alpha():\n    return Path\n"
        chunk = next(c for c in ast_chunk(src, "code:m.py") if "def alpha" in c["text"])
        self.assertIn("from pathlib import Path", chunk["text"])


class AstChunkFallbackTests(unittest.TestCase):
    """Fallbacks are the safety property: ast_chunk must never do WORSE than
    chunk_text on input it cannot parse or has nothing to split."""

    def test_non_python_falls_back_to_chunk_text(self):
        src = "package main\n\nfunc main() {}\n"
        self.assertEqual(ast_chunk(src, "code:main.go"), chunk_text(src, "code:main.go"))

    def test_syntax_error_falls_back_to_chunk_text(self):
        src = "def broken(:\n    this is not python\n"
        with self.assertRaises(SyntaxError):
            ast.parse(src)
        self.assertEqual(ast_chunk(src, "code:m.py"), chunk_text(src, "code:m.py"))

    def test_module_with_no_defs_falls_back_to_chunk_text(self):
        # Must keep chunk_text's exact whole-file ref (no spurious line range).
        src = "X = 1\nY = 2\n"
        out = ast_chunk(src, "code:m.py")
        self.assertEqual(out, chunk_text(src, "code:m.py"))
        self.assertEqual(out[0]["ref"], "code:m.py")

    def test_null_bytes_fall_back_instead_of_raising(self):
        src = "def a():\n    return '\x00'\n"
        self.assertEqual(ast_chunk(src, "code:m.py"), chunk_text(src, "code:m.py"))


class AstChunkFitsEmbedderBudgetTests(unittest.TestCase):
    """The whole point: chunks small enough that the 512-token embedder reads
    them WHOLE. Uses a chars-per-token proxy so this stays stdlib-only and
    always-run; the real tokenizer measurement is in the eval test."""

    def test_ast_chunks_are_far_smaller_than_a_300_line_window(self):
        # A realistic dense module: 40 functions of 12 lines = 480 lines, which
        # chunk_text would slice into ~2 uniformly dense 300-line windows.
        src = "".join(
            f"def fn_{i}(a, b):\n" + "".join(f"    x{j} = a + b + {j}\n" for j in range(10))
            + f"    return x0 + {i}\n\n"
            for i in range(40)
        )
        windowed = chunk_text(src, "code:m.py")
        asted = ast_chunk(src, "code:m.py")
        self.assertGreater(len(asted), len(windowed))
        biggest_window = max(len(c["text"]) for c in windowed)
        biggest_ast = max(len(c["text"]) for c in asted)
        self.assertLess(biggest_ast, biggest_window / 2,
                        "AST chunks must be dramatically smaller than a line window, "
                        "or they do not fix the 512-token truncation")


class AstChunkOversizedChunkSafetyValveTests(unittest.TestCase):
    """Found live 2026-07-17 via the debugging playbook's sibling-sweep step:
    the SAME size-based safety valve added to ts_chunk.py (evals/ts_chunk.py)
    was never ported to this module, despite ast_chunk.py existing FIRST that
    same session and being reported "proven". No existing fixture here was
    ever large/dense enough to trigger it -- all 17 pre-existing tests in this
    file passed throughout, which is exactly why the gap survived.

    Three distinct unbounded-assembly points, each proven with a real or
    minimal repro before any fix: a per-definition chunk (measured on the
    real committed corpus's own llm/cli.py: 23,497 chars vs chunk_text's
    9,997), a large class's head-before-first-method chunk (50,297 vs 6,300),
    and the module-level leftover-code chunk (57,786 vs 6,000, collapsing to
    essentially the whole file as one chunk -- the exact same shape as the
    Jest-describe-block bug found and fixed in ts_chunk.py, reproduced here
    for a large non-def module-level blob instead)."""

    def test_large_single_function_gets_rewindowed(self):
        body = "".join(f"    v{i} = {i}\n" for i in range(800))
        src = f"def big():\n{body}    return None\n"
        chunks = ast_chunk(src, "code:big.py")
        biggest = max(len(c["text"]) for c in chunks)
        self.assertLess(biggest, 10_000,
                        f"single function was not decomposed: {biggest} chars")
        self.assertGreater(len(chunks), 1)

    def test_large_class_head_gets_rewindowed(self):
        head_attrs = "".join(f"    ATTR_{i} = {i}\n" for i in range(2500))
        methods = "".join(f"    def m{i}(self):\n        return {i}\n" for i in range(80))
        src = f"class Big:\n{head_attrs}{methods}"
        chunks = ast_chunk(src, "code:b.py")
        biggest = max(len(c["text"]) for c in chunks)
        self.assertLess(biggest, 10_000,
                        f"class head was not decomposed: {biggest} chars")

    def test_module_level_leftover_blob_gets_rewindowed(self):
        # A real def alongside the blob is REQUIRED: without one, `out` stays
        # empty and this degenerately exercises the "no defs -> chunk_text"
        # fallback instead of the leftover-blob path this test means to prove.
        blob = "".join(f"CONFIG[{i!r}] = {i}\n" for i in range(3000))
        src = "def helper():\n    return 1\n\n\n" + blob
        chunks = ast_chunk(src, "code:c.py")
        self.assertTrue(any("helper" in c["text"] for c in chunks),
                        "helper must be a real captured definition, or this "
                        "degenerately exercises the empty-out fallback")
        biggest = max(len(c["text"]) for c in chunks)
        self.assertLess(biggest, 10_000,
                        f"leftover blob was not decomposed: {biggest} chars")
        self.assertGreater(len(chunks), 2)

    def test_leftover_blob_content_is_not_lost(self):
        blob = "".join(f"CONFIG[{i!r}] = {i}\n" for i in range(3000))
        src = "def helper():\n    return 1\n\n\n" + blob
        chunks = ast_chunk(src, "code:c.py")
        for marker in ("CONFIG[0]", "CONFIG[1500]", "CONFIG[2999]"):
            self.assertTrue(any(marker in c["text"] for c in chunks),
                            f"content lost: no chunk contains {marker}")

    @unittest.skipUnless(_CORPUS_PATH.exists(), "needs the committed corpus")
    def test_committed_corpus_code_chunks_never_exceed_the_valve_ceiling(self):
        # The real, non-arbitrary bar: the valve's own documented ceiling
        # (2x chunk_text's window -- same threshold ts_chunk.py uses), not an
        # ad hoc multiplier of chunk_text's own per-file baseline. Checks
        # EVERY code chunk actually in the committed corpus directly (T5
        # migrated it to AST chunking, so this is the corpus's real, current
        # state, not a re-derivation from a hypothetical whole-file blob) --
        # a real, large, single top-level function legitimately landing under
        # the valve ceiling is accepted, matching the same tail already
        # accepted in ts_chunk.py.
        rows = [json.loads(l) for l in _CORPUS_PATH.read_text().splitlines() if l.strip()]
        code_chunks = [r for r in rows if r["source"] == "code"]
        self.assertTrue(code_chunks, "committed corpus has no code chunks")
        biggest = max(code_chunks, key=lambda c: len(c["text"]))
        self.assertLessEqual(len(biggest["text"]), _MAX_EMITTED_CHUNK_CHARS,
                             f"{biggest['ref']} is {len(biggest['text'])} chars, "
                             f"over the {_MAX_EMITTED_CHUNK_CHARS}-char valve ceiling")

    def test_small_definitions_are_unaffected_by_the_valve(self):
        src = "def alpha():\n    return 1\n"
        chunks = ast_chunk(src, "code:m.py")
        self.assertEqual(len(chunks), 1)
        self.assertIn("alpha", chunks[0]["text"])


class AstChunkDecoratorTests(unittest.TestCase):
    """Found live 2026-07-17 during T5 (the corpus migration): a top-level
    decorated function's `ast.FunctionDef.lineno` points to the `def` line,
    NOT the `@decorator` line above it (confirmed: `ast.parse` sets them to
    genuinely different line numbers) -- so the decorator fell outside the
    function's covered range and leaked into the module-level leftover bucket
    as its own orphaned, contentless chunk, disconnected from the function it
    decorates. Measured on the real migrated corpus: 92 of 580 chunks (15.9%)
    were exactly this -- a bare `@something` line with no body, pure noise.
    First found on llm/hookspecs.py, where EVERY hook is a bare
    `@hookspec`-decorated one-liner, making the file's citations useless
    without this fix."""

    def test_top_level_decorated_function_keeps_its_decorator(self):
        src = "@hookspec\ndef register_tools(register):\n    \"doc\"\n"
        chunks = ast_chunk(src, "code:m.py")
        fn_chunk = next(c for c in chunks if "register_tools" in c["text"])
        self.assertIn("@hookspec", fn_chunk["text"])
        # And no OTHER chunk should hold the decorator on its own -- proves
        # it wasn't just duplicated into both places.
        others = [c for c in chunks if c is not fn_chunk]
        self.assertFalse(any("@hookspec" in c["text"] for c in others))

    def test_no_orphaned_decorator_only_chunk_is_produced(self):
        src = "import x\n\n@hookspec\ndef register_tools(register):\n    \"doc\"\n"
        chunks = ast_chunk(src, "code:m.py")
        for c in chunks:
            body_lines = [l for l in c["text"].splitlines() if l.strip()]
            # A chunk whose only non-blank content is decorator line(s) is the
            # exact defect: pure noise, zero evidence value.
            non_label_non_header = [l for l in body_lines if not l.startswith("#") and "import" not in l]
            if non_label_non_header:
                self.assertFalse(
                    all(l.strip().startswith("@") for l in non_label_non_header),
                    f"orphaned decorator-only chunk: {c}")

    def test_multiple_stacked_decorators_all_stay_with_the_function(self):
        src = "@first\n@second\n@third\ndef alpha():\n    return 1\n"
        chunks = ast_chunk(src, "code:m.py")
        fn_chunk = next(c for c in chunks if "def alpha" in c["text"])
        for dec in ("@first", "@second", "@third"):
            self.assertIn(dec, fn_chunk["text"])

    def test_decorated_method_in_a_large_class_keeps_its_decorator(self):
        methods = "".join(
            f"    @staticmethod\n    def m{i}():\n        return {i}\n" for i in range(25)
        )
        src = f"class Big:\n{methods}"
        self.assertGreater(src.count("\n"), _MAX_WHOLE_CLASS_LINES)
        chunks = ast_chunk(src, "code:m.py")
        for i in (0, 12, 24):
            c = next(c for c in chunks if f"def m{i}(" in c["text"])
            self.assertIn("@staticmethod", c["text"],
                         f"method m{i}'s decorator was orphaned from its own chunk")

    def test_decorated_class_head_boundary_does_not_duplicate_the_decorator(self):
        # The class-head chunk (attrs before the first method) must stop
        # BEFORE the first method's decorator, or the decorator appears in
        # both the head chunk and the method's own chunk.
        head_attrs = "".join(f"    ATTR_{i} = {i}\n" for i in range(70))
        methods = "".join(
            f"    @staticmethod\n    def m{i}():\n        return {i}\n" for i in range(5)
        )
        src = f"class Big:\n{head_attrs}{methods}"
        chunks = ast_chunk(src, "code:m.py")
        head = next(c for c in chunks if "ATTR_0" in c["text"] and "def m0" not in c["text"])
        self.assertNotIn("@staticmethod", head["text"])
        m0 = next(c for c in chunks if "def m0(" in c["text"])
        self.assertIn("@staticmethod", m0["text"])


if __name__ == "__main__":
    unittest.main()
