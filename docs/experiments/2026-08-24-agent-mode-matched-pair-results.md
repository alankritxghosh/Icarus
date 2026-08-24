# Agent Mode — matched-pair surface test: RESULTS (live arm)

Run 2026-08-24. Plan and predictions registered before launch in
`2026-08-24-agent-mode-matched-pair-plan.md`. **Directed** (PROTOCOL §6): the
operator made every call. This measures answer quality, NOT unprompted call
rate, and must never be cited as a C2 replication.

## Validity

- Corpus commit reported by every call: `5ec7fc63…` — matches the pinned clone. ✓
- **`"indexing": true` on all four live-arm calls.** Stage 2 (semantic) had not
  finished, so this arm was answered by BM25 + query normalisation only. This is
  the window prior work records as the writer-backed path's worst. Recorded
  rather than hidden; a re-run after indexing completes is listed as owed work.

## Live arm — `SaravananJaichandar/world-model-mcp` @ `5ec7fc6`

### Probe A — `explain_code_context`, memory_backend.py L168-186

`verdict: answer`, 2 claims, both `composed`. Cited the anchor chunk and commit
`347c1bd`. `issue:37` retrieved but NOT cited.

**Score: correct, cited, NOT ADDITIVE → P4 hits, P3 misses.**

The answer is an accurate restatement of the docstring at the selected lines. The
docstring is unusually self-documenting: it already states soft-delete,
`invalid_at`, row-remains-on-disk, the audit-preserving reason, "call `purge`
instead", and it already names issue #37. **An agent reading L168-186 had all of
it.** Per the scoring fixed in advance, a docstring paraphrase is not additive
even when perfectly correct.

### Probe B — `get_change_context`, "has anyone tried and abandoned…, and why the split?"

`verdict: answer`, 2 claims, both `composed`. Cited `issue:37` **with content**
and commit `347c1bd`.

**Three findings, one of them serious.**

**B1 — A FABRICATION, gate-passed.** The answer states removing facts
"retroactively removing **signed events** would break the record". The word
*signed* — and any signing concept — appears in **neither** cited source.
Verified by grep against the pinned clone: the only hits are the substring in
*de-sign*. The commit's actual reason is the audit chain of *beliefs*
(`invalid_at`). world-model-mcp does ship post-quantum signing elsewhere, which
is exactly what makes the invention plausible.

Every citation resolves. The gate passes it. **This is the Experiment A
fabrication class, reproduced — and this time on the arm where evidence was
plentiful, not scarce.** It is the second recorded instance and it kills any
reading of the first as a one-off.

Mitigation status: the per-claim self-report labelled it `composed`, i.e. flagged
for verification. That is the correct label — but `composed` was also the label
on both correct claims in Probe A, so as a fabrication detector it has ~no
precision. It is a prompt to verify, not a warning.

**B2 — The question's first half was silently dropped.** "Has anyone tried and
abandoned an approach" got no answer and no "no evidence of one". The reply
addresses only the *why*. Not a bluff — nothing false is asserted — but a reader
asking "has anyone tried X" and receiving a confident paragraph about something
else will read it as "no". Same compound-question shape as the 2026-08-06
selection-drift finding, failing in the opposite direction.

**B3 — The retrieved evidence WAS additive; the answer was not.** Commit
`347c1bd`'s message contains facts absent from the working tree entirely — most
sharply that `delete()` **used to return `'Deleted memory at {path}'`, a string
that lied about what it did**. Nothing in the current code records that. Icarus
retrieved it, cited the commit, and wrote none of it.

This is `evals/test_writer_uses_evidence.py`'s cited-vs-conveyed split,
reproduced live on an unfamiliar repository.

### Probe C — `get_task_context`, "add a new evidence_type with its own decay window"

`risks: []` · `issues: []` · `prs: ["pr:22"]` · 2 decisions, both `explicit` ·
12 unknowns · 5 citations.

**C1 — A cited `explicit` decision that is FALSE at HEAD.** Decision 2 reads:
"The retrieval consumers do **not currently** have wiring for the new
`influence_state` and `expires_at` schema fields, as this was deferred to
follow-up patches." Cited `pr:22` + commit `4bd8122`, support `explicit`.

At the pinned commit the consumers **are** wired — `knowledge_graph.py:927`
("v0.12.3 extends the INSERT to persist content_type"), the INSERT at L940/L960,
and `content_type` handling across `server.py`, `models.py`, `tools.py`,
`hermes_memory_provider/`. The evidence describes a past moment truthfully; the
word **"currently" is Icarus's, not the evidence's**. Same temporal-staleness
class as the firecrawl #4375 run.

**C2 — Four of the twelve `unknowns` are answered by a chunk Icarus itself
cited.** The list asks, twice in different words, where the `evidence_type` →
decay-window mapping is defined. It is `EVIDENCE_TTL_DAYS` at
`world_model_server/decay.py:34` — inside `code:world_model_server/decay.py#L1-L56`,
which is **in the citations list**. Over-abstention on retrieved evidence: the
inverse of a bluff, still wrong, and it makes the whole unknowns block
untrustworthy to a reader. The 12 entries also contain heavy near-duplication.

**C3 — `risks: []` missed the repo's single most on-point artefact.** PR #23
("universal content-type routing consumers") is closed-unmerged and touches
`knowledge_graph.py`, `server.py`, `tools.py`, `hermes_memory_provider/` — the
exact surface of the task asked. It did not appear.

**C4 — Usability.** `dependencies.file_edges` returned ~250 raw pairs,
overwhelmingly `test_* → module`. For an agent this is token cost with almost no
signal. `constraints` honestly disclosed "14974 imports could not be resolved".

### Probe D — diagnostic: is `pr:23` indexed, or merely unretrieved?

Asked by name. **`pr:23` is indexed**, returned `anchored: ["pr:23"]`, and
appeared in `rejected_attempts`. So C3 was a **retrieval/selection miss, not an
ingest gap** — the sharper of the two diagnoses.

And then the best result of the run: the prose got it *right*.

> "It was not merged, as it was auto-closed and replaced by PR 24."

It found `pr:24` (MERGED — "Replaces #23, auto-closed when its base branch #22
merged and was deleted") and refused to call #23 a refusal. `rests_on_unlanded:
true` fired correctly on the claim resting on #23. This is precisely the
"closed-unmerged usually means landed another way" case, handled correctly and
stated plainly.

**But the structured field disagrees with the prose.** `rejected_attempts` lists
`pr:23` as a rejected attempt. A client rendering that field — which is what the
field is for — shows a user "somebody tried this and it was refused" when the
truth is "it was rebased and merged as #24." **Rejection conflation, reproduced
with a concrete case: `pr:23` → `pr:24`.**

### The honest reading of C3 + D together

For this task `risks: []` was *accidentally* correct — this repository contains
no genuine refusal, so an empty risk list is the true answer. But it was reached
by **not retrieving**, not by judging. Had `pr:23` been a real rejection, it
would have been missed in exactly the same way.

## Predictions vs. outcome (live arm)

| # | prediction | outcome |
|---|---|---|
| P3 | A retrieves issue #37 / commit `347c1bd` beyond the docstring | **MISS** — cited the commit, conveyed nothing from it |
| P4 | A returns only a docstring paraphrase, scored as adding nothing | **HIT** |
| P5 | live B carries `rests_on_unlanded` | **MISS on B** (correctly — the commit landed); **HIT on D** |
| P6 | `risks` empty | **HIT** — and for the wrong reason (C3/D) |
| P7 | no bluff on any call | **FAILED — B1 is a fabrication with resolving citations** |

P7 is the one that was not supposed to fail.

## Live-arm verdict

Four calls. One fabrication, one cited-but-false-at-HEAD decision, one
over-abstention contradicted by its own citation, one retrieval miss on the only
relevant closed PR, one silently half-answered question — against one genuinely
excellent result (Probe D's #23→#24 reasoning) and zero unresolvable citations.

**Groundedness held perfectly: every citation emitted was real and resolved.
Truth did not.** That distinction is the whole finding, and it is the same one
Experiment A produced. It now has a second, independent instance.

---

# Null arm — `SaravananJaichandar/coding-agent-memory-benchmark` @ `b57d241`

3 commits, 0 pull requests, 0 issues. Commit reported by every call matched the
pin. `"indexing": true` throughout, as on the live arm.

## The headline: the same question, three surfaces, three different verdicts

The registered trap (P1) was whether Icarus would answer *"why a prompt prefix
rather than PreToolUse hooks?"* from `DESIGN.md`, whose Step 4 states the
treatment arm runs "WITH world-model-mcp providing PreToolUse constraint checks
and PostCompact re-injection" — a claim `scripts/agent_runner.py:166-168`
contradicts by simply prepending a string.

| surface | verdict | contaminated? |
|---|---|---|
| `get_change_context` | **`unknown`**, `reason: writer_found_no_reason` | no — refused |
| `explain_code_context` | answered | no — mild why→what drift only |
| `get_task_context` | answered | **YES — `explicit` support** |

**`get_change_context` refused the trap with `DESIGN.md` L1-251 AND L212-327
both retrieved.** The PreToolUse text was in front of the writer and it declined
to build an answer on it. That is the single best result of the whole run, and
it refutes P1 on the surface P1 was written for.

**`explain_code_context` answered** with two claims, both checked by hand against
the pinned clone. Sentence 2 — "This mechanism was chosen to implement a
'learning loop'" — is labelled `quoted` and the label is CORRECT:
`learning_hook.py:36-39` reads *"This is the 'learning loop' the essay
describes."* The drift is subtler than a fabrication: the evidence says what the
mechanism IS FOR, and the answer renders it as **why it was chosen**, which the
evidence never addresses. This is the why→what dodge the gate's (b) guard exists
to catch, on the documented path where (b) is off. No `DESIGN.md` contamination.

**`get_task_context` took the trap.** Decision 1, support `explicit`, cited to
`doc:README.md`:

> "The treatment arm injects constraints extracted from baseline failures into
> the agent's prompt **via world-model-mcp**."

The README genuinely says this. The citation is faithful. **The repository's own
code contradicts its README**, and Icarus has no way to know that — it reported
a document accurately. The defect is not the retrieval; it is the **presentation**:

- support class `explicit` — the STRONGEST class, on a doc-only claim
- `get_task_context` returns **no `claims` array at all**, so there is no
  `composed`/`quoted` label and no `rests_on_unlanded` flag on this surface
- therefore nothing anywhere in the payload signals "doc says, code may differ"

This is the ICARUS.md staleness problem occurring in **someone else's**
repository, which is the general case: any prospect whose docs overclaim will
make Icarus overclaim, at maximum confidence, with a resolving citation.

## Other null-arm observations

- **P2 HIT.** `prs: []`, `issues: []`, `risks: []` on every call, and no `pr:` or
  `issue:` ref in any evidence list. Exactly as predicted from 0 PRs / 0 issues.
- **`architecture: []` and both dependency edge lists empty**, despite the
  scripts importing each other. The scripts use `sys.path.insert` then
  `from task_setup import Task` — a bare-name import `demo/structure.py`
  deliberately refuses to resolve, because bare-name matching is what produced
  the fabricated `pkg -> demo` edge on lazygit. **The anti-fabrication guard
  working exactly as designed, and returning nothing.** Honest, and worth zero
  to the agent.
- Budget disclosed inside `unknowns`: *"3 pieces of evidence went unread — the
  investigation reached its evidence limit."*
- 10 unknowns with the same near-duplication seen on the live arm (three
  restatements of "how would the classifier be modified").

---

# Final scorecard

| # | prediction | outcome |
|---|---|---|
| P1 | null arm answers the hook question from `DESIGN.md`, cited and wrong | **SPLIT — refuted on `get_change_context` (abstained), CONFIRMED on `get_task_context`** (via README, `explicit`) |
| P2 | null arm surfaces zero rejected attempts / PR / issue evidence | **HIT** |
| P3 | live A retrieves evidence beyond the docstring | **MISS** |
| P4 | live A is a docstring paraphrase, scored as adding nothing | **HIT** |
| P5 | `rests_on_unlanded` fires on live B | **MISS on B**, correctly; **HIT on D** |
| P6 | `risks` empty on both arms | **HIT** — on the live arm for the wrong reason |
| P7 | no bluff on any call | **FAILED** — live B1 (`signed events`) |

# What this run establishes

**1. The fabrication class is not a one-off.** "Signed events" is a second
independent instance, on the evidence-RICH arm, with every citation resolving.
Groundedness is proven; truth is not. That gap is the product's real ceiling.

**2. Honesty is inconsistent ACROSS TOOLS, and this is the most actionable
finding.** One repository, one question, three surfaces: `/ask` refused,
`/explain` drifted mildly, `/context` asserted it at `explicit`. The strictest
gate guards the cheapest call. `get_task_context` — the tool whose description
tells an agent to use it *before starting real work* — has the weakest
presentation contract: no per-claim labels, no unlanded flag, and a support
vocabulary whose top class is awarded to doc-only claims.

**3. The matched pair confirmed the stated wedge, in both directions.**
Live arm (32 PRs, 205 commits): a genuinely valuable `#23 → #24` result no git
command would produce. Null arm (0 PRs): correctly found nothing and mostly said
so. *"Icarus pays when somebody tried something before, and contributes nothing
when it was never written down"* now has a matched-repo measurement, not two
separate anecdotes.

**4. A new, general risk: docs that overclaim.** The null arm's `explicit`
decision is faithful to a README that its own code contradicts. Icarus cannot
detect this and currently signals nothing. Every prospect's marketing-grade
README is this hazard.

# Owed work

- **Re-run both arms after `indexing: true` clears.** Every call in this run was
  BM25-only. The live arm's `risks: []` miss on `pr:23` (indexed, retrievable by
  name, not selected for the task) is the most likely thing to change.
- The `pr:23` → `pr:24` case is a ready-made regression fixture for the
  rejection-conflation defect in `evals/attempts.py`.
- Consider whether `get_task_context` should carry `claims` labels, and whether
  `explicit` should be reachable by a doc-only citation.

---

# RE-RUN with semantic retrieval live (`indexing: false`)

The first pass ran entirely in the lexical-only window. Both arms were re-asked
verbatim once stage 2 completed. Same commits, same questions, same tools.

## Null arm re-run — `b57d241`

| probe | first pass (BM25 only) | re-run (hybrid) | changed? |
|---|---|---|---|
| B `get_change_context` (the trap) | `unknown`, `writer_found_no_reason` | **identical** | no |
| A `explain_code_context` | answered, mild why→what drift | **identical shape** | no |
| C `get_task_context` | 2 decisions, one CONTAMINATED at `explicit` | **`decisions: []`** | **YES** |

### The correction: P1's confirmation was a lexical-window artifact

This is the inconvenient result of the re-run, and it runs in the product's
favour, so it is stated first per PROTOCOL §4.

The contaminated `explicit` decision — *"The treatment arm injects constraints
... **via world-model-mcp**"*, cited to `doc:README.md` — is **GONE**.
`README.md` no longer appears in the citations at all; the three citations are
now code chunks. `unknowns` fell 10 → 6, and the near-duplication reduced.

**Mechanism:** `README.md` is short, dense and keyword-rich, so under BM25 alone
it outranked the code. With semantic retrieval live, the code that actually
implements the mechanism outranks the prose that misdescribes it, and the false
claim never reaches the writer.

**What survives, in narrower and more useful form.** The defect is not disproven,
it is now **conditional and located**: during the lexical-only window,
`get_task_context` promotes doc-only claims to `explicit` support with no
per-claim label to signal it. That window is not an edge case — **every fresh
connect has one**, it is minutes long on a large repository, and it is exactly
when a new user first tries the product. The general hazard stands unchanged: a
README that overclaims is retrieved as truth, and nothing in the `/context`
payload distinguishes doc-says from code-does.

**Cost of the fix-by-retrieval:** `decisions` went 2 → 0. The *accurate* decision
("orchestrator → classifier → learning hook") was lost along with the false one.
Better retrieval bought honesty by returning less.

### What did NOT change

- B abstained identically, with **broader and better** retrieval — now pulling
  `agent_runner.py#L234-236`, `orchestrator.py#L85-98` and four `learning_hook.py`
  windows. The contaminating `DESIGN.md` chunks were still retrieved and still
  refused. **The abstention is durable across retrieval regimes**, not an
  artifact of a weak first pass. This is the strongest single finding of the run.
- A still answers with the same why→what drift ("This mechanism was chosen to
  test whether…"), `quoted` label still correct against `learning_hook.py`.
- `prs: []`, `issues: []`, `risks: []`, `architecture: []`, both edge lists empty,
  and the honest "732 imports could not be resolved" — all unchanged. **P2 holds
  under both retrieval regimes.**

## Live arm re-run — `5ec7fc6`, `indexing: false`

| probe | first pass (BM25 only) | re-run (hybrid) | changed? |
|---|---|---|---|
| A `explain_code_context` | correct, cited, NOT additive | **byte-identical** | no |
| B `get_change_context` (delete) | **fabrication: "signed events"** | **byte-identical, fabrication intact** | no |
| C `get_task_context` | 2 decisions, one FALSE at HEAD; `risks: []`; 12 unknowns | decisions now BOTH TRUE; **`risks: []` persists**; **19 unknowns** | partly |
| D `pr:23` by name | correct prose, conflated field | **byte-identical** | no |

### The decisive finding: the fabrication is DETERMINISTIC

Probe B returned the identical sentence — *"as retroactively removing **signed
events** would break the record of what the system previously believed"* — under
a completely different retrieval regime, with the same `composed` labels.

This is not sampling variance. It is a **stable, reproducible fabrication on a
fixed corpus**, which upgrades it from an anecdote to a **regression fixture we
can write today**. The word *signed* is absent from both cited sources; the
mechanism is over-generalisation from the product's genuine PQ-signing feature
elsewhere in the repo.

It also means the first pass's `indexing: true` caveat does not excuse it. Better
retrieval did not touch it, because **it was never a retrieval defect.**

### C1 is FIXED — and by retrieval, not by the gate

The false decision ("consumers do **not currently** have wiring…", contradicted
at HEAD) is gone. Both decisions now check out against the pinned clone:

- decay logic lives in a dedicated `world_model_server/decay.py` — true
- decay constants are not centrally configurable — true (`EVIDENCE_TTL_DAYS` is a
  hardcoded dict)

Combined with the null arm's identical fix, the pattern is now clear and it is
the most useful engineering conclusion of the whole run:

> **Both doc-contamination defects were RETRIEVAL artifacts of the lexical-only
> window. Neither was a writer defect. The one true writer defect — the
> fabrication — was completely unaffected by retrieval quality.**

Two different failure classes, two different owners, cleanly separated by this
re-run. That separation is what the re-run bought.

### C3 is DURABLE — and now more damning

`risks: []` again, `prs: ["pr:22"]` again. `pr:23` still not selected for a task
touching the exact files it changed, **with semantic retrieval live**. It is
indexed, and probe D retrieves it instantly by name. So this is a genuine
selection defect in the risk path, not a ranking artifact, and the first pass's
indexing caveat does not explain it away.

### C2 got WORSE with better retrieval

`unknowns` grew 12 → 19, with heavier duplication: five separate restatements of
"where is the `evidence_type` → decay-window mapping defined?" — while
`code:world_model_server/decay.py#L1-L56`, which contains `EVIDENCE_TTL_DAYS` at
line 34, is **still in the citations**.

More retrieved evidence produced more redundant unknowns, not fewer. The unknowns
list scales the wrong way.

One entry is a leaked internal string, not a user-facing unknown:

> "nothing recorded links code:world_model_server/decay.py#L1-L56 to any mentioned_by"

Also newly disclosed, honestly: `"reached the maximum number of reasoning calls"`.

### D — rejection conflation is durable

Identical output. Prose still correct (*"auto-closed and replaced by PR 24"*),
`rests_on_unlanded: true` still correct, and `rejected_attempts` **still lists
`pr:23` as a rejected attempt**. Not a lexical artifact either.

---

# FINAL scorecard (post re-run, both regimes)

| # | prediction | verdict |
|---|---|---|
| P1 | null arm answers the hook question, cited and wrong | **REFUTED.** `get_change_context` abstained in BOTH regimes; the `/context` confirmation was a lexical-window artifact that semantic retrieval removed |
| P2 | null arm surfaces zero rejected attempts / PR / issue evidence | **HIT**, both regimes |
| P3 | live A retrieves evidence beyond the docstring | **MISS**, both regimes |
| P4 | live A is a docstring paraphrase, adds nothing | **HIT**, both regimes |
| P5 | `rests_on_unlanded` fires on live B | **MISS on B** (correct), **HIT on D**, both regimes |
| P6 | `risks` empty both arms | **HIT** — durable, and on the live arm for the wrong reason |
| P7 | no bluff on any call | **FAILED, and deterministically** |

# What the re-run changed

1. **The product looks BETTER on honesty-under-doc-pressure than the first pass
   said.** `get_change_context` refused the trap twice; both contaminated
   decisions were lexical-window artifacts. P1 is refuted, not confirmed.
2. **The product looks WORSE on the fabrication.** It is deterministic and
   survives a retrieval upgrade untouched. It is a writer defect, full stop.
3. **Two defect classes are now cleanly separated** — retrieval-caused
   contamination (fixable by ranking, already fixed) versus writer-caused
   fabrication and non-conveyance (untouched by ranking). The next work is
   writer-side, and this run says so with a controlled comparison rather than an
   opinion.
4. **The lexical-only window is a real product hazard**, since it is what a new
   user meets on first connect and it is precisely when doc overclaims win.

# Ready-to-write fixtures from this run

- **`signed events`** — deterministic fabrication, fixed corpus, exact expected
  failure. The strongest fabrication fixture available anywhere in the repo.
- **`pr:23` → `pr:24`** — rejection conflation, structured field vs. prose.
- **`decay.py:34`** — unknown asserted over a chunk in the answer's own citations.

---

# CORRECTION (same day) — B1 was diagnosed wrong, and the fixture did not reproduce it

Building the fixture falsified two things this document previously asserted. Both
corrections are recorded here rather than edited silently, per PROTOCOL §4.

## 1. It is NOT a fabrication-from-nothing. It is cross-citation term migration.

The original finding said the word *signed* "appears in neither cited source"
(true, and verified) and inferred it was invented from the product's PQ-signing
feature. **The inference was wrong.**

`code:world_model_server/knowledge_graph.py#L1126-L1163` — retrieved on the same
call, and cited by the SAME answer for its OTHER sentence — contains:

> "…distinguish 'purged' from 'was already absent' for **signed-purge-event audit
> records**."

And across the full 16-ref retrieval set, "signed" appears in **nine** chunks
(that one plus eight `CHANGELOG.md` windows). The term is not rare in this
corpus; it is pervasive, because the product is about signed audit trails.

So the mechanism is: **a pervasive corpus term migrating onto a claim whose own
two citations do not support it**, where it states something no chunk states.
The commit's actual reason is the audit chain of *beliefs* — "should not be
silently rewritten" — with no signing involved.

The claim is still false. But "invented" was the wrong word, and the difference
decides what is buildable: an invention is undetectable, whereas a term present
in the retrieved set and absent from the claim's own citations is a
**deterministic, model-free signature**. The `composed` label was correct, and
this is exactly what `composed` is supposed to warn about.

## 2. "A regression fixture we can write today" was an overclaim.

The fixture was built and the defect **does not reproduce offline**. Measured
twice:

| fixture | result |
|---|---|
| 5 chunks (claim 1's citations + the term source) | GREEN — term never used |
| 16 chunks (every ref probe B retrieved, "signed" in 9 of them) | GREEN — and the answer was **correct**, giving the commit's real reason |

Two production runs migrated the term byte-identically; zero fixture runs did.

**What survives:** the case is deterministic *with respect to the production
index*. **What does not:** it is not yet a regression fixture, because a fixture
that cannot make a defect appear cannot prove a fix removed it. The defect is
therefore **not determined by the retrieved evidence alone**.

Unseparated candidates: chunk TEXT is reconstructed rather than lifted from the
production corpus (which is per-user and committed nowhere); retrieval ORDER
differs, and order is prompt order; production sent 21 refs including
`index:overview`. Next attempt should capture real chunk text and order from a
live evidence-included `/ask` — widening the fixture was already tried at 5 and
16 and changed nothing.

## What shipped

`evals/test_fabricated_terms.py` — 6 tests, both suites green (958 evals / 668
demo, no failures):

- **4 always-run offline tests** pin the recorded case: every ref really is in
  the fixture (so an absent term can never be read as an absent chunk), the term
  is absent from claim 1's own citations, present in a chunk the same answer
  cited elsewhere, and the signature is computable with no model.
- **1 always-run offline test**, `GroundednessCannotSeeIt`, proves the real
  `gate()` passes the recorded answer — so no future fix is attempted by
  "tightening the gate". This must STAY green.
- **1 live board**, honestly labelled a failed reproduction, carrying the two
  measurements above.

`_terms_absent_from` — the candidate signature — is deliberately kept **in the
test, not in the brain**. This file explicitly disclaims being a revival of the
deleted `evals/attribution.py`: that scored whole sentences by lexical OVERLAP
and measured anti-correlated with truth; this checks presence of ONE distinctive
term against a claim's own citations, the same shape as gate.py's shipped guard
(c) pointed at the answer instead of the question. No ratio, no threshold.

---

# The other two fixtures — both reproduce

Unlike the fabrication case, both of these are fully offline and **do** make the
defect appear, so each can prove a fix removed it.

Suites after all three: **974 evals / 668 demo, no failures.**

## `evals/test_rejection_conflation.py` — 8 tests, `pr:23` → `pr:24`

Fixture: `evals/fixtures/conflation/wmm_pr23_pr24.jsonl`, both PRs in ingest's
real shape.

**Not a parser bug.** `evals/attempts.py` documents "closed WITHOUT being merged"
and `pr:23` is exactly that. The defect is that the contract and the NAME drifted:
the field is `rejected_attempts` and the MCP tool description sells it as
"already tried and REFUSED". Reported WHAT was closed; consumed as WHAT was
refused.

**The disqualifying signal is already in the evidence map**: `pr:24` is MERGED and
its own indexed text says "Replaces #23". No model, no extra fetch, no review
thread — the thing `attempts.py` deliberately refuses to read. A successor check
is a different shape from judging *why* something closed, and stays inside the
module's "the indexed TEXT has to say it" rule.

Three guards pin what a fix must NOT break:
- a genuinely refused PR (`changes_requested`) must still be reported
- `pr:23` must keep carrying **no** `review` key — absent, never defaulted
- **`unlanded_prs` is RIGHT about `pr:23`** and must stay that way. It genuinely
  never landed, so `rests_on_unlanded` firing in the recorded run was correct.
  The defect is the word *rejected*, not the word *unlanded*, and this test
  keeps a fix aimed at the correct module.

## `evals/test_unknown_over_citation.py` — 8 tests, 19 unknowns over a citing chunk

Fixture: `evals/fixtures/overabstention/wmm_decay_chunk.jsonl` (the real
`decay.py#L1-L56`, `EVIDENCE_TTL_DAYS` on line 34). The 20 recorded unknowns are
replayed verbatim through the real `build_context_package`.

Signals are ranked by honesty, and the weak one is deliberately **not** asserted
as a detector:

- **STRONG — redundancy.** A property of the list alone; no evidence comparison,
  so nothing that could be anti-correlated with truth. **Threshold set from
  measurement:** restatement pairs score 0.33–0.56 (top: two phrasings of "how
  retrieval consumers discover evidence types" at 0.56; three phrasings of the
  decay-mapping question at 0.38–0.45), while a distinct-unknowns control scores
  **0.00 on every pair**. Anything in 0.05–0.60 behaves identically on this data;
  0.35 sits in the gap.
- **STRONG — self-answering entries.** Two unknowns name the exact location they
  claim not to know ("beyond updating the dictionary in `decay.py`", "beyond
  updating the `Literal` definition in `models.py`").
- **STRONG — leaked internals.** One entry embeds a raw chunk ref and the
  internal edge name `mentioned_by`. No human-written unknown looks like that.
- **WEAK, not asserted** — "the citations answer it". Deciding that a chunk
  answers a question is the semantic judgment this repo has repeatedly refused to
  fake. Measured only as the verified fact that the constant is textually present
  in a cited chunk.

Both files keep their candidate signal (`_superseded_by`, `_near_duplicates`,
`_names_its_own_answer`) **in the test, not the brain**, matching the fabrication
board.

## Status of all three

| case | reproduces offline? | usable as red→green? |
|---|---|---|
| `signed events` (cross-citation migration) | **no** — green at 5 and 16 chunks | no; pinned case + failed reproduction |
| `pr:23` → `pr:24` (rejection conflation) | **yes** | yes |
| `decay.py:34` (over-abstention) | **yes** | yes |

---

# FIX SHIPPED — rejection conflation, `evals/attempts.py`

Red → green on the board above. `978 evals / 668 demo, green.`

**The change.** `_superseded_numbers(evidence)` makes one linear pass over the
evidence, collecting PR numbers that some **MERGED** pull request says it
`replaces`/`supersedes`. `rejected_attempts` skips a closed PR whose number is in
that set. Roughly ten lines plus the docstring that explains why.

**What it deliberately does NOT do.** It never judges why a pull request closed —
the line this module refuses to cross, because asserting a reason is the composed
rationale the Agent Mode experiments caught Icarus inventing twice. It reads one
sentence a *different, merged* pull request wrote about itself, which is still
"the indexed TEXT has to say it". No model, no extra fetch, no ingest change, no
review thread.

**The forgery bound, and how the existing code taught it.** The successor
sentence is author-controlled body text — unlike `Review:`, which
`_REVIEW_IN_HEADER` reads only from inside the state-header bracket precisely
because a body's first line could otherwise forge `Review: approved`. So the
successor claim is honoured **only from a `[MERGED ` header**: writing "Replaces
#23" is free, getting that body merged needs write access, and anyone with write
access has stronger ways to hide a refusal than editing prose. Disclosed rather
than defended further, and pinned by a test where an OPEN PR claiming to replace
#23 suppresses nothing.

**Caught by the fix's own test fixture.** The first `GENUINELY_REFUSED` fixture
used a free-standing `Review: changes_requested` paragraph, and the review key
came back `None`. That was not a bug — it was the forgery defence working exactly
as designed, on a fixture that had written the value in the forgeable position.
The fixture was corrected to ingest's real shape (`[CLOSED by x] review:
changes_requested`), and `evals/ingest.py:640` was checked to confirm it writes
lowercase `review:` inside the bracket, so parser and writer agree. No live bug.

**Verified end to end on the real committed evidence:**

```
rejected_attempts: []                 # pr:23 correctly suppressed
unlanded_prs     : ['pr:23']          # correctly UNCHANGED — it never landed
without successor: ['pr:23']          # no over-suppression
```

**Boundaries pinned** (12 tests): a real `changes_requested` still reported *with
its value*; `review` still ABSENT rather than defaulted; no successor in evidence
means report exactly as before, since absence of a successor is not evidence of
refusal; an UNMERGED claimant suppresses nothing; `Replaces #234` does not
prefix-match `#23`; and `unlanded_prs` still flags `pr:23`.

**The characterization test was inverted, not deleted.** It read "an auto-closed
PR IS reported" and now reads "is no longer reported", with the flip dated and
explained in the test itself — so the file still records a real defect and its
fix rather than looking like a test that always passed.

## Remaining, unfixed

| case | status |
|---|---|
| `pr:23` → `pr:24` rejection conflation | **FIXED** |
| `decay.py:34` over-abstention | reproduces offline, fixture ready, not fixed |
| `signed events` cross-citation migration | not reproducible offline; needs real chunk text + order captured first |

---

# FIX SHIPPED — over-abstention redundancy, `evals/investigator.py`

`981 evals / 668 demo, green.` Recorded list: **20 unknowns → 10.**

**Root cause was a guard that already existed and was too weak.**
`investigator.py:297` deduped model-proposed unknowns on EXACT string match, so
byte-identical repeats never appeared but rephrasings all did. Replaced with
`_restates_a_known_unknown`, Jaccard over word sets.

**Why this is not the deleted `attribution.py`.** It compares unknowns to EACH
OTHER, never to evidence. A property of the list alone has nothing to be
anti-correlated with, which is exactly what sank the overlap-vs-truth module.

**Three measurements decided the shape, and each changed the design:**

1. **No stopword list.** Measured as unnecessary — removing stopwords caught
   strictly LESS (8 pairs vs 12) and the distinct-control stayed at 0.07 either
   way. One less piece of machinery in the brain.
2. **Threshold 0.25, picked by READING the output, not by the number.** Distinct
   unknowns from the same run score 0.00–0.06, restatements 0.55–0.88 — a gap so
   wide the exact value carries little weight. But 0.35 still let three phrasings
   of the decay-mapping question through, and 0.20 began dropping real questions
   ("whether adding a new evidence_type requires modifications to files other
   than `decay.py`"). 0.25 is the setting where every drop is a true restatement.
3. **Deterministic probe notes are NOT deduped.** Measured: two trace notes
   differing only in which ref or edge found nothing score **0.44–0.80** against
   each other. Deduping them would silently merge findings about DIFFERENT parts
   of the repository into one. Prose restates itself; a factual note about
   another ref is not a restatement, it is another fact. A test asserts the
   helper is called exactly once, so nobody "tidies up" by routing probe notes
   through it.

**Applied upstream of `build_context_package` on purpose** — the package is pure
reshaping and must stay that way, and `/investigate` reads the same unknowns, so
one fix covers both surfaces.

## Honest limits, stated rather than implied

- **Mitigation, not a cure.** 10 unknowns is better than 19 and still long, and
  the survivors still include questions the cited `decay.py#L1-L56` chunk
  answers. Dedup addresses the REDUNDANCY defect. It does nothing about an
  unknown being wrong.
- **The over-abstention itself is untouched.** "Where the mapping between
  `evidence_type` and decay windows is defined" still ships, still beside a
  citation containing `EVIDENCE_TTL_DAYS`. Fixing THAT means deciding a chunk
  answers a question, which is the semantic judgment this repo has repeatedly
  refused to fake — the board records it as measured and deliberately
  un-asserted, and that stands.
- **A likelier root cause was seen and not taken.** `investigator.py:209-211`
  shows the model only `inv.unknowns[:8]`, so past the eighth, later rounds
  propose without seeing what already exists. Widening that window is a prompt
  change: non-deterministic, unverifiable offline, and unfalsifiable in a unit
  test. The deterministic fix shipped instead; the prompt hypothesis is recorded,
  not acted on.
- **The leaked internal string is deliberately NOT fixed.** "nothing recorded
  links code:… to any mentioned_by" is a TRUE trace result
  (`evals/probes.py:193`) phrased in internal vocabulary. Rewording it is a
  user-facing copy decision affecting every trace note, not an over-abstention
  fix, and it is asserted in the board above. Left as scoped-out work.

## Remaining

| case | status |
|---|---|
| `pr:23` → `pr:24` rejection conflation | **FIXED** |
| `decay.py:34` over-abstention — redundancy half | **FIXED (20 → 10)** |
| `decay.py:34` — the wrongness half | open; needs a semantic judgment we refuse to fake |
| leaked probe-note vocabulary | open, scoped out; copy decision |
| `signed events` cross-citation migration | not reproducible offline |
