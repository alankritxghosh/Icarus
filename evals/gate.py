# evals/gate.py
"""The deterministic honesty gate: turns the writer's raw reply into a Result
and can only ever fail safe toward abstention.

This is auditable code, not a model. An answer is emitted ONLY if the reply
parses as JSON with verdict "answer", a non-empty answer string, and at least
one citation that resolves to a chunk we actually retrieved. A parse failure, a
missing field, an explicit unknown, or citations we did not retrieve all
collapse to "unknown". The model cannot make us bluff: every emitted citation
is resolved back to a genuinely-retrieved ref (never invented).

Citation matching is tolerant of harmless reformatting the writer applies to a
retrieved ref -- dropping the `source:` prefix (`code:foo#L1-L2` -> `foo#L1-L2`)
or echoing the prompt's display brackets (`[code:foo#L1-L2]`) -- both observed
live and both previously discarded a correct, grounded code answer. Tolerance
only ever maps a citation onto a ref that WAS retrieved; a citation matching no
retrieved chunk is still forced to "unknown", so groundedness is not weakened.
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


def _debracket(cit) -> str:
    """A writer sometimes echoes the prompt's display brackets around a ref
    (`[code:foo#L1-L2]`). Strip surrounding brackets and whitespace. Non-strings
    (malformed JSON) become "" and match nothing."""
    if not isinstance(cit, str):
        return ""
    c = cit.strip()
    while len(c) >= 2 and c[0] == "[" and c[-1] == "]":
        c = c[1:-1].strip()
    return c


_LINES = re.compile(r"#L(\d+)(?:-L(\d+))?$")


# The complete set of source labels the ingester can emit (evals/ingest.py:
# _EXTENSION_SOURCES values plus pr/issue). Only these count as a `source:`
# prefix -- so a path that itself contains a ':' (legal in a git path, e.g.
# `dir/a:b.py`) is NOT mistaken for a source, which would false-reject a
# citation to it. Keep in sync if ingest gains a new source.
_KNOWN_SOURCES = frozenset({"code", "doc", "config", "pr", "issue"})


def _source(ref: str):
    """The `source:` label of a ref (`code:foo#L1` -> 'code'), or None if the ref
    carries no RECOGNIZED source prefix (a bare body, or a path whose own text
    happens to contain a ':'). Only a token in _KNOWN_SOURCES counts."""
    head = ref.split(":", 1)[0] if ":" in ref else None
    return head if head in _KNOWN_SOURCES else None


def _parse_ref(ref: str):
    """Split a ref into (path, start, end). Drops a recognized `source:` prefix
    and a trailing `#Lstart-Lend` (or `#Lline`) window. start/end are None for a
    whole-file / non-line ref (`code:foo.py`, `pr:1435`). Only a KNOWN source
    prefix is stripped, so a ':' inside a path is preserved as part of the path."""
    body = ref.split(":", 1)[1] if _source(ref) is not None else ref
    m = _LINES.search(body)
    if not m:
        return body, None, None
    path = body[: m.start()]
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else start
    return path, start, end


def _resolve(cit, retrieved: List[str]):
    """Map a writer citation to the canonical retrieved ref it denotes, tolerating
    reformatting the writer applies to a retrieved ref -- a dropped `source:`
    prefix, display brackets, or narrowing a chunk's window to the specific line
    it used (`code:foo.py#L1-L300` -> `foo.py#L21`) -- but NEVER matching a ref
    that was not retrieved. A citation grounds to a retrieved ref when: (a) if the
    citation names a source, it equals the retrieved ref's source; AND (b) their
    paths match; AND (c) the cited lines are CONTAINED in the retrieved chunk's
    window (every line the citation claims was actually shown to the writer).
    Returns the canonical retrieved ref, or None.

    (c) is CONTAINMENT, not overlap: a citation claiming lines BEYOND the
    retrieved window (`code:foo.py#L1-L10000` against a retrieved
    `code:foo.py#L250-L300`) is refused, because it asserts unretrieved lines --
    accepting it would let a broad citation launder a claim about evidence that
    was never shown. A whole-file retrieved chunk covers any citation to that
    path; a whole-file citation against a merely-windowed retrieved chunk is
    refused (it claims more than was shown).

    The source check (a) means a citation can never ground to a DIFFERENT source
    that merely shares a path/number (e.g. `code:1489` never grounds to a
    retrieved `pr:1489`); a bare-body citation (source dropped, the common LLM
    reformatting) keeps the prefix-drop tolerance."""
    cleaned = _debracket(cit)
    if not cleaned:
        return None
    if cleaned in retrieved:                       # exact (after debracketing)
        return cleaned
    csource = _source(cleaned)
    cpath, cstart, cend = _parse_ref(cleaned)
    if not cpath:
        return None
    for r in retrieved:
        if csource is not None and csource != _source(r):
            continue                               # named source must match
        rpath, rstart, rend = _parse_ref(r)
        if cpath != rpath:
            continue
        if rstart is None:                         # retrieved whole file covers any citation
            return r
        if cstart is None:                         # citation claims whole file but only a
            continue                               # window was retrieved -> claims more than shown
        if rstart <= cstart and cend <= rend:      # cited span is CONTAINED in retrieved window
            return r
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
    grounded = []
    for c in citations:
        r = _resolve(c, retrieved)
        if r is not None and r not in grounded:
            grounded.append(r)
    if not grounded:
        return Result(verdict="unknown")
    return Result(verdict="answer", answer=answer.strip(), citations=grounded, retrieved=list(retrieved))
