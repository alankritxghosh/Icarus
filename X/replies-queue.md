# Reply queue — E1, batch 1

**These are payloads, not aimed replies.** I have no live view of your feed, so
inventing five specific parent posts would be fabrication. Each one below is
self-contained, carries a number nobody else has, and fires on a trigger you
will see within a day of scrolling.

## Rules for every one of these

- **No link. No product name unless asked.** A reply that pitches gets read as
  spam and costs the follow. Every one of these lets someone click your name to
  find out who measured it — that is the whole mechanism.
- **Never lead with agreement.** "Great post" is noise; it is also the exact
  register `CLAUDE.md` forbids.
- **Sample size stays in the sentence.** "on one repo", "across 11 tasks".
- **Do not force a fit.** If the parent post is not actually about the trigger,
  skip it. A wrong-fit reply reads as a bot and there is no recovering the
  impression.
- **Reply within ~30 minutes of the parent going up.** Late replies sit below
  the fold and reach nobody, which defeats the entire point of the play.
- Log each send in `experiments.md` E1: parent handle, topic, which payload,
  and any follow that came of it.

## How to find the parents

Search these, sorted by Latest, and reply to real posts from accounts the
primary segment reads:
`AGENTS.md` · `CLAUDE.md context` · `MCP server tool` · `coding agent context`
· `agent memory` · `SWE-bench` · `"my agent" repo context` · `RAG citations
hallucination`

---

### R1 — A closed PR is being read as a rejection
**Fires when:** agent memory · repo context · git history · "agents don't know what was tried"
**Payload (232 chars):**

> I read 60 pull requests on one repo to check what "closed without merging" means. 11 were closed unmerged. Only 2 had a reviewer asking for changes. 3 were approved and closed anyway. Refused and abandoned are the same event in git.


### R2 — Someone is designing an MCP tool or writing tool descriptions
**Fires when:** MCP · tool design · "the agent never calls my tool"
**Payload (238 chars):**

> We measured this on one repo. Described by what the tool holds: 0 calls across 11 agent tasks. Described by the moments it applies - about to edit a file, about to open a PR: 1 in 4. An agent reads a description as a trigger condition, not a description.


### R3 — Someone shares their AGENTS.md / CLAUDE.md setup
**Fires when:** AGENTS.md · CLAUDE.md · repo context files
**Payload (213 chars):**

> There is a measurement on this. Across SWE-bench tasks and real repos, context files didn't generally improve success rates, and raised inference cost over 20%. Repository overviews helped least. arXiv:2602.11988.


### R4 — Hallucination detection, citation checking, "how do you know it didn't make it up"
**Fires when:** grounding · citations · hallucination detection
**Payload (253 chars):**

> I built a detector for this and deleted it. Scoring a sentence by lexical overlap with the sources it cites is anti-correlated with truth: a plausible fabrication is assembled from the evidence's own words, so it scores higher than an honest paraphrase.


### R5 — Someone quotes a big number mined from repos
**Fires when:** "I analyzed N repos" · open-source data threads
**Payload (223 chars):**

> Worth checking who produced the number. One repo showed 1,283 pull requests closed without merging. Nobody makes 1,283 decisions on a mocking library. Filter out bot authors: 62. 95% of the pile was dependabot and renovate.


---

## What these are actually for

Not impressions. **The endpoint is a primary-segment follower**, and the
mechanism is: a builder reads a number they cannot get anywhere else, clicks the
name, finds a bio that says "I post the measurements", and follows.

Every payload above is a piece of your own recorded work — R1 and R5 from the
vault's Learning notes, R2 from the C2 experiment, R3 a paper verified to
author and arXiv id, R4 a negative result we deleted. **None of it is
reproducible by anyone who did not do the work.** That is the only real
advantage this account has, and replies are the only place it currently gets
seen.

## Refill

When these five are spent, pull the next five from `content-pillars.md` — items
1, 2, 11, 14 and 16 are the strongest untouched ones. Keep the same shape:
number first, sample size in the sentence, no link, no pitch.
