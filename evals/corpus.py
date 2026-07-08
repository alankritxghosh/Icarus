# evals/corpus.py
"""The corpus: chunks of evidence, each carrying a citation ref.

A chunk is one retrievable unit. `ref` is the normalized "source:ref" citation
the grader checks against gold (e.g. "pr:1435", "code:llm/models.py"). The
corpus is generated once by ingest.py and committed as chunks.jsonl so evals
run offline and reproducibly.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Chunk:
    ref: str
    source: str  # "pr" | "issue" | "code"
    text: str


def load_chunks(path) -> List[Chunk]:
    chunks: List[Chunk] = []
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        chunks.append(Chunk(ref=d["ref"], source=d["source"], text=d["text"]))
    return chunks


_LINE_RANGE = re.compile(r"^L(\d+)-L(\d+)$")
_FILE_ADDRESSABLE_SOURCES = ("code", "doc", "config")


def chunk_covers_lines(chunk: Chunk, path: str, start: int, end: int) -> bool:
    """Does `chunk` cover any line in [start, end] (1-indexed, inclusive) of
    `path`? Brick D's line-resolution primitive: a GitHub selection names a
    file + line range, not a search query, so this replaces retrieval for the
    "anchor" evidence.

    Only code/doc/config chunks are file-addressable at all -- a pr:/issue:
    ref has no line semantics. Within a matching path, a chunk produced by
    ingest.py's chunk_text() is one of two real shapes: a windowed chunk with
    a `#Lstart-Lend` suffix (overlap-tested against [start, end]), or a
    whole-file chunk with NO suffix (chunk_text's own contract when a file
    fits in one window -- see its docstring) -- which matches ANY requested
    range in that file, since whole-file is the finest granularity available
    for it. A malformed line suffix (should never happen from chunk_text, but
    a corpus is data, not code -- fail closed) never matches, never raises.
    """
    if chunk.source not in _FILE_ADDRESSABLE_SOURCES:
        return False
    ref_path, hash_sep, line_range = chunk.ref.partition(":")[2].partition("#")
    if ref_path != path:
        return False
    if not hash_sep:
        return True  # whole-file chunk: covers any line in this file
    m = _LINE_RANGE.match(line_range)
    if not m:
        return False
    chunk_start, chunk_end = int(m.group(1)), int(m.group(2))
    return chunk_start <= end and start <= chunk_end
