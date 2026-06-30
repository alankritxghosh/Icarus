# Brick 4 — Answer-correctness grading (the judge-later half) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Each task is red→green: a failing test first, then the smallest code that turns it green. **Never weaken a test, the grader, or the honesty gates to pass.** Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work in an isolated worktree per [CLAUDE.md](../../CLAUDE.md).

**Goal:** Make `answer_correctness` stop being `PENDING` and become a real, tracked number on the 6 answerable questions — by judging each emitted prose answer against a recorded reference with an LLM-judge-with-reference — **without ever touching the two deterministic honesty gates** (groundedness, abstention recall), which stay auditable and pinned at 100%.

**The non-negotiable, restated for this brick:** `answer_correctness` is the *fuzzy, judge-later* quality dial — explicitly NOT a gate (see [docs/EVALUATION.md], grader.py docstring). It is allowed to use an LLM. The honesty gates are a separate, deterministic mechanism and this brick does not change them. A wrong-but-confident answer is caught by the *judge* (a quality miss); a *bluff* (ungrounded citation / failure to abstain) is still caught deterministically by the gates. We never let the judge become the honesty mechanism.

**Architecture:** `add reference answers to the labelled set → build a judge prompt (question + reference + candidate) → a Judge calls the rented Provider → a deterministic parser turns the reply into correct/incorrect, failing safe to "incorrect" → the grader computes answer_correctness over answered answerable questions only, scoring abstentions and wrong answers as not-correct.` The judge reuses the existing `Provider` abstraction, so the unit suite runs offline with `StaticProvider`; the real judge runs only in a skippable network test and the board.

**Tech Stack:** Python 3 stdlib only — **no new dependency**. Reuses `evals/provider.py` (`OpenRouterProvider`). Judge model configurable; default a capable free model (see Decision 2). API key from `OPENROUTER_API_KEY` — never hardcoded, never committed.

---

## Decisions needed from Alankrit before/while executing (call these out at review)

1. **Reference answers are ground-truth labels — you must verify them.** The 6 answerable questions have no reference prose today, only `gold_citations[].why` rationales. Task 1 distills a one–two sentence `reference_answer` for each from those `why` fields. Because these become the yardstick every future answer is judged against, **Alankrit signs off on the 6 reference answers** before Task 5 runs. (I draft; you approve.)
2. **Judge model vs. writer model — DECIDED.** To avoid self-grading bias the judge uses a *different* free model than the writer: **`poolside/laguna-m.1:free`** (resolves to `laguna-m.1-20260312:free`). Verified live 2026-06-28: it returns clean JSON `{"verdict": "correct"}` for a matching candidate and `{"verdict": "incorrect"}` for a wrong one (discriminates, not a yes-machine). Writer stays `cohere/north-mini-code:free`. Cheap to change later — "the eval harness picks the model" (CLAUDE.md).
3. **Scoring rule (locked unless you object).** `answer_correctness` = (answered answerable questions whose answer the judge marks correct) ÷ (all 6 answerable). An abstention or a wrong answer scores 0. So the dial can never outrun honest, correct answering, and never rewards bluffing.

---

## Where we are (do not re-derive)

- Bricks 0–2 are merged to `main`. Board (`python3 -m evals.run --pipeline gated`, key set): groundedness 100%, abstention recall 100%, retrieval recall@k 100%, citation correctness 33.3%, **answer correctness `PENDING (manual / judge-later)`**, status RED. Offline suite: 37 tests, 2 skipped (network).
- Existing contracts:
  - `evals/provider.py` — `Provider.complete(prompt) -> str`; `StaticProvider` (offline double), `OpenRouterProvider(model=…)`.
  - `evals/pipeline.py` — `Result(verdict, answer, citations, retrieved)`, `GatedPipeline`.
  - `evals/grader.py` — `grade(questions, pipeline, k)`; returns `"answer_correctness": "PENDING (manual / judge-later)"`. **This brick extends it additively (new optional `judge=None` param); existing behavior and `test_grader.py` must stay green.**
  - `evals/phase1_questions.json` — 10 questions; the 6 answerable carry `gold_citations` with a `why`, but no `reference_answer`. **This brick adds `reference_answer` to the 6 answerable; it changes nothing else and removes nothing.**

## Scope of this plan

In scope: reference answers in the labelled set, the judge prompt builder, the deterministic verdict parser + `Judge`, the additive grader change, board/run wiring, and the eval that proves the dial moves. Out of scope (later bricks): the web demo (Brick 5), the recordable demo (Brick 6). Embeddings (Brick 3) remain cancelled — lexical recall@k is 100%.

---

### Task 0 — Prerequisite (human)

`OPENROUTER_API_KEY` exported for Task 5 / the board (Task 1–4 need no network). Verify (no secret printed): `python3 -c "import os;print('key set:', bool(os.environ.get('OPENROUTER_API_KEY')))"` → `key set: True`. Tasks 1–4 proceed immediately; Task 5 self-skips without the key.

---

### Task 1 — Reference answers as labels (data; verified by a test)

**Files:**
- Modify: `evals/phase1_questions.json` (ADD a `reference_answer` string to each of the 6 answerable questions; touch nothing else)
- Create: `evals/test_reference_answers.py`

**Step 1: Write the failing test** — `evals/test_reference_answers.py`:

```python
# evals/test_reference_answers.py
"""Every answerable question must carry a non-empty reference_answer (the
ground-truth the judge scores against). Unanswerable questions must NOT — there
is no correct answer to one whose reason was never recorded."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]


class ReferenceAnswerTests(unittest.TestCase):
    def test_answerable_have_nonempty_reference(self):
        for q in QUESTIONS:
            if q["label"] == "answerable":
                self.assertIn("reference_answer", q, q["id"])
                self.assertTrue(q["reference_answer"].strip(), q["id"])

    def test_unanswerable_have_no_reference(self):
        for q in QUESTIONS:
            if q["label"] == "unanswerable":
                self.assertNotIn("reference_answer", q, q["id"])


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `python3 -m unittest evals.test_reference_answers -v` → fails (no `reference_answer` yet).

**Step 3: Add the labels.** For each of `q01`–`q06`, add a `reference_answer` distilled from that question's `gold_citations[].why` (one–two sentences, the recorded reason — not invented). **Draft, then have Alankrit verify before Task 5.**

**Step 4: Run, confirm it PASSES.**

**Step 5: Commit**
```bash
git add evals/phase1_questions.json evals/test_reference_answers.py
git commit -m "$(printf 'Add reference answers to the 6 answerable questions (judge ground truth)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 2 — The judge prompt builder (pure function)

**Files:**
- Create: `evals/judge.py`
- Create: `evals/test_judge_prompt.py`

**Step 1: Write the failing test** — `evals/test_judge_prompt.py`:

```python
# evals/test_judge_prompt.py
import unittest

from .judge import build_judge_prompt


class BuildJudgePromptTests(unittest.TestCase):
    def setUp(self):
        self.prompt = build_judge_prompt(
            question="Why a new model class?",
            reference="Because other plugins import the old class, so it had to be left alone.",
            candidate="They added a new class to avoid breaking plugins that import the old one.",
        )

    def test_includes_all_three_inputs(self):
        self.assertIn("Why a new model class?", self.prompt)
        self.assertIn("other plugins import", self.prompt)
        self.assertIn("avoid breaking plugins", self.prompt)

    def test_asks_for_a_verdict_token(self):
        self.assertIn("correct", self.prompt.lower())

    def test_truncates_long_candidate(self):
        self.assertLess(len(build_judge_prompt("q", "ref", "x" * 5000)), 4000)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `No module named 'evals.judge'`.

**Step 3: Implement** — start `evals/judge.py` (the parser comes in Task 3):

```python
# evals/judge.py
"""LLM-judge-with-reference for answer correctness (the fuzzy, judge-later
quality dial — NOT an honesty gate). Builds a judge prompt and deterministically
parses the reply into correct/incorrect, failing safe to incorrect. Reuses the
Provider abstraction so the unit suite runs offline with StaticProvider.
"""

JUDGE_INSTRUCTION = (
    "You are grading whether a CANDIDATE answer matches the REFERENCE answer for "
    "a question about a software project. Judge only whether the candidate states "
    "the same core reason/fact as the reference. Ignore wording, length, and extra "
    "true detail. Do not reward a confident answer that contradicts or omits the "
    "reference's core reason.\n"
    'Reply with JSON and nothing else: {"verdict": "correct"} or '
    '{"verdict": "incorrect"}.'
)

_MAX_CANDIDATE_CHARS = 1500


def build_judge_prompt(question: str, reference: str, candidate: str) -> str:
    cand = candidate.strip()
    if len(cand) > _MAX_CANDIDATE_CHARS:
        cand = cand[:_MAX_CANDIDATE_CHARS] + " …"
    return (
        f"{JUDGE_INSTRUCTION}\n\nQUESTION: {question}\n\n"
        f"REFERENCE: {reference}\n\nCANDIDATE: {cand}"
    )
```

**Step 4: Run, confirm it PASSES.**

**Step 5: Commit**
```bash
git add evals/judge.py evals/test_judge_prompt.py
git commit -m "$(printf 'Add answer-correctness judge prompt builder\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 3 — The deterministic verdict parser + Judge (offline)

**Files:**
- Modify: `evals/judge.py` (append `parse_verdict` + `Judge`)
- Create: `evals/test_judge.py`

**Step 1: Write the failing test** — `evals/test_judge.py`:

```python
# evals/test_judge.py
"""The judge parses a reply into a boolean and fails safe to incorrect when the
reply is ambiguous. The Judge wires a Provider through build_judge_prompt."""

import json
import unittest

from .provider import StaticProvider
from .judge import parse_verdict, Judge


class ParseVerdictTests(unittest.TestCase):
    def test_correct(self):
        self.assertTrue(parse_verdict(json.dumps({"verdict": "correct"})))

    def test_incorrect(self):
        self.assertFalse(parse_verdict(json.dumps({"verdict": "incorrect"})))

    def test_embedded_json(self):
        self.assertTrue(parse_verdict('sure: {"verdict": "correct"} ok'))

    def test_unparseable_fails_safe_to_incorrect(self):
        self.assertFalse(parse_verdict("the model rambled"))

    def test_unknown_value_fails_safe_to_incorrect(self):
        self.assertFalse(parse_verdict(json.dumps({"verdict": "maybe"})))


class JudgeTests(unittest.TestCase):
    def test_judge_returns_bool_from_provider(self):
        j = Judge(StaticProvider(json.dumps({"verdict": "correct"})))
        self.assertTrue(j.is_correct("q", "ref", "cand"))

    def test_judge_fails_safe_when_provider_rambles(self):
        j = Judge(StaticProvider("no json here"))
        self.assertFalse(j.is_correct("q", "ref", "cand"))


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `cannot import name 'parse_verdict'`.

**Step 3: Implement** — append to `evals/judge.py`:

```python
import json
import re

_JSON = re.compile(r"\{.*\}", re.DOTALL)


def parse_verdict(raw: str) -> bool:
    """True only if the reply parses as JSON with verdict 'correct'; else False.
    Fails safe to incorrect (an unparseable judge never inflates the score)."""
    m = _JSON.search(raw or "")
    if not m:
        return False
    try:
        data = json.loads(m.group(0))
    except (ValueError, TypeError):
        return False
    return isinstance(data, dict) and data.get("verdict") == "correct"


class Judge:
    """Wraps a Provider into an answer-correctness judge."""

    def __init__(self, provider):
        self._provider = provider

    def is_correct(self, question: str, reference: str, candidate: str) -> bool:
        prompt = build_judge_prompt(question, reference, candidate)
        return parse_verdict(self._provider.complete(prompt))
```

(Move the `import json`/`import re` to the top of the file when appending, to keep imports tidy.)

**Step 4: Run, confirm it PASSES.**

**Step 5: Commit**
```bash
git add evals/judge.py evals/test_judge.py
git commit -m "$(printf 'Add deterministic verdict parser and Judge (fails safe to incorrect)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 4 — Grader computes answer_correctness when a judge is supplied (additive)

**Files:**
- Modify: `evals/grader.py` (add optional `judge=None` param; compute the dial only when given; default keeps the PENDING string)
- Create: `evals/test_answer_correctness.py`

**Critical constraint:** existing `test_grader.py` must stay green. With `judge=None` (the default), `grade()` behaves exactly as today, including `answer_correctness == "PENDING (manual / judge-later)"`. The gates are not touched.

**Step 1: Write the failing test** — `evals/test_answer_correctness.py`:

```python
# evals/test_answer_correctness.py
"""With a judge supplied, answer_correctness is a real number over the answerable
questions; without one it stays PENDING. A judge never affects the gates."""

import unittest

from .pipeline import Result, Pipeline
from .grader import grade


class _FixedPipeline(Pipeline):
    def __init__(self, by_q):
        self._by_q = by_q

    def answer(self, question):
        return self._by_q[question]


class _StubJudge:
    def __init__(self, correct: bool):
        self._correct = correct

    def is_correct(self, question, reference, candidate):
        return self._correct


QUESTIONS = [
    {"id": "a1", "label": "answerable", "question": "Q1", "reference_answer": "R1",
     "gold_citations": [{"source": "pr", "ref": "1"}]},
    {"id": "u1", "label": "unanswerable", "question": "Q2"},
]


def _answered():
    return _FixedPipeline({
        "Q1": Result(verdict="answer", answer="grounded", citations=["pr:1"], retrieved=["pr:1"]),
        "Q2": Result(verdict="unknown", retrieved=["code:x.py"]),
    })


class AnswerCorrectnessTests(unittest.TestCase):
    def test_pending_without_judge(self):
        board = grade(QUESTIONS, _answered(), k=5)
        self.assertEqual(board["answer_correctness"], "PENDING (manual / judge-later)")

    def test_scored_with_judge(self):
        board = grade(QUESTIONS, _answered(), k=5, judge=_StubJudge(True))
        self.assertEqual(board["answer_correctness"], 100.0)

    def test_wrong_answer_scores_zero(self):
        board = grade(QUESTIONS, _answered(), k=5, judge=_StubJudge(False))
        self.assertEqual(board["answer_correctness"], 0.0)

    def test_abstention_is_not_correct(self):
        # pipeline abstains on the answerable question -> 0/1 even with a yes-judge
        pipe = _FixedPipeline({
            "Q1": Result(verdict="unknown", retrieved=["pr:1"]),
            "Q2": Result(verdict="unknown", retrieved=[]),
        })
        board = grade(QUESTIONS, pipe, k=5, judge=_StubJudge(True))
        self.assertEqual(board["answer_correctness"], 0.0)

    def test_judge_does_not_break_gates(self):
        board = grade(QUESTIONS, _answered(), k=5, judge=_StubJudge(False))
        self.assertTrue(board["gates_ok"])
        self.assertEqual(board["gates"]["groundedness"], 100.0)
        self.assertEqual(board["gates"]["abstention_recall"], 100.0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run, confirm it FAILS** — `grade()` has no `judge` kwarg.

**Step 3: Implement** in `evals/grader.py`:
- Change the signature to `grade(questions, pipeline, k=5, judge=None)`.
- Reuse the already-computed `results` map. After the quality dials, compute:

```python
    if judge is None:
        answer_correctness = "PENDING (manual / judge-later)"
    else:
        answer_correctness = _pct(
            [
                results[q["id"]].verdict == "answer"
                and judge.is_correct(q["question"], q["reference_answer"], results[q["id"]].answer)
                for q in answerable
            ],
            empty_value=None,
        )
```

- Put `answer_correctness` into the returned dict in place of the hardcoded PENDING string. **Do not change `gates`, `gates_ok`, `quality_met`, or `status` logic** (status still keys off gates + retrieval/citation; answer correctness remains advisory).

**Step 4: Run, confirm it PASSES**, then the full offline suite (`test_grader.py` included) → all green.

**Step 5: Commit**
```bash
git add evals/grader.py evals/test_answer_correctness.py
git commit -m "$(printf 'Grade answer_correctness when a judge is supplied (additive, gates untouched)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 5 — Prove it on the real model (board + skippable integration test)

**Files:**
- Modify: `evals/run.py` (build a `Judge` and pass it to `grade` when the key is present; print the number)
- Create: `evals/test_answer_correctness_eval.py`

**Step 1: Add the integration test** — `evals/test_answer_correctness_eval.py` (self-skips without a key):

```python
# evals/test_answer_correctness_eval.py
"""Real-model proof: with the judge, answer_correctness becomes a number > 0 on
the answerable questions while BOTH honesty gates stay at 100%. Skipped without
OPENROUTER_API_KEY or the corpus."""

import json
import os
import unittest
from pathlib import Path

from .corpus import load_chunks
from .grader import grade
from .retriever import LexicalRetriever
from .provider import OpenRouterProvider
from .pipeline import GatedPipeline
from .judge import Judge

ROOT = Path(__file__).resolve().parent
QUESTIONS = json.loads((ROOT / "phase1_questions.json").read_text())["questions"]
CORPUS = ROOT / "corpus" / "chunks.jsonl"


@unittest.skipUnless(os.environ.get("OPENROUTER_API_KEY") and CORPUS.exists(),
                     "needs OPENROUTER_API_KEY and the corpus")
class AnswerCorrectnessEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chunks = load_chunks(CORPUS)
        pipe = GatedPipeline(LexicalRetriever(chunks), chunks, OpenRouterProvider())
        judge = Judge(OpenRouterProvider(model="poolside/laguna-m.1:free"))  # judge != writer
        cls.board = grade(QUESTIONS, pipe, k=5, judge=judge)

    def test_gates_hold(self):
        self.assertEqual(self.board["gates"]["groundedness"], 100.0)
        self.assertEqual(self.board["gates"]["abstention_recall"], 100.0)

    def test_answer_correctness_is_a_number_above_zero(self):
        self.assertIsInstance(self.board["answer_correctness"], float)
        self.assertGreater(self.board["answer_correctness"], 0.0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run it.** Without a key it SKIPS; with a key it RUNS. **If `answer_correctness` is surprisingly 0** while citation correctness > 0: inspect whether the judge is too strict or the reference answers are too narrow — fix the prompt or tighten the references (with Alankrit), never weaken the test.

**Step 3: Wire run.py.** Read `run.py` first. When `OPENROUTER_API_KEY` is set, construct `Judge(OpenRouterProvider(model="poolside/laguna-m.1:free"))` and pass `judge=judge` to `grade`; otherwise pass `judge=None` (board prints PENDING offline, unchanged). The existing `answer_correctness` print line already renders either a number or the PENDING string — confirm `_fmt` handles a float (it does) and the string is printed as-is.

**Step 4: Run the board (key set) + offline suite.**
- `OPENROUTER_API_KEY=… python3 -m evals.run --pipeline gated` → record the board; expect gates 100/100, **answer correctness now a number**, citation correctness unchanged from Brick 2.
- `python3 -m unittest discover -t . -s evals -p "test_*.py"` (no key) → all green, integration tests skipped.

**Step 5: Commit**
```bash
git add evals/run.py evals/test_answer_correctness_eval.py
git commit -m "$(printf 'Wire the judge into the board; answer_correctness becomes a tracked number\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 6 — Docs + indexes

Modify `CLAUDE.md` (Commands — note the judge runs when the key is set and that answer_correctness is now tracked), regenerate `general_index.md` + `detailed_index.md` for `judge.py`, the new tests, the `reference_answer` field, and the new `grade(..., judge=None)` signature.

```bash
git add CLAUDE.md general_index.md detailed_index.md
git commit -m "$(printf 'Document the answer-correctness judge; regenerate indexes\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Brick 4 — Definition of done
- With the key set, `python3 -m evals.run --pipeline gated` shows `answer_correctness` as a **number** (not PENDING), with groundedness and abstention recall still **100%**, and citation correctness unchanged from Brick 2.
- Offline: `python3 -m unittest discover -t . -s evals -p "test_*.py"` all green (network tests self-skip); `test_grader.py` unchanged and passing.
- `answer_correctness` is a **quality dial only** — the deterministic honesty gates were not modified; the judge cannot turn a bluff green.
- The 6 reference answers are verified by Alankrit; no test, gate, or label was weakened.

## What remains after this brick (Phase 1)
- Brick 5 — minimal web demo (question → answer → citations).
- Brick 6 — the recordable demo (one cited answer + one honest "I don't know").
- (Brick 3 — embeddings — stays cancelled: lexical recall@k is 100%.)
