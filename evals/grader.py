"""Deterministic grading of pipeline Results against the labelled set.

Only the auditable, label-checkable metrics live here (the "deterministic-now"
half agreed for Phase 1): groundedness, abstention recall/precision, retrieval
recall@k, citation correctness. Fuzzy *answer correctness* (prose vs a reference)
is the "judge-later" half -- it is reported as PENDING, never faked into a number,
so the board never looks greener than it has earned.

Two metrics are GATES that must read 100% on every run (docs/EVALUATION.md):
groundedness and abstention recall. The rest are quality dials we drive upward.
"""

from typing import Dict, List, Optional

from .pipeline import Pipeline, Result


def gold_refs(question: dict) -> List[str]:
    """Normalized gold citations for an answerable question, as "source:ref".

    Accepts either shape: a flat `citations: ["source:ref", ...]` list (already
    normalized, used by comprehension_questions.json), or the dict-list
    `gold_citations: [{"source", "ref"}, ...]` (used by phase1_questions.json).
    """
    if "citations" in question:
        return question["citations"]
    return [f"{c['source']}:{c['ref']}" for c in question.get("gold_citations", [])]


def _pct(flags: List[bool], empty_value: Optional[float]) -> Optional[float]:
    """Percentage of True in flags; empty_value when there is nothing to score."""
    if not flags:
        return empty_value
    return 100.0 * sum(1 for f in flags if f) / len(flags)


def grade(questions: List[dict], pipeline: Pipeline, k: int = 5, judge=None) -> Dict:
    """Run the pipeline over every question and compute the metric board.

    `judge` is the optional answer-correctness judge (the fuzzy, judge-later
    quality dial -- NOT an honesty gate). When None, answer_correctness stays the
    PENDING string and grading is unchanged. When given, it must expose
    is_correct(question, reference, candidate) -> bool. The judge never touches
    the deterministic gates: a wrong-but-confident answer is a quality miss, a
    bluff is still caught by groundedness/abstention recall.
    """
    results: Dict[str, Result] = {q["id"]: pipeline.answer(q["question"]) for q in questions}

    answerable = [q for q in questions if q["label"] == "answerable"]
    unanswerable = [q for q in questions if q["label"] == "unanswerable"]

    # --- Gates (must be 100%) ---
    # Groundedness: every answered question's citations are a subset of what it
    # retrieved. With no claims made, this is vacuously 100% (no ungrounded claims).
    answered = [q for q in questions if results[q["id"]].verdict == "answer"]
    groundedness = _pct(
        [all(c in results[q["id"]].retrieved for c in results[q["id"]].citations) for q in answered],
        empty_value=100.0,
    )
    # Abstention recall: of the truly-unrecorded questions, how many were abstained on.
    abstention_recall = _pct(
        [results[q["id"]].verdict == "unknown" for q in unanswerable],
        empty_value=100.0,
    )

    # --- Quality dials (drive upward; never at the expense of a gate) ---
    # Abstention precision: of all the abstentions, how many were truly unrecorded.
    abstained = [q for q in questions if results[q["id"]].verdict == "unknown"]
    abstention_precision = _pct(
        [q["label"] == "unanswerable" for q in abstained],
        empty_value=100.0,  # never abstaining = no false abstentions
    )
    # Retrieval recall@k: of answerable questions, how many had a gold ref in the top k.
    retrieval_recall = _pct(
        [any(g in results[q["id"]].retrieved[:k] for g in gold_refs(q)) for q in answerable],
        empty_value=None,
    )
    # Citation correctness: of answerable questions, how many were answered AND cited
    # every gold ref. Denominator is all answerable, so never-answering reads 0%.
    citation_correctness = _pct(
        [
            results[q["id"]].verdict == "answer"
            and all(g in results[q["id"]].citations for g in gold_refs(q))
            for q in answerable
        ],
        empty_value=None,
    )

    # Answer correctness: the fuzzy, judge-later dial. Only computed when a judge
    # is supplied; otherwise it stays PENDING (never faked into a number). Scored
    # over all answerable: an abstention or a wrong answer is not correct, so the
    # judge can never reward a bluff or outrun honest, correct answering.
    if judge is None:
        answer_correctness = "PENDING (manual / judge-later)"
    else:
        answer_correctness = _pct(
            [
                results[q["id"]].verdict == "answer"
                and judge.is_correct(q["question"], q["reference_answer"], results[q["id"]].answer)
                for q in answerable
            ],
            empty_value=None,
        )

    gates_ok = groundedness == 100.0 and abstention_recall == 100.0
    quality_met = retrieval_recall == 100.0 and citation_correctness == 100.0

    if not gates_ok:
        status = "RED -- HONESTY GATE BROKEN (this must never happen)"
    elif not quality_met:
        status = "RED -- gates hold, quality below target"
    else:
        status = "GREEN -- gates hold, quality at target (answer correctness still manual)"

    return {
        "k": k,
        "counts": {"total": len(questions), "answerable": len(answerable), "unanswerable": len(unanswerable)},
        "gates": {"groundedness": groundedness, "abstention_recall": abstention_recall},
        "quality": {
            "abstention_precision": abstention_precision,
            "retrieval_recall_at_k": retrieval_recall,
            "citation_correctness": citation_correctness,
        },
        "answer_correctness": answer_correctness,
        "gates_ok": gates_ok,
        "quality_met": quality_met,
        "status": status,
        "per_question": {
            q["id"]: {"label": q["label"], "verdict": results[q["id"]].verdict}
            for q in questions
        },
    }
