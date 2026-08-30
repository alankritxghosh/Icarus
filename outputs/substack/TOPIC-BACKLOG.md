# Substack topic backlog

Built 2026-08-23 from material already in the repo and the vault. **Nothing here
is invented.** Every entry names the file its evidence lives in. If a topic
cannot name one, it does not belong on this list.

Form target: Kamath, per `2026-08-23-style-analysis-four-writers.md`. Short,
first person plural where it fits, exact when exact numbers exist, explicit
about what is unknown, negative space defined, real ask at the end.

---

## The through-line

**"Things I measured that turned out backwards."**

This is not a theme chosen for tidiness. It is what the material already is.
Nearly every durable entry in `Learning.md` is a case where the intuitive answer
inverted under measurement:

- a fabrication scores *higher* on evidence-overlap than an honest paraphrase
- a system that fails *safe* hides its own bugs
- a closed pull request usually does *not* mean the team said no
- the top contributor usually *cannot* merge
- 1,283 decisions were *62* decisions
- a merged commit is evidence something happened once, not that it is *still true*
- a checklist that exists and is not run is *worse* than none, because it gets cited

An editorial identity that is a property of the evidence, rather than a register
borrowed from someone else, is the one thing on this list that cannot be copied
by a better writer with no measurements.

---

## Drafted already

1. **The detector that scored the lie higher than the truth** —
   `2026-08-23-01-detector-anticorrelated.md`. 1,235 words.
2. **Every rule in my protocol exists because I broke it first** —
   `2026-08-23-02-protocol-one-rule-per-failure.md`. 1,207 words.

---

## Tier 1 — write these next

### 3. A citation can be real and still be about the wrong thing
The flagship. **The same lesson learned three separate times, each with every
citation resolving so nothing downstream flagged it:** a fabricated Redis
`HYPERVECTOR` type grounded to adjacent real vector-set code; a line selection
in an httpx helper answered with a correctly-cited Pydantic v1/v2 decision; the
`..` path rule that does not exist. Ends on the honest boundary — groundedness
is provable in code, entailment is not, and saying so is the product's actual
guarantee.
*Source: `Learning.md` § Groundedness ≠ relevance ≠ truth; `evals/gate.py` guard (c).*
**Why now:** it is the single most reusable idea in the vault and it pairs with
article 1 rather than repeating it. Article 1 is one failed detector; this is
the class.

### 4. The bug that made my system look more honest
Two defects made Icarus abstain on code it demonstrably knew: a 1,500-char
prompt truncation cutting code windows to about 40 lines, and a gate rejecting
citations the writer had merely reformatted. Both failed *safe*, so both read as
integrity rather than as defects. 0 of 3 to 3 of 3 after the fix, gates still
100%.
*Source: `Learning.md` § Fail-safe bugs look like honesty.*
**Why now:** counter-intuitive, mechanically explicable, and it generalises to
any system with a conservative default. A reader with a retry loop or a
circuit breaker has this bug and does not know it.

### 5. Closed does not mean rejected
60 pull requests read on one repo: 11 closed without merging, and only **2** had
a reviewer asking for changes. 3 were approved and closed anyway. Separately, a
nine-PR tally where 8 of 9 closed-unmerged PRs meant *already done another way*.
Plus the second axis: `review_required` is not evidence nobody reviewed — a
dismissed approval, a resolved change request and a plain comment all land there.
*Source: `evals/attempts.py`; `Agent Mode.md` C2 tally; the meilisearch-swift dogfood record.*
**Why now:** this is the wedge stated as a fact about GitHub rather than a claim
about the product, and it is the material that earned replies from real
engineers this week.

### 6. Where the answer actually lives
7 questions asked across 10 real public repositories, and the citations that
answered them counted by source: **58 from commits, 17 from pull requests, 14
from issues, 2 from documentation, 1 from code.** 89 of 92 came from history.
Includes the honest half: 24 of 70 steps abstained, and every abstention was the
writer declining rather than the gate firing.
*Source: `evals/onboarding_probe.py`, first run 2026-07-29.*
**Why now:** it is the measurement behind the entire thesis and it has never
been published anywhere.

---

## Tier 2 — strong, needs an angle decision

### 7. Retrieval that fails on intent, not on words
Phrasings that name the identifier or describe the task rank the gold evidence
**1st**. Phrasing that shares no vocabulary with the evidence misses entirely.
Six measurements, and the honest ending is that ranking tuning did not fix it.
*Source: `evals/test_description_recall.py`; `Learning.md` § Intent-shaped recall.*
**Open:** this is a negative result about our own retrieval. Frame as a property
of embedding search generally, which it is, or it reads as a product weakness.

### 8. Every generic resolver I wrote fabricated confidently
A generic import resolver invented a `pkg -> demo` edge across 566 files of
lazygit, sitting indistinguishable among true edges. Resolving a Go package to
its alphabetically-first file made **18.1% of sampled edges wrong**. Fixed by
splitting package edges from file edges; final measurement **199 sampled edges,
0 unverified**. None of the three fabrications were caught by unit tests — all
three came from sampling output against real source.
*Source: `docs/HANDOFF.md:2786-2818`; `demo/structure.py`.*
**Why it is good:** the lesson is that you cannot unit-test your way to
truthfulness about a codebase you did not write. Landed as a reply to Debasish
Ghosh this week and fits his exact argument.

### 9. The code will match itself
Entry-point detection returned **70 entry points** on this repo because
`if __name__ == "__main__": unittest.main()` is boilerplate in every test file.
The detector module also matched *itself*, because it holds the guard string as
a literal. Same class as a commit-SHA regex firing on the hex-shaped English
word "defaced".
*Source: `Learning.md` § The code will match itself; `demo/entry_points.py`.*
**Angle:** short, funny, genuinely useful to anyone writing static analysis.
Good candidate for the shortest piece on the list.

### 10. A test that passed with the bug put back
A guard test in `demo/test_structure.py` was found vacuous: its decoy was a
`.yml` file rejected by the language filter before the rule under test was ever
reached, so it passed with the bug deliberately reintroduced. Pairs with the
checker whose `--selftest` exists precisely to prove it can fail before a pass
means anything.
*Source: `Learning.md` § Guards can be vacuous; `scripts/check_detailed_index.py`.*
**Angle:** every engineer has written one of these. Almost nobody has gone
looking.

### 11. A number that is technically true and rhetorically false
1,283 pull requests closed without merging on a mocking library. Filter bot
authors: **62**. 95% was dependabot and renovate. Two more repos: 449 to 163,
145 to 24. Separately, 41% of 172 checked open-source contacts could not merge
anything, and on one repo a single maintainer had merged all 100 PRs sampled.
*Source: `Learning.md` § A raw count is not a human count, § Activity is not authority.*
**Open:** both findings came out of building a prospect list. Write it as a
finding about GitHub data, never about our outreach — the no-failure rule.

---

## Tier 3 — real, lower priority

### 12. An agent reads a tool description as a trigger, not a description
0 calls across 11 sessions when the description said what the tool held. 1 in 4
after it named the moments instead. Same tool, same model, one repo.
*Source: `docs/experiments/2026-08-25-agent-mode-c2-rerun-fresh-sessions.md`.
The earlier 4-of-4 figure ran all four tasks in ONE session and is retired; do
not quote it. The re-run with four independent sessions measured 1 of 4.*
**Caveat already recorded:** the first version of this was rejected on X for
being a changelog of our own tooling. Must be written as the general lesson.

### 13. A commit is evidence something happened once, not that it is true now
Plus its sibling: a branch list is a to-do list that lies.
*Source: `Learning.md`, two adjacent entries.*

### 14. 76% of tractable open-source issues are already taken
*Source: `Learning.md`.* A finding about open source contribution, useful to
anyone trying to start.

### 15. Three tools, three disjoint noise sets, one real find
*Source: `Learning.md`.* On why running one scanner tells you almost nothing.

---

## Deliberately not on this list

- **The 60-second timeout.** Real and well-documented, but it is our own adapter
  defect. Closest thing on the list to a confession, and the no-failure rule in
  `Decision History.md` governs. Revisit only if it can be written purely as a
  finding about latency distributions straddling timeouts.
- **A comparative claim needs the comparison to exist.** Written 2026-08-23 and
  too raw — it is about a live post.
- **A measurement that cannot see a channel reports it as zero.** The mechanism
  is excellent and the numbers behind it are our own outreach results. Only
  publishable stripped of every business figure.
- **The six-month posting gap.** Listed in `X Content.md` § Ideas. It is a
  personal story with no measurement and it discloses inactivity.

---

## Sequencing recommendation

Publish **1 and 2 first** — they exist. Then **3**, because it is the flagship
and it converts the first two from anecdotes into a position. Then **5** and
**6**, which are the wedge stated as facts about GitHub rather than claims about
a product.

**Do not publish more than one piece a week until there is data.** Nothing in
the vault measures long-form at all. Two articles is a sample of zero.

---
---

# Part 2 — non-technical topics (added 2026-08-23)

Alankrit's call: deep-tech essays are the wrong opening for this publication
right now. **His own X data supports it** — personal posts measured 178, 154 and
123 views against 59, 33, 22 and 13 for product posts, and both replies the
account has ever received came from the personal pillar (`X Content.md` § What
the numbers suggest).

## The trap to avoid, stated first

The failure mode is drifting into generic self-development. That genre is
occupied by Koe and Shamani, who win it on standing and observation quality
neither of which is available at 14 followers. **A piece with no evidence and no
standing is invisible.**

The edge in a non-technical piece is the same as in a technical one: he actually
did the thing and wrote down what happened. The genre changes; the evidence
requirement does not. Every topic below is grounded in something real.

---

## Genre A — working with an AI colleague you cannot trust

The biggest mainstream subject he has genuine, daily, unusual authority on, and
it needs zero systems detail to write.

**A1. Verification became my whole job.**
The work did not get faster in the way people describe. It moved. Writing code
stopped being the bottleneck and checking it became one. Concrete anchors that
need no internals: an agent's own account of its work disagreed with the record
three times; a control agent declared a live bug fixed because only the merge
was visible; a fix that shipped and was not checked against the case that
motivated it until a day later.
*Real, and none of it requires explaining retrieval.*

**A2. What I stopped delegating, and why.**
The negative space piece, in Kamath's exact shape. Things an agent does well,
things it does confidently and badly, and the specific tasks that came back
in-house after being tried. Honest, useful, and unavailable to anyone who has
not actually run the experiment.

**A3. The confident wrong answer is the expensive one.**
A wrong answer that looks uncertain costs a minute. A wrong answer delivered
fluently costs a day, because you build on it. Anchor: the reply that was true
in every clause and wrong in its first word.
*Source: `evals/test_writer_uses_evidence.py`.*

---

## Genre B — the one-person company

His highest-reach material historically, and the vault is full of process nobody
else documents.

**B1. I write down every decision and the reason. Here is what it caught.**
Not a productivity essay — a working method with receipts. The vault/repo split,
one home per item, the rule that an unwritten lesson gets paid for twice.
Concrete: it caught a rebuild of something already deleted, and a re-decision of
something already settled.

**B2. Working alone is not the same as being free.**
Already the account's single highest-reach post as one line (178 views). Never
expanded. The honest version: what the freedom actually costs, and what nobody
tells you about being the only person who can decide anything.

**B3. I am not the strongest traditional developer.**
The second-highest performer (123 views), also never expanded. What shipping
fast actually substitutes for, and where it stops working. Koe's
self-implication move, except true and specific.

**B4. The two-hour decision I have made four hundred times.**
On decision fatigue as the real constraint of solo work, not time.

---

## Genre C — building something that admits it does not know

Business and ethics, not architecture. This is Kamath's register almost exactly
("to run a brokerage is to live with contradictions").

**C1. I built a product that says "I don't know", in a market that never does.**
The commercial cost of that decision, stated plainly: it demos worse. A
competitor that guesses looks better in every thirty-second comparison. Why it
is still the right call, and the exact thing it buys.

**C2. The contradiction I have not resolved.**
Straight Kamath. Name a real live tension and do not resolve it. Candidates in
`Unknowns.md`: whether the people who most need this are the ones least able to
buy it; whether the honest answer is the one anyone actually wants.

**C3. Overclaiming is the same sin as bluffing.**
The rule from `Product Philosophy.md` applied outward — to marketing copy,
benchmarks, launch posts and demos. **He has a live instance from 2026-08-23.**
Whether it is publishable turns on the no-failure rule, and the general version
is publishable without the instance.

---

## Genre D — how anyone should read a claim

Broad audience, no code, and the discipline is genuinely his.

**D1. Read the digits back.**
The practice of checking every number against its source before repeating it,
and what happens when you do not. Generalises to journalism, investing,
anything.

**D2. The checklist you wrote and did not run.**
`Learning.md`, 2026-08-23. A rule that exists but is skipped is worse than no
rule, because it gets cited as though it ran. Zero code required.

**D3. Nobody publishes the thing that did not work.**
On negative results as an asset rather than an embarrassment, across fields.
The generalised version of article 1 for a non-technical reader.

---

## Genre E — India, and building for a market you are not in

Nobody in the reference set writes this, and it is his by default.

**E1. Building a developer tool from India for a market that is not here.**
Timezones, credibility, the specific asymmetries. Real and unwritten.

**E2. What a cold email taught me about how engineers read.**
The five-second test, why the elaborate personalised version lost to the short
direct one, what a maintainer decides in the first line. **Governed by the
no-failure rule — the findings are publishable, the zeros are not.**

---

## Recommendation

Open with **A1**. It is the largest live subject on the internet right now, he
has unusual first-hand authority on it, it needs no systems knowledge, and it
still carries evidence — which keeps the publication's identity intact from the
first piece rather than establishing a voice that later has to change.

Then **B2** and **B3**, which are the two highest-reach things he has ever
written and have never been more than one line each.

Hold the technical backlog in Part 1. It becomes publishable once there are
readers who arrived for A and B; it is not deleted, it is sequenced.
