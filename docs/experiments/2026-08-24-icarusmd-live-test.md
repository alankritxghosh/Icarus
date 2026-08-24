# ICARUS.md tested live — prediction registered before the run

Date: 2026-08-24
Item: Work Queue § 7a, set by Alankrit 2026-08-21.
Protocol: `docs/experiments/PROTOCOL.md` §3 — prediction in writing before launch.

## Why this run exists

`ICARUS.md` is merged (PR #14) and the doc-truncation defect that would have
crippled it is fixed (`_MAX_CODE_CHUNK_CHARS`, 2026-08-21). **Nothing has yet
asked a live Icarus a question this file answers.** Everything so far is
unit-level: `evals/test_doc_evidence_truncation.py` proves the text reaches the
writer's prompt. It does not prove the text changes an answer.

## The four tests

**T1 — does it answer from the file at all?** Ask something whose answer exists
ONLY in `ICARUS.md`, and check the answer cites `doc:ICARUS.md`.

**T2 — does it still abstain?** Ask something the file does NOT answer. A file
that makes the system more confident everywhere is a regression, not a feature.
This is the test that matters most; T1 failing is disappointing, T2 failing is
a product defect.

**T3 — file versus code.** Introduce a deliberate disagreement and see which
wins. `ICARUS.md` states the code wins. Nothing enforces that.

**T4 — the deferred decision.** Privileged vs ordinary evidence, decided with
the measurement in hand rather than before it.

## Questions (fixed before running)

Answers to Q1 to Q3 exist in `ICARUS.md` and, as far as could be checked, in no
other single place in the repository:

- **Q1:** "What must not be changed casually in this repository?"
  Expect: the § *Things that must not be changed casually* list, citing `doc:ICARUS.md`.
- **Q2:** "Why is the eval corpus frozen?"
  Expect: pinned deliberately to `simonw/llm @ 94769b8`, `pinned: true` so the
  choice does not read as neglect.
- **Q3:** "Is there a free-tier serving path?"
  Expect: no. Killed 2026-07-13, one model (`gemini-paid`) for public and private.
- **Q4 (abstention):** a question about something genuinely unrecorded anywhere.
  Expect: honest unknown.

## REGISTERED PREDICTION

Written before any question was asked.

1. **T1 passes.** Q1 to Q3 answer and cite `doc:ICARUS.md`. Confidence: high.
   The truncation fix is proven at unit level and these facts are nowhere else.
2. **T2 passes.** Q4 abstains. Confidence: medium-high. The gate is unchanged
   and the board reads 100% abstention recall, but the whole point of this test
   is that a confident-sounding doc could drag an unrelated question into an
   answer, and nothing has measured that.
3. **T3: the FILE wins, not the code.** Confidence: medium, and this is the
   prediction most likely to be wrong in an interesting way. `ICARUS.md` asserts
   the code is authoritative, but retrieval has no notion of authority — it
   ranks by relevance. A prose sentence stating a rule will out-retrieve the
   code that implements it for a question phrased in prose. **If T3 fails, the
   sentence in `ICARUS.md` claiming the code wins is itself unenforced and must
   be softened**, which would be this run's most useful output.
4. **T4: privilege will NOT be justified.** Confidence: medium-high. The
   truncation fix already gave doc chunks the same 10,000-char budget as code,
   so the original argument for privileging this file by name has mostly been
   answered by a general fix.

## Result

Run on the real serving path (`demo.library.Library` -> `GatedPipeline`,
`gemini-paid`), repo `alankritxghosh/Icarus` @ `5680321`, public, ingested in
169s. `doc:ICARUS.md` present as exactly ONE chunk -- the shape the 2026-08-21
truncation fix was written for.

### T1 -- does it answer from the file? PASSES 1 OF 3

| Q | `ICARUS.md` rank in 21 retrieved | verdict |
|---|---|---|
| Q1 "what must not be changed casually" | **2nd** | answer, cites `doc:ICARUS.md` only |
| Q2 "why is the eval corpus frozen" | **not retrieved** | unknown |
| Q3 "is there a free-tier serving path" | **not retrieved** | unknown |

Q1's answer is correct and complete: it lists all six load-bearing items, citing
nothing but the file. **This is the first time `ICARUS.md` has changed a live
answer.**

**The abstentions were never the writer declining.** The file was not in the
evidence. The gate and writer behaved correctly -- they cannot cite what
retrieval did not hand them.

The pattern is sharp and it is the whole finding: **Q1's phrasing is verbatim
the file's section heading.** Q2 and Q3 use vocabulary that matches real
`evals/` and `demo/server.py` source far better than prose about it.
`ICARUS.md` is retrieved when a question echoes its own headings and vanishes
when it does not. This is the seventh measurement of the intent-shaped recall
problem in [[Learning]], now on the repository's own context file.

### T2 -- does it still abstain? PASSES

Both unrecorded questions abstained, before and after the fixture fix. The file
did not make the system more confident everywhere, which was the failure mode
that would have been a product defect rather than a disappointment.

### Found while diagnosing: 24.4% of the corpus was somebody else's code

Not what this run was looking for. `evals/fixtures/` holds source copied
verbatim from simonw/llm, facebook/react-native and bluesky-social/social-app so
the chunking evals stay deterministic. It was indexed as ordinary `code:`
evidence: **383 of 1,568 chunks**. Not harmless volume at the bottom of the
ranking -- Q3 put `fixtures/ast_chunking_eval/llm/cli.py` TWICE in its top eight
while `ICARUS.md` was absent.

Fixed: `fixtures` added to `_DENY_DIR_SEGMENTS` (`evals/ingest.py`), same
judgment already made for `vendor`. Six tests in `evals/test_ingest_files.py`,
proven red->green by reverting the one-line change and watching 3 fail. Suites
green: evals 952, demo 668.

| | before | after |
|---|---|---|
| total chunks | 1,568 | **1,185** |
| `code` | 811 | **431** |
| fixture chunks | 383 | **0** |

**47% of what Icarus believed was this project's code was another project's.**

### The fix did NOT fix what motivated it

Re-ingested and re-asked. `ICARUS.md` rank for Q2 and Q3: **still not retrieved.**

- **Q1** unchanged: rank 2, answers, cites the file.
- **Q2** flipped `unknown` -> `answer`, but cites `code:evals/corpus.py`, not
  `ICARUS.md`. The answer ("generated once by ingest.py and committed so
  evaluations run offline and reproducibly") is *true and shallow*: it misses
  the recorded reason -- pinned to `simonw/llm @ 94769b8`, permanently behind
  upstream on purpose, `pinned: true` so the choice does not read as neglect.
  **Removing the noise made this question answerable from code without ever
  reaching the recorded rationale**, which is arguably worse than the honest
  abstention it replaced.
- **Q3** still `unknown`, file still absent.
- **Q4** still abstains. T2 holds after the change.

Cleaning a quarter of the corpus was a real fix to a real defect **and it did
not move the thing it was meant to move.** Recorded as such rather than quietly
credited, per PROTOCOL §4.

### Writer non-determinism, observed

Q3 returned `unknown`, then `answer`, then `unknown` across three runs of the
identical question against the identical corpus. Recorded, not smoothed.

### Prediction versus outcome

| # | Registered | Outcome |
|---|---|---|
| 1 | T1 passes, high confidence | **WRONG.** 1 of 3 |
| 2 | T2 passes | **RIGHT** |
| 3 | T3: the file beats the code | **WRONG, more decisively than predicted.** The file does not compete at all -- it is not retrieved. On Q2 the code won by default. T3 as designed is untestable until retrieval reaches the file |
| 4 | T4: privilege NOT justified | **WEAKENED.** See below |

### T4 -- the deferred decision, with the measurement in hand

My prediction was that the truncation fix had already answered the case for
privileging `ICARUS.md` by name. **The measurement weakens that.** Truncation was
never the binding constraint: the file now arrives whole and is still not
retrieved for two questions out of three that it answers. The general routes are
close to exhausted -- [[Learning]] records six measurements where intent-shaped
recall did not yield to retrieval tuning, and a 24% corpus cleanup did not move
it either.

**Not decided here.** Deciding it inside the run that produced the evidence is
the mistake this protocol exists to prevent. What is now on the table that was
not before: privilege is no longer a shortcut around a fixable general problem,
because the general problem has resisted seven measurements. The cost is
unchanged -- a file that always wins also wins when it is wrong, and
`ICARUS.md` itself says the code is authoritative.

### Consequence for public claims

Nothing public currently claims `ICARUS.md` changes answers, so nothing needs
softening today. **Do not start claiming it.** The supportable claim is narrower:
the file is ingested, citable, and answers questions phrased close to its own
headings. Anything stronger is not measured.
