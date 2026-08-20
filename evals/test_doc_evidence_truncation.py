# evals/test_doc_evidence_truncation.py
"""RED failing eval for the doc-evidence truncation found 2026-08-21 while
dogfooding ICARUS.md (Work Queue #5).

THE GAP. `evals/synth.py` shows a retrieved chunk to the writer under one of two
caps: `_MAX_CODE_CHUNK_CHARS` (10,000) for `code`/`pr`/`issue`/`commit`/`diff`,
and `_MAX_CHUNK_CHARS` (1,500) for everything else -- which is `doc` and
`config`. `evals/ingest.py` meanwhile sizes a chunk against
`_MAX_CODE_CHUNK_CHARS`: it imports that very constant as `_CHUNK_MAX_CHARS`.
So the ingester will emit a single ~10,000-char `doc` chunk that the prompt then
shows 15% of, and the two halves of the pipeline disagree about how large a doc
chunk may be.

MEASURED, on this repository's own ICARUS.md: 1,500 of 9,549 characters reach
the writer. Exactly ONE of its eight sections survives; seven are truncated
away, including "Things that must not be changed casually" -- the section the
design named the highest-value one.

WHY NOTHING REPORTS IT. A citation to `doc:ICARUS.md` resolves against a
genuinely retrieved ref, so the honesty gate passes an answer drawn from the
surviving 16% exactly as it would pass one drawn from the whole file. This is
not a bluff and the honesty invariant holds -- which is precisely why it is
invisible: "the retriever can find it" and "the writer can read it" are
different properties, and only the first is observable from outside. Same family
as Finding #2 in test_code_answering_gap.py, which is why code got the larger
cap; doc was left behind.

These tests encode the DESIRED behavior, so they are RED until the brain is
fixed and GREEN after. Do NOT make them pass by removing the cap altogether --
the guards below prove a cap still exists and still bites.
"""
import re
import unittest
from pathlib import Path

from .corpus import Chunk
from .synth import build_prompt, _MAX_CHUNK_CHARS, _MAX_CODE_CHUNK_CHARS


_MARKER = "SENTINEL-LATE-SECTION"


def _doc_text(total_chars: int, tail: str = _MARKER) -> str:
    """A doc chunk whose LAST line is the thing the reader needs.

    Filled with unique numbered lines rather than repeated padding so a partial
    match cannot accidentally satisfy an assertion.
    """
    body = []
    n = 0
    while sum(len(x) for x in body) < total_chars:
        body.append(f"line {n:05d} of an engineering-context document\n")
        n += 1
    return "".join(body) + tail


class DocEvidenceReachesTheWriterTests(unittest.TestCase):
    """RED: a doc chunk the ingester considered one coherent unit is shown to
    the writer almost entirely truncated away."""

    def test_doc_chunk_larger_than_prose_cap_still_reaches_the_writer(self):
        # 6,000 chars: comfortably under what ingest will emit as ONE chunk
        # (it sizes against _MAX_CODE_CHUNK_CHARS = 10,000), comfortably over
        # the prose cap the prompt applies to `doc`.
        chunk = Chunk(ref="doc:ICARUS.md", source="doc", text=_doc_text(6000))
        self.assertLess(len(chunk.text), _MAX_CODE_CHUNK_CHARS,
                        "fixture must be a chunk ingest would emit whole")
        # 1500 is the OLD prose cap, written as a literal on purpose: comparing
        # against the live constant would make this precondition dissolve the
        # moment the cap moves, and a fixture that no longer reproduces the bug
        # is a test that passes for the wrong reason.
        self.assertGreater(len(chunk.text), 1500,
                           "fixture must exceed the historical prose cap of 1500, "
                           "or it never reproduced the gap")

        prompt = build_prompt("what must not be changed casually?", [chunk])

        self.assertIn(_MARKER, prompt,
                      "the end of a doc chunk never reaches the writer: "
                      "evidence that was retrieved, cited and gated is invisible")

    def test_real_icarus_md_reaches_the_writer_in_full(self):
        """The product-level version of the gap, on the real file.

        Structural rather than textual -- it asserts every `## ` heading
        survives -- so editing the document cannot make this test lie.
        """
        path = Path(__file__).resolve().parent.parent / "ICARUS.md"
        if not path.exists():                      # pragma: no cover
            self.skipTest("ICARUS.md not present")
        text = path.read_text()
        headings = re.findall(r"^## .*", text, flags=re.M)
        self.assertGreater(len(headings), 1, "fixture repo file lost its sections")

        chunk = Chunk(ref="doc:ICARUS.md", source="doc", text=text)
        prompt = build_prompt("what must not be changed casually?", [chunk])

        missing = [h for h in headings if h not in prompt]
        self.assertEqual(
            [], missing,
            f"{len(missing)} of {len(headings)} sections of ICARUS.md never "
            f"reach the writer, though the file is retrieved and citable")

    def test_the_two_halves_agree_on_how_large_a_chunk_may_be(self):
        """ingest imports _MAX_CODE_CHUNK_CHARS as its own chunk-size budget, so
        a source the prompt caps lower than that can always be emitted whole and
        shown in part. Pins the invariant rather than the numbers."""
        from .ingest import _CHUNK_MAX_CHARS
        self.assertEqual(_CHUNK_MAX_CHARS, _MAX_CODE_CHUNK_CHARS)
        self.assertGreaterEqual(
            _MAX_CHUNK_CHARS, _CHUNK_MAX_CHARS,
            "a chunk ingest emits whole is shown to the writer in part, and "
            "nothing anywhere reports the loss")


class TruncationStillExistsTests(unittest.TestCase):
    """GREEN, and MUST STAY GREEN. The fix raises the doc cap; it does not
    remove capping. An unbounded prompt is a different defect, not a fix."""

    def test_a_doc_chunk_beyond_the_large_cap_is_still_truncated(self):
        chunk = Chunk(ref="doc:HUGE.md", source="doc",
                      text=_doc_text(_MAX_CODE_CHUNK_CHARS + 5000))
        prompt = build_prompt("q", [chunk])
        self.assertNotIn(_MARKER, prompt,
                         "capping was removed rather than raised")
        self.assertIn("…", prompt, "truncation must stay visible when it happens")

    def test_code_chunk_budget_is_unchanged(self):
        chunk = Chunk(ref="code:x.py#L1-L300", source="code",
                      text=_doc_text(_MAX_CODE_CHUNK_CHARS - 200))
        self.assertIn(_MARKER, build_prompt("q", [chunk]))


if __name__ == "__main__":                         # pragma: no cover
    unittest.main()
