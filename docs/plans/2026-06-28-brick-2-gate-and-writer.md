# Brick 2 — Honesty Gate + Answer Writer — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Each task is red→green: a failing test first, then the smallest code that turns it green. **Never weaken a test, the grader, or the labelled set to pass.** Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work in an isolated worktree per [CLAUDE.md].

**Goal:** Turn `citation_correctness` green on the 6 answerable questions and keep abstention honest on the 4 unrecorded ones — by adding a rented answer-writer behind a deterministic honesty gate — while groundedness and abstention recall stay pinned at 100%.

**Architecture:** `retrieve → build a strict cite-or-abstain prompt → call a rented LLM (the "writer") → a deterministic gate parses the reply and emits an answer ONLY if it parses, claims "answer", has prose, and cites ≥1 retrieved ref; everything else fails safe to "unknown".` The LLM sits behind a one-function `Provider` so the unit suite runs offline with a test double; the real model is exercised only by a skippable network test and the board.

**Tech Stack:** Python 3 stdlib only — **no new dependency** (OpenRouter is called via `urllib.request`). OpenRouter free model as the writer (default `cohere/north-mini-code:free`, configurable). API key from `OPENROUTER_API_KEY` env var — never hardcoded, never committed.

---

## Where we are (do not re-derive)

- Brick 0 + Brick 1 are merged to `main`. The board (`python3 -m evals.run`) reads: groundedness 100%, abstention recall 100%, **retrieval recall@k 100%**, `citation_correctness 0%`, status RED. 17 tests pass via `python3 -m unittest discover -t . -s evals -p "test_*.py"`.
- Existing `evals/` modules and their contracts:
  - `pipeline.py` — `Result(verdict, answer, citations, retrieved)`, `Pipeline` interface, `StubPipeline`, `RetrievalPipeline`.
  - `retriever.py` — `LexicalRetriever(chunks).search(query, k) -> List[str]` (refs, best-first).
  - `corpus.py` — `Chunk(ref, source, text)`, `load_chunks(path)`.
  - `grader.py` — `grade(questions, pipeline, k)`. Groundedness requires `citations ⊆ retrieved`. Citation correctness = answered answerable questions that cite every gold ref. **Do not modify this file.**
  - `phase1_questions.json` — the verified labelled set. **Do not modify this file.**
  - Corpus: `evals/corpus/chunks.jsonl` (243 chunks, gold PRs present).

## Scope of this plan

In scope: the `Provider` abstraction, the prompt builder, the deterministic gate, the `GatedPipeline`, board wiring, and the eval that proves the brick. Out of scope (later bricks): embeddings (confirmed unnecessary), the web demo, the answer-correctness judge, the recordable demo.

---

### Task 0 — Prerequisite (NOT code; the human satisfies this before Task 5 runs)

Confirm, per [CLAUDE.md] and [docs/PHASE_1_PLAN.md]:
- OpenRouter account **data settings** reviewed (free routes may train on inputs → **public repos only**, which `simonw/llm` is). 
- `OPENROUTER_API_KEY` is exported in the shell that will run the integration test / board.

Verify (no secret printed): `python3 -c "import os;print('key set:', bool(os.environ.get('OPENROUTER_API_KEY')))"` → `key set: True`.

Tasks 1–4 need **no** network or key and can proceed immediately. Task 5's integration test self-skips when the key is absent.

---

### Task 1 — Provider abstraction (offline-testable)

**Files:**
- Create: `evals/provider.py`
- Create: `evals/test_provider.py`

**Step 1: Write the failing test** — `evals/test_provider.py`:

```python
# evals/test_provider.py
import os
import unittest

from .provider import StaticProvider, OpenRouterProvider


class StaticProviderTests(unittest.TestCase):
    def test_returns_queued_then_sticks_on_last(self):
        p = StaticProvider(["a", "b"])
        self.assertEqual(p.complete("x"), "a")
        self.assertEqual(p.complete("x"), "b")
        self.assertEqual(p.complete("x"), "b")  # sticks on last

    def test_accepts_a_single_string(self):
        self.assertEqual(StaticProvider("only").complete("x"), "only")


class OpenRouterProviderTests(unittest.TestCase):
    def test_raises_without_api_key(self):
        old = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            with self.assertRaises(RuntimeError):
                OpenRouterProvider().complete("hi")
        finally:
            if old is not None:
                os.environ["OPENROUTER_API_KEY"] = old


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS**
`python3 -m unittest evals.test_provider -v` → `No module named 'evals.provider'`.

**Step 3: Implement** — `evals/provider.py`:

```python
# evals/provider.py
"""Provider abstraction for the answer-writer (the rented LLM).

We rent the model, own the pipeline. The gate and pipeline depend only on
Provider.complete(prompt) -> str. OpenRouterProvider calls OpenRouter over
stdlib urllib (no third-party deps); tests use StaticProvider so the unit suite
stays offline and deterministic. API key comes from OPENROUTER_API_KEY — never
hardcode or commit it. Public repos only while on free models (see CLAUDE.md).
"""

import json
import os
import urllib.request


class Provider:
    def complete(self, prompt: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class StaticProvider(Provider):
    """Test double: returns queued responses in order, sticking on the last."""

    def __init__(self, responses):
        self._responses = [responses] if isinstance(responses, str) else list(responses)
        self._i = 0

    def complete(self, prompt: str) -> str:
        r = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return r


class OpenRouterProvider(Provider):
    """Calls an OpenRouter chat-completions model. Network. Stdlib only."""

    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str = "cohere/north-mini-code:free", timeout: float = 60.0):
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        body = json.dumps(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
        ).encode()
        req = urllib.request.Request(
            self.URL,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
```

**Step 4: Run, confirm it PASSES** — `python3 -m unittest evals.test_provider -v` → OK (3 tests).

**Step 5: Commit**
```bash
git add evals/provider.py evals/test_provider.py
git commit -m "$(printf 'Add Provider abstraction (OpenRouter over urllib + StaticProvider)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 2 — The cite-or-abstain prompt builder (pure function)

**Files:**
- Create: `evals/synth.py`
- Create: `evals/test_synth.py`

**Step 1: Write the failing test** — `evals/test_synth.py`:

```python
# evals/test_synth.py
import json
import unittest

from .corpus import Chunk
from .synth import build_prompt


class BuildPromptTests(unittest.TestCase):
    def setUp(self):
        self.chunks = [Chunk("pr:1", "pr", "We did X because Y."), Chunk("code:a.py", "code", "N = 32")]
        self.prompt = build_prompt("Why X?", self.chunks)

    def test_includes_question_and_refs_and_text(self):
        self.assertIn("Why X?", self.prompt)
        self.assertIn("pr:1", self.prompt)
        self.assertIn("We did X because Y.", self.prompt)
        self.assertIn("code:a.py", self.prompt)

    def test_demands_unknown_when_unsupported(self):
        # the instruction must offer an explicit abstention path
        self.assertIn("unknown", self.prompt.lower())

    def test_truncates_very_long_chunks(self):
        big = Chunk("pr:2", "pr", "x" * 5000)
        self.assertLess(len(build_prompt("q", [big])), 4000)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `python3 -m unittest evals.test_synth -v` → `No module named 'evals.synth'`.

**Step 3: Implement** — `evals/synth.py`:

```python
# evals/synth.py
"""Builds the strict cite-or-abstain prompt for the answer-writer.

The writer may only use the numbered evidence and must reply as JSON: either an
answer with the refs it relied on, or an explicit unknown. The deterministic
gate (evals/gate.py) enforces this afterwards; the prompt just asks for it.
"""

from typing import List

from .corpus import Chunk

INSTRUCTION = (
    "You answer questions about a software project using ONLY the numbered "
    "evidence below.\n"
    "Rules:\n"
    "1. If the evidence explicitly states the reason/answer, reply with JSON: "
    '{"verdict": "answer", "answer": "<one or two sentences>", '
    '"citations": ["<ref>", ...]}. Cite only the refs whose text supports it.\n'
    '2. If the evidence does NOT contain the answer, reply with JSON: '
    '{"verdict": "unknown"}.\n'
    "3. Never use outside knowledge. Never guess. When unsure, choose unknown.\n"
    "Reply with JSON and nothing else."
)

_MAX_CHUNK_CHARS = 1500


def build_prompt(question: str, chunks: List[Chunk]) -> str:
    blocks = []
    for c in chunks:
        text = c.text.strip()
        if len(text) > _MAX_CHUNK_CHARS:
            text = text[:_MAX_CHUNK_CHARS] + " …"
        blocks.append(f"[{c.ref}]\n{text}")
    return f"{INSTRUCTION}\n\nQUESTION: {question}\n\nEVIDENCE:\n" + "\n\n".join(blocks)
```

**Step 4: Run, confirm it PASSES** — OK (3 tests).

**Step 5: Commit**
```bash
git add evals/synth.py evals/test_synth.py
git commit -m "$(printf 'Add cite-or-abstain prompt builder\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 3 — The deterministic honesty gate (the conscience; pure, offline)

**Files:**
- Create: `evals/gate.py`
- Create: `evals/test_gate.py`

This is the most important file in the brick. It must fail safe to abstention in every ambiguous case. **Note (avoid a circular import):** `gate.py` imports `Result` from `pipeline.py`; `pipeline.py` must NOT import `gate` at module top level (the `GatedPipeline` in Task 4 imports it inside its method).

**Step 1: Write the failing test** — `evals/test_gate.py`:

```python
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


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `No module named 'evals.gate'`.

**Step 3: Implement** — `evals/gate.py`:

```python
# evals/gate.py
"""The deterministic honesty gate: turns the writer's raw reply into a Result
and can only ever fail safe toward abstention.

This is auditable code, not a model. An answer is emitted ONLY if the reply
parses as JSON with verdict "answer", a non-empty answer string, and at least
one citation that was actually retrieved. A parse failure, a missing field, an
explicit unknown, or citations we did not retrieve all collapse to "unknown".
The model cannot make us bluff: groundedness is guaranteed by construction
(citations are filtered to the retrieved set).
"""

import json
import re
from typing import List

from .pipeline import Result

_JSON = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str):
    m = _JSON.search(raw or "")
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (ValueError, TypeError):
        return None


def gate(raw: str, retrieved: List[str]) -> Result:
    data = _extract_json(raw)
    if not isinstance(data, dict) or data.get("verdict") != "answer":
        return Result(verdict="unknown")
    answer = data.get("answer")
    citations = data.get("citations")
    if not isinstance(answer, str) or not answer.strip():
        return Result(verdict="unknown")
    if not isinstance(citations, list):
        return Result(verdict="unknown")
    retrieved_set = set(retrieved)
    grounded = [c for c in citations if c in retrieved_set]
    if not grounded:
        return Result(verdict="unknown")
    return Result(verdict="answer", answer=answer.strip(), citations=grounded, retrieved=list(retrieved))
```

**Step 4: Run, confirm it PASSES** — OK (8 tests).

**Step 5: Commit**
```bash
git add evals/gate.py evals/test_gate.py
git commit -m "$(printf 'Add deterministic honesty gate (fails safe to abstention)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 4 — GatedPipeline (wire retrieve → writer → gate; offline-tested)

**Files:**
- Modify: `evals/pipeline.py` (APPEND `GatedPipeline`; do not touch existing classes; do NOT add a top-level `gate` import)
- Create: `evals/test_gated_pipeline.py`

**Step 1: Write the failing test** — `evals/test_gated_pipeline.py`:

```python
# evals/test_gated_pipeline.py
import json
import unittest

from .corpus import Chunk
from .retriever import LexicalRetriever
from .provider import StaticProvider
from .pipeline import GatedPipeline

CHUNKS = [
    Chunk("pr:1", "pr", "We mock with MSW because stubbing fetch broke on transport switches"),
    Chunk("pr:2", "pr", "bump version"),
]


def _pipe(provider):
    return GatedPipeline(LexicalRetriever(CHUNKS), CHUNKS, provider)


class GatedPipelineTests(unittest.TestCase):
    def test_emits_grounded_answer(self):
        raw = json.dumps({"verdict": "answer", "answer": "Because fetch stubbing broke.", "citations": ["pr:1"]})
        r = _pipe(StaticProvider(raw)).answer("why MSW instead of stubbing fetch")
        self.assertEqual(r.verdict, "answer")
        self.assertIn("pr:1", r.citations)

    def test_abstains_when_writer_abstains(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("why MSW")
        self.assertEqual(r.verdict, "unknown")

    def test_bluff_with_unretrieved_citation_is_forced_unknown(self):
        raw = json.dumps({"verdict": "answer", "answer": "made up", "citations": ["pr:9999"]})
        self.assertEqual(_pipe(StaticProvider(raw)).answer("why MSW").verdict, "unknown")

    def test_populates_retrieved_for_recall(self):
        r = _pipe(StaticProvider(json.dumps({"verdict": "unknown"}))).answer("why MSW instead of stubbing fetch")
        self.assertIn("pr:1", r.retrieved)  # recall@k still measurable even on abstain


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `cannot import name 'GatedPipeline'`.

**Step 3: Implement** — append to `evals/pipeline.py`:

```python


class GatedPipeline(Pipeline):
    """Retrieve -> writer (provider) -> deterministic honesty gate -> Result.

    The writer is constrained to answer only from retrieved evidence or abstain;
    the gate (evals/gate.py) enforces that deterministically, failing safe to
    'unknown'. `retrieved` is always the full top-recall_n list so retrieval
    recall@k stays measurable regardless of the verdict.
    """

    def __init__(self, retriever, chunks, provider, recall_n: int = 20, writer_k: int = 6):
        self._retriever = retriever
        self._by_ref = {c.ref: c for c in chunks}
        self._provider = provider
        self._recall_n = recall_n
        self._writer_k = writer_k

    def answer(self, question: str) -> Result:
        from .synth import build_prompt   # local imports avoid a circular import
        from .gate import gate
        retrieved = self._retriever.search(question, self._recall_n)
        top = [self._by_ref[r] for r in retrieved[: self._writer_k] if r in self._by_ref]
        if not top:
            return Result(verdict="unknown", retrieved=retrieved)
        result = gate(self._provider.complete(build_prompt(question, top)), retrieved)
        result.retrieved = retrieved
        return result
```

**Step 4: Run, confirm it PASSES** — OK (4 tests). Then full offline suite: `python3 -m unittest discover -t . -s evals -p "test_*.py"` → all green.

**Step 5: Commit**
```bash
git add evals/pipeline.py evals/test_gated_pipeline.py
git commit -m "$(printf 'Add GatedPipeline (retrieve -> writer -> deterministic gate)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 5 — Prove it on the real model (board + skippable integration test)

**Files:**
- Modify: `evals/run.py` (add `gated` to the `--pipeline` choices)
- Create: `evals/test_gated_eval.py`

**Step 1: Add the integration test** — `evals/test_gated_eval.py` (self-skips without a key):

```python
# evals/test_gated_eval.py
"""Real-model proof: the gated pipeline must lift citation correctness above
zero on the 6 answerable questions while keeping BOTH honesty gates at 100% --
including honest abstention on the 4 unrecorded code questions. Skipped when
OPENROUTER_API_KEY is absent (offline CI)."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
from .provider import OpenRouterProvider
from .pipeline import GatedPipeline

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(os.environ.get("OPENROUTER_API_KEY") and CORPUS.exists(),
                     "needs OPENROUTER_API_KEY and the corpus")
class GatedEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, OpenRouterProvider())
        cls.board = grade(QUESTIONS, pipe, k=5)

    def test_gates_hold(self):
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_citation_correctness_rose(self):
        self.assertGreater(self.board["quality"]["citation_correctness"], 0.0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run it.**
`python3 -m unittest evals.test_gated_eval -v`.
- Without a key: it SKIPS (expected in offline CI).
- With a key (after Task 0): it RUNS against the real model.

**If `test_gates_hold` fails** because the model bluffed on a code question (abstention recall < 100): this is the crux. Do NOT weaken the test. Harden, in this order, re-running after each: (a) sharpen the `INSTRUCTION` in `synth.py` (make the unknown path more emphatic; add a one-line example of choosing unknown); (b) if still bluffing, add an OPTIONAL gate rule in `gate.py` — require ≥1 citation whose `source` is `pr` or `issue` (rationale lives there, not in code) — gated behind a flag, with a new offline test in `test_gate.py` proving it; (c) if the free model simply can't hold the line, try another free model id via `OpenRouterProvider(model=...)` — "the eval harness picks the model" (CLAUDE.md). Record what you tried.

**Step 3: Add `gated` to the board.** In `evals/run.py`:
- change the `--pipeline` choices to `["stub", "retrieval", "gated"]`;
- in the pipeline-construction block, add a `gated` branch that builds `GatedPipeline(LexicalRetriever(load_chunks(CORPUS)), load_chunks(CORPUS), OpenRouterProvider())` with `name = "GatedPipeline"`. (Load the chunks once into a local variable and reuse.)
Read `run.py` first to match the exact existing strings before editing.

**Step 4: Run the board (with key) and the offline suite.**
- `python3 -m evals.run --pipeline gated` → record the full board. Expected: groundedness 100%, abstention recall 100%, **citation_correctness > 0%** (ideally rising toward 100% over the 6 answerable), abstention precision up from 40%. Status may still be RED only because answer_correctness is PENDING (manual) — that is fine.
- `python3 -m unittest discover -t . -s evals -p "test_*.py"` (no key) → all green, integration test SKIPPED.

**Step 5: Commit**
```bash
git add evals/run.py evals/test_gated_eval.py evals/synth.py evals/gate.py
git commit -m "$(printf 'Wire GatedPipeline into the board; citation correctness rises with gates held\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 6 — Docs + indexes

**Files:** Modify `CLAUDE.md` (Commands section — add `--pipeline gated` and the `OPENROUTER_API_KEY` note), regenerate `general_index.md` + `detailed_index.md` for the new modules (`provider.py`, `synth.py`, `gate.py`, and the new `GatedPipeline`).

**Step: Commit**
```bash
git add CLAUDE.md general_index.md detailed_index.md
git commit -m "$(printf 'Document the gated pipeline; regenerate indexes\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Brick 2 — Definition of done
- With `OPENROUTER_API_KEY` set: `python3 -m evals.run --pipeline gated` shows **groundedness 100%, abstention recall 100%, citation_correctness > 0%** (rising), abstention precision improved from 40%.
- Offline: `python3 -m unittest discover -t . -s evals -p "test_*.py"` all green (the network test self-skips); the gate's conscience tests in `test_gate.py` pass.
- The gate is deterministic and auditable; no test, grader, or labelled-set assertion was weakened; `grader.py` and `phase1_questions.json` are unchanged.
- `answer_correctness` remains `PENDING` (that's Brick 4, the judge — out of scope here).

## What remains after this brick (Phase 1)
- Brick 4 — answer-correctness grading (judge-later).
- Brick 5 — minimal web demo.
- Brick 6 — the recordable demo (the honest "I don't know" hero shot).
(Brick 3 — embeddings — is cancelled: lexical retrieval already gives recall@k 100%.)
