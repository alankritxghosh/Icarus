# evals/test_gate.py
"""The gate's conscience: an answer survives ONLY when grounded; everything
ambiguous collapses to honest abstention. These prove the model cannot make us
bluff."""

import json
import unittest

from .gate import gate

RETRIEVED = ["pr:1435", "issue:506", "code:llm/models.py"]


def _ans(answer, citations):
    return json.dumps({"verdict": "answer", "answer": answer, "citations": citations})


class GateTests(unittest.TestCase):
    def test_grounded_answer_passes(self):
        r = gate(_ans("Because Y.", ["pr:1435"]), RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])
        self.assertTrue(r.answer)

    def test_drops_citations_not_retrieved_but_keeps_grounded_ones(self):
        r = gate(_ans("Because Y.", ["pr:1435", "pr:9999"]), RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])  # pr:9999 dropped

    def test_answer_with_only_unretrieved_citations_forces_unknown(self):
        self.assertEqual(gate(_ans("Made up.", ["pr:9999"]), RETRIEVED).verdict, "unknown")

    def test_empty_citations_forces_unknown(self):
        self.assertEqual(gate(_ans("No source.", []), RETRIEVED).verdict, "unknown")

    def test_empty_answer_forces_unknown(self):
        self.assertEqual(gate(_ans("", ["pr:1435"]), RETRIEVED).verdict, "unknown")

    def test_explicit_unknown(self):
        self.assertEqual(gate(json.dumps({"verdict": "unknown"}), RETRIEVED).verdict, "unknown")

    def test_unparseable_text_forces_unknown(self):
        self.assertEqual(gate("the model rambled with no json", RETRIEVED).verdict, "unknown")

    def test_json_embedded_in_prose_is_extracted(self):
        raw = "Sure!\n" + _ans("Because Y.", ["pr:1435"]) + "\nhope that helps"
        self.assertEqual(gate(raw, RETRIEVED).verdict, "answer")

    def test_case_insensitive_verdict_still_answers(self):
        # A writer emitting "Answer"/"ANSWER" instead of lowercase "answer"
        # must not be wrongly forced to unknown -- fail-safe-only hardening,
        # can only ever turn a would-be-unknown into a legitimate answer.
        raw = json.dumps({"verdict": "Answer", "answer": "Because Y.", "citations": ["pr:1435"]})
        r = gate(raw, RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])

    def test_single_string_citation_still_grounds(self):
        # A writer emitting a lone citation string instead of a one-item list
        # must still ground, not be forced to unknown for a format mismatch.
        raw = json.dumps({"verdict": "answer", "answer": "Because Y.", "citations": "pr:1435"})
        r = gate(raw, RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertEqual(r.citations, ["pr:1435"])


class MalformedLineWindowTests(unittest.TestCase):
    """A citation whose line window is impossible (line 0/negative or end<start)
    is not a real location -- it can only be fabricated or garbled, so it must
    never ground (Sol P0). Well-formed contained windows still ground."""

    def test_inverted_range_forced_unknown(self):
        r = gate(_ans("x", ["code:f.py#L300-L250"]), ["code:f.py#L250-L300"])
        self.assertEqual(r.verdict, "unknown")

    def test_line_zero_forced_unknown(self):
        r = gate(_ans("x", ["code:f.py#L0"]), ["code:f.py"])
        self.assertEqual(r.verdict, "unknown")

    def test_wellformed_contained_window_still_grounds(self):
        r = gate(_ans("x", ["code:f.py#L260-L280"]), ["code:f.py#L250-L300"])
        self.assertEqual(r.verdict, "answer")


class RationaleGuardTests(unittest.TestCase):
    """(b) The gate refuses a rationale-seeking ("why") question whose grounded
    evidence states no actual reason -- catching the "answered the what, dodged
    the why" failure groundedness alone is blind to. Only active when the caller
    supplies question + evidence; fail-safe (only ever adds abstention)."""

    CODE_EVIDENCE = {"code:llm/models.py": "CONVERSATION_NAME_LENGTH = 32"}
    REASON_EVIDENCE = {"pr:1435": "We capped names at 32 so that they stay readable."}

    def test_why_over_code_with_no_reason_abstains(self):
        r = gate(_ans("It's 32, set in models.py", ["code:llm/models.py"]),
                 ["code:llm/models.py"],
                 question="Why is the limit 32 specifically?", evidence=self.CODE_EVIDENCE)
        self.assertEqual(r.verdict, "unknown")

    def test_why_with_recorded_reason_answers(self):
        r = gate(_ans("Because names stay readable.", ["pr:1435"]),
                 ["pr:1435"],
                 question="Why is the limit 32?", evidence=self.REASON_EVIDENCE)
        self.assertEqual(r.verdict, "answer")

    def test_why_with_discussion_source_answers_even_without_marker(self):
        # A pr/issue/doc citation IS recorded discussion -- it clears (b) even if
        # its snippet has no explicit marker word (real answerable why-questions
        # cite the PR/issue that discusses the change).
        ev = {"pr:1432": "Add an options= dict parameter to .prompt() and .reply()."}
        r = gate(_ans("It adds an options dict.", ["pr:1432"]), ["pr:1432"],
                 question="Why does .prompt() accept an options= dict?", evidence=ev)
        self.assertEqual(r.verdict, "answer")

    def test_non_why_question_over_code_answers(self):
        r = gate(_ans("The limit is 32.", ["code:llm/models.py"]),
                 ["code:llm/models.py"],
                 question="What is the max name length?", evidence=self.CODE_EVIDENCE)
        self.assertEqual(r.verdict, "answer")

    def test_guard_inactive_without_question_or_evidence(self):
        # Back-compat: a 2-arg call (no question/evidence) keeps the old behavior.
        r = gate(_ans("It's 32.", ["code:llm/models.py"]), ["code:llm/models.py"])
        self.assertEqual(r.verdict, "answer")


class EntityPresenceGuardTests(unittest.TestCase):
    """(c) A question naming a DISTINCTIVE code identifier that appears NOWHERE
    in the evidence the writer saw is forced to unknown -- catching a fabricated
    symbol grounded to adjacent real code (found live 2026-07-18: Redis has no
    `HYPERVECTOR` type, but its real vector-set code let the writer answer as if
    it did). Only active with `evidence`; fail-safe (only ever adds abstention)."""

    # Real Redis vector code -- note it never contains the fabricated "HYPERVECTOR".
    VECTOR_EVIDENCE = {"code:src/vector.c#L1-L50":
                       "int vectorSetTypeAdd(robj *o) { /* store an embedding vector */ }"}

    def test_fabricated_identifier_absent_from_evidence_forces_unknown(self):
        r = gate(_ans("Redis's HYPERVECTOR type stores embeddings in a vector set.",
                      ["code:src/vector.c#L1-L50"]),
                 ["code:src/vector.c#L1-L50"],
                 question="How does Redis's HYPERVECTOR data type store embeddings?",
                 evidence=self.VECTOR_EVIDENCE)
        self.assertEqual(r.verdict, "unknown")

    def test_qualified_fabricated_leaf_absent_forces_unknown(self):
        # The LEAF symbol is what's checked: real siblings enable_io/enable_all
        # are present, but the fabricated enable_speculative_io is not.
        ev = {"code:tokio/src/runtime/builder.rs#L1-L80":
              "pub fn enable_io(&mut self) -> &mut Self {} pub fn enable_all(&mut self) {}"}
        r = gate(_ans("enable_speculative_io turns on speculative IO.",
                      ["code:tokio/src/runtime/builder.rs#L1-L80"]),
                 ["code:tokio/src/runtime/builder.rs#L1-L80"],
                 question="How does tokio's runtime::Builder::enable_speculative_io() work?",
                 evidence=ev)
        self.assertEqual(r.verdict, "unknown")

    def test_real_identifier_present_still_answers(self):
        ev = {"code:django/db/models/query.py#L1-L50":
              "def bulk_create(self, objs): # resolve conflicts via on_conflict"}
        r = gate(_ans("bulk_create resolves conflicts with on_conflict.",
                      ["code:django/db/models/query.py#L1-L50"]),
                 ["code:django/db/models/query.py#L1-L50"],
                 question="How does Django's bulk_create() handle conflicts?", evidence=ev)
        self.assertEqual(r.verdict, "answer")

    def test_plain_english_question_never_fires(self):
        # No distinctive identifier in the question -> guard is inert.
        ev = {"code:pkg/scheduler.go#L1-L50": "// selects the best node for the pod"}
        r = gate(_ans("It scores nodes and picks the best.", ["code:pkg/scheduler.go#L1-L50"]),
                 ["code:pkg/scheduler.go#L1-L50"],
                 question="How does the scheduler decide which node a pod lands on?", evidence=ev)
        self.assertEqual(r.verdict, "answer")

    def test_common_acronym_not_over_abstained(self):
        # A common tech acronym (HTTP) reads as a subject word, not a code symbol;
        # it must not force abstain merely for being all-caps and absent verbatim.
        ev = {"code:src/http.c#L1-L20": "// parse the request line and headers"}
        r = gate(_ans("It parses the request line and headers.", ["code:src/http.c#L1-L20"]),
                 ["code:src/http.c#L1-L20"],
                 question="How does HTTP request parsing work?", evidence=ev)
        self.assertEqual(r.verdict, "answer")

    def test_single_titlecase_word_not_flagged(self):
        # A single Title-case word (Interceptor) is ordinary prose, deliberately
        # NOT treated as a distinctive identifier -> guard stays inert.
        ev = {"code:okhttp/RealCall.kt#L1-L30": "the chain proceeds through each stage"}
        r = gate(_ans("The chain runs each stage in order.", ["code:okhttp/RealCall.kt#L1-L30"]),
                 ["code:okhttp/RealCall.kt#L1-L30"],
                 question="How does the Interceptor chain process a request?", evidence=ev)
        self.assertEqual(r.verdict, "answer")

    def test_guard_inactive_without_evidence(self):
        # 2-arg / no-evidence callers are unaffected (back-compat).
        r = gate(_ans("HYPERVECTOR stores embeddings.", ["code:src/vector.c#L1-L50"]),
                 ["code:src/vector.c#L1-L50"],
                 question="How does Redis's HYPERVECTOR data type store embeddings?")
        self.assertEqual(r.verdict, "answer")


if __name__ == "__main__":
    unittest.main()
