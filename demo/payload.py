# demo/payload.py
"""Turn a pipeline Result into the JSON the demo page renders.

Answers carry prose + citations (each with a source URL). The honest "unknown"
carries no answer and no citations, but always exposes `searched` (the retrieved
refs) so the abstention is transparent to the viewer -- you can see what it
looked at before it honestly declined.
"""

from evals.pipeline import Result

from .links import ref_to_url


def build_payload(result: Result, repo: str, commit: str) -> dict:
    citations = []
    if result.verdict == "answer":
        citations = [{"ref": ref, "url": ref_to_url(ref, repo, commit)} for ref in result.citations]
    return {
        "verdict": result.verdict,
        "answer": result.answer if result.verdict == "answer" else "",
        "citations": citations,
        "searched": list(result.retrieved),
    }
