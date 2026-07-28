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

HONEST BOUNDARY (what is and isn't deterministic here):
- GROUNDEDNESS is fully deterministic and auditable: every emitted citation is
  resolved back to a genuinely-retrieved ref, with a valid, contained line
  window -- the writer can never make us cite invented or unretrieved evidence.
- ABSTENTION when the answer was never written down is only PARTLY provable in
  code. Two deterministic guards catch the clearest dodges: (b) a "why" question
  answered from evidence that records no reason (a bare code constant), and (c) a
  question naming a DISTINCTIVE code identifier that appears nowhere in the
  evidence the writer saw -- a fabricated symbol grounded to adjacent real code
  (Redis's non-existent "HYPERVECTOR" over the real vector-set code, found live).
  Neither makes the gate a model: it cannot semantically verify that arbitrary
  evidence truly ENTAILS an arbitrary answer. For cases (b)/(c) don't cover,
  abstention still leans on the cite-or-abstain writer. So:
  no bluffed citations, ever (deterministic); "I don't know when unrecorded" is
  code-enforced for the clear case and writer-reliant beyond it. Don't overclaim.
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
_KNOWN_SOURCES = frozenset({"code", "doc", "config", "pr", "issue", "commit"})


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
    csource = _source(cleaned)
    cpath, cstart, cend = _parse_ref(cleaned)
    if not cpath:
        return None
    # A malformed line window (line 0/negative, or end < start) is not a real
    # location -- it can only be fabricated or garbled, so it must never ground.
    # Guard here, BEFORE the exact-match shortcut, so a malformed ref can't slip
    # through even if it textually equals a (equally malformed) retrieved string.
    if cstart is not None and (cstart < 1 or cend < cstart):
        return None
    if cleaned in retrieved:                       # exact (after debracketing)
        return cleaned
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


# --- (b) rationale-support guard ----------------------------------------------
# Groundedness (citations subset of retrieved) proves the writer cited real
# evidence, but NOT that the evidence answers the question. The blind spot is a
# "why" question answered with a "what": "why is the limit 32?" -> "it's 32,
# defined in models.py" cites a real code line that contains no REASON. This
# guard lets the gate refuse that: when the question seeks a rationale, at least
# one grounded chunk's text must actually state a reason, else abstain.
#
# It is a deterministic heuristic, and deliberately fail-safe: it can only ever
# turn an "answer" into "unknown", never the reverse -- so it cannot weaken
# groundedness or abstention recall. Its only cost is possible over-abstention on
# a genuinely answerable why-question (a QUALITY trade, measured on the board),
# never a bluff. Only active when the caller supplies both `question` and
# `evidence` (the serving pipeline does); older 2-arg callers are unaffected.
_SEEKS_RATIONALE = re.compile(r"\b(why|rationale|reason(?:ing|ed|s)?|motivat\w*)\b", re.I)

_RATIONALE_MARKERS = (
    "because", "since ", "so that", "so as", "in order to", "to avoid",
    "to ensure", "to prevent", "to support", "to allow", "to keep", "to make ",
    "rather than", "instead of", "the reason", "rationale", "chosen", "chose ",
    "decided", "decision", "intended", "intent", "motivat", "designed to",
    "this allows", "this ensures", "this lets", "we want", "we need",
    "so we ", "which lets", "which allows", "avoids", "ensures", "prevents",
)


def _seeks_rationale(question) -> bool:
    return isinstance(question, str) and _SEEKS_RATIONALE.search(question) is not None


# --- (d) self-disclaiming answer guard ----------------------------------------
# The gate takes the writer's own `verdict` field at face value. A writer can set
# verdict="answer" and then write prose that is plainly an ABSTENTION -- found
# live 2026-07-22 on psf/requests:
#
#   Q: "Why is DEFAULT_REDIRECT_LIMIT exactly 30?"
#   A: "The evidence does not state a specific reason for why the limit is 30;
#       it only defines DEFAULT_REDIRECT_LIMIT as 30 in the source code."
#   verdict: "answer"   <- wrong; this is an honest unknown wearing the wrong label
#
# Guard (b) let it through because the cited 107-line chunk happened to contain
# "to ensure" in an UNRELATED comment, which satisfied _states_reason. Rather than
# trying to make (b) semantically precise (that way lies building a model), this
# guard reads the ANSWER: if the writer says it doesn't know, believe it, whatever
# the verdict field claims.
#
# Nothing about groundedness changes -- this only ever turns "answer" into
# "unknown", so it cannot admit a bluff. The risk is the opposite one, over-
# abstention, which is why the patterns require a disclaimer ABOUT A REASON or
# about the evidence itself, not any ordinary negation. "The code does not
# validate input" and "the timeout is not configurable" are real answers and must
# not trip it; the board is the check on that.
_DISCLAIMS_ANSWER = (
    # "does not state/give/explain ... a reason" (also doesn't / did not / don't)
    re.compile(r"\b(?:do(?:es)?|did)\s*n(?:o|')t\s+"
               r"(?:state|say|specify|explain|mention|provide|indicate|give|record|document)\b"
               r"[^.]{0,60}?\b(?:reason|rationale|explanation|why|justification|motivation)\b", re.I),
    # "the reason is not stated / was never documented"
    re.compile(r"\b(?:reason|rationale|explanation|justification)\b[^.]{0,40}?"
               r"\b(?:is|was|are|were)\s+(?:not|never)\s+"
               r"(?:stated|specified|explained|given|provided|recorded|documented)\b", re.I),
    # "no specific reason is given" / "no explanation"
    re.compile(r"\bno\s+(?:specific\s+|explicit\s+|documented\s+|stated\s+)?"
               r"(?:reason|rationale|explanation|justification)\b", re.I),
)


def _disclaims_answer(answer) -> bool:
    """True when the answer's own prose says the reason isn't recorded."""
    if not isinstance(answer, str):
        return False
    return any(p.search(answer) for p in _DISCLAIMS_ANSWER)


def _states_reason(text) -> bool:
    if not isinstance(text, str):
        return False
    low = text.lower()
    return any(m in low for m in _RATIONALE_MARKERS)


# --- (c) entity-presence guard ------------------------------------------------
# Groundedness proves the citation was retrieved, not that the question's SUBJECT
# exists. A fabricated symbol whose name sits next to real, adjacent code -- "how
# does Redis's HYPERVECTOR type store embeddings?" over the real vector-set code
# -- can be answered confidently even though `HYPERVECTOR` appears NOWHERE in the
# evidence (found live 2026-07-18). This guard extracts the DISTINCTIVE code
# identifiers a question names (snake_case, an internal camelCase boundary, or a
# long ALL-CAPS token -- the shapes that must appear verbatim in real code) and,
# if any is absent from every evidence chunk the writer saw, forces unknown.
# Deterministic and fail-safe: only ever turns answer -> unknown, so it cannot
# weaken groundedness or abstention recall; its only cost is possible
# over-abstention (a QUALITY trade, measured on the board). A plain word or a
# single Title-case word (`Interceptor`, `Scheduler`) is deliberately NOT
# distinctive -- flagging those would over-abstain on ordinary prose; the
# accepted gap is a fabricated single-Capitalized-word type. Only active when the
# caller supplies `evidence` (the serving path); 2-arg callers are unaffected.
_IDENT_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:(?:\.|::)[A-Za-z_][A-Za-z0-9_]*)*")

# Common all-caps tech acronyms that read as ordinary subject words, not code
# symbols -- excluded so "how does HTTP parsing work" is never force-abstained
# just for naming a real, non-identifier acronym.
_COMMON_ACRONYMS = frozenset({
    "HTTP", "HTTPS", "JSON", "HTML", "XML", "YAML", "TOML", "REST", "GRPC",
    "SQL", "TCP", "UDP", "DNS", "URL", "URI", "CORS", "OAUTH", "JWT", "CSS",
    "CLI", "SDK", "SSL", "TLS", "API", "CRUD", "UUID", "ASCII", "UTF", "RPC",
})


def _is_distinctive(sym: str) -> bool:
    """A code-identifier-shaped token unusual enough that real evidence would
    contain it verbatim if the question were truly about it: snake_case, an
    internal camelCase boundary, or a long non-acronym ALL-CAPS token."""
    if "_" in sym:
        return True
    if re.search(r"[a-z][A-Z]", sym):
        return True
    return sym.isupper() and sym.isalpha() and len(sym) >= 4 and sym not in _COMMON_ACRONYMS


def _named_identifiers(question) -> list:
    """The distinctive identifiers a question names, each reduced to its LEAF
    symbol (`runtime::Builder::enable_io` -> `enable_io`) -- the thing actually
    asked about, not its qualifiers."""
    if not isinstance(question, str):
        return []
    out = []
    for tok in _IDENT_TOKEN.findall(question):
        leaf = re.split(r"\.|::", tok)[-1]
        if _is_distinctive(leaf) and leaf not in out:
            out.append(leaf)
    return out



# --- why the gate abstained -------------------------------------------------
# A verdict of "unknown" is a single word covering several very different
# situations, and conflating them costs real information. On the unknowns map,
# "nobody wrote this down" and "you asked about something that isn't in this
# repo" render identically -- so a fabricated symbol inflates a team's apparent
# documentation debt, and a genuine gap is indistinguishable from a typo.
#
# It also decides a product question: whether a gap is unrecorded ANYWHERE, or
# merely unrecorded in the sources Icarus reads. That is the evidence for or
# against adding a second source (Linear/Jira), and without it the argument is
# just opinion.
#
# Stable strings, not an enum: they are written to an append-only JSONL ledger
# that outlives any one process, and a renamed enum member would silently
# reinterpret months of history.
ABSTAIN_NO_EVIDENCE = "no_evidence"            # retrieval returned nothing at all
ABSTAIN_WRITER = "writer_abstained"            # the writer itself said unknown
ABSTAIN_UNPARSEABLE = "unparseable_reply"      # not JSON / no verdict field
ABSTAIN_NO_PROSE = "no_answer_text"            # claimed answer, wrote nothing
ABSTAIN_MALFORMED_CITATIONS = "malformed_citations"
ABSTAIN_UNGROUNDED = "ungrounded_citations"    # cited nothing we actually retrieved
ABSTAIN_ENTITY_ABSENT = "entity_absent"        # guard (c): the named thing isn't here
ABSTAIN_NO_RECORDED_REASON = "no_recorded_reason"  # guard (b): evidence records no why
ABSTAIN_SELF_DISCLAIMED = "self_disclaimed"    # guard (d): the prose disclaims knowing

def _entity_is_absent(question, evidence) -> bool:
    """True when the question names a distinctive identifier that appears
    NOWHERE in the evidence the writer saw (guard (c)'s test, factored out).

    Used for two different jobs: forcing an abstention, and CLASSIFYING one. A
    writer that honestly declines a question about a symbol that does not exist
    never reaches guard (c) -- so without this the ledger records
    "writer_abstained", the unknowns map reads it as real documentation debt,
    and a question about a thing that isn't in the repo inflates the team's
    apparent problem. Measured live 2026-07-29 on exactly that case.
    """
    if evidence is None:
        return False
    idents = _named_identifiers(question)
    if not idents:
        return False
    haystack = "\n".join(evidence.values()).lower()
    return not all(sym.lower() in haystack for sym in idents)


def gate(raw: str, retrieved: List[str], question: str = None, evidence: dict = None) -> Result:
    data = _extract_json(raw)
    verdict = data.get("verdict") if isinstance(data, dict) else None
    if not isinstance(data, dict) or not isinstance(verdict, str) or verdict.lower() != "answer":
        # Distinguish "the writer honestly said unknown" from "the reply was
        # unusable" -- one is the product working, the other is a defect.
        if not (isinstance(verdict, str) and verdict.lower() == "unknown"):
            reason = ABSTAIN_UNPARSEABLE
        elif _entity_is_absent(question, evidence):
            # The writer declined first, so guard (c) never ran -- but the more
            # informative truth is available and is not "nobody documented it".
            reason = ABSTAIN_ENTITY_ABSENT
        else:
            reason = ABSTAIN_WRITER
        return Result(verdict="unknown", abstention_reason=reason)
    answer = data.get("answer")
    citations = data.get("citations")
    if not isinstance(answer, str) or not answer.strip():
        return Result(verdict="unknown", abstention_reason=ABSTAIN_NO_PROSE)
    if isinstance(citations, str):
        citations = [citations]
    if not isinstance(citations, list):
        return Result(verdict="unknown", abstention_reason=ABSTAIN_MALFORMED_CITATIONS)
    grounded = []
    for c in citations:
        r = _resolve(c, retrieved)
        if r is not None and r not in grounded:
            grounded.append(r)
    if not grounded:
        return Result(verdict="unknown", abstention_reason=ABSTAIN_UNGROUNDED)
    # (c) The question's distinctive named identifiers must actually appear in the
    # evidence the writer saw. A fabricated symbol grounded to adjacent real code
    # (Redis's non-existent "HYPERVECTOR" over the real vector-set code) is a
    # bluff: the citation resolves, but the thing asked about isn't there. Absent
    # -> abstain. Fail-safe: only ever answer -> unknown. (Off for callers that
    # pass no evidence, and for .explain(), which passes question=None.)
    if _entity_is_absent(question, evidence):
        return Result(verdict="unknown", retrieved=list(retrieved),
                      abstention_reason=ABSTAIN_ENTITY_ABSENT)
    # (b) A rationale-seeking ("why") question needs grounded evidence that
    # actually RECORDS a reason -- otherwise the writer answered an easier
    # question than the one asked (the "why 32?" -> "it's 32" dodge). A recorded
    # rationale lives in DISCUSSION (a pr/issue/doc chunk) or in prose that states
    # a reason; a bare code/config definition does not justify a "why". If no
    # grounded chunk clears that bar, abstain. Fail-safe: this only ever turns an
    # answer into unknown. (Aligned with the product: undocumented "why" is an
    # honest unknown even when the WHAT is right there in the code.)
    if evidence is not None and _seeks_rationale(question):
        def _records_reason(r):
            # A commit message is written rationale in the same sense as a PR or
            # issue body -- an author explaining a change in prose.
            return _source(r) in ("pr", "issue", "doc", "commit") or _states_reason(evidence.get(r, ""))
        if not any(_records_reason(r) for r in grounded):
            return Result(verdict="unknown", retrieved=list(retrieved),
                          abstention_reason=ABSTAIN_NO_RECORDED_REASON)
    # (d) The writer's verdict field is a CLAIM, not a fact. If the prose itself
    # says the reason isn't recorded, that is an abstention regardless of the label
    # -- believe the sentence, not the field. Unconditional: it reads only the
    # answer, so it protects .explain() and 2-arg callers too.
    if _disclaims_answer(answer):
        return Result(verdict="unknown", retrieved=list(retrieved),
                      abstention_reason=ABSTAIN_SELF_DISCLAIMED)
    return Result(verdict="answer", answer=answer.strip(), citations=grounded, retrieved=list(retrieved))
