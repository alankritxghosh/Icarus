# evals/test_unknown_over_citation.py
"""The unknowns list declares ignorance of what the package's own citations
answer, restates itself five times, and leaks an internal string.

THE RECORDED CASE (2026-08-24, live, `SaravananJaichandar/world-model-mcp`
@ `5ec7fc6`; docs/experiments/2026-08-24-agent-mode-matched-pair-results.md).
`get_task_context` on "add a new evidence_type category with its own decay
window" returned **19 unknowns** while citing
`code:world_model_server/decay.py#L1-L56` -- a chunk whose line 34 is:

    EVIDENCE_TTL_DAYS: dict[str, int] = {
        "source_code": 365, "test": 180, "session": 14,
        "user_correction": 730, "bug_fix": 365,
    }

That is the mapping four separate unknowns say they cannot find.

THE INVERSE OF A BLUFF, AND STILL WRONG. Nothing false is asserted, so no gate
can fire and nothing in the honesty vocabulary describes it. But a caller reads
"we could not determine where the mapping is defined" and stops looking -- in a
payload that just handed them the file, the window, and the constant. It also
makes the whole block untrustworthy: once a reader finds one unknown answered by
the citations, the other eighteen stop carrying information.

IT GOT WORSE WITH BETTER RETRIEVAL: 12 unknowns in the lexical-only window, 19
once the semantic index finished. More evidence produced more redundant
unknowns. Whatever generates them scales the wrong way.

WHAT IS DETERMINISTICALLY CHECKABLE, HONESTLY RANKED. This file is careful not
to repeat `evals/attribution.py`'s mistake of scoring prose against evidence:

  * STRONG -- redundancy. Near-duplicate unknowns are a property of the LIST
    ALONE. No evidence comparison, no semantics, nothing to be anti-correlated
    with. Four restatements of one question is measurable and indefensible.
  * STRONG -- self-answering unknowns. Two entries name the exact location they
    claim not to know ("beyond updating the dictionary in decay.py", "beyond
    updating the `Literal` definition in `models.py`"). A string that contains
    its own answer is checkable without touching the corpus.
  * STRONG -- leaked internals. One entry is not an English unknown at all.
  * WEAK, and deliberately NOT asserted as a detector -- "the citations answer
    it". Deciding that a chunk answers a question is the semantic judgment this
    repo has repeatedly refused to fake. It is measured here only as the
    already-verified fact that the constant is present in a cited chunk.

`_near_duplicates` and `_names_its_own_answer` live here, in the test, not in the
brain.
"""
import json
import re
import unittest
from pathlib import Path

from .context_package import build_context_package
from .investigation import Investigation
from .pipeline import Result

_CHUNK = Path(__file__).resolve().parent / "fixtures" / "overabstention" / "wmm_decay_chunk.jsonl"

DECAY_REF = "code:world_model_server/decay.py#L1-L56"

# Verbatim, all 19 plus the leaked entry, exactly as returned on 2026-08-24.
RECORDED_UNKNOWNS = [
    "How a new evidence_type is registered within the decay engine's hardcoded dictionary.",
    "Whether the retrieval consumers dynamically discover evidence types via a database schema or metadata service.",
    "Where the mapping between `evidence_type` and decay windows (half-lives) is defined.",
    "How to register a new `evidence_type` in the decay engine.",
    "Whether the decay engine uses a centralized configuration file, hardcoded logic, or dynamic discovery for evidence types.",
    "How the decay engine maps specific `evidence_type` strings to decay windows (e.g., half-lives).",
    "Whether adding a new `evidence_type` requires modifications to files other than `decay.py` or the test suite.",
    "How retrieval consumers determine which `evidence_type` to use when querying the system.",
    "How the decay engine maps specific `evidence_type` values to decay windows (e.g., is it a centralized registry or hardcoded logic?)",
    "Where the decay engine logic is physically located within the codebase.",
    "How retrieval consumers discover or utilize evidence types beyond the schema definition.",
    "How retrieval consumers validate or discover evidence types.",
    "Whether retrieval consumers share a constant or enum with decay.py.",
    "Whether the decay engine logic is hardcoded or decoupled from retrieval consumers.",
    "The specific files required to be modified to register a new evidence type beyond updating the dictionary in decay.py.",
    "Where the decay engine logic is implemented.",
    "How the decay engine maps evidence types to decay windows.",
    "Whether retrieval consumers use the `evidence_type` field in `models.py` for validation.",
    "How to register a new evidence type in the system beyond updating the `Literal` definition in `models.py`.",
    "nothing recorded links code:world_model_server/decay.py#L1-L56 to any mentioned_by",
]

_STOP = {"the", "a", "an", "is", "are", "to", "of", "in", "for", "and", "or",
         "whether", "how", "what", "where", "it", "its", "this", "that", "be",
         "beyond", "specific", "e.g.", "new", "within", "by", "with", "on"}


def _tokens(s):
    return {w for w in re.findall(r"[a-z_]+", s.lower()) if w not in _STOP and len(w) > 2}


def _near_duplicates(unknowns, threshold=0.35):
    """Pairs of unknowns whose token sets overlap past `threshold` (Jaccard).

    A property of the list alone -- no evidence, no model. Returns index pairs so
    a failure message can name the actual sentences.

    THRESHOLD SET FROM MEASUREMENT, not taste. Over the 20 recorded unknowns the
    restatement pairs score 0.33-0.56 -- the top being "How retrieval consumers
    discover or utilize evidence types" against "How retrieval consumers validate
    or discover evidence types" at 0.56, and three separate phrasings of "how does
    the decay engine map evidence_type to decay windows" at 0.38-0.45. The
    distinct-unknowns control scores **0.00 on every pair**. With separation that
    wide anything in 0.05-0.60 behaves identically on this data; 0.35 sits in the
    gap. If a future case lands between the bands, that case -- not this number --
    is the thing to look at.
    """
    pairs = []
    for i in range(len(unknowns)):
        for j in range(i + 1, len(unknowns)):
            a, b = _tokens(unknowns[i]), _tokens(unknowns[j])
            if not a or not b:
                continue
            if len(a & b) / len(a | b) >= threshold:
                pairs.append((i, j))
    return pairs


def _names_its_own_answer(unknown):
    """Does an unknown name a concrete code location while claiming not to know?

    Keys on a filename or a dotted/underscored identifier appearing inside a
    sentence whose whole job is to say the thing is undetermined.
    """
    return bool(re.search(r"\b\w+\.py\b", unknown)) or bool(
        re.search(r"`[A-Za-z_][A-Za-z0-9_]*`", unknown))


def _package(unknowns):
    inv = Investigation(objective="add a new evidence_type", question="add a new evidence_type")
    inv.unknowns = list(unknowns)
    result = Result(verdict="answer", citations=[DECAY_REF])
    structure = {"file_edges": [], "file_edge_evidence": [], "package_edges": [],
                 "components": [], "most_depended_on_files": [],
                 "unresolved_import_count": 0, "unanalysed_languages": []}
    return build_context_package(inv, result, structure, texts={})


class TheCitedChunkAnswersFourOfThem(unittest.TestCase):
    """Always-run, offline. The already-verified fact, not a semantic judgment:
    the constant four unknowns ask for is textually present in a cited chunk."""

    @classmethod
    def setUpClass(cls):
        if not _CHUNK.exists():                        # pragma: no cover
            raise unittest.SkipTest("overabstention fixture missing")
        cls.text = json.loads(_CHUNK.read_text().splitlines()[0])["text"]

    def test_the_mapping_is_literally_in_the_cited_chunk(self):
        self.assertIn("EVIDENCE_TTL_DAYS", self.text)
        self.assertIn("evidence_type", self.text)
        for evidence_type in ("source_code", "user_correction", "bug_fix"):
            self.assertIn(evidence_type, self.text)

    def test_the_chunk_is_the_one_the_package_cites(self):
        self.assertEqual(_package(RECORDED_UNKNOWNS)["citations"], [DECAY_REF])


class RedundancyIsMeasurable(unittest.TestCase):
    """Always-run, offline. The strongest signal, and a property of the list
    alone."""

    def test_the_recorded_unknowns_are_heavily_redundant(self):
        pairs = _near_duplicates(RECORDED_UNKNOWNS)
        self.assertGreaterEqual(
            len(pairs), 3,
            "the recorded list is no longer redundant -- if a dedup shipped, "
            "invert this and record it; otherwise the fixture has drifted")

    def test_a_clean_list_is_not_flagged(self):
        """The guard that keeps the signal honest: three genuinely distinct
        unknowns must produce no pairs, or the threshold is measuring nothing."""
        clean = [
            "Why the 730-day window was chosen for user_correction.",
            "Whether a sweep worker runs in the hosted deployment.",
            "Who owns the migration when a column is added to facts.",
        ]
        self.assertEqual(_near_duplicates(clean), [])


class UnknownsThatNameTheirOwnAnswer(unittest.TestCase):
    """Always-run, offline."""

    def test_at_least_two_unknowns_name_a_concrete_location(self):
        named = [u for u in RECORDED_UNKNOWNS if _names_its_own_answer(u)]
        self.assertGreaterEqual(len(named), 2, f"expected self-answering entries, got {named}")

    def test_a_genuine_unknown_names_no_location(self):
        """Must stay green through any fix: an unknown about something truly
        unrecorded has to survive."""
        self.assertFalse(_names_its_own_answer(
            "Why the specific half-life values were chosen beyond the general "
            "claim that different evidence rots at different rates."))


class TheFixAtTheSeamItLandedOn(unittest.TestCase):
    """FIXED 2026-08-24. Near-duplicate dedup shipped in
    `evals.investigator._restates_a_known_unknown`, applied to MODEL-PROPOSED
    unknowns only. Measured on the recorded list: 20 -> 10.

    It is upstream of `build_context_package` on purpose. The package is pure
    reshaping and must stay that way, and `/investigate` reads the same unknowns
    -- fixing it at the append site fixes both surfaces."""

    def test_the_recorded_restatements_are_now_dropped(self):
        from .investigator import _restates_a_known_unknown as restates
        kept = []
        for u in RECORDED_UNKNOWNS:
            if not restates(u, kept):
                kept.append(u)
        self.assertLess(len(kept), len(RECORDED_UNKNOWNS) - 5,
                        f"dedup regressed: {len(RECORDED_UNKNOWNS)} -> {len(kept)}")
        decay_mapping = [k for k in kept if "maps" in k and "decay window" in k.lower()]
        self.assertLessEqual(len(decay_mapping), 1,
                             f"the decay-mapping question survives {len(decay_mapping)}x: {decay_mapping}")

    def test_genuinely_distinct_unknowns_all_survive(self):
        """The guard that matters more than the dedup: three different questions
        must all be kept. A dedup that quietly eats real unknowns is worse than
        the redundancy it removes."""
        from .investigator import _restates_a_known_unknown as restates
        distinct = [
            "Why the 730-day window was chosen for user_correction.",
            "Whether a sweep worker runs in the hosted deployment.",
            "Who owns the migration when a column is added to facts.",
        ]
        kept = []
        for u in distinct:
            if not restates(u, kept):
                kept.append(u)
        self.assertEqual(kept, distinct)

    def test_deterministic_probe_notes_are_NOT_deduped(self):
        """Measured 2026-08-24: two trace notes differing only in which ref or
        edge found nothing score 0.44-0.80 against each other. Deduping those
        would merge findings about DIFFERENT parts of the repository into one,
        so the probe-note append sites keep the exact-match guard. This test
        exists so nobody 'tidies up' by routing them through the new helper."""
        import inspect
        from . import investigator
        src = inspect.getsource(investigator)
        self.assertEqual(
            src.count("_restates_a_known_unknown("), 2,
            "the near-duplicate guard should be DEFINED once and CALLED once "
            "(model-proposed unknowns only); a third occurrence means it was "
            "applied to deterministic probe notes -- see this test's docstring")


class ContextPackageStaysAPassthrough(unittest.TestCase):
    """Always-run, offline. `build_context_package` does no filtering of its own
    and must not start: it is pure reshaping of already-gated output, and the
    dedup belongs upstream where `/investigate` benefits too."""

    def test_all_recorded_unknowns_survive_into_the_package(self):
        self.assertEqual(_package(RECORDED_UNKNOWNS)["unknowns"], RECORDED_UNKNOWNS)

    def test_the_leaked_internal_string_is_published_verbatim(self):
        leaked = "nothing recorded links code:world_model_server/decay.py#L1-L56 to any mentioned_by"
        self.assertIn(leaked, _package(RECORDED_UNKNOWNS)["unknowns"],
                      "if this is now filtered, say so in the experiment record")
        # What marks it as internal rather than an English unknown: it embeds a
        # raw chunk ref and an internal edge name. No human-written unknown does.
        self.assertRegex(leaked, r"code:[^\s]+#L\d+-L\d+")
        self.assertIn("mentioned_by", leaked)
