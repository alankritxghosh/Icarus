# evals/judge.py
"""LLM-judge-with-reference for answer correctness (the fuzzy, judge-later
quality dial -- NOT an honesty gate). Builds a judge prompt and deterministically
parses the reply into correct/incorrect, failing safe to incorrect. Reuses the
Provider abstraction so the unit suite runs offline with StaticProvider.
"""

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
