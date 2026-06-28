# evals/corpus.py
"""The corpus: chunks of evidence, each carrying a citation ref.

A chunk is one retrievable unit. `ref` is the normalized "source:ref" citation
the grader checks against gold (e.g. "pr:1435", "code:llm/models.py"). The
corpus is generated once by ingest.py and committed as chunks.jsonl so evals
run offline and reproducibly.
"""

import json
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
