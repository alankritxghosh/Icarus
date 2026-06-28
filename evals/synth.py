# evals/synth.py
"""Builds the strict cite-or-abstain prompt for the answer-writer.

The writer may only use the numbered evidence and must reply as JSON: either an
answer with the refs it relied on, or an explicit unknown. The deterministic
gate (evals/gate.py) enforces this afterwards; the prompt just asks for it.
"""

from typing import List

from .corpus import Chunk

INSTRUCTION = (
    "You answer questions about a software project using ONLY the numbered "
    "evidence below.\n"
    "Rules:\n"
    "1. If the evidence explicitly states the reason/answer, reply with JSON: "
    '{"verdict": "answer", "answer": "<one or two sentences>", '
    '"citations": ["<ref>", ...]}. Cite only the refs whose text supports it.\n'
    '2. If the evidence does NOT contain the answer, reply with JSON: '
    '{"verdict": "unknown"}.\n'
    "3. Never use outside knowledge. Never guess. When unsure, choose unknown.\n"
    "Reply with JSON and nothing else."
)

_MAX_CHUNK_CHARS = 1500


def build_prompt(question: str, chunks: List[Chunk]) -> str:
    blocks = []
    for c in chunks:
        text = c.text.strip()
        if len(text) > _MAX_CHUNK_CHARS:
            text = text[:_MAX_CHUNK_CHARS] + " …"
        blocks.append(f"[{c.ref}]\n{text}")
    return f"{INSTRUCTION}\n\nQUESTION: {question}\n\nEVIDENCE:\n" + "\n\n".join(blocks)
