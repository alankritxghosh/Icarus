# Fabrication recheck — does the shipped per-claim self-report catch Experiment A's fabrication?

Date: 2026-08-11
Repo: `astral-sh/uv` @ `a50af60` (re-ingested today; Experiment A ran against
`1881d307`, so this is a different corpus of the same repo)
Queued by: HANDOFF 2026-08-11, §5 open item 2.

## The question

Experiment A run 1 produced the one fabrication across four measured tasks:
Icarus asserted that absolute paths are preserved *"when a relative path would
require traversing outside the project root (e.g. starting with `..`)"* — a
rule that does not exist at HEAD. Every citation resolved, so the honesty gate
passed it (groundedness proves evidence is real, not that the answer follows
from it).

`per_claim` / `attribute_claims` (`0f5a313`) shipped later the same day. Nobody
had checked whether it would flag that sentence. This is that check.

## Method

One `/ask` against the live Azure brain with the same body the MCP adapter
sends (`include_evidence: true, per_claim: true`), via a short-lived app-issued
agent session. Verdict `answer`, not indexing.

Caveat: the original question's exact wording was never logged — only its
substance ("what constraints exist on relative paths"). The question used here
was reconstructed: *"What constraints exist on when a relative path is
preserved as relative versus written as an absolute path in uv.lock?"*

## Result — the fabrication reproduced, and it was labelled `quoted`

Answer, sentence 2, near-verbatim to run 1:

> Additionally, absolute paths are preserved if the relative path would require
> traversing outside the project root (i.e., starting with '..').

Self-report for that sentence:

```
label='quoted'  citations=[pr:17122]
```

`quoted` is the label a reader is told to *trust* — the tool description tells
the agent that `composed` sentences are the ones to verify. **The fabrication
is not flagged. The gap is real and still open.**

For completeness, sentence 1 was also `quoted`, on
`commit:eec8048…`; those two chunks were the only gate-verified citations.

## Why this is worse than "the defense missed one"

Run 1 diagnosed the fabrication as an over-generalisation *across two real
sources* (`pr:17122` + `issue:15417`). That framing is what makes a
`composed` label sound like the right defense. **The writer does not agree with
that diagnosis.** It self-reports a single source, so the sentence is
structurally indistinguishable from an honest restatement.

So `composed` is aimed at the wrong shape. A writer that fabricates by
over-reading ONE chunk reports one ref and gets the trusted label. The
self-report is evidence, not proof — documented in the code — and this is that
limitation landing on the exact case it was hoped to cover.

What `pr:17122` actually says (its indexed excerpt):

> "fix: preserve absolute paths in lockfile when user specifies absolute
> find-links [CLOSED by majiayu000]"

It is about honouring an absolute path the **user wrote**. It says nothing
about `..` or the project root. The sentence is a real citation to a real
chunk that does not state the claim.

## Second finding, not previously recorded

`pr:17122` is **CLOSED WITHOUT MERGING** — it appears in this same payload's
own `rejected_attempts` list, alongside `pr:15870` and `pr:17316`. The answer
therefore rests a claim about *current behaviour* on a proposal that was
refused. Nothing in the gate, the self-report, or the claim label notices that
the cited chunk is a rejected attempt rather than shipped behaviour, even
though the payload already computes exactly that fact one field away.

That is a cheap, deterministic signal that exists today and is not wired into
anything: **a claim whose only citation is a closed-unmerged PR should not read
as a statement of how the system behaves.**

## Status of the queued item

HANDOFF §5 item 2 is answered: **not covered**. The already-shipped mechanism
does not flag this fabrication class. Two concrete follow-ups, neither built:

1. The `quoted`-vs-`composed` split does not separate honest restatement from
   single-source over-reading. Whether anything cheap can, is open.
2. Cross-referencing claim citations against `rejected_attempts` is cheap,
   deterministic, and currently unwired.
