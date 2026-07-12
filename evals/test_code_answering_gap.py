# evals/test_code_answering_gap.py
"""RED failing eval for the two code-answering gaps found 2026-07-12 during the
extensive-testing mandate. Both make Icarus abstain on a code answer it actually
produced correctly. Neither is a bluff -- the honesty invariant holds -- but both
silently discard correct work on CODE specifically, and the frozen board is blind
to them because every answerable gold in phase1_questions.json is answered from a
short pr:/issue: chunk, never from code.

These tests encode the DESIRED behavior, so they are RED until the brain is fixed
and GREEN after. Do NOT make them pass by weakening a gate.

  * Finding #3 -- the deterministic gate (evals/gate.py) rejects a correctly-
    grounded code citation because the writer reformats the retrieved ref:
    it drops the `code:` source prefix (`code:foo.py#L1-L300` -> `foo.py#L1-L300`,
    observed 3/3 live on the paid Gemini writer) or wraps the ref in the prompt's
    own display brackets (`code:llm/models.py` -> `[code:llm/models.py]`, observed
    live). gate.py matches citations by exact set membership, so a correct answer
    whose only fault is ref formatting collapses to "unknown".

  * Finding #2 -- evals/synth.build_prompt truncates every evidence chunk to 1500
    chars, but evals/ingest.py deliberately chunks code into 300-line windows
    (much larger: committed corpus code chunks are median ~4300 chars, max ~131k).
    So the writer sees only ~40 lines of a chunk the ingester deemed one coherent
    unit -- the answer can be retrieved #1 yet be invisible. The real case: the
    `split_words` logic sat at char ~2838 of the 7483-char envconfig.go#L1-L300
    chunk and was truncated out, forcing an honest-but-wrong abstention.

The GREEN guards below MUST STAY GREEN: the fix must not let an ungrounded
citation through. A citation that matches no retrieved chunk (even after
normalizing prefix/brackets) is still forced to "unknown".
"""
import json
import unittest

from .corpus import Chunk
from .gate import gate
from .synth import build_prompt
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline


def _answer_citing(ref):
    return json.dumps({
        "verdict": "answer",
        "answer": "process() raises ErrBad when the spec is not a struct pointer.",
        "citations": [ref],
    })


class GateGroundsReformattedCodeCitation(unittest.TestCase):
    """Finding #3, at the root cause (the gate)."""

    RETRIEVED = ["code:foo.py#L1-L300"]

    def test_prefix_dropped_code_citation_is_grounded(self):
        # Writer dropped the `code:` source prefix -- observed 3/3 live (paid Gemini).
        r = gate(_answer_citing("foo.py#L1-L300"), self.RETRIEVED)
        self.assertEqual(
            r.verdict, "answer",
            "gate discarded a correct answer whose only fault was the writer "
            "dropping the 'code:' prefix from a retrieved ref",
        )
        self.assertIn("code:foo.py#L1-L300", r.citations)

    def test_bracket_wrapped_code_citation_is_grounded(self):
        # Writer echoed the prompt's display brackets -- observed live (paid Gemini).
        r = gate(_answer_citing("[code:foo.py#L1-L300]"), self.RETRIEVED)
        self.assertEqual(
            r.verdict, "answer",
            "gate discarded a correct answer whose only fault was the writer "
            "wrapping a retrieved ref in the prompt's display brackets",
        )
        self.assertIn("code:foo.py#L1-L300", r.citations)

    def test_line_narrowed_code_citation_is_grounded(self):
        # Writer narrowed the chunk's window to the specific line it used
        # (`code:foo.py#L1-L300` -> `foo.py#L21`) -- observed live on the paid
        # writer. Line 21 is inside the retrieved window, so it is grounded.
        r = gate(_answer_citing("foo.py#L21"), self.RETRIEVED)
        self.assertEqual(
            r.verdict, "answer",
            "gate discarded a correct answer that cited the specific line "
            "(#L21) inside the retrieved window (#L1-L300)",
        )
        self.assertIn("code:foo.py#L1-L300", r.citations)

    def test_named_source_must_match_no_cross_source_grounding(self):
        # Hardening (2026-07-13, per the independent gate audit): when a citation
        # carries a source: prefix, it must equal the retrieved ref's source, so
        # a citation can NEVER ground to a different source that merely shares a
        # path/number. Latent-hole closure; must stay green.
        self.assertEqual(gate(_answer_citing("code:1489"), ["pr:1489"]).verdict, "unknown")
        self.assertEqual(gate(_answer_citing("issue:1489"), ["pr:1489"]).verdict, "unknown")
        self.assertEqual(gate(_answer_citing("code:README.md"), ["doc:README.md"]).verdict, "unknown")
        # ...but a bare-body citation (source dropped) still grounds -- tolerance kept.
        r = gate(_answer_citing("foo.py#L1-L300"), self.RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertIn("code:foo.py#L1-L300", r.citations)

    # --- GREEN guards: groundedness must not be weakened by the fix ---
    def test_line_outside_retrieved_window_forced_unknown(self):
        # A line the retrieved chunk does not cover points OUTSIDE shown
        # evidence -- must stay unknown (no bluff via a fabricated line).
        r = gate(_answer_citing("foo.py#L5000"), self.RETRIEVED)
        self.assertEqual(r.verdict, "unknown")
        self.assertEqual(r.citations, [])

    def test_exact_code_citation_still_grounded(self):
        r = gate(_answer_citing("code:foo.py#L1-L300"), self.RETRIEVED)
        self.assertEqual(r.verdict, "answer")
        self.assertIn("code:foo.py#L1-L300", r.citations)

    def test_unretrieved_citation_still_forced_unknown(self):
        # A ref that matches no retrieved chunk (even after normalization) is a
        # bluff and must still collapse to unknown -- this must STAY green.
        r = gate(_answer_citing("code:other.py#L1-L300"), self.RETRIEVED)
        self.assertEqual(r.verdict, "unknown")
        self.assertEqual(r.citations, [])

    def test_citation_claiming_lines_beyond_window_forced_unknown(self):
        # P0 (found by an independent GPT-5.6 review): a citation claiming lines
        # BEYOND the retrieved window asserts unretrieved evidence. Matching is
        # CONTAINMENT, not overlap -- a broad range must NOT launder into the
        # narrow retrieved ref.
        narrow = ["code:foo.py#L250-L300"]
        self.assertEqual(gate(_answer_citing("code:foo.py#L1-L10000"), narrow).verdict, "unknown")
        self.assertEqual(gate(_answer_citing("foo.py#L1-L10000"), narrow).verdict, "unknown")
        # a partially-past-the-end range is also refused (line 350 was not shown)
        self.assertEqual(gate(_answer_citing("code:foo.py#L280-L350"), self.RETRIEVED).verdict, "unknown")
        # ...but a range fully inside still grounds
        self.assertEqual(gate(_answer_citing("code:foo.py#L260-L290"), narrow).verdict, "answer")

    def test_colon_in_path_still_grounds(self):
        # P2 (same review): git paths may contain ':'. A prefix-dropped citation
        # to such a path must still ground (false-reject fix) -- only a KNOWN
        # source token is treated as a prefix.
        r = gate(_answer_citing("dir/a:b.py#L20"), ["code:dir/a:b.py#L1-L300"])
        self.assertEqual(r.verdict, "answer")
        self.assertIn("code:dir/a:b.py#L1-L300", r.citations)


class ServingPipelineAnswersCodeQuestion(unittest.TestCase):
    """Finding #3, end to end through the real serving pipeline."""

    def test_prefix_dropped_answer_is_served_not_abstained(self):
        chunk = Chunk(
            "code:foo.py#L1-L300", "code",
            "def process(spec):\n"
            "    if not is_struct_pointer(spec):\n"
            "        raise ErrBad('specification must be a struct pointer')\n",
        )
        # StaticProvider encodes the REAL paid-writer behavior: a correct answer
        # that cites the retrieved ref with the `code:` prefix dropped.
        raw = _answer_citing("foo.py#L1-L300")
        pipe = GatedPipeline(LexicalRetriever([chunk]), [chunk], StaticProvider(raw))
        r = pipe.answer("what does process raise when spec is not a struct pointer")
        self.assertEqual(
            r.verdict, "answer",
            "the serving path abstained on a correct, retrieved code answer "
            "because the writer dropped the 'code:' prefix",
        )
        self.assertIn("code:foo.py#L1-L300", r.citations)


class PromptShowsEnoughOfACodeChunk(unittest.TestCase):
    """Finding #2: a code chunk the ingester deemed one 300-line window is ~80%
    invisible to the writer because build_prompt truncates it to 1500 chars."""

    def test_answer_deep_in_a_code_window_is_visible_to_writer(self):
        deep = "SPLIT_WORDS_LOGIC_TOKEN"
        line = "some_variable = compute_value(x, y)\n"   # ~36 chars/line
        # ~90 lines (~3240 chars) before the token, ~90 after: a single realistic
        # sub-300-line code window whose middle currently gets truncated away.
        text = (line * 90) + deep + "\n" + (line * 90)
        chunk = Chunk("code:foo.py#L1-L300", "code", text)
        prompt = build_prompt("what does split_words do to a field name", [chunk])
        self.assertIn(
            deep, prompt,
            "the writer never sees code past ~1500 chars, so an answer sitting "
            "mid-window in a 300-line code chunk is invisible even when retrieved",
        )


if __name__ == "__main__":
    unittest.main()
