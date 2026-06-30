# Brick 3 — Embeddings + semantic retrieval (paraphrase robustness) — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Per [docs/WORKFLOWS.md](../WORKFLOWS.md), each task is red→green: a failing eval/test first, then the smallest code that turns it green. **Never weaken a test, the grader, the labelled set, or the honesty gates to pass.** Every commit appends `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Work in an isolated worktree per [CLAUDE.md](../../CLAUDE.md).
>
> **STATUS: prepared, NOT yet approved to execute.** Brick 3 was deferred in Phase 1 because lexical recall@k reads 100% on the labelled set. **Task 0 (a dependency decision) must be approved by Alankrit before any code or install.** Do not begin until then.

**Goal:** Make retrieval robust to *vocabulary mismatch* — when a user asks in their own words instead of the PR's words — by adding local semantic embeddings fused with the existing BM25 (hybrid retrieval), proven by a new paraphrase probe set, **without regressing the original labelled set (recall@k stays 100%) and without touching the two deterministic honesty gates.**

## Why this brick exists now (the evidence that overturns the cancellation)

Measured 2026-06-28 against the committed corpus, `LexicalRetriever`, k=5:

| Gold PR | Original question | Low-overlap paraphrase |
|---|---|---|
| pr:1435 | gold @2 | **gold not in top-5** |
| pr:1442 | gold @1 | **gold not in top-5** |
| pr:1482 | gold @1 | **gold not in top-5** |
| pr:1481 | gold @4 | **gold not in top-5** |

BM25 only looked perfect because the 6 labelled questions reuse the gold PRs' vocabulary. Reworded with synonyms (what real users do), lexical recall collapses. **This is the gap embeddings close.** It is a genuine, reproducible failing eval — not a speculative optimization.

**Architecture:** `embed every corpus chunk once (committed artifact) → at query time embed the question → score chunks by cosine similarity → fuse the dense ranking with the BM25 ranking via Reciprocal Rank Fusion (RRF) → HybridRetriever returns refs best-first.` Hybrid (not pure-dense) so we *gain* paraphrase robustness without *losing* the exact-match cases BM25 already nails. The embedder sits behind a one-method `Embedder` abstraction (mirrors `Provider`), so the unit suite runs offline with a deterministic test-double embedder; the real model is exercised only by a skippable test and a one-time embed tool.

---

## Task 0 — Prerequisite: the dependency decision (HUMAN; blocks everything)

Embeddings are the first capability the stdlib cannot provide. Per CLAUDE.md ("Don't add dependencies without asking"; "local open embeddings"; "never train on customer code; rent the LLM, own the pipeline"), this needs Alankrit's explicit sign-off **before install**.

**Decision A — embedding model (local, open):**
- **Recommended: `model2vec`** — distilled *static* embeddings. Pure-numpy inference, no PyTorch, tiny (~30MB), fast, fully local. Lowest dependency weight; good enough to beat lexical on paraphrase.
- Alt: `fastembed` (ONNX, BGE-small) — better quality, heavier (onnxruntime), still no torch.
- Avoid: `sentence-transformers` (drags in torch — large, slow install) unless quality demands it.

**Decision B — vector store:** **none.** ~300 chunks → brute-force cosine over a single NumPy matrix is instant. No FAISS, no vector DB. (NumPy enters as a dependency regardless of Decision A.)

**Decision C — privacy posture:** embeddings run **locally**; chunk text never leaves the machine. Consistent with the trust-boundary rule. (Public repo here, but we hold the product line.)

**New dependencies introduced (pending approval):** the chosen embedding lib **+ `numpy`**. Nothing else.

Until A/B/C are approved, stop. Tasks 1 and (the test-double parts of) 2 & 4 are dependency-free and could be staged, but the brick is not "done" without the real model.

---

## Where we are (do not re-derive)

- Bricks 0–2, 4 are merged to `main`. Board (`--pipeline gated`, key set): both gates 100%, retrieval recall@k 100% **on the labelled set**, citation correctness ~50%, answer correctness a number. Offline suite green (network/judge tests self-skip).
- Contracts:
  - `evals/corpus.py` — `Chunk(ref, source, text)`, `load_chunks`.
  - `evals/retriever.py` — `LexicalRetriever(chunks).search(query, k) -> List[str]` (refs, best-first), plus `tokenize`. **Do not modify; HybridRetriever wraps it.**
  - `evals/pipeline.py` — `GatedPipeline(retriever, chunks, provider, …)` takes *any* retriever exposing `.search(query, k)`.
  - `evals/grader.py`, `evals/phase1_questions.json` — unchanged by this brick except the probe set is a **separate new file**.

## Scope

In scope: the paraphrase probe set, the `Embedder` abstraction + test double, a one-time embed tool + committed embeddings artifact, `SemanticRetriever` + `HybridRetriever`, the eval proving the gap closes, and an opt-in board wiring. Out of scope: changing the writer, the gate, the judge, or the labelled set; any vector database; replacing BM25 (we fuse, not replace).

---

### Task 1 — Paraphrase probe set + lock the lexical gap (data; dependency-free)

**Files:** Create `evals/phase1_probes.json` (data), `evals/test_lexical_gap.py`.

The probe set is **labels** (Alankrit verifies): for each of the 6 answerable questions, a reworded version with deliberately low lexical overlap with the gold PR, same `gold_citations`. Example (q01 → pr:1435): *"Why build a separate handler for the newer endpoint rather than extending the current one?"*

**Step 1 (RED→stays-true):** `test_lexical_gap.py` builds `LexicalRetriever` over the committed corpus and asserts its recall@5 **on the probe set is at or below a ceiling** (e.g. ≤ 50%) — documenting and locking the gap. (Skips if corpus absent.) This test passes immediately because the gap is real, and *must keep passing* — if a future change makes BM25 alone good on paraphrases, embeddings aren't needed and the brick should be revisited.

**Step 2:** Write the 6 paraphrases; verify with a quick BM25 run that each gold ref is indeed outside top-5 (so the gap is honest, not cherry-picked).

**Step 3: Commit**
```bash
git add evals/phase1_probes.json evals/test_lexical_gap.py
git commit -m "$(printf 'Add paraphrase probe set; lock the lexical vocabulary-mismatch gap\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 2 — Embedder abstraction + deterministic test double (offline)

**Files:** Create `evals/embedder.py`, `evals/test_embedder.py`.

- `class Embedder` — interface: `embed(texts: List[str]) -> List[List[float]]`.
- `class HashingEmbedder(Embedder)` — **test double**, no model/network: deterministic bag-of-tokens hashed into a fixed-width L2-normalized vector. Lets `SemanticRetriever` be unit-tested offline (it won't prove paraphrase quality — that's the real model's job in Task 5 — but it proves the *retrieval mechanics*: cosine ranking, top-k, determinism).
- `class LocalEmbedder(Embedder)` — wraps the approved model (Decision A); imported lazily so importing the module never requires the dep.

**Tests** (offline, double only): same text → identical vector; different text → different vector; vectors are unit-norm; batch length matches input.

**Commit:** `Add Embedder abstraction (interface + offline hashing double)`.

---

### Task 3 — One-time embed tool + committed embeddings artifact (needs the model)

**Files:** Create `evals/embed.py` (tool, like `ingest.py`), generate `evals/corpus/embeddings.jsonl` (or `.npy` + a ref index).

Mirrors the corpus pattern: embeddings are a **committed, reproducible artifact** so unit tests and the board run offline against fixed vectors. `embed.py` loads the corpus, runs `LocalEmbedder`, writes one vector per chunk keyed by `ref`. Run once: `python3 -m evals.embed`. Verify the artifact has one vector per chunk and matching dimensionality.

**Commit:** `Add embed tool and committed corpus embeddings artifact`.

---

### Task 4 — SemanticRetriever + HybridRetriever (offline-tested with the double)

**Files:** Create `evals/semantic.py`, `evals/test_semantic.py`.

- `class SemanticRetriever` — holds chunk refs + a vector matrix (loaded from the artifact, or embedded live via an injected `Embedder`); `search(query, k)` embeds the query and returns top-k refs by cosine. NumPy brute force.
- `class HybridRetriever` — composes `LexicalRetriever` + `SemanticRetriever`; `search(query, k)` fuses the two rankings with **RRF** (`score = Σ 1/(c + rank_i)`, c≈60), returns top-k. Exposes the same `.search(query, k)` signature so `GatedPipeline` accepts it unchanged.

**Tests** (offline, `HashingEmbedder` + tiny synthetic corpus): semantic ranks the cosine-closest chunk first; hybrid returns a chunk that *only* one of the two retrievers surfaces (proves fusion); at-most-k; deterministic ties.

**Commit:** `Add SemanticRetriever and HybridRetriever (RRF fusion)`.

---

### Task 5 — Prove the gap closes (real model; skippable) + opt-in board wiring

**Files:** Create `evals/test_semantic_eval.py`; modify `evals/run.py` (add `--retriever {lexical,hybrid}`, default `lexical`).

**The proof** (`test_semantic_eval.py`, skips without the model/artifact): build `HybridRetriever` over the committed corpus + artifact and assert, at k=5:
1. recall **on the paraphrase probe set rises to target** (e.g. ≥ 80%, up from ≤ 50%) — the green;
2. recall **on the original labelled set stays 100%** — no regression;
3. with `HybridRetriever` wired into `GatedPipeline`, **both honesty gates stay 100%** — the gate is retriever-agnostic, but we prove it.

**If (1) fails:** the chosen model is too weak — revisit Decision A (try `fastembed`), never weaken the target. **If (2) regresses:** raise the BM25 weight / lower `c` in RRF; never drop the original-set assertion.

Wire `--retriever hybrid` into the board so `python3 -m evals.run --pipeline gated --retriever hybrid` is runnable. Default stays `lexical` so the offline board is unchanged.

**Commit:** `Prove hybrid retrieval closes the paraphrase gap with the original set and gates held`.

---

### Task 6 — Docs + indexes

Update `CLAUDE.md` (stack note: embeddings now in; new commands; the dependency), regenerate `general_index.md` + `detailed_index.md` for `embedder.py`, `embed.py`, `semantic.py`, the new tests, and the probe set.

**Commit:** `Document hybrid retrieval and embeddings; regenerate indexes`.

---

## Brick 3 — Definition of done
- `python3 -m evals.run --pipeline gated --retriever hybrid` (model + key set): paraphrase-probe recall@5 **≥ target**, original-set recall@5 **100%**, both gates **100%**.
- Offline suite green; `test_lexical_gap.py` still documents the gap; real-model/embedding tests self-skip without the artifact.
- No new vector DB; the only new deps are the approved embedding lib + numpy; the gate, writer, judge, grader, and labelled set are unchanged.

## Honest caveats (decide before executing)
- **Is the paraphrase gap worth the dependency now?** The product will need it (real users paraphrase), but Phase 1's *current demo* passes on lexical. Reasonable to (a) execute now for robustness, or (b) keep this plan on the shelf and ship the demo (Brick 5) first, executing Brick 3 when a real corpus or harder questions force it. **This plan is ready for either choice.**
- The probe set is new ground truth — its quality gates the whole brick; Alankrit verifies the 6 paraphrases (Task 1).
