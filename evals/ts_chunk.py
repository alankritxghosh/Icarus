"""tree-sitter-backed AST-aware code chunking for the React Native language
set: TypeScript/TSX, Flow-typed JS, Objective-C/C++, Java, Kotlin.

Extends `ast_chunk.py`'s proven approach (splitting at function/class
boundaries instead of `ingest.chunk_text`'s fixed 300-line windows, to fix
the embedder's 512-token truncation) beyond Python, which stdlib `ast` cannot
parse. Python keeps using `ast_chunk.py` -- it has no tree-sitter dependency
and already works; this module exists for everything stdlib `ast` cannot
touch. See docs/plans/2026-07-17-ast-chunking-all-languages.md for the scope
and the measured evidence behind every choice below.

Every design decision here was forced by parsing REAL source from real React
Native repos (Expensify/App, facebook/react-native, bluesky-social/social-app,
mattermost/mattermost-mobile, wix/react-native-navigation), not guessed from
grammar docs:

- `.js` in a real RN app is Flow-typed, not plain JS. The `javascript` grammar
  produced 424 ERROR nodes across 20 real files (import type, typed class
  fields, `as const`...). The `tsx` grammar produced 17 -- a 96% reduction --
  because Flow and TypeScript's type-annotation syntax overlap heavily. So
  `.js`/`.jsx`/`.mjs`/`.cjs` all parse with the `tsx` grammar here, not
  `javascript`.
- Modern TS/RN code is `export const Foo = () => {...}`, not
  `function Foo() {...}`: measured on real files, `lexical_declaration`
  outnumbered `function_declaration` roughly 30:1. A chunker that only looks
  for `function_declaration` would miss nearly every function.
- `.mm`/`.m` methods nest two levels deep
  (`class_implementation` -> `implementation_definition` -> `method_definition`),
  confirmed on a real 2,335-line file.
- Jest-style test files (`describe('X', () => { ... hundreds of `it(...)`
  blocks ... })`) are a top-level CALL EXPRESSION, not a function/class/const
  definition -- invisible to the definitions/containers/wrappers scheme below.
  Measured live on real Expensify test files: without a safety valve, a whole
  such file (up to ~950,000 chars, `SearchUIUtilsTest.ts`) fell entirely into
  the undecomposed "leftover" bucket as ONE chunk -- dramatically WORSE than
  `chunk_text`'s own 300-line windows would have produced for the same file.
  Rather than special-case every callback-block shape a real codebase might
  use (test frameworks, builder patterns, IIFEs...), any single chunk this
  module emits that exceeds `_MAX_EMITTED_CHUNK_LINES` is re-windowed via
  `chunk_text` before being returned. This is the mechanism that makes "never
  worse than chunk_text" an enforced property instead of a hope, and it also
  covers the case of one single legitimately huge definition (a 1,300-line
  React component was found live in the same sweep) the same way.
- Java methods nest inside `class_body`; Kotlin functions inside
  `class_body`/`companion_object`. Both confirmed clean (0 ERROR nodes) on
  real 700-1,700 line files.

Contract matches `ast_chunk.ast_chunk` and `ingest.chunk_text`: returns
`[{"ref": ..., "text": ...}]`, no `"source"` key, `#Lstart-Lend` ref suffix.
Falls back to `chunk_text` on: no grammar for the extension, tree-sitter not
installed, a parse whose ERROR-node rate is too high to trust structurally, or
a file with no definitions found -- so this can never do worse than today.
"""

import re
from typing import List, Optional

from .ingest import _CHUNK_MAX_CHARS, _CHUNK_WINDOW_LINES, chunk_text

# The React Native language set (2026-07-17 scope: measure and ship what a
# real design partner's codebase needs, not every grammar the pack ships).
# `.h` is deliberately ABSENT: measured both the `c` and `objc` grammars
# against real RN headers and got 360 / 171 ERROR nodes respectively -- ambi-
# guous between the two, neither clean. `.h` stays on chunk_text; see the
# plan doc's Risks section. `.py` is deliberately absent too: ast_chunk.py
# already covers it with zero dependency.
_LANGUAGE_BY_EXT = {
    ".ts": "typescript", ".tsx": "tsx",
    ".js": "tsx", ".jsx": "tsx", ".mjs": "tsx", ".cjs": "tsx",
    ".mm": "objc", ".m": "objc",
    ".java": "java",
    ".kt": "kotlin",
}

# Above this share of ERROR nodes in the parse tree, the parse is untrusted
# structurally and the whole file falls back to chunk_text rather than ship a
# chunking built on a broken tree. 2% is well above the 17/(thousands of
# nodes) rate measured on real, successfully-handled Flow files, and well
# below what a genuinely wrong grammar or corrupted file produces.
_MAX_ERROR_RATE = 0.02

# A single emitted chunk longer than this (2x chunk_text's own window) means
# the AST walk failed to decompose something -- a call-expression-wrapped test
# block, or one genuinely giant definition. Re-window it via chunk_text rather
# than ship something worse than the baseline this module exists to beat.
#
# LINE count alone is not enough to catch this: found live 2026-07-17 on a
# real 112-line span (well under this threshold) that was still 252,878
# chars -- a machine-generated file with a handful of enormous single lines.
# The line-count check catches an undecomposed BLOCK of many normal-sized
# lines (the Jest describe() case); this char check catches the orthogonal
# case of just a few pathologically long lines. Uses chunk_text's own
# per-window budget so "would chunk_text itself have split this" is the
# actual bar, not an arbitrary second number.
_MAX_EMITTED_CHUNK_LINES = 2 * _CHUNK_WINDOW_LINES
_MAX_EMITTED_CHUNK_CHARS = 2 * _CHUNK_MAX_CHARS

# A container (class/interface/etc.) at or under this many lines stays whole:
# it IS the coherent unit, and comfortably fits the embedder's 512-token
# budget. Same threshold as ast_chunk.py's Python path, for consistency.
_MAX_WHOLE_CONTAINER_LINES = 60
_MAX_HEADER_IMPORTS = 15
_IMPORT_SCAN_LINES = 80

# Per-language node-type config, each entry populated ONLY from node types
# actually observed parsing real source (see module docstring + the plan
# doc's evidence table) -- never from grammar documentation alone.
_LANG_CONFIG = {
    "typescript": dict(
        definitions={"function_declaration", "generator_function_declaration",
                     "class_declaration", "abstract_class_declaration",
                     "interface_declaration", "enum_declaration"},
        containers={"class_declaration", "abstract_class_declaration",
                    "interface_declaration"},
        members={"method_definition", "method_signature"},
        wrappers={"export_statement"},
        decl_wrappers={"lexical_declaration", "variable_declaration"},
        fn_value_types={"arrow_function", "function_expression",
                        "generator_function"},
        imports={"import_statement"},
    ),
    "objc": dict(
        definitions={"class_implementation", "class_interface",
                     "category_interface", "protocol_declaration"},
        containers={"class_implementation", "class_interface",
                    "category_interface", "protocol_declaration"},
        members={"method_definition"},
        wrappers=set(), decl_wrappers=set(), fn_value_types=set(),
        imports={"preproc_include"},
    ),
    "java": dict(
        definitions={"class_declaration", "interface_declaration",
                     "enum_declaration", "record_declaration"},
        containers={"class_declaration", "interface_declaration",
                    "enum_declaration", "record_declaration"},
        members={"method_declaration", "constructor_declaration"},
        wrappers=set(), decl_wrappers=set(), fn_value_types=set(),
        imports={"import_declaration"},
    ),
    "kotlin": dict(
        definitions={"class_declaration", "object_declaration",
                     "function_declaration"},
        containers={"class_declaration", "object_declaration",
                    "companion_object"},
        members={"function_declaration"},
        wrappers=set(), decl_wrappers=set(), fn_value_types=set(),
        imports={"import_list"},
    ),
}
_LANG_CONFIG["tsx"] = _LANG_CONFIG["typescript"]  # same shape, JSX superset


def _get_parser(language: str):
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError:
        return None
    try:
        return get_parser(language)
    except Exception:
        return None


def _node_name(node) -> Optional[str]:
    """The identifier a container/definition is named by. Verified per
    grammar: TS/Java expose it via the `name` field; Kotlin and ObjC do not
    (confirmed empirically -- `child_by_field_name('name')` returns None for
    both), so this falls back to the first direct `identifier`/
    `type_identifier` child, which is where the name actually lives in both."""
    named = node.child_by_field_name("name")
    if named is not None:
        return named.text.decode("utf-8", "replace")
    for child in node.children:
        if child.type in ("identifier", "type_identifier"):
            return child.text.decode("utf-8", "replace")
    return None


def _error_rate(node) -> float:
    total = errors = 0

    def walk(n):
        nonlocal total, errors
        total += 1
        if n.type == "ERROR":
            errors += 1
        for c in n.children:
            walk(c)

    walk(node)
    return (errors / total) if total else 1.0


def ts_chunk(text: str, ref_prefix: str, ext: str) -> List[dict]:
    """Split `text` (source for `ext`) at function/class/method boundaries via
    tree-sitter. Falls back to `chunk_text` whenever the result can't be
    trusted -- unsupported extension, tree-sitter unavailable, an
    untrustworthy parse, or a file with nothing to split."""
    language = _LANGUAGE_BY_EXT.get(ext)
    if language is None:
        return chunk_text(text, ref_prefix)

    parser = _get_parser(language)
    if parser is None:
        return chunk_text(text, ref_prefix)

    try:
        tree = parser.parse(text.encode("utf-8", "replace"))
    except Exception:
        return chunk_text(text, ref_prefix)

    if _error_rate(tree.root_node) > _MAX_ERROR_RATE:
        return chunk_text(text, ref_prefix)

    cfg = _LANG_CONFIG[language]
    lines = text.splitlines()
    header = _scope_header(lines, cfg["imports"])
    path = ref_prefix.split(":", 1)[-1]

    out: List[dict] = []
    covered = set()

    def span(node):
        return node.start_point[0] + 1, node.end_point[0] + 1

    def cover(node):
        start, end = span(node)
        covered.update(range(start, end + 1))

    def emit(start_line, end_line, member_of=None, named=None) -> dict:
        # `member_of`: this chunk is a method/member living inside that
        # container ("-- in Baz"). `named`: this chunk itself defines that
        # identifier ("-- Bar"). At most one is meaningful per chunk -- a
        # definition doesn't have both a name and a container in this label.
        if member_of:
            suffix = f" -- in {member_of}"
        elif named:
            suffix = f" -- {named}"
        else:
            suffix = ""
        label = f"# {path}{suffix}"
        body = "\n".join(lines[start_line - 1:end_line])
        parts = [label, header, "", body] if header else [label, body]
        return {"ref": f"{ref_prefix}#L{start_line}-L{end_line}",
                "text": "\n".join(parts)}

    def emit_and_append(start_line, end_line, member_of=None, named=None):
        # The safety valve: a single span this module wants to emit as ONE
        # chunk, but which is too long to trust as "successfully decomposed"
        # (a Jest describe() block, one legitimately giant function/class-head).
        # Re-window it via chunk_text -- plain, unlabeled, exactly like the
        # fallback path -- rather than ship something worse than the 300-line
        # baseline this module exists to beat. Uses ABSOLUTE source lines
        # (start_line is real), so the remapped refs stay honest GitHub
        # line-link ranges, not relative-to-substring numbering.
        line_count = end_line - start_line + 1
        candidate = emit(start_line, end_line, member_of=member_of, named=named)
        # Check the REAL emitted text (label + header + body), not just the
        # raw source span -- a span whose body alone is under budget can still
        # push a chunk over it once the scope header is glued on. Found live:
        # a 436-line, ~19,600-char component body plus its import header
        # landed at 21,043 chars, ~5% over this valve's own 20,000-char bound,
        # because the check was on the body alone.
        if line_count > _MAX_EMITTED_CHUNK_LINES or len(candidate["text"]) > _MAX_EMITTED_CHUNK_CHARS:
            sub_text = "\n".join(lines[start_line - 1:end_line])
            for sub in chunk_text(sub_text, ref_prefix):
                m = re.search(r"#L(\d+)-L(\d+)$", sub["ref"])
                if m:
                    s = start_line - 1 + int(m.group(1))
                    e = start_line - 1 + int(m.group(2))
                else:
                    s, e = start_line, end_line
                out.append({"ref": f"{ref_prefix}#L{s}-L{e}", "text": sub["text"]})
            return
        out.append(candidate)

    def emit_node(node, member_of=None, named=None):
        start, end = span(node)
        emit_and_append(start, end, member_of=member_of, named=named)

    def handle_definition(node):
        start, end = span(node)
        if (end - start) <= _MAX_WHOLE_CONTAINER_LINES or node.type not in cfg["containers"]:
            emit_node(node, named=_node_name(node))
            cover(node)
            return

        # A container too big to keep whole: split into its members, plus one
        # chunk for anything in the container's own head (docstring/fields/
        # decorators) that precedes the first member -- real evidence (a
        # class constant, an ObjC ivar block), same reasoning as
        # ast_chunk.py's class-attribute handling.
        scope = _node_name(node) or node.type
        members = _find_members(node, cfg["members"])
        if not members:
            emit_node(node, named=_node_name(node))
            cover(node)
            return

        first_member_start = min(span(m)[0] for m in members)
        if first_member_start > start and any(
            l.strip() for l in lines[start:first_member_start - 1]
        ):
            emit_and_append(start, first_member_start - 1, named=scope)
        for m in members:
            emit_node(m, member_of=scope)
        cover(node)

    def unwrap(node):
        """Resolve a node to the definition(s) it actually represents,
        descending through export wrappers and const-assigned functions. May
        yield zero, one, or (for `const a = ..., b = () => {}`) several."""
        if node.type in cfg["wrappers"]:
            for child in node.children:
                if child.is_named:
                    yield from unwrap(child)
            return
        if node.type in cfg["decl_wrappers"]:
            for decl in node.children:
                if decl.type != "variable_declarator":
                    continue
                value = decl.child_by_field_name("value")
                if value is not None and value.type in cfg["fn_value_types"]:
                    # Chunk at the OUTER node's span (includes `export`/`const
                    # name =`), not just the function body, so the citation is
                    # a complete, attributable excerpt.
                    yield ("named", decl, node)
            return
        if node.type in cfg["definitions"]:
            yield ("plain", node, node)

    for top in tree.root_node.children:
        for kind, inner, outer in unwrap(top):
            if kind == "named":
                name_node = inner.child_by_field_name("name")
                label = name_node.text.decode("utf-8", "replace") if name_node else None
                start, end = span(outer)
                emit_and_append(start, end, named=label)
                cover(outer)
            else:
                handle_definition(inner)

    if not out:
        return chunk_text(text, ref_prefix)

    # Leftover: lines no emitted chunk covers (imports, module constants, or
    # -- before the safety valve above existed -- a whole undecomposed Jest
    # test file). Grouped into their natural CONTIGUOUS runs rather than one
    # blob spanning the whole file: each run gets an honest absolute
    # #Lstart-Lend (not a shared, imprecise whole-file ref), and reuses the
    # same size-aware emit_and_append, so a giant leftover run degrades to
    # chunk_text windowing exactly like everything else.
    uncovered = [i for i in range(1, len(lines) + 1) if i not in covered]
    run_start = None
    for i in uncovered + [None]:
        if i is not None and (run_start is None or i == prev + 1):
            run_start = run_start if run_start is not None else i
        else:
            if run_start is not None and any(l.strip() for l in lines[run_start - 1:prev]):
                emit_and_append(run_start, prev)
            run_start = i
        prev = i
    return out


def _find_members(container_node, member_types) -> list:
    """Members nested under a container, at whatever depth they actually
    live at (verified per-language: ObjC nests two levels deep via
    `implementation_definition`; Java/Kotlin one level via `class_body`).
    Does not descend into a NESTED container -- a method of an inner class
    belongs to that inner class, not this one."""
    found = []

    def walk(node, top):
        for child in node.children:
            if child.type in member_types:
                found.append(child)
            elif not top and child.type in _ALL_CONTAINER_TYPES:
                continue  # nested container: its members are its own concern
            else:
                walk(child, top=False)

    walk(container_node, top=True)
    return found


_ALL_CONTAINER_TYPES = {t for cfg in _LANG_CONFIG.values() for t in cfg["containers"]}


def _scope_header(lines: List[str], import_types: set) -> str:
    # A cheap text-based header: real import syntax across this language set
    # is single-line (`import ...`, `#import "..."`), so scanning leading
    # lines by a per-language prefix keeps this simple and avoids re-parsing
    # for header purposes.
    # import_types uniquely identifies the language here (small enough set).
    prefix = None
    if import_types == {"import_statement"}:
        prefix = "import "
    elif import_types == {"preproc_include"}:
        prefix = "#import"
    elif import_types == {"import_declaration"}:
        prefix = "import "
    elif import_types == {"import_list"}:
        prefix = "import "
    if prefix is None:
        return ""
    matches = [l for l in lines[:_IMPORT_SCAN_LINES] if l.strip().startswith(prefix)]
    return "\n".join(matches[:_MAX_HEADER_IMPORTS])
