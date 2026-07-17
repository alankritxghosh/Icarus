"""AST-aware code chunking: split source at function/class boundaries.

Why this exists (measured 2026-07-17, not assumed):

`ingest.chunk_text` splits code into fixed 300-line windows. Its own comment
claims that window is "small enough for a BM25/embedding retriever to score a
chunk as a coherent unit". For BM25 that is true. For the EMBEDDING retriever
it is false by ~4x: `bge-small-en-v1.5` (evals/provider.LocalEmbeddingProvider)
truncates at 512 tokens, keeping the first 512 and silently dropping the rest,
while a real 300-line window measures p50 ~2,234 tokens. So semantic retrieval
read roughly the first quarter of every window and was blind to the rest --
silently, on every repo, including the committed board.

Splitting on the AST instead makes the chunk boundary agree with the unit a
developer actually asks about (a function, a class), which almost always fits
inside 512 tokens. Measured on the comprehension board, same run, PR/issue
chunks held identical, only code chunking varied:

    arm           chunks   p50 tok   %>512   semantic r@5
    window-300        63     2,234     87%      69.2%
    ast              580       161     10%      92.3%

(Re-verified 2026-07-17 against the actual committed `test_ast_chunking_eval.py`
after the size-based safety valve below landed -- an EARLIER, less rigorous
measurement of this module claimed 100.0% recall / 433 chunks; that number was
never actually produced by the real, committed eval and should not have been
written here. Caught via the debugging playbook's sibling-sweep step: `emit()`
had no size cap at all, so a single dense function/class-head/module-blob
could ship as one unbounded chunk, and the aggregate p50/recall stats this
table reports don't surface a single outlier -- exactly how the gap survived
inside evidence already being measured. The valve fixes the outliers (see
`_MAX_EMITTED_CHUNK_LINES`/`_MAX_EMITTED_CHUNK_CHARS` below) and the real,
re-verified recall is still a decisive win over the baseline, just not 100%.)

This module is stdlib-only, deliberately. Python's `ast` covers the eval
board (simonw/llm is pure Python) and proves the approach WITHOUT spending a
new dependency on an unproven idea. Generalising to TS/TSX/Objective-C (i.e.
the React Native repos) needs tree-sitter, which is a real dependency decision
-- see docs/HANDOFF.md. Until then non-Python falls back to `chunk_text`, so
this can never do worse than today.
"""

import ast
import re
from typing import List

from .ingest import _CHUNK_MAX_CHARS, _CHUNK_WINDOW_LINES, chunk_text

# How many leading lines to scan for imports, and how many to keep, when
# building a chunk's scope header. A header exists so a retrieved method still
# shows what it belongs to and what it imports -- the "context header" the cAST
# / code-chunk research attaches to each chunk. Kept small: the header is
# overhead on every chunk, and a chunk's own body is what should dominate its
# embedding.
_IMPORT_SCAN_LINES = 80
_MAX_HEADER_IMPORTS = 15

# A class shorter than this stays whole: it IS the coherent unit a developer
# asks about, and it comfortably fits the embedder's 512-token budget. A longer
# one is split per method, or it would blow exactly the budget this module
# exists to respect.
_MAX_WHOLE_CLASS_LINES = 60

# The safety valve (found live 2026-07-17, via the debugging playbook's
# sibling-sweep step, applied AFTER the identical mechanism was already built
# into ts_chunk.py the same session for the same reason -- this module had it
# too and nothing caught it, since no existing fixture was large/dense enough
# to trigger any of the three unguarded assembly points below).
#
# A per-definition chunk, a large class's head-before-first-method chunk, or
# the module-level leftover-code chunk can each be emitted with NO size cap:
# a single real function/class whose body is unusually large or dense (one
# big literal, thousands of module-level assignments) shipped whole,
# regardless of size -- measured on the real committed corpus's own
# llm/cli.py at 23,497 chars vs chunk_text's 9,997 for the same file, and up
# to 57,786 chars (collapsing to essentially the whole file as one chunk) on
# a synthetic module-level-blob repro. Any single chunk this module wants to
# emit that exceeds this bound (2x chunk_text's own window, matching
# ts_chunk.py's identical threshold) gets re-windowed via chunk_text itself,
# using absolute source line numbers so the resulting refs stay honest
# GitHub line-links -- exactly the mechanism proven in ts_chunk.py.
_MAX_EMITTED_CHUNK_LINES = 2 * _CHUNK_WINDOW_LINES
_MAX_EMITTED_CHUNK_CHARS = 2 * _CHUNK_MAX_CHARS

_IMPORT_RE = re.compile(r"^\s*(?:import |from )")


def _scope_header(lines: List[str]) -> str:
    imports = [l for l in lines[:_IMPORT_SCAN_LINES] if _IMPORT_RE.match(l)]
    return "\n".join(imports[:_MAX_HEADER_IMPORTS])


def ast_chunk(text: str, ref_prefix: str) -> List[dict]:
    """Split Python `text` at function/class boundaries.

    Contract is identical to `ingest.chunk_text`: returns a list of
    ``{"ref": ..., "text": ...}`` dicts and never a "source" key -- the caller
    owns the source tag. Refs use the same ``#Lstart-Lend`` window format
    chunk_text already emits, so `gate._resolve` and `corpus.chunk_covers_lines`
    keep working unchanged: a citation is grounded when its lines are contained
    in the retrieved chunk's window, and an AST chunk is just a window whose
    bounds follow the code's own structure instead of a fixed line count.

    Falls back to `chunk_text` when the text isn't parseable Python (a syntax
    error, or any non-Python source) and when the module has no top-level
    functions or classes to split on -- in that case the file is already the
    coherent unit and must keep chunk_text's exact whole-file ref format,
    line-range suffix and all.
    """
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        # ValueError covers source containing null bytes -- classify_file
        # already rejects those, but ast_chunk must not assume its caller did.
        return chunk_text(text, ref_prefix)

    lines = text.splitlines()
    header = _scope_header(lines)
    path = ref_prefix.split(":", 1)[-1]

    def emit(start, end, scope=None) -> dict:
        label = f"# {path}" + (f" -- in class {scope}" if scope else "")
        body = "\n".join(lines[start - 1:end])
        parts = [label, header, "", body] if header else [label, body]
        return {"ref": f"{ref_prefix}#L{start}-L{end}", "text": "\n".join(parts)}

    out: List[dict] = []

    def emit_and_append(start, end, scope=None):
        # The safety valve: re-window via chunk_text -- plain, unlabeled,
        # exactly like the fallback path -- rather than ship a chunk worse
        # than the 300-line baseline this module exists to beat. Checked
        # against the FINAL assembled text (label + header + body), not just
        # the raw span, since header overhead alone can push a borderline
        # span over the bound. Uses ABSOLUTE source lines, so remapped refs
        # stay honest GitHub line-link ranges.
        line_count = end - start + 1
        candidate = emit(start, end, scope=scope)
        if line_count > _MAX_EMITTED_CHUNK_LINES or len(candidate["text"]) > _MAX_EMITTED_CHUNK_CHARS:
            sub_text = "\n".join(lines[start - 1:end])
            for sub in chunk_text(sub_text, ref_prefix):
                m = re.search(r"#L(\d+)-L(\d+)$", sub["ref"])
                if m:
                    s = start - 1 + int(m.group(1))
                    e = start - 1 + int(m.group(2))
                else:
                    s, e = start, end
                out.append({"ref": f"{ref_prefix}#L{s}-L{e}", "text": sub["text"]})
            return
        out.append(candidate)

    def real_start(node):
        # ast.FunctionDef/AsyncFunctionDef/ClassDef.lineno points to the
        # `def`/`class` line, NOT any @decorator above it (confirmed:
        # ast.parse gives them genuinely different line numbers) -- so a
        # decorated node's true start is its EARLIEST decorator, or its own
        # line if it has none. Using node.lineno alone left every decorator
        # uncovered, orphaning it into the module-level leftover bucket as
        # its own contentless chunk. Measured live on the real migrated
        # corpus: 92 of 580 chunks (15.9%) were exactly this.
        decorators = getattr(node, "decorator_list", None)
        return min(d.lineno for d in decorators) if decorators else node.lineno

    covered = set()

    def cover(node):
        covered.update(range(real_start(node), getattr(node, "end_lineno", node.lineno) + 1))

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            emit_and_append(real_start(node), getattr(node, "end_lineno", node.lineno))
            cover(node)
        elif isinstance(node, ast.ClassDef):
            methods = [n for n in node.body
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            span = getattr(node, "end_lineno", node.lineno) - node.lineno
            if span <= _MAX_WHOLE_CLASS_LINES or not methods:
                emit_and_append(real_start(node), getattr(node, "end_lineno", node.lineno))
            else:
                # The class docstring and class-level attributes belong to no
                # method. They are real evidence (a class constant answers a
                # "what is X" question just as a module constant does), so emit
                # them as their own chunk spanning declaration -> first method.
                # Without this they leak into the module preamble below and get
                # filed under a whole-file ref, misattributing them.
                #
                # Only when there IS something beyond the `class X:` line
                # though -- a chunk holding a bare declaration is pure noise,
                # and the class name already rides on every method chunk's
                # scope header. head_end stops BEFORE the first method's own
                # decorator (real_start, not .lineno), or that decorator would
                # appear in both this chunk and the method's own.
                head_end = real_start(methods[0]) - 1
                if "\n".join(lines[node.lineno:head_end]).strip():
                    emit_and_append(node.lineno, head_end)
                for m in methods:
                    emit_and_append(real_start(m), getattr(m, "end_lineno", m.lineno), scope=node.name)
            cover(node)

    if not out:
        # No top-level defs/classes (a constants module, a script). chunk_text
        # already handles this correctly -- don't invent a different ref shape.
        return chunk_text(text, ref_prefix)

    # Module-level code that isn't inside any emitted def/class: imports,
    # constants, __all__, the module docstring. This is real evidence (the
    # board asks about CONVERSATION_NAME_LENGTH, a bare module constant), so it
    # must not be dropped just because it has no AST boundary of its own.
    #
    # Grouped into NATURAL CONTIGUOUS RUNS rather than one blob spanning the
    # whole file: each run gets an honest absolute #Lstart-Lend (not a shared,
    # imprecise whole-file ref), and reuses emit_and_append, so a large
    # leftover run (found live: a big module-level blob collapsed to
    # essentially the whole file as one 57,786-char chunk before this fix)
    # degrades to chunk_text windowing exactly like everything else.
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
