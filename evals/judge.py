# evals/judge.py
"""LLM-judge-with-reference for answer correctness (the fuzzy, judge-later
quality dial -- NOT an honesty gate). Builds a judge prompt and deterministically
parses the reply into correct/incorrect, failing safe to incorrect. Reuses the
Provider abstraction so the unit suite runs offline with StaticProvider.
"""

import json
import re

JUDGE_INSTRUCTION = (
    "You are grading whether a CANDIDATE answer matches the REFERENCE answer for "
    "a question about a software project. Judge only whether the candidate states "
    "the same core reason/fact as the reference. Ignore wording, length, and extra "
    "true detail. Do not reward a confident answer that contradicts or omits the "
    "reference's core reason.\n"
    'Reply with JSON and nothing else: {"verdict": "correct"} or '
    '{"verdict": "incorrect"}.'
)

_MAX_CANDIDATE_CHARS = 1500


def build_judge_prompt(question: str, reference: str, candidate: str) -> str:
    cand = candidate.strip()
    if len(cand) > _MAX_CANDIDATE_CHARS:
        cand = cand[:_MAX_CANDIDATE_CHARS] + " …"
    return (
        f"{JUDGE_INSTRUCTION}\n\nQUESTION: {question}\n\n"
        f"REFERENCE: {reference}\n\nCANDIDATE: {cand}"
    )


_JSON = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(raw: str) -> bool:
    """True only if the reply parses as JSON with verdict 'correct'; else False.
    Fails safe to incorrect (an unparseable judge never inflates the score)."""
    m = _JSON.search(raw or "")
    if not m:
        return False
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and data.get("verdict") == "correct"


class Judge:
    """Wraps a Provider into an answer-correctness judge."""

    def __init__(self, provider):
        self._provider = provider

    def is_correct(self, question: str, reference: str, candidate: str) -> bool:
        prompt = build_judge_prompt(question, reference, candidate)
        return parse_verdict(self._provider.complete(prompt))
