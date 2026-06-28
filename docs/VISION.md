# Icarus — Product Vision

> The brain your engineering org wishes it had: ask it anything about your code,
> your pull requests, and the decisions behind them, and get a straight answer —
> spoken like a colleague, with the receipts one glance away, and an honest
> "I don't know" when no one ever wrote the reason down.

This document is the north star. It is intentionally bigger than what exists
today. Every brick we build is judged by one question: *does it move us toward
this, without breaking the one thing that makes it trustworthy?*

---

## 1. The product, in one sentence

A **conversational engineering brain** a company can buy — a privacy-first
assistant that learns a company's codebase and the history of decisions around
it well enough to answer *why*, *what*, and *how* in natural language, and that
always knows the difference between what it can prove and what it's guessing.

## 2. The scene we are building toward

An engineer holds a hotkey and speaks:

> "Why do we mock service requests with MSW instead of stubbing fetch?"

Icarus answers out loud, conversationally — a sentence or two, the way a senior
teammate would. At the same time, a translucent overlay shows the **grounding**:
the pull request, the review comment, the exact lines it drew from. The voice
carries the gist. The screen carries the proof. If no one ever recorded the
reason, Icarus says so — plainly — instead of inventing one.

That is the whole product: **fluent like Iron Man's JARVIS, but honest about what
it actually knows.**

## 3. The non-negotiable: it cannot bluff

Language models produce confident, fluent, wrong answers in the same voice they
use when right. So the citation is not decoration; it is the **trust mechanism**.

Our rule, forever:

- **Citations don't have to be spoken — they have to exist.** Voice delivers the
  gist; the overlay shows the evidence on demand.
- **The spoken claim may only summarize evidence the system actually retrieved.**
  It never answers from a model's memory. The visible evidence is the leash; any
  drift between what is said and what is shown is exposed on screen, by design.
- **"I don't know" is a feature, not a failure.** When the reason was never
  recorded, Icarus says so. This is the single behavior that earns an engineer's
  trust on the *second* hard question — and the thing a pure fluent assistant
  gets catastrophically wrong.

## 4. Three axes, one product

Icarus is one brain, grown along independent axes. Confusing "different surface"
with "different product" is the trap.

| Axis | Version 1 | Later |
|------|-----------|-------|
| **Core engine** (honest retrieval: cite-or-unknown) | the defensible core + grounded conversational synthesis | deeper structural understanding |
| **Data sources** (what it knows) | **GitHub** (PRs, reviews, merges, reverts) | Slack, Linear, Notion, org-wide |
| **Interface** (how you talk to it) | **macOS app + voice (hotkey) + overlay** | team surfaces, web |
| **Deployment** (where compute runs) | per-company private cloud (+ a local tier where required) | managed multi-tenant for lower-trust segments |

The core engine is the slow, defensible, expensive part — and it is
interface-agnostic, source-agnostic, and deployment-agnostic. Voice is the
*dangerous* axis, because it smuggles in model calls and the temptation to guess
— so the talker is only ever built on top of a brain that is already incapable
of bluffing.

## 5. Why this is a cloud product (and still private)

The promise is **not** "nothing ever leaves the device." The promise is **"your
code stays inside your trust boundary, and we never train on it."**

A big company codebase, a good language model, and fast voice are too heavy for
one laptop — they would be slow and drain the battery, and every engineer would
get a different experience based on their hardware. So the heavy thinking runs in
the cloud. But it runs in a space **rented privately per company**, walled off
from every other customer, under written guarantees:

- **Never trained on customer code.**
- **Discarded after each request** (zero-data-retention).
- **Real compliance** (SOC 2, ISO 27001, and BAAs where needed).

A **local tier** stays available for the most regulated / air-gapped customers —
degraded but still honest. Cite-or-unknown never degrades, on any tier.

See [ARCHITECTURE.md](ARCHITECTURE.md) for how the face/brain split makes this work.

## 6. What "knowing the org" really means (and its honest ceiling)

The goal is for Icarus to know a codebase as well as anyone who has touched it.
But the most valuable "why" often lives in a Slack thread, a postmortem, or
someone's head — never committed. **You cannot retrieve what was never recorded.**

So the brain has two jobs:

- **Recall** everything that *was* written down, across more history than any
  human can hold — and cite it.
- **Capture** the why at the moment it happens (PR descriptions, decision
  prompts) so it *enters* the corpus. Part of the product's job is to make the
  org write things down.

We claim superhuman *recall*, never superhuman *omniscience*. That honesty is
the brand.

## 7. Experience principles

- **Talks first, proof one glance away.** Conversational by default; never a
  paragraph of citations read aloud.
- **The unknown state is beautiful, not apologetic.** "No recorded reason found,"
  plus what it looked at — a first-class screen.
- **Push-to-talk, never always-listening.** Icarus listens only while you hold
  the key. Privacy is a posture, not a setting.
- **Speed is load-bearing.** The hotkey → speak → answer loop must feel
  immediate, or the magic dies — a legitimate reason to run heavy inference in
  the cloud.
- **The model transforms, it never invents.** The conversational layer rephrases
  retrieved, cited evidence into a natural answer. It is never allowed to answer
  from training memory.
- **Show your work, don't hide it.** "Here is my proof," not "hidden from the
  room."
- **Never capture the screen silently.** If Icarus ever reads on-screen context,
  it must be explicit, opt-in, and never silently uploaded.

## 8. What this is NOT (so we don't drift)

- Not an autonomous coding agent.
- Not a confident chatbot that answers from training memory.
- Not a multi-tenant cloud service that pools or trains on a company's source by
  default.
- Not a product that hides its reasoning or pretends to know what it doesn't.
- Not a silent screen-watcher.
- Not Alankrit's personal memory system. Personal and commercial contexts stay
  isolated, always.

## 9. How we'll know we're winning

- An engineer asks a hard "why" and gets a correct, cited answer in seconds — and
  trusts it because they can see the receipt.
- The *second* time Icarus says "no one recorded this," the engineer trusts that
  too.
- New hires ramp by *talking to the codebase* instead of interrupting senior
  engineers.
- The org starts writing decisions down because Icarus makes that knowledge pay
  off.

See [METRICS.md](METRICS.md) for how each of these becomes a number.

---

*This vision is fixed in direction and flexible in path. We build toward it one
honest brick at a time, and we never trade away the one property that makes it
worth trusting: it knows the difference between what it can prove and what it's
guessing.*
