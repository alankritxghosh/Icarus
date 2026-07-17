"""Unit tests for ts_chunk: the tree-sitter-backed multi-language chunker.

Self-skips without tree-sitter/tree-sitter-language-pack installed (a real
extension, unlike fastembed and ast_chunk.py's stdlib ast). Every fixture
below mirrors a pattern measured against real source in real React Native
repos on 2026-07-17 (see the module docstring and
docs/plans/2026-07-17-ast-chunking-all-languages.md) -- never an invented
"typical" pattern.
"""

import unittest

try:
    import tree_sitter_language_pack  # noqa: F401
    _HAS_TREE_SITTER = True
except ImportError:
    _HAS_TREE_SITTER = False

if _HAS_TREE_SITTER:
    from .ts_chunk import ts_chunk
from .ingest import chunk_text


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkContractTests(unittest.TestCase):
    def test_refs_use_chunk_texts_window_format(self):
        src = "export function alpha() {\n  return 1;\n}\n"
        for c in ts_chunk(src, "code:m.ts", ".ts"):
            self.assertRegex(c["ref"], r"^code:m\.ts#L\d+-L\d+$")

    def test_no_source_key_matching_chunk_text(self):
        src = "export function alpha() {\n  return 1;\n}\n"
        for c in ts_chunk(src, "code:m.ts", ".ts"):
            self.assertNotIn("source", c)


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkTypeScriptTests(unittest.TestCase):
    """.ts/.tsx: measured real code is dominated by `export const Foo = () =>
    {}` (lexical_declaration), not `function Foo() {}` -- 118:4 on a real
    file. A chunker that only recognizes function_declaration would miss
    nearly every function."""

    def test_splits_const_arrow_function_export(self):
        src = ('import React from "react";\n\n'
               'export const Foo = () => {\n  return 1;\n};\n\n'
               'export const Bar = () => {\n  return 2;\n};\n')
        chunks = ts_chunk(src, "code:m.tsx", ".tsx")
        named = {c["ref"]: c["text"] for c in chunks if "Foo" in c["text"] or "Bar" in c["text"]}
        foo = next(t for r, t in named.items() if "return 1" in t)
        bar = next(t for r, t in named.items() if "return 2" in t)
        self.assertIn("Foo", foo)
        self.assertNotIn("return 2", foo)
        self.assertIn("Bar", bar)
        self.assertNotIn("return 1", bar)

    def test_named_const_arrow_chunk_labels_its_own_name(self):
        src = 'export const ComposePost = () => {\n  return 1;\n};\n'
        chunk = next(c for c in ts_chunk(src, "code:m.tsx", ".tsx") if "return 1" in c["text"])
        self.assertIn("ComposePost", chunk["text"].splitlines()[0])

    def test_plain_function_declaration_still_splits_and_is_named(self):
        src = 'export function alpha() {\n  return 1;\n}\n'
        chunk = next(c for c in ts_chunk(src, "code:m.ts", ".ts") if "return 1" in c["text"])
        self.assertIn("alpha", chunk["text"].splitlines()[0])

    def test_small_class_stays_whole(self):
        src = 'class Tiny {\n  a() { return 1; }\n  b() { return 2; }\n}\n'
        chunks = ts_chunk(src, "code:m.ts", ".ts")
        class_chunks = [c for c in chunks if "class Tiny" in c["text"]]
        self.assertEqual(len(class_chunks), 1)
        self.assertIn("a()", class_chunks[0]["text"])
        self.assertIn("b()", class_chunks[0]["text"])

    def test_large_class_splits_per_method_with_scope_label(self):
        methods = "".join(f"  m{i}() {{\n    return {i};\n  }}\n" for i in range(25))
        src = f"class Big {{\n{methods}}}\n"
        self.assertGreater(src.count("\n"), 60)
        chunks = ts_chunk(src, "code:m.ts", ".ts")
        method_chunks = [c for c in chunks if "-- in Big" in c["text"]]
        self.assertEqual(len(method_chunks), 25)

    def test_jsx_syntax_parses_without_falling_back(self):
        src = ('import React from "react";\n\n'
               'export const View1 = () => {\n  return <div className="x">hi</div>;\n};\n')
        chunks = ts_chunk(src, "code:m.tsx", ".tsx")
        # A genuine parse produces a named chunk for View1; a silent fallback
        # to chunk_text would instead return exactly chunk_text's output.
        self.assertNotEqual(chunks, chunk_text(src, "code:m.tsx"))
        self.assertTrue(any("View1" in c["text"] for c in chunks))

    def test_module_level_constant_is_preserved(self):
        src = 'export const MAX_LEN = 32;\n\nexport function alpha() {\n  return 1;\n}\n'
        chunks = ts_chunk(src, "code:m.ts", ".ts")
        self.assertTrue(any("MAX_LEN = 32" in c["text"] for c in chunks))


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkFlowJsTests(unittest.TestCase):
    """React Native's real .js is Flow-typed. Measured: the `javascript`
    grammar produced 424 ERROR nodes across 20 real files; `tsx` produced 17.
    ts_chunk must therefore route .js through `tsx`, not `javascript`."""

    def test_flow_type_annotations_parse_via_tsx_grammar(self):
        src = (
            'import type {Foo} from "./Foo";\n\n'
            'export function process(x: number): string {\n'
            '  const y: ?Foo = null;\n'
            '  return String(x);\n'
            '}\n'
        )
        chunks = ts_chunk(src, "code:m.js", ".js")
        # A real split (not a chunk_text fallback) proves the Flow syntax
        # actually parsed instead of tripping the ERROR-rate gate.
        self.assertNotEqual(chunks, chunk_text(src, "code:m.js"))
        self.assertTrue(any("process" in c["text"] for c in chunks))

    def test_flow_typed_class_field_parses(self):
        src = (
            'class Store {\n'
            '  _vibrating: boolean = false;\n'
            '  start() {\n    return 1;\n  }\n'
            '}\n'
        )
        chunks = ts_chunk(src, "code:m.js", ".js")
        # A real parse produces a class chunk; a fallback would too (the
        # fallback text also literally contains "Store"), so the meaningful
        # assertion is that this DIFFERS from the fallback -- proving a real
        # tsx-grammar parse happened, not just that the substring survived.
        self.assertNotEqual(chunks, chunk_text(src, "code:m.js"))
        self.assertTrue(any("Store" in c["text"] for c in chunks))


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkObjcTests(unittest.TestCase):
    """.mm/.m: measured real methods nest as
    class_implementation -> implementation_definition -> method_definition
    (confirmed on a real 2,335-line file)."""

    def test_small_implementation_stays_whole(self):
        src = ('#import "Foo.h"\n\n'
               '@implementation Foo\n'
               '- (void)doThing {\n  NSLog(@"hi");\n}\n'
               '@end\n')
        chunks = ts_chunk(src, "code:m.mm", ".mm")
        impl = [c for c in chunks if "@implementation Foo" in c["text"]]
        self.assertEqual(len(impl), 1)

    def test_large_implementation_splits_per_method(self):
        methods = "".join(
            f"- (int)method{i} {{\n    return {i};\n}}\n" for i in range(25)
        )
        src = f"@implementation Big\n{methods}@end\n"
        self.assertGreater(src.count("\n"), 60)
        chunks = ts_chunk(src, "code:m.mm", ".mm")
        method_chunks = [c for c in chunks if "-- in Big" in c["text"]]
        self.assertEqual(len(method_chunks), 25)

    def test_import_header_appears_on_method_chunks(self):
        methods = "".join(
            f"- (int)method{i} {{\n    return {i};\n}}\n" for i in range(25)
        )
        src = f'#import "Foo.h"\n\n@implementation Big\n{methods}@end\n'
        chunks = ts_chunk(src, "code:m.mm", ".mm")
        method_chunk = next(c for c in chunks if "-- in Big" in c["text"])
        self.assertIn('#import "Foo.h"', method_chunk["text"])


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkJavaTests(unittest.TestCase):
    """.java: methods nest inside class_body (confirmed on real 700-900 line
    files, 0 ERROR nodes)."""

    def test_large_class_splits_per_method(self):
        methods = "".join(
            f"  int method{i}() {{\n    return {i};\n  }}\n" for i in range(25)
        )
        src = f"package com.example;\n\nclass Big {{\n{methods}}}\n"
        self.assertGreater(src.count("\n"), 60)
        chunks = ts_chunk(src, "code:Big.java", ".java")
        method_chunks = [c for c in chunks if "-- in Big" in c["text"]]
        self.assertEqual(len(method_chunks), 25)

    def test_small_class_stays_whole(self):
        src = "class Tiny {\n  int a() { return 1; }\n}\n"
        chunks = ts_chunk(src, "code:Tiny.java", ".java")
        self.assertEqual(len([c for c in chunks if "class Tiny" in c["text"]]), 1)


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkKotlinTests(unittest.TestCase):
    """.kt: functions nest inside class_body (confirmed on real 1,400-1,700
    line files, 0 ERROR nodes). Kotlin's class_declaration has NO `name`
    FIELD (confirmed empirically) -- the name is a positional type_identifier
    child, which _node_name must fall back to."""

    def test_large_class_splits_per_method_and_is_named_correctly(self):
        methods = "".join(
            f"    fun method{i}(): Int {{\n        return {i}\n    }}\n" for i in range(25)
        )
        src = f"package com.example\n\nclass Big {{\n{methods}}}\n"
        self.assertGreater(src.count("\n"), 60)
        chunks = ts_chunk(src, "code:Big.kt", ".kt")
        method_chunks = [c for c in chunks if "-- in Big" in c["text"]]
        self.assertEqual(len(method_chunks), 25)
        # Regression guard for the real bug found live: Kotlin exposes no
        # `name` FIELD on class_declaration, so a naive
        # child_by_field_name("name") silently returns None and every method
        # would be mislabeled "-- in class_declaration" instead of "-- in Big".
        self.assertFalse(any("in class_declaration" in c["text"] for c in chunks))


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkOversizedChunkSafetyValveTests(unittest.TestCase):
    """Found live 2026-07-17 sweeping real Expensify/App test files: a
    top-level Jest `describe('X', () => { ...hundreds of it() blocks... })`
    is a CALL EXPRESSION, invisible to the definitions/containers/wrappers
    scheme (it's neither a function/class/const definition). Without a
    safety valve the entire file fell into the undecomposed "leftover"
    bucket as ONE chunk -- measured up to ~950,000 chars on a real file,
    dramatically worse than chunk_text's own 300-line windows would have
    produced for the same content. This is the regression guard."""

    def test_jest_describe_block_does_not_become_one_giant_chunk(self):
        # A bare describe()-only file would hit ts_chunk's OWN "no
        # definitions found -> chunk_text" fallback trivially, which does
        # NOT exercise the leftover/safety-valve path this test means to
        # prove -- real Expensify test files always have imports plus a real
        # captured definition alongside the describe() block, so `out` is
        # non-empty and the describe() block genuinely lands in the
        # leftover-run bucket. Mirror that shape: a real helper export makes
        # `out` non-empty, forcing the describe() block through the valve.
        body = "".join(
            f"  it('does thing {i}', () => {{\n"
            f"    expect(doThing({i})).toBe({i});\n"
            f"  }});\n\n"
            for i in range(150)
        )
        src = ('export function helper() {\n  return 1;\n}\n\n'
               f"describe('a big real-shaped test suite', () => {{\n{body}}});\n")
        self.assertGreater(src.count("\n"), 600)  # a real-sized test file
        chunks = ts_chunk(src, "code:BigTest.ts", ".ts")
        self.assertTrue(any("helper" in c["text"] for c in chunks),
                        "the helper export must be captured as a real definition, "
                        "or this test degenerately exercises the empty-out fallback "
                        "instead of the leftover/safety-valve path")
        biggest = max(len(c["text"]) for c in chunks)
        # chunk_text's own 300-line window tops out around a few KB for
        # typical density; a multi-chunk split well under 10KB per chunk
        # proves the valve actually engaged, not that one lucky node matched.
        self.assertLess(biggest, 10_000,
                        f"describe() block was not decomposed: {biggest} char chunk")
        self.assertGreater(len(chunks), 2)

    def test_oversized_chunk_still_covers_every_line_no_content_dropped(self):
        body = "".join(f"  it('t{i}', () => {{ expect({i}).toBe({i}); }});\n" for i in range(150))
        src = ('export function helper() {\n  return 1;\n}\n\n'
               f"describe('suite', () => {{\n{body}}});\n")
        chunks = ts_chunk(src, "code:BigTest.ts", ".ts")
        for marker in ("t0'", "t75'", "t149'"):
            self.assertTrue(any(marker in c["text"] for c in chunks),
                            f"content lost: no chunk contains {marker}")

    def test_one_giant_function_also_gets_rewindowed(self):
        # The other real case found live: a single legitimate definition
        # (a 1,300-line React component, found in bluesky-social/social-app)
        # too big to be a useful "one chunk" even though it IS one real unit.
        body = "".join(f"  const v{i} = {i};\n" for i in range(650))
        src = f"export const Big = () => {{\n{body}  return null;\n}};\n"
        self.assertGreater(src.count("\n"), 600)
        chunks = ts_chunk(src, "code:Big.tsx", ".tsx")
        biggest = max(len(c["text"]) for c in chunks)
        self.assertLess(biggest, 10_000)
        self.assertGreater(len(chunks), 1)

    def test_few_lines_with_one_pathological_line_also_gets_rewindowed(self):
        # A DISTINCT bug from the two above, found live 2026-07-17 sweeping
        # real files: mattermost-mobile's app/utils/emoji/index.ts is 125
        # lines total (nowhere near the 600-LINE valve threshold) but one
        # single machine-generated line is ~250,000 chars. The leftover-run
        # bucket for that span was only 112 LINES, so the line-count check
        # never fired, and the char-less emit() path shipped it whole. A
        # line-count-only valve can never catch this class -- there are no
        # "extra" lines to count.
        #
        # A helper function is required alongside the huge object literal:
        # `export const Emojis = {...}` alone captures NOTHING (an object
        # literal isn't in fn_value_types), so `out` would stay empty and
        # this would degenerately exercise ts_chunk's OTHER, top-level
        # "if not out: return chunk_text(...)" fallback -- which also
        # happens to pass, for the wrong reason, exactly the same trap this
        # suite already caught once for the Jest describe() test above.
        huge_line = "export const Emojis = {" + "x" * 60_000 + "};"
        src = ("export function helper() { return 1; }\n"
               f"import x from 'y';\n{huge_line}\nexport const other = 1;\n")
        self.assertLess(src.count("\n"), 600)  # confirms this isn't case #1
        chunks = ts_chunk(src, "code:index.ts", ".ts")
        self.assertTrue(any("helper" in c["text"] for c in chunks),
                        "the helper must be captured as a real definition, or "
                        "this degenerately exercises the empty-out fallback")
        biggest = max(len(c["text"]) for c in chunks)
        self.assertLess(biggest, 15_000,
                        f"few-line/huge-char span was not decomposed: {biggest} chars")

    def test_small_definitions_are_unaffected_by_the_valve(self):
        # The valve must not touch anything already well-sized -- only a
        # regression here would show up as an unexpected fallback/split.
        src = 'export const Foo = () => {\n  return 1;\n};\n'
        chunks = ts_chunk(src, "code:m.ts", ".ts")
        self.assertEqual(len(chunks), 1)
        self.assertIn("Foo", chunks[0]["text"])


@unittest.skipUnless(_HAS_TREE_SITTER, "needs tree-sitter-language-pack")
class TsChunkFallbackTests(unittest.TestCase):
    """The safety property: ts_chunk must never do WORSE than chunk_text."""

    def test_unsupported_extension_falls_back_to_chunk_text(self):
        # .h is deliberately unsupported: measured 360 ERROR nodes with the
        # `c` grammar and 171 with `objc` on real RN headers -- ambiguous
        # between the two, neither clean enough to trust.
        src = "void foo();\n"
        self.assertEqual(ts_chunk(src, "code:m.h", ".h"), chunk_text(src, "code:m.h"))

    def test_garbage_input_falls_back_via_error_rate_gate(self):
        src = "{{{ this is not valid code in any language ]]] &&&& ***\n" * 20
        result = ts_chunk(src, "code:m.ts", ".ts")
        self.assertEqual(result, chunk_text(src, "code:m.ts"))

    def test_file_with_no_definitions_falls_back(self):
        src = "// just a comment\nconst x = 1;\n"
        result = ts_chunk(src, "code:m.ts", ".ts")
        self.assertEqual(result, chunk_text(src, "code:m.ts"))

    def test_empty_string_falls_back_without_crashing(self):
        result = ts_chunk("", "code:m.ts", ".ts")
        self.assertEqual(result, chunk_text("", "code:m.ts"))


class TsChunkNoDependencyFallbackTests(unittest.TestCase):
    """Runs WITHOUT the skipUnless guard -- proves the lazy-import contract:
    ts_chunk must be safely callable even when tree-sitter-language-pack
    genuinely isn't installed, exactly like fastembed's pattern elsewhere in
    this codebase. Monkeypatches the internal parser getter rather than
    uninstalling the real package."""

    def test_missing_tree_sitter_falls_back_to_chunk_text(self):
        from . import ts_chunk as mod
        original = mod._get_parser
        mod._get_parser = lambda language: None
        try:
            src = "export function alpha() {\n  return 1;\n}\n"
            result = mod.ts_chunk(src, "code:m.ts", ".ts")
            self.assertEqual(result, chunk_text(src, "code:m.ts"))
        finally:
            mod._get_parser = original


if __name__ == "__main__":
    unittest.main()
