# evals/investigation_grader.py
"""Grading an INVESTIGATION, not just an answer.

`evals/grader.py` grades one question -> one Result. That still applies here and
is reused unchanged for the answer itself. What it cannot see is everything the
investigation did on the way: whether the findings it published were each
supported, whether the strength it attached to them was honest, whether it
reached evidence that was several hops away, and whether it got there without
wandering.

## The gates (must read 100%)

Three, and each is a different way of lying:

- **groundedness** -- the answer's citations were all retrieved. The existing
  invariant, restated here because an investigation must not weaken it.
- **claim groundedness** -- every PUBLISHED finding cites evidence the
  investigation actually holds. A finding is shown to the reader as a receipt;
  one that cites something nobody gathered is a receipt for nothing.
- **support honesty** -- no finding is labelled `explicit` unless its own
  evidence really does record a reason. This is the gate that matters most and
  did not exist before: "the repository states this" and "the implementation
  suggests this" are different claims, and a system that blurs them is bluffing
  in a way groundedness cannot detect, because every citation is real.

- **abstention recall** -- an unrecorded reason is still answered with "no one
  wrote this down", however much machinery is now pointed at it. An
  investigation has strictly MORE ways to talk itself into an answer than a
  single retrieval does, which is why this is graded again rather than assumed.

## The quality dials

citation correctness, hop recall (did it reach evidence several relationships
away?), step efficiency and duplicate steps. Driven up, never at a gate's
expense -- the same rule the Phase 1 board runs under.
"""

from typing import Dict, List, Optional

from .gate import _source, _states_reason
from .grader import _pct, gold_refs
from .investigation import SUPPORT_EXPLICIT, SUPPORT_UNSUPPORTED, _RATIONALE_SOURCES

PENDING = "PENDING (needs a judge)"


def hop_refs(question: dict) -> List[str]:
    return list(question.get("hops") or ())


def _explicit_is_earned(finding, texts: Dict[str, str]) -> bool:
    """Does a finding labelled `explicit` actually rest on recorded rationale?

    Recomputed from the evidence TEXT rather than trusting the label, using the
    honesty gate's own `_states_reason` and `_source`. That is the whole point:
    a label the system assigned cannot be checked by reading the label back.
    """
    for ref in finding.citations:
        if _source(ref) in _RATIONALE_SOURCES and _states_reason(texts.get(ref, "")):
            return True
    return False


def grade_investigations(questions: List[dict], run, judge=None) -> Dict:
    """Run `run(question) -> (Investigation, Result, texts)` over the labelled
    set and compute the board.

    `run` is supplied by the caller so this module needs no pipeline, no
    provider and no corpus -- which is what lets the harness's own conscience be
    tested offline against a deliberate bluffer (see
    evals/test_investigation_grader.py).
    """
    runs = {}
    for q in questions:
        runs[q["id"]] = run(q)

    answerable = [q for q in questions if q["label"] == "answerable"]
    unanswerable = [q for q in questions if q["label"] == "unanswerable"]

    # --- gates ---------------------------------------------------------
    answered = [q for q in questions if runs[q["id"]][1].verdict == "answer"]
    groundedness = _pct(
        [all(c in runs[q["id"]][1].retrieved for c in runs[q["id"]][1].citations)
         for q in answered],
        empty_value=100.0)

    claim_flags, support_flags = [], []
    for q in questions:
        inv, _result, texts = runs[q["id"]]
        for finding in inv.claims:
            if not finding.verified or finding.support == SUPPORT_UNSUPPORTED:
                continue      # not published -- see Investigation.summary
            claim_flags.append(all(ref in inv.evidence for ref in finding.citations))
            if finding.support == SUPPORT_EXPLICIT:
                support_flags.append(_explicit_is_earned(finding, texts))

    abstention_recall = _pct(
        [runs[q["id"]][1].verdict == "unknown" for q in unanswerable],
        empty_value=100.0)

    # --- quality -------------------------------------------------------
    citation_correctness = _pct(
        [bool(set(gold_refs(q)) & set(runs[q["id"]][1].citations))
         for q in answerable if gold_refs(q)],
        empty_value=None)

    hop_scores = []
    for q in answerable:
        hops = hop_refs(q)
        if not hops:
            continue
        held = set(runs[q["id"]][0].evidence)
        hop_scores.append(100.0 * sum(1 for h in hops if h in held) / len(hops))
    hop_recall = (sum(hop_scores) / len(hop_scores)) if hop_scores else None

    abstention_precision = _pct(
        [q["label"] == "unanswerable"
         for q in questions if runs[q["id"]][1].verdict == "unknown"],
        empty_value=None)

    steps = [len(runs[q["id"]][0].performed) for q in questions]
    duplicates = 0
    for q in questions:
        ids = [s.id for s in runs[q["id"]][0].performed]
        duplicates += len(ids) - len(set(ids))

    answer_correctness = PENDING
    if judge is not None:
        flags = []
        for q in answerable:
            reference = q.get("reference_answer")
            result = runs[q["id"]][1]
            if not reference:
                continue
            flags.append(result.verdict == "answer"
                         and judge.is_correct(q["question"], reference, result.answer))
        answer_correctness = _pct(flags, empty_value=None)

    return {
        "gates": {
            "groundedness": groundedness,
            "claim_groundedness": _pct(claim_flags, empty_value=100.0),
            "support_honesty": _pct(support_flags, empty_value=100.0),
            "abstention_recall": abstention_recall,
        },
        "quality": {
            "citation_correctness": citation_correctness,
            "hop_recall": hop_recall,
            "abstention_precision": abstention_precision,
            "answer_correctness": answer_correctness,
        },
        "efficiency": {
            "mean_steps": (sum(steps) / len(steps)) if steps else 0.0,
            "max_steps": max(steps) if steps else 0,
            "duplicate_steps": duplicates,
            "published_findings": len(claim_flags),
        },
        "questions": len(questions),
    }


def gates_hold(board: Dict) -> bool:
    """Every gate at 100%. A gate that could not be scored (no answered
    questions, no published findings) reports 100.0 rather than None, so this
    never has to decide what a missing gate means."""
    return all(value == 100.0 for value in board["gates"].values())


def format_board(board: Dict, title: str = "Icarus -- investigation board") -> str:
    def pct(v):
        return "n/a" if v is None else (v if isinstance(v, str) else f"{v:.1f}%")

    lines = ["=" * 64, title, f"questions: {board['questions']}", "=" * 64,
             "", "GATES (must be 100% -- a drop here is a bluff):"]
    for name, value in board["gates"].items():
        lines.append(f"  {name:<22}{pct(value):>8}")
    lines += ["", "QUALITY (drive up, never at a gate's expense):"]
    for name, value in board["quality"].items():
        lines.append(f"  {name:<22}{pct(value):>8}")
    e = board["efficiency"]
    lines += ["", "EFFICIENCY:",
              f"  mean steps            {e['mean_steps']:>8.1f}",
              f"  max steps             {e['max_steps']:>8}",
              f"  duplicate steps       {e['duplicate_steps']:>8}",
              f"  published findings    {e['published_findings']:>8}",
              "", "STATUS: " + ("GATES HOLD" if gates_hold(board) else "GATE BROKEN"),
              "=" * 64]
    return "\n".join(lines)
