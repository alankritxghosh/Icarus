# evals/test_corpus.py
import json
import unittest
from pathlib import Path
import tempfile

from .corpus import Chunk, load_chunks, chunk_covers_lines


class CorpusLoaderTests(unittest.TestCase):
    def test_loads_jsonl_into_chunks(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "chunks.jsonl"
            p.write_text(
                json.dumps({"ref": "pr:1", "source": "pr", "text": "hello"}) + "\n"
                + "\n"  # blank line tolerated
                + json.dumps({"ref": "code:a.py", "source": "code", "text": "x=1"}) + "\n"
            )
            chunks = load_chunks(p)
            self.assertEqual([c.ref for c in chunks], ["pr:1", "code:a.py"])
            self.assertIsInstance(chunks[0], Chunk)
            self.assertEqual(chunks[0].source, "pr")


class ChunkCoversLinesTests(unittest.TestCase):
    """Brick D's line-resolution primitive: given a GitHub selection
    {path, start, end}, does this chunk cover it? Must handle BOTH real ref
    shapes evals/ingest.py's chunk_text() produces: a windowed chunk with a
    '#Lstart-Lend' suffix, and a whole-file chunk with none (the committed
    simonw/llm corpus predates line-window chunking and is entirely this
    shape -- see the plan doc's D0 status note)."""

    def test_line_ranged_chunk_overlapping_the_selection_matches(self):
        c = Chunk("code:llm/tools.py#L10-L40", "code", "...")
        self.assertTrue(chunk_covers_lines(c, "llm/tools.py", 15, 20))

    def test_line_ranged_chunk_partially_overlapping_matches(self):
        c = Chunk("code:llm/tools.py#L10-L40", "code", "...")
        self.assertTrue(chunk_covers_lines(c, "llm/tools.py", 35, 50))  # tail overlap
        self.assertTrue(chunk_covers_lines(c, "llm/tools.py", 1, 12))   # head overlap

    def test_line_ranged_chunk_not_overlapping_does_not_match(self):
        c = Chunk("code:llm/tools.py#L10-L40", "code", "...")
        self.assertFalse(chunk_covers_lines(c, "llm/tools.py", 41, 50))
        self.assertFalse(chunk_covers_lines(c, "llm/tools.py", 1, 9))

    def test_whole_file_chunk_with_no_line_suffix_matches_any_range(self):
        # This is the committed corpus's actual shape -- must still resolve.
        c = Chunk("code:llm/models.py", "code", "...")
        self.assertTrue(chunk_covers_lines(c, "llm/models.py", 1, 5))
        self.assertTrue(chunk_covers_lines(c, "llm/models.py", 9999, 10005))

    def test_different_path_never_matches(self):
        c = Chunk("code:llm/tools.py#L10-L40", "code", "...")
        self.assertFalse(chunk_covers_lines(c, "llm/cli.py", 15, 20))

    def test_pr_and_issue_sources_never_match(self):
        # Only code/doc/config are file-addressable; a PR/issue ref has no
        # line semantics at all.
        self.assertFalse(chunk_covers_lines(Chunk("pr:1", "pr", "..."), "llm/tools.py", 1, 5))
        self.assertFalse(chunk_covers_lines(Chunk("issue:1", "issue", "..."), "llm/tools.py", 1, 5))

    def test_doc_and_config_sources_do_match(self):
        self.assertTrue(chunk_covers_lines(Chunk("doc:README.md", "doc", "..."), "README.md", 1, 5))
        self.assertTrue(chunk_covers_lines(Chunk("config:pyproject.toml", "config", "..."), "pyproject.toml", 1, 5))

    def test_malformed_line_suffix_treated_as_no_match(self):
        # Defensive: a ref that somehow has a '#' but isn't 'Lstart-Lend' must
        # fail closed (no match), never raise and never silently match-all.
        c = Chunk("code:llm/tools.py#weird", "code", "...")
        self.assertFalse(chunk_covers_lines(c, "llm/tools.py", 1, 5))


if __name__ == "__main__":
    unittest.main()
