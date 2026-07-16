"""Tests for chunk_text, the pure line-window chunker (Task A2).

Offline/pure: builds synthetic multi-line strings in memory, no filesystem, no
network. Proves the two required ref shapes:

  - a file short enough to fit in one window -> exactly one chunk, ref has NO
    line range (matches today's whole-file `fetch_code` ref format exactly, so
    a short file's citation format doesn't change when routed through this
    function -- Task A3's backward-compatibility requirement).
  - a file longer than one window -> multiple chunks, each ref carrying a
    1-indexed, inclusive `#Lstart-Lend` suffix, with the exact configured
    overlap between consecutive windows, and the last window ending exactly at
    the real last line (no padding past EOF).

Does not touch fetch_code/_collect_files/ingest_repo/classify_file -- wiring
this in is Task A3, not this one.
"""

import unittest

from .ingest import (
    _CHUNK_MAX_CHARS,
    _CHUNK_OVERLAP_LINES,
    _CHUNK_WINDOW_LINES,
    chunk_text,
)


def _make_lines(n):
    """n lines of distinct, greppable synthetic content: 'line 1', 'line 2', ..."""
    return "\n".join(f"line {i}" for i in range(1, n + 1)) + "\n"


def _make_dense_lines(n, line_len=200):
    """n lines, each padded to line_len chars -- for char-budget tests where a
    file is short in LINE count but long in CHAR count (e.g. long docstrings,
    generated tables)."""
    lines = []
    for i in range(1, n + 1):
        content = f"line{i}"
        lines.append(content + "x" * (line_len - len(content)))
    return "\n".join(lines) + "\n"


class ShortFileTests(unittest.TestCase):
    """A file at or under the window size must produce exactly one chunk in
    today's whole-file ref format -- no line range."""

    def test_short_text_is_one_chunk_no_line_range(self):
        text = _make_lines(20)
        chunks = chunk_text(text, "code:pkg/small.py")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["ref"], "code:pkg/small.py")
        self.assertEqual(chunks[0]["text"], text)

    def test_exact_boundary_is_still_one_chunk(self):
        # A file with exactly _CHUNK_WINDOW_LINES lines must NOT split -- the
        # boundary case is still "fits in a single window".
        text = _make_lines(_CHUNK_WINDOW_LINES)
        chunks = chunk_text(text, "code:pkg/boundary.py")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["ref"], "code:pkg/boundary.py")
        self.assertEqual(chunks[0]["text"], text)

    def test_single_line_file(self):
        text = "just one line\n"
        chunks = chunk_text(text, "doc:README.md")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["ref"], "doc:README.md")
        self.assertEqual(chunks[0]["text"], text)

    def test_empty_text_is_one_chunk(self):
        # Degenerate but real input (an empty file passed classify_file).
        chunks = chunk_text("", "code:pkg/empty.py")
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["ref"], "code:pkg/empty.py")
        self.assertEqual(chunks[0]["text"], "")

    def test_whitespace_only_long_file_splits_into_valid_windows(self):
        # All-blank-line file, longer than one window: still splits cleanly
        # into non-degenerate windows (no content isn't the same as no lines).
        total_lines = _CHUNK_WINDOW_LINES * 2 + 50
        text = "\n" * total_lines
        chunks = chunk_text(text, "code:pkg/blank.py")
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertIn("#L", c["ref"])
            line_part = c["ref"].split("#L", 1)[1]
            start_str, end_str = line_part.split("-L")
            start, end = int(start_str), int(end_str)
            self.assertLessEqual(start, end)
            self.assertGreaterEqual(end, start)
        last_line_part = chunks[-1]["ref"].split("#L", 1)[1]
        _, last_end_str = last_line_part.split("-L")
        self.assertEqual(int(last_end_str), total_lines)


class LongFileTests(unittest.TestCase):
    """A file over the window size must split into overlapping windows with
    line-range refs, 1-indexed and inclusive."""

    def setUp(self):
        # Comfortably more than one window past the threshold so we get
        # several windows, not just two.
        self.total_lines = _CHUNK_WINDOW_LINES * 2 + 50
        self.text = _make_lines(self.total_lines)
        self.chunks = chunk_text(self.text, "code:pkg/big.py")

    def test_multiple_chunks_produced(self):
        self.assertGreater(len(self.chunks), 1)

    def test_first_window_starts_at_line_1(self):
        first = self.chunks[0]
        self.assertEqual(first["ref"], f"code:pkg/big.py#L1-L{_CHUNK_WINDOW_LINES}")

    def test_first_window_text_matches_its_line_range(self):
        first_lines = self.text.splitlines()[0:_CHUNK_WINDOW_LINES]
        self.assertEqual(self.chunks[0]["text"], "\n".join(first_lines) + "\n")

    def test_overlap_between_consecutive_windows_is_exact(self):
        # Parse start/end out of each windowed ref and assert the real
        # stride: each window after the first starts exactly
        # (window - overlap) lines after the previous window's start.
        starts = []
        for c in self.chunks:
            ref = c["ref"]
            self.assertIn("#L", ref)
            line_part = ref.split("#L", 1)[1]
            start_str, end_str = line_part.split("-L")
            starts.append(int(start_str))
        stride = _CHUNK_WINDOW_LINES - _CHUNK_OVERLAP_LINES
        for i in range(1, len(starts)):
            self.assertEqual(starts[i] - starts[i - 1], stride)

    def test_last_window_ends_exactly_at_real_last_line_no_padding(self):
        last = self.chunks[-1]
        line_part = last["ref"].split("#L", 1)[1]
        _, end_str = line_part.split("-L")
        self.assertEqual(int(end_str), self.total_lines)
        # And its text is the real tail, not padded with blank lines.
        last_text_lines = last["text"].splitlines()
        self.assertEqual(last_text_lines[-1], f"line {self.total_lines}")

    def test_no_window_starts_past_the_end_of_file(self):
        for c in self.chunks:
            line_part = c["ref"].split("#L", 1)[1]
            start_str, _ = line_part.split("-L")
            self.assertLessEqual(int(start_str), self.total_lines)

    def test_every_windowed_chunk_is_non_degenerate(self):
        for c in self.chunks:
            line_part = c["ref"].split("#L", 1)[1]
            start_str, end_str = line_part.split("-L")
            start, end = int(start_str), int(end_str)
            self.assertLess(start, end + 1)  # start <= end (at least 1 line)
            self.assertGreaterEqual(end, start)
            self.assertGreater(len(c["text"]), 0)

    def test_refs_are_unique(self):
        refs = [c["ref"] for c in self.chunks]
        self.assertEqual(len(refs), len(set(refs)))

    def test_windows_cover_the_whole_file_without_gaps(self):
        # Every line number from 1..total_lines must fall inside at least one
        # window's [start, end] range -- overlap is fine, a gap is not.
        covered = set()
        for c in self.chunks:
            line_part = c["ref"].split("#L", 1)[1]
            start_str, end_str = line_part.split("-L")
            covered.update(range(int(start_str), int(end_str) + 1))
        self.assertEqual(covered, set(range(1, self.total_lines + 1)))


class JustOverBoundaryTests(unittest.TestCase):
    def test_one_line_over_the_window_splits_into_two(self):
        text = _make_lines(_CHUNK_WINDOW_LINES + 1)
        chunks = chunk_text(text, "code:pkg/tiny_over.py")
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["ref"], f"code:pkg/tiny_over.py#L1-L{_CHUNK_WINDOW_LINES}")
        last_line_part = chunks[1]["ref"].split("#L", 1)[1]
        _, end_str = last_line_part.split("-L")
        self.assertEqual(int(end_str), _CHUNK_WINDOW_LINES + 1)


class DenseShortFileTests(unittest.TestCase):
    """A file at or under _CHUNK_WINDOW_LINES (300) lines, but whose lines are
    long enough that its total char count exceeds the writer's per-chunk
    budget (synth.py's _MAX_CODE_CHUNK_CHARS), must still split. Reproduces a
    live-found bug: the whole-file short-circuit only checked line count,
    never chars -- a dense short file became ONE oversized chunk that
    build_prompt silently truncated, even though it was retrieved and reached
    the writer's top-k."""

    def test_dense_short_file_still_splits_by_char_budget(self):
        # 100 lines * 200 chars/line ~= 20,000 chars: well under
        # _CHUNK_WINDOW_LINES (300) lines, well over _CHUNK_MAX_CHARS.
        text = _make_dense_lines(100, line_len=200)
        chunks = chunk_text(text, "code:pkg/dense.py")
        self.assertGreater(len(chunks), 1)

    def test_every_chunk_stays_within_the_char_budget(self):
        text = _make_dense_lines(100, line_len=200)
        chunks = chunk_text(text, "code:pkg/dense.py")
        for c in chunks:
            self.assertLessEqual(len(c["text"]), _CHUNK_MAX_CHARS)

    def test_marker_past_the_char_budget_survives_into_some_chunk(self):
        # A marker placed past char 10,000 in a <=300-line file must survive
        # into at least one chunk small enough that build_prompt never has to
        # truncate it away.
        prefix = _make_dense_lines(60, line_len=200)  # ~12,000 chars
        marker_line = "MARKER_TOKEN" + "y" * 187
        text = prefix + marker_line + "\n"
        chunks = chunk_text(text, "code:pkg/dense_marker.py")
        self.assertTrue(any("MARKER_TOKEN" in c["text"] for c in chunks))
        for c in chunks:
            self.assertLessEqual(len(c["text"]), _CHUNK_MAX_CHARS)

    def test_dense_file_windows_still_cover_the_whole_file_without_gaps(self):
        text = _make_dense_lines(100, line_len=200)
        total_lines = 100
        chunks = chunk_text(text, "code:pkg/dense_cover.py")
        covered = set()
        for c in chunks:
            ref = c["ref"]
            self.assertIn("#L", ref)
            line_part = ref.split("#L", 1)[1]
            start_str, end_str = line_part.split("-L")
            covered.update(range(int(start_str), int(end_str) + 1))
        self.assertEqual(covered, set(range(1, total_lines + 1)))


class RefPrefixContractTests(unittest.TestCase):
    def test_hash_in_ref_prefix_is_rejected(self):
        # A "#" in ref_prefix would produce a ref with two "#"s for a
        # windowed chunk (e.g. "code:weird#anchor.py#L1-L300"), ambiguous for
        # any downstream parser that recovers the path via ref.split("#")[0].
        # Real repo-relative paths never contain "#" -- this is a caller
        # contract, so it must fail loudly rather than silently produce a
        # malformed ref.
        with self.assertRaises(AssertionError):
            chunk_text(_make_lines(_CHUNK_WINDOW_LINES * 2), "code:pkg/weird#anchor.py")


if __name__ == "__main__":
    unittest.main()
