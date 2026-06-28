# evals/gate.py
"""The deterministic honesty gate: turns the writer's raw reply into a Result
and can only ever fail safe toward abstention.

This is auditable code, not a model. An answer is emitted ONLY if the reply
parses as JSON with verdict "answer", a non-empty answer string, and at least
one citation that was actually retrieved. A parse failure, a missing field, an
explicit unknown, or citations we did not retrieve all collapse to "unknown".
The model cannot make us bluff: groundedness is guaranteed by construction
(citations are filtered to the retrieved set).
"""

import json
import re
from typing import List

from .pipeline import Result

_JSON = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str):
    m = _JSON.search(raw or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (ValueError, TypeError):
        return None


def gate(raw: str, retrieved: List[str]) -> Result:
    data = _extract_json(raw)
    if not isinstance(data, dict) or data.get("verdict") != "answer":
        return Result(verdict="unknown")
    answer = data.get("answer")
    citations = data.get("citations")
    if not isinstance(answer, str) or not answer.strip():
        return Result(verdict="unknown")
    if not isinstance(citations, list):
        return Result(verdict="unknown")
    retrieved_set = set(retrieved)
    grounded = [c for c in citations if c in retrieved_set]
    if not grounded:
        return Result(verdict="unknown")
    return Result(verdict="answer", answer=answer.strip(), citations=grounded, retrieved=list(retrieved))
