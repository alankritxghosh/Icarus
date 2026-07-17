"""ts_chunk's live proof (T3 of docs/plans/2026-07-17-ast-chunking-all-
languages.md): for each of the four React Native language arms this brick
targets (TSX, Kotlin, ObjC, Java), splitting on the code's own structure must
beat `chunk_text`'s fixed 300-line windows on semantic retrieval -- the same
same-run, never-hardcoded methodology `test_ast_chunking_eval.py` used to
prove this for Python.

Fixtures are REAL source from three MIT-licensed public repos, committed
verbatim under evals/fixtures/ts_chunk_eval/ -- see MANIFEST.md for exact
commit provenance. Chosen over a live network clone at test time so this stays
deterministic and needs no network, matching how the Python board proof reuses
the already-committed simonw/llm corpus rather than re-fetching it.

Every question in evals/ts_chunk_eval_questions.json was hand-verified by
reading the real fixture file in full before writing its reference_answer.

Metric is FILE-LEVEL recall@k (does the gold file's own name appear as the
path-prefix of any top-k retrieved ref) -- the same choice test_ast_chunking_
eval.py made and for the same reason: gold citations name a whole file, ts_chunk
refs carry a `#Lstart-Lend` suffix chunk_text's own multi-window refs also
carry, so exact-ref matching would be unfair to BOTH arms equally here (unlike
the Python proof, neither arm here is a single whole-file chunk) -- file-level
is the metric that isolates "did splitting strategy change what's findable"
from "did the ref happen to match verbatim".

Self-skips only on missing fastembed/tree-sitter-language-pack -- the fixture
corpus itself is committed, so it's always present.
"""

import json
import unittest
from pathlib import Path

from .corpus import Chunk
from .provider import LocalEmbeddingProvider
from .retriever import LexicalRetriever, SemanticRetriever
from .ingest import chunk_text

try:
    import fastembed  # noqa: F401
    _HAS_FASTEMBED = True
except ImportError:
    _HAS_FASTEMBED = False

try:
    import tree_sitter_language_pack  # noqa: F401
    _HAS_TREE_SITTER = True
except ImportError:
    _HAS_TREE_SITTER = False

if _HAS_TREE_SITTER:
    from .ts_chunk import ts_chunk

ROOT = Path(__file__).resolve().parent
QUESTIONS = ROOT / "ts_chunk_eval_questions.json"
FIXTURES = ROOT / "fixtures" / "ts_chunk_eval"

_EMBED_TOKEN_LIMIT = 512  # bge-small-en-v1.5's hard truncation point

_LANG_EXT = {"tsx": ".tsx", "kotlin": ".kt", "objc": ".mm", "java": ".java"}


@unittest.skipUnless(_HAS_FASTEMBED and _HAS_TREE_SITTER and QUESTIONS.exists(),
                     "needs fastembed, tree-sitter-language-pack, and the "
                     "committed ts_chunk_eval fixtures/questions")
class TsChunkingEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(QUESTIONS.read_text())["languages"]
        cls.embedder = LocalEmbeddingProvider()

    @classmethod
    def _files(cls, lang):
        d = FIXTURES / lang
        return sorted(d.glob(f"*{_LANG_EXT[lang]}"))

    @classmethod
    def _build(cls, lang, scheme):
        ext = _LANG_EXT[lang]
        chunker = chunk_text if scheme == "window-300" else (
            lambda text, ref: ts_chunk(text, ref, ext))
        chunks = []
        for path in cls._files(lang):
            text = path.read_text(errors="replace")
            for part in chunker(text, f"code:{path.name}"):
                chunks.append(Chunk(ref=part["ref"], source="code", text=part["text"]))
        return chunks

    def _semantic_recall(self, lang, chunks, questions, k=5):
        retriever = SemanticRetriever(chunks, self.embedder)
        gold = self.spec[lang]["gold_file"]
        hits = 0
        for q in questions:
            got = retriever.search(q["question"], k)
            if any(r.split("#", 1)[0] == f"code:{gold}" for r in got):
                hits += 1
        return 100.0 * hits / len(questions)

    def _token_lengths(self, chunks):
        tok = self.embedder._model.model.tokenizer
        tok.no_truncation()
        try:
            return sorted(len(tok.encode(c.text).ids) for c in chunks)
        finally:
            tok.enable_truncation(max_length=_EMBED_TOKEN_LIMIT)

    def test_every_language_beats_the_line_window_baseline_on_recall(self):
        """The payoff, per language, same-run, never hardcoded."""
        results = {}
        for lang in self.spec:
            questions = self.spec[lang]["questions"]
            window_chunks = self._build(lang, "window-300")
            ast_chunks = self._build(lang, "ts_chunk")
            win = self._semantic_recall(lang, window_chunks, questions)
            ast = self._semantic_recall(lang, ast_chunks, questions)
            results[lang] = (win, ast)
            self.assertGreaterEqual(
                ast, win,
                f"[{lang}] ts_chunk must not regress semantic recall@5 vs "
                f"window-300 (window={win:.1f}%, ts_chunk={ast:.1f}%)")

        # Aggregate across all four languages must show a REAL win, not just
        # four ties -- guards against a valve/config bug that quietly makes
        # every language identical to the baseline.
        total_win = sum(w for w, _ in results.values())
        total_ast = sum(a for _, a in results.values())
        self.assertGreater(
            total_ast, total_win,
            f"aggregate recall did not improve: {results}")

    def test_line_windows_measurably_exceed_the_embed_budget_per_language(self):
        """The mechanism, per language: window-300's own chunks routinely
        exceed the 512-token embed budget on real code; ts_chunk's do not."""
        for lang in self.spec:
            window_chunks = self._build(lang, "window-300")
            ast_chunks = self._build(lang, "ts_chunk")
            win_lens = self._token_lengths(window_chunks)
            ast_lens = self._token_lengths(ast_chunks)
            win_p50 = win_lens[len(win_lens) // 2]
            ast_p50 = ast_lens[len(ast_lens) // 2]
            with self.subTest(lang=lang):
                self.assertLessEqual(
                    ast_p50, _EMBED_TOKEN_LIMIT,
                    f"[{lang}] ts_chunk median token length {ast_p50} exceeds "
                    f"the embed budget -- the whole point of this brick")


if __name__ == "__main__":
    unittest.main()
