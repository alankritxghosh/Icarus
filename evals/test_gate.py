# evals/test_gate.py
"""The gate's conscience: an answer survives ONLY when grounded; everything
ambiguous collapses to honest abstention. These prove the model cannot make us
bluff."""

import json
import unittest

from . import gate as gate_mod
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

class SelfDisclaimingAnswerGuardTests(unittest.TestCase):
    """Guard (d): the writer's `verdict` field is a CLAIM, not a fact.

    Found live 2026-07-22 on psf/requests: verdict="answer" whose prose was
    plainly an abstention ("the evidence does not state a specific reason").
    Guard (b) had passed it because the cited 107-line chunk happened to contain
    "to ensure" in an unrelated comment. Believe the sentence, not the field.
    """

    REF = "code:src/requests/models.py#L1-L107"
    # A head-of-file chunk whose UNRELATED comment satisfies _states_reason --
    # this is what made guard (b) insufficient, so the fixture keeps it.
    EVIDENCE = {REF: ("# models.py\nimport datetime\n"
                      "# alias to ensure compatibility.\n"
                      "DEFAULT_REDIRECT_LIMIT = 30\n")}

    def _gate(self, answer, question="Why is DEFAULT_REDIRECT_LIMIT exactly 30?"):
        raw = json.dumps({"verdict": "answer", "answer": answer, "citations": [self.REF]})
        return gate(raw, [self.REF], question=question, evidence=self.EVIDENCE)

    def test_the_live_case_is_forced_to_unknown(self):
        r = self._gate("The evidence does not state a specific reason for why the limit "
                       "is 30; it only defines DEFAULT_REDIRECT_LIMIT as 30 in the source code.")
        self.assertEqual(r.verdict, "unknown")
        self.assertEqual(r.citations, [])

    def test_other_self_disclaimers_are_caught(self):
        for answer in [
            "No specific reason is given in the retrieved code.",
            "The rationale was never documented in the linked pull request.",
            "The provided context doesn't explain why this value was chosen.",
            "No explanation for the choice appears in the evidence.",
        ]:
            with self.subTest(answer=answer):
                self.assertEqual(self._gate(answer).verdict, "unknown")

    def test_real_answers_containing_negation_are_NOT_abstained(self):
        """The expensive failure mode for this guard is over-abstention, so these
        must all survive: each is a genuine answer that merely contains 'not'."""
        for answer in [
            "The code does not validate input, so callers must sanitize it first.",
            "The timeout is not configurable because the socket is shared across sessions.",
            "Three retries were chosen because five masked a dead node for a staging week.",
            "requests does not specify a default timeout, so a hung server blocks forever.",
            "HTTP/2 is unsupported because urllib3 lacks support for it.",
            "The reason given in PR 1482 is that five retries hid failures.",
        ]:
            with self.subTest(answer=answer):
                self.assertEqual(self._gate(answer).verdict, "answer")

    def test_guard_applies_without_question_or_evidence(self):
        """It reads only the answer, so 2-arg callers and .explain() are protected too."""
        raw = json.dumps({"verdict": "answer",
                          "answer": "No specific reason is given for this value.",
                          "citations": [self.REF]})
        self.assertEqual(gate(raw, [self.REF]).verdict, "unknown")

    def test_guard_never_turns_unknown_into_answer(self):
        """Fail-safe direction: it can only ever remove an answer."""
        raw = json.dumps({"verdict": "unknown", "answer": "", "citations": []})
        self.assertEqual(gate(raw, [self.REF]).verdict, "unknown")



class AbstentionReasonTests(unittest.TestCase):
    """"Unknown" is one word covering several very different situations, and
    conflating them costs real information.

    On the unknowns map, "nobody wrote this down" and "you asked about something
    that isn't in this repo" render identically — so a fabricated symbol inflates
    a team's apparent documentation debt and a genuine gap is indistinguishable
    from a typo. It also decides whether a gap is unrecorded ANYWHERE or merely
    unrecorded in the sources Icarus reads, which is the evidence for or against
    adding a second source."""

    def test_an_answer_carries_no_reason(self):
        r = gate(json.dumps({"verdict": "answer", "answer": "Because Y.",
                             "citations": ["pr:1"]}), ["pr:1"])
        self.assertEqual(r.verdict, "answer")
        self.assertIsNone(r.abstention_reason)

    def test_the_writer_abstaining_is_distinct_from_a_broken_reply(self):
        # One is the product working as designed; the other is a defect. They
        # must never be counted as the same thing.
        self.assertEqual(gate(json.dumps({"verdict": "unknown"}), []).abstention_reason,
                         gate_mod.ABSTAIN_WRITER)
        self.assertEqual(gate("not json at all", []).abstention_reason,
                         gate_mod.ABSTAIN_UNPARSEABLE)

    def test_an_ungrounded_citation_is_recorded_as_such(self):
        r = gate(json.dumps({"verdict": "answer", "answer": "x",
                             "citations": ["pr:99999"]}), ["pr:1"])
        self.assertEqual(r.abstention_reason, gate_mod.ABSTAIN_UNGROUNDED)

    def test_a_fabricated_symbol_is_recorded_as_entity_absent(self):
        # THE case this exists for: not a documentation gap at all.
        r = gate(json.dumps({"verdict": "answer", "answer": "It shards.",
                             "citations": ["code:db.py"]}),
                 ["code:db.py"],
                 question="How does QuantumIndexShard work?",
                 evidence={"code:db.py": "class BTree: pass"})
        self.assertEqual(r.verdict, "unknown")
        self.assertEqual(r.abstention_reason, gate_mod.ABSTAIN_ENTITY_ABSENT)

    def test_an_undocumented_why_is_recorded_as_no_recorded_reason(self):
        # A REAL documentation gap — the thing exists, the reason was never
        # written down. This is the bucket a team should act on.
        r = gate(json.dumps({"verdict": "answer", "answer": "It is 30.",
                             "citations": ["code:c.py"]}),
                 ["code:c.py"],
                 question="Why is the redirect limit 30?",
                 evidence={"code:c.py": "REDIRECT_LIMIT = 30"})
        self.assertEqual(r.verdict, "unknown")
        self.assertEqual(r.abstention_reason, gate_mod.ABSTAIN_NO_RECORDED_REASON)

    def test_the_two_buckets_are_actually_different_values(self):
        # If these ever collapse, the map silently goes back to being useless.
        self.assertNotEqual(gate_mod.ABSTAIN_ENTITY_ABSENT,
                            gate_mod.ABSTAIN_NO_RECORDED_REASON)

    def test_a_self_disclaiming_answer_is_recorded_as_such(self):
        r = gate(json.dumps({"verdict": "answer",
                             "answer": "The evidence does not state a reason for the limit.",
                             "citations": ["pr:1"]}), ["pr:1"])
        self.assertEqual(r.abstention_reason, gate_mod.ABSTAIN_SELF_DISCLAIMED)

    def test_every_reason_is_a_plain_stable_string(self):
        # They are written to an append-only JSONL ledger that outlives any one
        # process; a renamed value would silently reinterpret months of history.
        for name in dir(gate_mod):
            if name.startswith("ABSTAIN_"):
                self.assertIsInstance(getattr(gate_mod, name), str)
