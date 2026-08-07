# Icarus — Product Vision

> The brain your engineering org wishes it had: ask it anything about your code,
> your pull requests, and the decisions behind them, and get a straight answer —
> spoken like a colleague, with the receipts one glance away, and an honest
> "I don't know" when no one ever wrote the reason down.

This document is the north star. It is intentionally bigger than what exists
today. Every brick we build is judged by one question: *does it move us toward
this, without breaking the one thing that makes it trustworthy?*

**Positioning:** *"Git remembers what changed. Icarus remembers why."* We do not sell
"AI that explains repositories" — explanation is the **wedge** that earns trust. The
product is **organizational memory**: the *why* behind a codebase, preserved against the
churn of people leaving. People buy reduced onboarding, preserved institutional knowledge,
faster debugging, and confidence to change things — not explanations. See
[decisions/2026-06-30-organizational-memory-positioning.md](decisions/2026-06-30-organizational-memory-positioning.md).

**The category, longer term:** every serious attempt to let AI act on a
company's own operational knowledge — handling refunds, incident response,
pricing exceptions — eventually needs a foundation it can trust: knowledge
that's provably grounded, not confidently synthesized. Icarus's honesty
discipline (cite-or-unknown, proven in code, not just claimed) is that
foundation, built first on the hardest, most structured slice of a company's
knowledge — its codebase — because GitHub gives provenance no Slack thread or
email chain ever will. We are not building a general company brain today; we
are building the trust primitive one will eventually require.

---

## 1. The product, in one sentence

**Icarus is your company's engineering memory.** It reconstructs why systems
became the way they are from code, pull requests, reviews, and recorded
decisions—with evidence a person can verify and an honest unknown when the
reason was never recorded.

**The ideal one-sentence journey:** before an engineer or coding agent makes a
meaningful change, Icarus supplies the repo-scoped recorded why and its evidence
— or clearly states what it found and what remains unknown — then gets out of
the way.

### The engineering-memory loop

The product is not complete when it finds nothing. That unknown becomes a
visible Memory Gap:

1. An engineer asks a real question.
2. Icarus searches the bounded record and proves no rationale was documented.
3. The team explicitly records the missing rationale through a reviewed,
   repository-owned pull request. The gap is visibly proposed and cannot spawn
   duplicate proposals.
4. After merge and re-index, the same question receives a cited answer.
5. The gap is resolved by evidence—not by clicking a button or writing a draft.

The magic moment is not merely “AI answered.” It is: **Icarus remembered
something the team would otherwise have lost—or proved nobody ever documented
it, then helped the team stop that knowledge from dying.**

Every proposed feature faces one test: *does this preserve, reconstruct, or
reason over engineering memory?* Generic autocomplete, code generation, test
generation, and autonomous bug fixing do not pass that test.

The company roadmap follows the dependency:

1. Become the memory.
2. Become the reasoning engine over that memory.
3. Become the advisor that improves decisions because it understands what came
   before.

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

The same brain also meets an engineer inside Claude Code, Codex, Cursor, or
another MCP-capable tool. Before the coding agent proposes a meaningful change,
it asks Icarus for the recorded why. Icarus returns a cited answer or an honest
unknown plus the bounded evidence retrieval considered. The coding agent uses
that context to improve its plan; Icarus never writes the code or silently
changes repositories on its behalf. This is a second client of the same
organizational memory, not a second product and not a retreat from the human
conversation above. The engineer signs into the Mac app once; approved coding
tools receive only a short-lived, public-read Icarus session, never the
Keychain-held GitHub credential.

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
| **Interface** (how you talk to it) | **macOS app + voice (hotkey) + overlay, browser extension, read-only coding-agent tools** | team surfaces, web |
| **Deployment** (where compute runs) | one unified cloud we operate, with **per-tenant data isolation** | true single-tenant / in-customer-cloud for the most regulated (enterprise upsell) |

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
the cloud. It runs in **one unified cloud we operate**, but every company's data
is **isolated per tenant** — separate stores and keys, never pooled with another
customer's.

**True today, enforced in code, not just promised:**

- **Never trained on customer code.**
- **Discarded after each request** (zero-data-retention).

**The target for the first security-conscious paying customer, not yet
pursued:**

- **Real compliance** (SOC 2, ISO 27001, and BAAs where needed).

A **single-tenant tier — their own cloud, or fully local** — stays available for
the most regulated / air-gapped customers (an enterprise upsell), degraded where
needed but still honest. Cite-or-unknown never degrades, on any tier.

See [decisions/2026-06-30-unified-cloud-per-tenant-isolation.md](decisions/2026-06-30-unified-cloud-per-tenant-isolation.md)
for why unified-with-isolation, not private-per-company-by-default.

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
  org write things down. **Capture is the moat** — the highest-value "why"s
  ("Kafka not RabbitMQ?") are usually never written in a PR, so retrieval alone
  has a low hit-rate exactly where the value is; getting the rationale recorded is
  the defensible, unglamorous part nobody does well.

Asking is **pull** — low frequency, only when you're confused. The higher-order
goal is **push**: proactively surfacing **stale decisions** (*"chosen in 2023
because X lacked feature Y; Y shipped; nobody revisited it"*). Push is what makes
Icarus a tool you touch daily, not only when stuck — and is the strategic answer to
the usage-frequency risk.

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
- **Humans and agents share one truth boundary.** Agents receive structured
  evidence, not a more permissive answer. An unknown remains unknown; related
  evidence may shape a plan but must never be promoted into an invented reason.
- **Never capture the screen silently.** If Icarus ever reads on-screen context,
  it must be explicit, opt-in, and never silently uploaded.

## 8. What this is NOT (so we don't drift)

- Not an autonomous coding agent.
- Not a confident chatbot that answers from training memory.
- Not a cloud that pools or trains on a company's source — tenants stay isolated
  (separate stores + keys) even in the one unified cloud.
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
- Coding agents consult Icarus before meaningful changes, and the retrieved
  context measurably changes plans or prevents avoidable review corrections.
- The org starts writing decisions down because Icarus makes that knowledge pay
  off.

See [METRICS.md](METRICS.md) for how each of these becomes a number.

---

*This vision is fixed in direction and flexible in path. We build toward it one
honest brick at a time, and we never trade away the one property that makes it
worth trusting: it knows the difference between what it can prove and what it's
guessing.*
