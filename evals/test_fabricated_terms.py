# evals/test_fabricated_terms.py
"""Cross-citation term migration: a term real somewhere in the retrieved set,
attached to a claim whose OWN citations do not support it.

THE RECORDED CASE (2026-08-24, live, `SaravananJaichandar/world-model-mcp`
@ `5ec7fc6`; see docs/experiments/2026-08-24-agent-mode-matched-pair-results.md).
Asked why `delete()` leaves a fact retrievable, the production writer answered:

    "The delete() method was designed as a soft-delete to preserve audit-chain
     semantics, as retroactively removing SIGNED EVENTS would break the record
     of what the system previously believed."

citing `commit:347c1bd` and `code:world_model_server/memory_backend.py#L168-L187`.

Neither cited chunk contains "signed", or any signing concept. The commit states
the reason plainly and differently: the chain of what was ever believed "should
not be silently rewritten". Nothing about signatures.

WHERE THE WORD CAME FROM, and why this is not a fabrication-from-nothing. The
FIRST diagnosis of this case was wrong and is corrected here, because the
difference decides what can be built. `code:world_model_server/knowledge_graph.py
#L1126-L1163` -- retrieved on the same call, and cited by the SAME answer for its
OTHER sentence -- contains:

    "...distinguish 'purged' from 'was already absent' for signed-purge-event
     audit records."

So the term is real, it was in front of the writer, and it belongs to `purge`
audit records. It migrated onto a sentence about `delete`, where it states
something no chunk states. That makes this **composition across chunks**, which
is precisely what the `composed` label means -- and the label DID fire.

WHY THIS IS WORTH A FIXTURE.
  * It is DETERMINISTIC. Re-asked verbatim after the semantic index finished
    building -- a completely different retrieval regime -- the answer came back
    byte-identical. A stable wrong answer on a fixed corpus is a testable one.
  * Groundedness cannot see it. Every citation resolves; the gate passes it.
    That is proven below rather than asserted.
  * Unlike overlap scoring, it has a CHECKABLE signature (see next note).

NOT A REVIVAL OF `evals/attribution.py`. That module scored sentences by lexical
OVERLAP with cited chunks and was deleted for measuring anti-correlated with
truth: a plausible fabrication is assembled from the evidence's own words, so it
scores HIGHER than an honest paraphrase (docs/experiments/2026-08-10-quotation-
vs-composition-negative-result.md). This is the opposite shape -- not a ratio over
a whole sentence, but the presence of ONE distinctive term, checked against the
claim's own citations. It is the same shape as gate.py's shipped guard (c), which
checks a distinctive identifier from the QUESTION against the evidence; the
untested direction is the same check pointed at the ANSWER. No scoring, no
threshold, no ranking.

WHAT THIS FILE DOES AND DOES NOT DO. It pins the case and proves the signature is
computable. It ships NO detector into the brain -- `_terms_absent_from` lives
here, in the test, deliberately. If a guard is ever built, this is the red board
it has to turn green, and the helper is the thing to lift.
"""
import json
import os
import unittest
from pathlib import Path

from .corpus import Chunk
from .env_file import load_env_file
from .gate import gate

_HERE = Path(__file__).resolve().parent
_CORPUS = _HERE / "fixtures" / "fabrication" / "wmm_delete_chunks.jsonl"

QUESTION = ("Has anyone tried and abandoned an approach to making delete() "
            "actually erase the fact from disk, and why was the two-primitive "
            "delete/purge split chosen instead?")

# The migrated term, lower-cased. Kept as a list so a second recorded case can
# be added without reshaping the board.
MIGRATED_TERM = "signed"

# The answer exactly as the production writer returned it, twice, on 2026-08-24.
# Verbatim on purpose: a paraphrase would be a test of a sentence nobody wrote.
RECORDED_ANSWER = (
    "The `delete()` method was designed as a soft-delete to preserve audit-chain "
    "semantics, as retroactively removing signed events would break the record of "
    "what the system previously believed. The two-primitive design was chosen to "
    "provide a separate `purge()` method for hard-deletion, satisfying compliance "
    "requirements like GDPR Article 17 or HIPAA retention without compromising the "
    "integrity of the audit chain."
)

CLAIM_1_CITATIONS = [
    "commit:347c1bd8b50f23c1f20b8c1541f4aea3d984d09f",
    "code:world_model_server/memory_backend.py#L168-L187",
]
# Retrieved on the same call, cited by the SAME answer for its other sentence.
TERM_SOURCE = "code:world_model_server/knowledge_graph.py#L1126-L1163"


def _load_chunks():
    return [Chunk(**json.loads(line))
            for line in _CORPUS.read_text().splitlines() if line.strip()]


def _terms_absent_from(term: str, refs, chunks) -> bool:
    """Is `term` absent from the text of every chunk in `refs`?

    The candidate signature, kept in the test rather than the brain. Substring,
    case-folded, and deliberately dumb -- the disclosed cost is that it cannot
    tell `signed` in "signed events" from `signed` inside "designed", which is
    exactly the false positive that made the hand-check of this case necessary
    in the first place. Callers below use word-boundary text, not raw substring,
    for that reason.
    """
    by_ref = {c.ref: c.text.lower() for c in chunks}
    words = set()
    for ref in refs:
        for w in by_ref.get(ref, "").replace("-", " ").split():
            words.add(w.strip(".,:;()[]{}'\"`"))
    return term.lower() not in words


class RecordedCaseIsIntact(unittest.TestCase):
    """Always-run, offline, no key. Pins the case itself so the board cannot
    quietly stop describing what happened."""

    @classmethod
    def setUpClass(cls):
        if not _CORPUS.exists():                       # pragma: no cover
            raise unittest.SkipTest("fabrication fixture missing")
        cls.chunks = _load_chunks()

    def test_every_ref_in_the_case_is_really_in_the_fixture(self):
        """Without this, an absent term could just mean an absent chunk."""
        present = {c.ref for c in self.chunks}
        for ref in CLAIM_1_CITATIONS + [TERM_SOURCE]:
            self.assertIn(ref, present, f"{ref} missing from the fixture corpus")

    def test_the_term_is_absent_from_the_claims_own_citations(self):
        """The defect's first half: claim 1 cites two chunks, and neither of them
        contains the term the claim turns on."""
        self.assertTrue(
            _terms_absent_from(MIGRATED_TERM, CLAIM_1_CITATIONS, self.chunks),
            "'signed' now appears in claim 1's own citations -- the recorded case "
            "has changed and this board is describing something that no longer "
            "happened; re-read the experiment record before editing anything")

    def test_the_term_is_present_in_a_different_retrieved_chunk(self):
        """The defect's second half, and the correction to the first diagnosis:
        the term was NOT invented. It is real, in a chunk the same answer cited
        for a different sentence, about `purge` rather than `delete`."""
        self.assertFalse(
            _terms_absent_from(MIGRATED_TERM, [TERM_SOURCE], self.chunks),
            f"{TERM_SOURCE} no longer contains the migrated term")

    def test_the_signature_is_computable_without_a_model(self):
        """What a future guard would key on, stated as one assertion: present in
        the retrieved set, absent from this claim's citations. Deterministic, no
        threshold, no ranking, no model call."""
        all_refs = [c.ref for c in self.chunks]
        self.assertFalse(_terms_absent_from(MIGRATED_TERM, all_refs, self.chunks))
        self.assertTrue(_terms_absent_from(MIGRATED_TERM, CLAIM_1_CITATIONS, self.chunks))


class GroundednessCannotSeeIt(unittest.TestCase):
    """Always-run, offline, no key, no network. The characterization that must
    STAY green: the honesty gate passes this answer. Not a defect in the gate --
    every citation IS real and IS contained -- but the proof that groundedness
    was never the property that would catch this, so no future fix should be
    attempted by 'tightening the gate'."""

    def test_the_gate_passes_the_recorded_answer(self):
        retrieved = CLAIM_1_CITATIONS + [TERM_SOURCE]
        raw = json.dumps({"verdict": "answer", "answer": RECORDED_ANSWER,
                          "citations": CLAIM_1_CITATIONS})
        result = gate(raw, retrieved, question=QUESTION)
        self.assertEqual(
            result.verdict, "answer",
            "The gate now refuses the recorded answer. If that was deliberate, "
            "this test documents a real behaviour change and the experiment "
            "record needs updating -- do not just flip the assertion.")
        self.assertTrue(result.citations, "a passing answer must carry citations")


class LiveReproductionAttempt(unittest.TestCase):
    """Live, costs money, self-skips without GEMINI_PAID_API_KEY.

    **THIS BOARD IS GREEN, AND GREEN HERE IS NOT SUCCESS -- IT IS A FAILED
    REPRODUCTION.** Read this before trusting the file's title.

    Intent was the red half of red -> green. It did not work out that way, and
    the result is recorded here rather than quietly deleted.

    MEASURED 2026-08-24, twice:

      * 5-chunk fixture (the refs claim 1 cited, plus the term source): the
        answer never used the term. GREEN.
      * 16-chunk fixture -- every ref probe B actually retrieved, minus
        `index:overview`, with "signed" present in NINE of them: still GREEN, and
        the answer was CORRECT -- "the history of what was believed should not be
        silently rewritten", which is the commit's real stated reason.

    So the migration reproduced twice byte-identically against the ~9k-chunk
    PRODUCTION index and zero times against a fixture holding the same retrieved
    refs. What that licenses, and what it does not:

      * It is deterministic WITH RESPECT TO the production index. Two runs, two
        retrieval regimes, byte-identical output.
      * It is NOT yet a regression fixture. A fixture that cannot make the defect
        appear cannot prove a fix removed it.
      * Therefore the defect is NOT determined by the retrieved evidence alone.
        Candidates not yet separated: chunk TEXT differs (these are reconstructed
        to match ingest's shape, not lifted byte-identical from the production
        corpus, which is not committed anywhere); retrieval ORDER differs, and
        order is prompt order; production sent 21 refs including `index:overview`.

    Until one of those is isolated, the honest description of the case is "stable
    on the production index, not reproducible offline" -- and the offline classes
    above, which pin the recorded case and prove groundedness cannot see it, are
    the load-bearing part of this file.
    """

    @classmethod
    def setUpClass(cls):
        load_env_file(".env")
        if not os.environ.get("GEMINI_PAID_API_KEY"):
            raise unittest.SkipTest("GEMINI_PAID_API_KEY not set; live board")
        if not _CORPUS.exists():                       # pragma: no cover
            raise unittest.SkipTest("fabrication fixture missing")

        from .pipeline import GatedPipeline
        from .provider import make_provider
        from .retriever import LexicalRetriever

        cls.chunks = _load_chunks()
        # Lexical only: all five chunks are on-topic by construction, so ranking
        # is not what this board measures, and it keeps the board runnable
        # without fastembed.
        pipeline = GatedPipeline(LexicalRetriever(cls.chunks), cls.chunks,
                                 make_provider("gemini-paid"))
        cls.result = pipeline.answer(QUESTION)

    def test_the_answer_does_not_migrate_a_term_across_citations(self):
        answer = (self.result.answer or "")
        print(f"\n  verdict   : {self.result.verdict}"
              f"\n  citations : {self.result.citations}"
              f"\n  answer    : {answer[:200]}")
        cited = list(self.result.citations or [])
        words = set()
        for w in answer.lower().replace("-", " ").split():
            words.add(w.strip(".,:;()[]{}'\"`"))
        if MIGRATED_TERM not in words:
            return  # the migration did not recur on this fixture
        self.assertFalse(
            _terms_absent_from(MIGRATED_TERM, cited, self.chunks),
            f"the answer uses '{MIGRATED_TERM}' while none of its own citations "
            f"{cited} contain it -- cross-citation migration reproduced")
