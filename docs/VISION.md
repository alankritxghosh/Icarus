# JARVIS Engineering Intelligence — Product Vision

> The brain your engineering org wishes it had: ask it anything about your code, your
> pull requests, and the decisions behind them, and get a straight answer — spoken like a
> colleague, with the receipts one glance away, and an honest "I don't know" when no one
> ever wrote the reason down.

This document is the north star. It is intentionally bigger than what exists today. Every
brick we build is judged by one question: *does it move us toward this, without breaking
the one thing that makes it trustworthy?*

---

## 1. The product, in one sentence

A **conversational engineering brain** — a privacy-first assistant that understands a
company's codebase and the history of decisions around it well enough to answer *why*,
*what*, and *how* in natural language, and that always knows the difference between what it
can prove and what it's guessing.

## 2. The scene we are building toward

An engineer holds a key, speaks into their mic:

> "Why do we mock service requests with MSW instead of stubbing fetch?"

JARVIS answers out loud, conversationally — a sentence or two, the way a senior teammate
would. At the same time, a translucent overlay on screen shows the **grounding**: the ADR,
the pull request, the review comment, the exact lines it drew from. The voice carries the
gist. The screen carries the proof. If no one ever recorded the reason, JARVIS says so —
plainly — instead of inventing one.

That is the whole product: **fluent like Iron Man's JARVIS, but honest about what it
actually knows.**

## 3. The non-negotiable: it cannot bluff

The movie's JARVIS speaks without citations because the story makes it infallible. Real
systems are not infallible — language models produce confident, fluent, wrong answers in
the same voice they use when right. So the citation was never decoration; it is the
**trust mechanism**.

Our rule, forever:

- **Citations don't have to be spoken — they have to exist.** Voice delivers the gist;
  the overlay shows the evidence on demand.
- **The spoken claim may only summarize evidence the system actually retrieved.** It never
  answers from a model's memory. The visible evidence is the leash; any drift between what
  is said and what is shown is exposed on screen, by design.
- **"I don't know" is a feature, not a failure.** When the reason was never recorded,
  JARVIS says so. This is the single behavior that earns an engineer's trust on the second
  hard question — and the thing a pure fluent assistant gets catastrophically wrong.

A brain that talks beautifully but can't tell when it's wrong is a liability with a great
voice. We are building the opposite.

## 4. Three axes, one product

The vision is not three different products. It is one brain, grown along three independent
axes. Confusing "different surface" with "different product" is the trap.

| Axis | Today | Next | Later |
|------|-------|------|-------|
| **Core engine** (honest retrieval: cite-or-unknown) | ✅ the defensible core | grounded conversational synthesis on top | — |
| **Data sources** (what it knows) | local Git checkout | **GitHub** (PRs, reviews, merges, reverts) | Slack, Linear, Notion, org-wide |
| **Interface** (how you talk to it) | terminal (CLI) | macOS app | voice (ctrl-to-talk) + overlay |
| **Deployment** (where compute runs) | local | local + customer-cloud | local / customer-cloud / managed |

The core engine is the slow, defensible, expensive part — and it is interface-agnostic,
source-agnostic, and **deployment-agnostic**. The macOS app is mostly packaging (the product
is already a library with a thin CLI on top). Voice is the *dangerous* transition, because it
smuggles in model calls, conversational synthesis, and the temptation to guess — so it comes
last, on top of a core that is already incapable of bluffing.

**Where inference runs is a deployment choice, not a core-engine change.** Heavy synthesis
and voice will outgrow most laptops, so that work can run in the cloud — but moving *compute*
to the cloud must never mean moving *ownership* of a customer's source out of their trust
boundary (see §8).

## 5. Build order (each layer inherits "can't lie" from the one below)

1. **Honest retrieval core.** Find recorded evidence, cite it, or say unknown. *(Exists.)*
2. **Widen the evidence — GitHub first.** PR descriptions, review comments, approvals,
   merge & revert events, linked issues. Still pure retrieval + citation. This is where
   "why was this PR made / merged / reverted" becomes answerable — when it was written down.
3. **Structural understanding.** Parse enough of the code to answer "what uses X" with
   verifiable evidence, instead of refusing it.
4. **Grounded conversational synthesis.** A model that speaks in natural language but only
   over retrieved, cited evidence — it *transforms* findings into a colleague-style answer,
   it does not generate facts from memory. This is the deliberate crossing into model calls,
   and the first layer that may run on cloud compute (under §8's trust rules).
5. **The surfaces.** macOS app with a visible evidence panel; voice with ctrl-to-talk and
   the translucent grounding overlay.

We never build the talker before the brain it speaks for.

## 6. What "knowing the org" really means (and its honest ceiling)

The goal is for JARVIS to know a codebase as well as anyone who has touched it. But the
most valuable "why" often lives in a Slack thread, a postmortem, or someone's head — never
committed. **You cannot retrieve what was never recorded.**

So the brain has two jobs, not one:

- **Recall** everything that *was* written down, across far more history than any human can
  hold — and cite it.
- **Capture** the why at the moment it happens (PR descriptions, decision prompts) so it
  *enters* the corpus. Part of the product's job is to make the org write things down.

We claim superhuman *recall*, never superhuman *omniscience*. That honesty is the brand.

## 7. Experience principles

- **Talks first, proof one glance away.** Conversational by default; never a paragraph of
  citations read aloud. The evidence is always present, never shoved in your face.
- **The unknown state is beautiful, not apologetic.** "No recorded reason found" plus what
  it looked at — designed as a first-class screen.
- **Push-to-talk, never always-listening.** JARVIS listens only while you hold the key.
  Privacy is a posture, not a setting.
- **Speed is load-bearing.** The ctrl→speak→answer loop must feel immediate, or the magic
  dies. This favors local caching and fast speech — and is a legitimate reason to run heavy
  inference in the cloud (the validated path: Wispr Flow went cloud *specifically* for speech
  speed and accuracy).
- **The model transforms, it never invents.** The conversational layer rephrases retrieved,
  cited evidence into a natural answer — like Wispr Flow's cleanup model reformatting a
  transcript without adding facts. It is never allowed to answer from training memory.
- **Show your work, don't hide it (anti-Cluely brand).** Same translucent-overlay UI
  pattern, opposite posture: "here is my proof," not "hidden from the room."
- **Never capture the screen silently.** If JARVIS ever reads on-screen context, it must be
  explicit, opt-in, and never silently uploaded. (Wispr Flow's periodic active-window
  screenshots are its single biggest trust flashpoint — for an engineering product, silent
  screen capture could sweep up other companies' code and secrets. We do not repeat it.)

## 8. Privacy and trust posture

The promise is **not** "nothing ever leaves the device." The promise is **"your code stays
inside your trust boundary, and we never train on it."** Those are different guarantees, and
the second is the one that actually earns a software company's trust. Holding that promise is
what lets us move compute to the cloud (which we must, for heavy synthesis and voice) without
giving up the moat.

**Deployment is a spectrum, and where we draw the line is the whole game:**

- **Local.** Everything on the user's machine. Maximum privacy, limited by hardware. We keep
  this tier deliberately — it is the wedge against cloud incumbents and the only option the
  most regulated / air-gapped customers will accept. (A degraded-but-still-honest small-model
  tier counts; cite-or-unknown never degrades.)
- **Customer-cloud / single-tenant (the default target for heavy work).** Inference runs in
  the customer's own cloud or an isolated single-tenant environment. Compute is solved; the
  source never enters a shared pool.
- **Managed multi-tenant.** Easiest UX, largest liability — we hold the code. A deliberate,
  later, eyes-open choice for lower-trust segments only, **never the foundation.**

**The cloud trust mechanism (proven in-market by Wispr Flow):** when compute is remote, trust
is held by *controls*, not by architecture — **zero-data-retention mode, never train on
customer data, discard-after-request, and real compliance (SOC 2, ISO 27001, BAA where
needed).** This is exactly how a cloud-only voice product won a privacy-sensitive category.
Our customer's asset (source code + decision history) is far more sensitive than dictated
text, so these controls are the floor, not a premium add-on.

- **Personal and commercial contexts stay isolated.** Personal memory systems are never
  mixed into the commercial product.
- **A credential is a responsibility.** As we add integrations (GitHub first), each new
  credential and each byte that leaves the trust boundary is a deliberate, minimized decision.

## 9. What this is NOT (so we don't drift)

- Not an autonomous coding agent.
- Not a confident chatbot that answers from training memory.
- Not a multi-tenant cloud service that pools or trains on a company's source by default.
- Not a product that hides its reasoning or pretends to know what it doesn't.
- Not a silent screen-watcher.

## 10. How we'll know we're winning

- An engineer asks a hard "why" and gets a correct, cited answer in seconds — and trusts it
  because they can see the receipt.
- The *second* time JARVIS says "no one recorded this," the engineer trusts that too.
- New hires ramp by *talking to the codebase* instead of interrupting senior engineers.
- The org starts writing decisions down because JARVIS makes that knowledge pay off.

---

*This vision is fixed in direction and flexible in path. We build toward it one honest
brick at a time, and we never trade away the one property that makes it worth trusting:
it knows the difference between what it can prove and what it's guessing.*
