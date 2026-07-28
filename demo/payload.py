# demo/payload.py
"""Turn a pipeline Result into the JSON the demo page renders.

Answers carry prose + citations (each with a source URL). The honest "unknown"
carries no answer and no citations, but always exposes `searched` (the retrieved
refs) so the abstention is transparent to the viewer -- you can see what it
looked at before it honestly declined.

`anchored` splits out the refs that were looked up because the QUESTION named
them, from the ones search merely suggested. Both are in `searched` (anchors
first), but a flat list made a correctly-anchored abstention -- "PR 6952" looked
up first, exactly as asked -- read as "ignored the question and searched
blindly". Additive: `searched` still lists everything, so "all of them shown"
stays true.
"""

from evals.pipeline import Result

from .links import ref_to_url

# A citation excerpt is PROOF shown inline, not a preview pane: it has to fit a
# small overlay without pushing the answer off screen. Bounded on both axes --
# lines and characters -- because one machine-generated line can be enormous
# (measured up to ~250,000 chars during ingest work) and a line cap alone
# wouldn't catch it.
_EXCERPT_LINES = 4
_EXCERPT_CHARS = 300
_EXCERPT_LINE_CHARS = 96


def excerpt(text: str) -> str:
    """The first few real lines of a cited chunk, bounded for display.

    Truncation is always MARKED with a '…' so the reader can never mistake a
    clipped excerpt for the whole of the evidence -- an unmarked clip would be a
    quiet misrepresentation of the proof, which is the one thing this product
    cannot do.
    """
    if not text:
        return ""
    out, total = [], 0
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if len(line) > _EXCERPT_LINE_CHARS:
            line = line[:_EXCERPT_LINE_CHARS].rstrip() + "…"
        out.append(line)
        total += len(line)
        if len(out) >= _EXCERPT_LINES or total >= _EXCERPT_CHARS:
            break
    joined = "\n".join(out)
    # Mark the clip whenever anything was dropped, by lines or by characters.
    stripped = [l for l in text.splitlines() if l.strip()]
    if len(stripped) > len(out) or any(len(l.rstrip()) > _EXCERPT_LINE_CHARS for l in stripped[:len(out)]):
        joined += "\n…"
    return joined


def build_payload(result: Result, repo: str, commit: str, indexing: bool = False) -> dict:
    """`indexing` marks an answer produced while the search index is still being
    built (lexical only, semantic pending).

    It exists because an abstention in that window means "I have not finished
    reading", which is a DIFFERENT claim from "no one wrote this down" -- and
    this product's whole promise is that the second one is trustworthy. Proven
    live 2026-07-28: the same question abstained mid-window and answered once
    the embed finished, on an identical corpus. Defaults False so every existing
    caller keeps its exact shape."""
    citations = []
    if result.verdict == "answer":
        citations = [{"ref": ref,
                      "url": ref_to_url(ref, repo, commit),
                      "excerpt": excerpt(result.evidence.get(ref, ""))}
                     for ref in result.citations]
    return {
        "verdict": result.verdict,
        "answer": result.answer if result.verdict == "answer" else "",
        "citations": citations,
        "searched": list(result.retrieved),
        "anchored": list(result.anchored),
        "indexing": bool(indexing),
        # WHY it abstained (evals/gate.py's ABSTAIN_* constants), so the
        # unknowns map can separate "nobody recorded this" from "the thing you
        # asked about isn't in this repo". None on an answer.
        "reason": result.abstention_reason if result.verdict == "unknown" else None,
    }
