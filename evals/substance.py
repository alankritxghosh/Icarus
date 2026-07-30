# evals/substance.py
"""Did an answer actually ANSWER, or did it just say something true?

A QUALITY DIAL, never a gate. Nothing here touches the honesty path: it cannot
change a verdict, force an abstention, or affect what may be cited. It exists
to measure one thing the existing metrics cannot see.

WHY IT EXISTS. Found live on alankritxghosh/Icarus, on the tour's `conventions`
step:

    "The project asks the question, 'What conventions or practices does this
     project expect contributors to follow?' as part of its guided onboarding
     tour."                          -- citing code:demo/onboarding.py#L1-L90

Retrieval had matched the literal question string in Icarus's own source, and
the writer described the question's EXISTENCE rather than answering it. The
citation is real, so the honesty gate correctly let it through -- the gate
checks that evidence was genuinely retrieved, not that an answer is useful.
And `evals/onboarding_probe.py` counted it as one of `conventions`' 9/10
successes, which means the headline "54/70 answered" is softer than it reads.

This is deliberately NOT `evals/judge.py`. That judge grades a candidate
against a REFERENCE answer, and ten arbitrary public repositories have no
reference answers. The question here is different and needs no reference: does
this text answer the question asked, or does it dodge?

Fails safe to HOLLOW. This judge grades our own output, so an unparseable or
failed reply must never inflate the score -- the same reasoning that makes
`judge.parse_verdict` fail safe to "incorrect".
"""

from .gate import extract_json

SUBSTANCE_INSTRUCTION = (
    "You are grading whether an ANSWER actually answers the QUESTION asked "
    "about a software project, or whether it dodges.\n"
    "Mark it \"hollow\" if it: restates or describes the question instead of "
    "answering it; says only that the topic exists, is discussed, or is asked "
    "about somewhere; describes the project's documentation or tooling rather "
    "than the thing asked about; or is so vague it would be true of almost any "
    "repository.\n"
    "Mark it \"substantive\" if a reader would learn something specific and "
    "concrete about THIS project from it -- even if brief, and even if "
    "incomplete.\n"
    "Judge only substance. Ignore length, tone, formatting, and whether you "
    "personally believe the claim is correct.\n"
    'Reply with JSON and nothing else: {"verdict": "substantive"} or '
    '{"verdict": "hollow"}.'
)

_MAX_ANSWER_CHARS = 2000


def build_substance_prompt(question: str, answer: str) -> str:
    text = (answer or "").strip()
    if len(text) > _MAX_ANSWER_CHARS:
        text = text[:_MAX_ANSWER_CHARS] + " …"
    return f"{SUBSTANCE_INSTRUCTION}\n\nQUESTION: {question}\n\nANSWER: {text}"


def parse_substance(raw) -> bool:
    """True only if the reply parses as JSON with verdict 'substantive'."""
    data = extract_json(raw)
    return isinstance(data, dict) and data.get("verdict") == "substantive"


def is_substantive(provider, question: str, answer: str) -> bool:
    """Ask `provider` whether `answer` answers `question`.

    An empty answer is hollow without spending a call -- an abstention has no
    text, and counting one as substantive would be a lie. A provider failure is
    hollow too: a measurement that cannot be taken must not be scored as a win.
    """
    if not (answer or "").strip():
        return False
    try:
        return parse_substance(provider.complete(build_substance_prompt(question, answer)))
    except Exception:
        return False
