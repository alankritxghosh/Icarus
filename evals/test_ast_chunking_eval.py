"""AST chunking's live proof: it must beat fixed line-windows on the
comprehension board's retrieval, measured in the SAME run, never hardcoded.

The controlled comparison holds everything constant except code chunking:
  - PR/issue chunks: taken verbatim from the committed corpus, identical in
    both arms (only CODE chunking is under test).
  - source text: raw whole-file Python from `evals/fixtures/ast_chunking_eval/`
    (the same pinned `simonw/llm @ 94769b8` commit as the corpus itself,
    extracted from the corpus's own code chunks before the 2026-07-17
    AST-chunking migration -- T5 of
    docs/plans/2026-07-17-ast-chunking-all-languages.md), re-chunked two ways.
    Committed as an independent fixture, not read live from
    `evals/corpus/chunks.jsonl`, because that corpus's code IS NOW
    AST-chunked -- it's one of the two arms this test compares, not raw
    material for both. See the fixture directory's MANIFEST.md.
  - retriever, questions, embedder, k: identical.

Metric is FILE-LEVEL recall@k -- "did any chunk from the gold file reach the
top k". This is deliberate and load-bearing: grader.grade's own
retrieval_recall_at_k does EXACT ref membership, and the board's gold
citations are whole-file refs (`code:llm/models.py`) while AST chunks carry
line ranges (`...#L100-L150`). Scoring AST on exact-ref membership would score
it 0 for a reason unrelated to quality -- a rigged comparison. File-level is
fair to both arms and, if anything, handicaps AST: its many small chunks
compete for the same k slots where the window arm has one big chunk per file.

Self-skips without fastembed or the corpus, like every other live eval here.
"""

import json
import re
import unittest
from pathlib import Path

from .ast_chunk import ast_chunk
from .corpus import Chunk
from .ingest import chunk_text
from .provider import LocalEmbeddingProvider
from .retriever import LexicalRetriever, SemanticRetriever

try:
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False

ROOT = Path(__file__).resolve().parent
CORPUS = ROOT / "corpus" / "chunks.jsonl"
COMPREHENSION = ROOT / "comprehension_questions.json"
FIXTURES = ROOT / "fixtures" / "ast_chunking_eval"

_EMBED_TOKEN_LIMIT = 512  # bge-small-en-v1.5's hard truncation point


def _gold_file(ref):
    """Strip any #Lstart-Lend suffix -- compare at file granularity."""
    return re.sub(r"#L\d+(-L\d+)?$", "", ref)


@unittest.skipUnless(_HAS_FASTEMBED and CORPUS.exists() and COMPREHENSION.exists()
                     and FIXTURES.exists(),
                     "needs fastembed, the corpus, comprehension_questions.json, "
                     "and the ast_chunking_eval fixtures")
class AstChunkingEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = json.loads(COMPREHENSION.read_text())
        questions = raw["questions"] if isinstance(raw, dict) else raw
        cls.answerable = [q for q in questions if q["label"] == "answerable"]

        committed = [json.loads(l) for l in CORPUS.read_text().splitlines() if l.strip()]
        cls.prose = [Chunk(ref=c["ref"], source=c["source"], text=c["text"])
                     for c in committed if c["source"] in ("pr", "issue")]
        # Raw whole-file Python from the committed fixture snapshot (NOT the
        # live corpus -- see module docstring) is the real file content to
        # re-chunk two ways.
        cls.files = [
            (f"code:llm/{p.relative_to(FIXTURES / 'llm').as_posix()}", p.read_text())
            for p in sorted((FIXTURES / "llm").rglob("*.py"))
        ]
        assert cls.files, "ast_chunking_eval fixtures have no .py files to re-chunk"

        cls.embedder = LocalEmbeddingProvider()
        cls.arms = {name: cls._build(name) for name in ("window-300", "ast")}

    @classmethod
    def _build(cls, scheme):
        chunker = chunk_text if scheme == "window-300" else ast_chunk
        chunks = list(cls.prose)
        for ref, text in cls.files:
            for part in chunker(text, ref):
                chunks.append(Chunk(ref=part["ref"], source="code", text=part["text"]))
        return chunks

    def _semantic_recall(self, chunks, k=5):
        retriever = SemanticRetriever(chunks, self.embedder)
        hits = 0
        for q in self.answerable:
            golds = {_gold_file(g) for g in q["citations"]}
            got = {_gold_file(r) for r in retriever.search(q["question"], k)}
            if golds & got:
                hits += 1
        return 100.0 * hits / len(self.answerable)

    def _code_token_lengths(self, chunks):
        """True (untruncated) token lengths of the code chunks."""
        tok = self.embedder._model.model.tokenizer
        tok.no_truncation()
        try:
            return sorted(len(tok.encode(c.text).ids)
                          for c in chunks if c.source == "code")
        finally:
            # This tokenizer IS the one the model embeds with; leaving
            # truncation off feeds >512 tokens into a 512-position embedding
            # and crashes ONNX. Always restore it.
            tok.enable_truncation(max_length=_EMBED_TOKEN_LIMIT)

    def test_line_windows_overflow_the_embedder_budget_and_ast_chunks_do_not(self):
        """The mechanism. chunk_text's own comment claims a 300-line window is
        'small enough for a BM25/embedding retriever to score a chunk as a
        coherent unit'. That is false for the embedder by several multiples --
        this is the measurement that proves it, and that AST chunking fixes it.
        """
        win = self._code_token_lengths(self.arms["window-300"])
        ast_lens = self._code_token_lengths(self.arms["ast"])
        win_p50 = win[len(win) // 2]
        ast_p50 = ast_lens[len(ast_lens) // 2]

        self.assertGreater(win_p50, _EMBED_TOKEN_LIMIT,
                           "expected the median line-window to EXCEED the embedder's "
                           "512-token budget (the bug this brick exists to fix)")
        self.assertLessEqual(ast_p50, _EMBED_TOKEN_LIMIT,
                             f"AST chunks must fit the embedder whole; p50={ast_p50}")

        over = lambda L: 100.0 * sum(1 for x in L if x > _EMBED_TOKEN_LIMIT) / len(L)
        self.assertLess(over(ast_lens), over(win) / 2,
                        "AST chunking must at least halve the share of chunks the "
                        "embedder silently truncates")

    def test_ast_chunking_beats_line_windows_on_semantic_recall(self):
        """The payoff, same-run and never hardcoded: splitting on the code's own
        structure strictly improves what semantic retrieval can find."""
        win = self._semantic_recall(self.arms["window-300"])
        ast_recall = self._semantic_recall(self.arms["ast"])
        self.assertGreater(
            ast_recall, win,
            f"AST chunking must beat line windows on semantic recall@5 "
            f"(window={win:.1f}%, ast={ast_recall:.1f}%)")

    def test_ast_chunking_does_not_regress_lexical_retrieval(self):
        """Guard the other half of the hybrid: BM25 reads full text regardless
        of the embedder's budget, so AST chunking must not cost lexical recall
        while it buys semantic recall."""
        def lexical_recall(chunks, k=5):
            retriever = LexicalRetriever(chunks)
            hits = 0
            for q in self.answerable:
                golds = {_gold_file(g) for g in q["citations"]}
                got = {_gold_file(r) for r in retriever.search(q["question"], k)}
                if golds & got:
                    hits += 1
            return 100.0 * hits / len(self.answerable)

        win = lexical_recall(self.arms["window-300"])
        ast_recall = lexical_recall(self.arms["ast"])
        self.assertGreaterEqual(
            ast_recall, win,
            f"AST chunking regressed lexical recall@5 "
            f"(window={win:.1f}%, ast={ast_recall:.1f}%)")


if __name__ == "__main__":
    unittest.main()
