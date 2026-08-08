# Investigation engine — findings and plan (2026-08-08)

Icarus answers in one shot: retrieve → write → gate. This plan turns that into a
bounded, evidence-first **investigation loop** without replacing a single
component that works today.

Status: **all seven phases built**, then hardened under review (2026-08-08).

**Hardening pass — the honesty correction worth reading first.** `explicit` was
described, and rendered in the Mac UI, as "The repository states this". Marker
matching cannot prove that: evidence reading "changed because logging was noisy"
under a finding about database scalability trips the same markers as a matching
one. Per AGENTS.md, arbitrary semantic entailment is writer-reliant and cannot be
proven deterministically, so the CLASS was narrowed to describe the EVIDENCE
CITED ("Cites evidence that records a reason"), the grader metric was renamed
`support_honesty` -> `explicit_cites_rationale` with its scope documented, and
`SUPPORT_HEADLINES` now pins wording that no surface may upgrade. What remains
proven is unchanged: the citation boundary and the explicit deterministic
guards. A SECOND review pass (Codex, on the hardening commit) found four more, each
reproduced first: the SYNTHESIS PROMPT still instructed "explicit: the
repository states this. Say it plainly." -- the labels had been corrected while
the instruction that writes the actual sentence still demanded the entailment,
so the fix now renders findings through `SUPPORT_HEADLINES` itself and is tested
against the complete generated prompt; `forget()` deleted a conversation without
bumping the generation, so an in-flight investigation could resurrect a subject
after disconnect; the evidence-character cap was charged AFTER a whole parallel
round was retained (2,000 chars kept against a 1-char allowance); and a commit
SHA was treated as a corpus identity even though ingest includes mutable
discussion, while provenance and the pipeline were read separately and could be
torn by a concurrent refresh -- now one atomic `Library.snapshot()` per request,
keyed by `(repo, commit, corpus-content fingerprint)` so eviction or process
restart cannot make two different ingests collide.

A final adversarial pass (2026-08-09) closed the remaining cross-boundary gaps:
the reader now retains only the gate's canonical citations; malformed planner
containers fail closed; a subjectless retrieval can feed later trace steps;
budget clipping drops the lowest-ranked tail; overlapping follow-ups are
latest-started-wins; live-only evidence is not carried as immutable conversation
state; exact import windows are preserved as relationship proof; request
snapshots freeze the indexing caveat; and the Mac clears investigation text on
repo switch/sign-out while rendering the server's actual abstention reason.

Seven other defects were fixed in the same pass -- carried findings
surviving a corpus refresh, `refers_back` inheriting a subject for "the
project"/"the protocol", unbounded planner arguments reaching the retriever,
`/investigate` billing ~10x its rate-limit weight, a stale investigation
overwriting a fresh one, `conclude()` exceeding the writer budget, and every
server refusal being reported to a Mac user as a connection problem. (`evals/entities.py`, `investigation.py`,
`probes.py`, `investigator.py`, + the three prompt builders in `synth.py`).
 Read §A before §E.

Two findings from building it, both from running against the real corpus rather
than fixtures:

- **File relationships must target FILES, not chunks.** Fanning edges across a
  file's overlapping windows turned 30 real import edges into 56,056 emitted
  ones. See `entities.Edge`.
- **"Unsupported" is not "decided".** A run ended after ONE round reporting
  "every hypothesis decided" while a second hypothesis had zero evidence and two
  queued steps that had never run. `should_stop` now treats a hypothesis nothing
  was gathered for as still open. This is the premature-stop failure mode this
  design exists to avoid, and it took a real run to see it.

`compare()` now has two routes, best first: the pull request's own diff
(`ingest.fetch_pr_diff`, one request, no dependence on how the repository
merges), falling back to reading its commits live. The second route alone was
not enough — it depends on the `(#400)` squash-merge subject convention and
finds nothing at all where that convention is absent.

The committed corpus was deliberately NOT re-ingested. The `Linked issues:` line
changes the text of any PR that closes an issue, which would move retrieval
scores and silently re-baseline the frozen Phase 1 board; the change applies to
every future ingest, and the entity index reads exact links where they exist and
falls back to `#N` mentions where they do not. Re-ingesting the board corpus is
a separate, deliberate decision.

---

## 0. What the repository actually does today (read, not assumed)

### 0.1 How Icarus retrieves

`demo/library.py::_build_retriever` builds
`NormalizingRetriever(HybridRetriever(LexicalRetriever, SemanticRetriever))` —
query normalization, then RRF fusion of BM25 and local fastembed cosine. That is
the *only* retrieval path in serving.

`evals/pipeline.py::GatedPipeline.answer` runs it once:

```
anchor lookup (exact "#N" / commit SHA)  ->  .search(question, recall_n=20)
     -> dedupe -> top writer_k=10 chunks -> build_prompt -> provider -> gate()
```

Two things already break the "pure retrieval" framing and matter enormously here:

- **Anchor lookup is already an exact-identifier primitive.** `_ISSUE_OR_PR_REF`
  / `_COMMIT_SHA` pull identifiers out of the question and resolve them against
  `self._by_ref`, falling back to `live_fetch` / `live_commit_fetch`. This is
  `inspect()` in everything but name.
- **Live fetch already reaches past the index.** `ingest.fetch_ref_detail`
  (one PR/issue + full discussion) and `ingest.fetch_commit_detail` (one commit
  + real per-file `patch` hunks) are bounded, on-demand, caller-token-scoped
  lookups. `compare()` has a real diff source already; it just isn't reachable
  from a PR number.

### 0.2 How repository entities are represented

There is **one** representation: `evals/corpus.Chunk(ref, source, text)`, one
JSONL line each. `ref` is the citation *and* the primary key. Sources in use:

| source | ref shape | built by | carries |
|---|---|---|---|
| `pr` | `pr:400` | `fetch_prs` | title, state/author/labels, body, **`Files changed (N): path (+a/-d) · …`** (first 30), comments, review bodies |
| `issue` | `issue:372` | `fetch_issues` | title, state/author/labels, body, comments |
| `commit` | `commit:<sha>` | `fetch_commits` | subject + body message only (**no file list, no diff** — deliberate, measured 27s vs 2s) |
| `code`/`doc`/`config` | `code:path/file.py#L1-L300` | `fetch_code` | source text, line-windowed or AST-chunked |
| `index` | `index:overview` | `index_facts` | file/language counts |

There is no entity table, no graph store, no per-entity record. **An entity is a
prefix on a ref string.** That is a feature: every entity is already citable and
already linkable (`demo/links.ref_to_url`).

### 0.3 What relationships exist

Almost none are *stored*. What exists:

| relationship | where it lives today | status |
|---|---|---|
| PR → changed files | prose inside the `pr:` chunk text | **derivable by regex**, capped at 30 files (`_MAX_FILES_LISTED`) |
| PR → linked issues | `closingIssuesReferences` is fetched at `ingest.py:675` and **thrown away** after choosing which issues to fetch; `#N` body mentions survive inside the chunk text | derivable-but-lossy; a one-line ingest change makes it exact |
| file → file | `demo/structure.py::build_structure` — real import edges, Python/JS/Go, language-specific resolvers, 199 sampled edges 0 wrong | **already built and trustworthy** |
| file → lines | `evals/corpus.chunk_covers_lines` | already built |
| commit → PR | commit subject `(#400)` squash convention, inside chunk text | derivable, convention-dependent |
| PR → commits, PR → diff hunks, function → callers | **nothing** | missing |

### 0.4 How citations are produced

`evals/gate.py::gate(raw, retrieved, question, evidence)` — deterministic, four
guards: (a) groundedness via `_resolve` (tolerant of reformatting, strict on
path/line containment and source prefix), (b) why→what rationale guard, (c)
entity-presence guard, (d) self-disclaimed answer. Failure is always
answer → unknown, with an `abstention_reason`. `demo/payload.build_payload` maps
grounded refs to URLs + excerpts.

**The gate already is `verify()` for a single claim** — it takes prose, its
citations, and the evidence, and decides whether the claim is supported. It just
runs once over a whole answer instead of per claim.

### 0.5 How conversational context is maintained

**It isn't.** `POST /ask` (`demo/server.py:770`) is stateless: question in,
payload out. `demo/ledger.py` records question/verdict/citations against the
*repo with no identity*, deliberately. `demo/visits.py` stores four facts and is
forbidden from touching questions. `AskHistory.swift` is client-side display.
Nothing anywhere resolves "it".

### 0.6 Where the current architecture blocks investigation

1. `_answer_from` is a **single** writer→gate call with no place to put an
   intermediate result. `Result` has no accumulation surface.
2. Evidence selection happens **once**, before the writer sees anything. Nothing
   can say "given what I just read, fetch that".
3. There is **no relationship traversal at answer time** — `structure.py` and
   `repo_map.py` are `/map`-only and never reach the writer.
4. `compare()` has no entry point: PR chunks carry file *names*, not hunks.
5. Confidence is binary (answer | unknown). There is no vocabulary for
   "inferred".
6. No conversation state, so "why did it change?" is a fresh, subject-less query.

### 0.7 What is already sufficient — do not rebuild

- Retrieval (hybrid + normalization). Untouched.
- `Chunk`/ref as the universal entity identity and citation. Untouched.
- `gate()`. Reused **per claim**, unchanged.
- `build_prompt` cite-or-abstain contract, selection marker, chunk budgets.
- `fetch_ref_detail` / `fetch_commit_detail` leak-safe token plumbing.
- `structure.py` import graph — becomes `trace(file → dependents)` verbatim.
- The trust interlock, rate limits, entitlement checks, per-user isolation.

### 0.8 Minimum viable architectural change

Three new pure modules and one loop, all **above** `GatedPipeline`, plus one new
ingest function and one endpoint:

```
evals/entities.py      derived relationship index (chunks in, edges out — pure)
evals/investigation.py state dataclasses + deterministic confidence classifier
evals/probes.py        the five primitives over (GatedPipeline, entity index)
evals/investigator.py  the bounded loop
ingest.fetch_pr_diff   the one genuinely missing evidence source
demo/investigations.py bounded per-(identity,repo) session store
POST /investigate      one endpoint, same payload shape + an evidence trail
```

`GatedPipeline.answer` and `.explain` are **not modified**. Every existing eval
number stays byte-identical, by construction.

---

## A. Architecture

```
POST /investigate {question}
        |
        v
  demo/investigations.py  ---- prior state for (identity, repo)?  ---> subject binding
        |                       (deterministic: last subject refs)
        v
+---------------------------- evals/investigator.py -------------------------+
|                                                                            |
|  1. FRAME        deterministic: named refs -> subject   |  LLM: objective   |
|                                                          |     + hypotheses |
|  2. PLAN         LLM proposes typed steps from a CLOSED vocabulary;         |
|                  deterministic validator drops anything not well-formed     |
|                                                                            |
|  3. RUN ROUND    ThreadPoolExecutor over independent steps  (I/O bound)     |
|                    retrieve() inspect() trace() compare()   -- evals/probes |
|                                                                            |
|  4. READ         LLM per step: which hypotheses does this evidence support  |
|                  or contradict, and what claim does it license? -> gate()   |
|                                                                            |
|  5. UPDATE       deterministic: claims, evidence refs, hypothesis tallies,  |
|                  contradictions, unknowns, dedupe, budget spend             |
|                                                                            |
|  6. STOP?        deterministic (see §C.4).  no -> back to 2 with the state  |
|                                                                            |
|  7. SYNTHESIZE   LLM writes the answer FROM THE CLAIMS ONLY; every claim    |
|                  re-verified by gate() individually before it ships         |
+----------------------------------------------------------------------------+
        |
        v
  payload: answer + claims[] each {text, support, confidence, citations[]}
           + unknowns[] + contradictions[] + trail[] (every step, in order)
```

Evidence flow — one direction, never re-entrant:

```
Chunk (ref, source, text)   <-- the only evidence unit, unchanged
   -> probe returns EvidenceRef(ref, via_step, source)
   -> Claim(text, citations=[ref...], support=..., confidence=...)
   -> gate() re-verifies claim vs the evidence dict it was drawn from
   -> Answer cites Claims; Claims cite refs; refs link to GitHub
```

Nothing enters the answer that did not pass through `gate()` twice — once when
read, once when synthesized. That is a **strengthening** of today's honesty
posture, not a relaxation.

### Component table

| component | change |
|---|---|
| `evals/retriever.py`, `library.py`, `trust.py`, `auth`, `registry` | untouched |
| `evals/gate.py` | untouched; called per claim |
| `evals/synth.py` | **add** three prompt builders; existing `build_prompt` untouched |
| `evals/pipeline.py` | **add** read-only accessors only (`chunk_for(ref)`); no logic change |
| `evals/ingest.py` | **add** `fetch_pr_diff` + persist `linked_issues` in PR chunk text |
| new: `entities.py`, `investigation.py`, `probes.py`, `investigator.py` | the engine |
| `demo/server.py` | **add** `/investigate` (shares `/ask`'s limiter + entitlement) |
| `demo/payload.py` | **add** `build_investigation_payload`; `build_payload` untouched |
| Mac app / extension | Phase 6, optional — `/ask` keeps working unchanged |

---

## B. Data model

Dataclasses, stdlib only, same conventions as `Result`/`Chunk`.

```python
# evals/investigation.py

SUPPORT_EXPLICIT   = "explicit"    # a pr/issue/doc/commit chunk states it
SUPPORT_STRONG     = "strong"      # >=2 independent refs imply it, none against
SUPPORT_WEAK       = "weak"        # 1 ref, or code-only evidence
SUPPORT_UNSUPPORTED = "unsupported"

@dataclass(frozen=True)
class EvidenceRef:
    ref: str            # "pr:400" — the SAME identity as a citation
    source: str         # pr | issue | commit | code | doc | config | diff
    via: str            # step id that surfaced it — the audit trail
    states_reason: bool # gate._states_reason(text), computed once

@dataclass
class Claim:
    text: str
    citations: List[str]          # subset of the evidence the reader saw
    support: str                  # one of SUPPORT_*
    hypothesis_id: str = None     # None for a standalone fact
    verified: bool = False        # gate() said answer, not unknown

@dataclass
class Hypothesis:
    id: str
    statement: str
    supporting: List[str] = field(default_factory=list)    # claim ids
    contradicting: List[str] = field(default_factory=list)
    status: str = "open"          # open | supported | partial | refuted | unsupported

@dataclass(frozen=True)
class Step:
    id: str                       # deterministic: sha1(primitive|args)[:8]
    primitive: str                # retrieve | inspect | trace | compare | verify
    args: dict
    reason: str                   # which hypothesis/unknown it targets

@dataclass
class Investigation:
    objective: str
    subject: List[str]                     # anchor refs — what "it" means
    hypotheses: List[Hypothesis]
    claims: List[Claim]
    evidence: Dict[str, EvidenceRef]       # ref -> provenance
    performed: List[Step]                  # ordered, the trail
    pending: List[Step]
    unknowns: List[str]
    contradictions: List[tuple]            # (claim_id, claim_id, why)
    spend: Budget                          # steps, writer calls, chars
```

Confidence is **computed, never generated**:

```python
def classify(claim, evidence) -> str:
    refs = [evidence[r] for r in claim.citations if r in evidence]
    if any(e.states_reason and e.source in ("pr","issue","doc","commit") for e in refs):
        return SUPPORT_EXPLICIT
    kinds = {e.source for e in refs}
    if len(refs) >= 2 and len(kinds) >= 2:
        return SUPPORT_STRONG
    return SUPPORT_WEAK if refs else SUPPORT_UNSUPPORTED
```

`states_reason` / source-class reuse `gate._states_reason` and `gate._source`
directly, so the investigation's notion of "recorded rationale" cannot drift
from the honesty gate's.

---

## C. Control loop

```python
def investigate(question, pipeline, entities, prior=None, budget=Budget()):
    # 1. FRAME -- deterministic subject binding first
    named = anchor_refs(question, pipeline)                 # reuses pipeline's regexes
    subject = named or (prior.subject if prior and is_followup(question) else [])
    objective, hypotheses = llm_frame(question, subject, pipeline, prior)   # LLM #1

    inv = Investigation(objective, subject, hypotheses, ...)
    inv.pending = seed_steps(subject, question)             # deterministic seeds:
                                                            # inspect(subject),
                                                            # trace(subject->issues,
                                                            #       ->files, ->commits)
    while inv.pending and budget.allows(inv):
        round_ = [s for s in take(inv.pending, budget.max_parallel)
                  if s.id not in {p.id for p in inv.performed}]   # dedupe
        results = parallel(run_probe(s, pipeline, entities) for s in round_)  # threads

        for step, ev in zip(round_, results):
            inv.performed.append(step)
            inv.evidence.update(ev)
            reading = llm_read(inv, step, ev)               # LLM #2, per step
            for claim in gated_claims(reading, ev):         # gate() each, drop bluffs
                claim.support = classify(claim, inv.evidence)
                inv.claims.append(claim)
                score_hypotheses(inv, claim)                # deterministic tally
        detect_contradictions(inv)                          # deterministic
        inv.pending += next_steps(inv)                      # LLM #1 again, validated

    for c in inv.claims:                                    # 7. verify pass
        c.verified = gate(as_answer(c), list(inv.evidence), evidence=texts(inv)).verdict == "answer"

    return llm_synthesize(inv)                              # LLM #3, claims-only prompt
```

### C.1 Where the LLM is and is not

| deterministic (code) | LLM |
|---|---|
| entity resolution, anchor refs, subject binding | phrasing the objective |
| every graph traversal (`trace`) | proposing hypotheses |
| step dedupe, budget, parallel scheduling | choosing which step to run next (from a closed vocabulary) |
| citation → ref resolution, groundedness | reading one step's evidence into a candidate claim |
| support/confidence classification | writing the final prose from claims |
| contradiction detection (same subject, opposed polarity, both explicit) | — |
| stopping | — |

The LLM never emits a ref that isn't already in `inv.evidence`; `gate()` drops it
if it tries. The LLM never assigns confidence.

### C.2 Step vocabulary (closed)

`retrieve(query)` · `inspect(ref)` · `trace(ref, edge)` where `edge ∈
{linked_issues, changed_files, commits, dependents, dependencies, subsequent_prs,
mentions}` · `compare(pr)` · `verify(claim_text)`. Anything else the model emits
is dropped by the validator and logged in the trail as `rejected`.

### C.3 Parallelism

`concurrent.futures.ThreadPoolExecutor(max_workers=4)` over one round's steps.
Probes are I/O bound (`gh` subprocess, provider HTTP, cached embeddings).
Results are re-ordered into queue order before state update, so a run is
reproducible given the same provider outputs. **No agents, no message passing,
no shared mutable state inside a round** — the state is updated single-threaded
after the round joins.

### C.4 Stopping — deterministic

Stop when **any** holds:

1. `pending` is empty (nothing left that targets an undecided hypothesis), or
2. every hypothesis is decided (`supported`/`refuted`/`unsupported`) **and** no
   unresolved contradiction remains, or
3. budget exhausted: `max_steps=12`, `max_writer_calls=10`,
   `max_evidence_chars=120_000`, `max_rounds=4`, or
4. **diminishing returns**: a round adds no new *ref* to `inv.evidence` and no
   new claim. Two such rounds ends it.

Rule 4 is what kills the wander. It is measured on refs, not on model
self-report. Whatever is unresolved at stop becomes an `unknown` in the answer —
budget exhaustion is disclosed, never silently dressed as completeness.

---

## D. Tool interface

```python
# evals/probes.py -- every probe returns Dict[ref, EvidenceRef] and mutates nothing

def retrieve(pipeline, query, k=8) -> Dict[str, EvidenceRef]
    # pipeline._retriever.search -- the SAME hybrid+normalized path as /ask

def inspect(pipeline, ref, token=None) -> Dict[str, EvidenceRef]
    # indexed chunk if present; else ingest.fetch_ref_detail / fetch_commit_detail

def trace(entities, ref, edge) -> List[str]
    # pure lookup in the derived index; returns refs, never text.
    #   pr -> linked_issues | changed_files | commits | subsequent_prs
    #   code -> dependents | dependencies      (demo/structure.py edges)
    #   issue -> mentions

def compare(repo, pr, token=None) -> Dict[str, EvidenceRef]
    # ingest.fetch_pr_diff -> a `diff:pr/400` chunk of real hunks, bounded by
    # _REF_DETAIL_MAX_CHARS. One `gh pr diff` call, exact-identifier lookup --
    # the same shape and token discipline as fetch_commit_detail.

def verify(pipeline, claim, evidence) -> bool
    # evals.gate.gate(...) verbatim on a one-claim answer. No new honesty logic.
```

`entities.build_entity_index(chunks)` is pure — chunks in, edges out, same
discipline as `repo_map.py`/`structure.py`:

- `pr → changed_files` from the `Files changed (N): …` line (**ceiling: 30
  files**; publish `files_truncated: true` when the line says "… and N more").
- `pr → linked_issues` from `#N` in the PR chunk text, **plus** exact
  `closingIssuesReferences` once Phase 2 persists them into the chunk text.
- `commit → pr` from a `(#N)` subject; **flagged convention-dependent**.
- `code → dependents/dependencies` delegated to `structure.build_structure`.
- Every edge carries the ref that proves it. An edge that cannot name its proof
  is not emitted.

---

## E. Implementation plan

| phase | files | work | tests | acceptance | risk |
|---|---|---|---|---|---|
| **1. Entity index** | new `evals/entities.py`, `evals/test_entities.py` | derive edges from chunk text; every edge carries proof ref | fabricated-edge guards (bare-number match, PR body quoting `#N` of another repo, truncated file list), purity (`open`/`socket` patched to raise), determinism under reorder | edges verified by hand against `simonw/llm` corpus; **0 unproven edges**; existing suites unchanged | over-claiming edges — mitigated by copying `structure.py`'s no-generic-fallback rule |
| **2. Diff + exact links** | `evals/ingest.py` | `fetch_pr_diff`; persist `closingIssuesReferences` as a `Linked issues: #N` line in the PR chunk text | offline request-shape tests; bounded output; token never in argv | `chunking`-style meta bump not needed (text-only); board re-ingest **not** required for phase 1–4 to work | changing chunk text changes retrieval scores → re-run board before landing |
| **3. State + confidence** | new `evals/investigation.py`, tests | dataclasses, `classify`, budget, dedupe | classifier pinned against `gate._states_reason`/`_source` (not a hand copy); unsupported when no refs | pure module, no I/O | drift from gate — pinned by test |
| **4. Probes + loop** | new `evals/probes.py`, `evals/investigator.py`, prompt builders in `synth.py` | the loop, closed vocabulary validator, thread pool | offline loop tests with `StaticProvider`: dedupe fires, budget caps, diminishing-returns stop, invalid step rejected, ungrounded claim dropped by gate | a scripted 4-step investigation runs offline and produces a claims list; **`python3 -m evals.run` byte-identical** | model proposing junk steps → validator drops; cost → budget |
| **5. Endpoint + continuity** | `demo/investigations.py`, `demo/server.py`, `demo/payload.py` | LRU session store keyed `(identity, repo)`, TTL; `/investigate` behind `/ask`'s limiter + entitlement | isolation test (two identities never see each other's state), 401/403/429 paths, follow-up binds subject deterministically | 4-turn conversation (`talk about PR #400` → `why did it change?` → `what did it affect?` → `why here?`) holds one subject | **persist refs + claims only, never evidence text**; recompute text from the live corpus each turn |
| **6. Eval suite** | `evals/investigation_questions.json`, `evals/test_investigation_eval.py` | §17's nine dimensions | grounding, citation correctness, step efficiency (≤ budget), multi-hop PR→issue→code→later-PR, contradiction detection, honest missing-info, explicit-vs-inferred labelling, 4-turn continuity, **regression: existing board unchanged** | gates 100%; multi-hop answered where single-shot `/ask` cannot | cost — mark the live board opt-in like `test_paid_writer_eval` |
| **7. UI trail** | `mac/`, `extension/` | render claims with support labels + the step trail | Swift decode tests against captured real payloads | a reader can see which evidence caused each part | last; nothing else depends on it |

Phases 1, 3 are pure and land with zero behavioural risk. Phase 4 is the first
that can change an answer, and it changes only the new endpoint.

---

## F. What this deliberately does not do

- No agent with 20 tools. Five primitives, closed step vocabulary, validated.
- No new store, no graph database, no re-index. Edges are derived from chunks
  already in memory, per request, the way `/map` already is.
- No new honesty semantics. `gate()` is the only arbiter, called more often.
- No multi-agent. One thread pool over I/O-bound probes.
- No change to `/ask`, `.explain()`, the retriever, or the eval board.
