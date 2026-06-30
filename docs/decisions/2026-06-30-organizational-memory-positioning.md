# Decision: Icarus is organizational memory; explanation is the wedge

- **Date:** 2026-06-30
- **Status:** Accepted (positioning + roadmap emphasis). Sharpens, does not replace,
  [docs/VISION.md](../VISION.md) and [docs/STRATEGY.md](../STRATEGY.md).
- **Source:** an external staff-engineer / YC-partner-style evaluation of the working
  prototype (Mac app: GitHub sign-in → connect a public repo → ⌘⇧I → cited answer or honest
  unknown). Rated ~7.5–8/10 as a proof of concept; the gap is productization + market fit,
  not engineering.

## What was validated
- The **trust model is the differentiation**: "if we don't know, we say so" + **clickable
  provenance** (open the actual PR, verify yourself) — not LLM-style "according to…".
- The **hotkey overlay** UX fits a developer's flow (no extra browser tab).
- These are memorable and rare in the "chat with your repo" crowd.

## The reframe (already our north star — now explicit)
**Icarus is not an explanation tool. Explanation is v1 — the wedge that earns trust.
The product is organizational memory: the *why* behind a codebase, preserved.**
Code is forgotten; companies forget decisions; every departure erases architectural
rationale. That loss is the expensive problem, and where the value (and money) is.

Keep explanation as the trojan horse: it's the low-risk way to earn the right to sit on a
team's institutional memory. Don't downgrade it — but don't mistake it for the destination.

## Two insights that change priorities

### 1. Pull is low-frequency; push is the fix (the #1 SaaS risk)
Explanation is **pull** — you only ask when confused, so usage frequency is structurally low,
which is dangerous for SaaS. The answer is **push**: proactively surfacing **stale
decisions** — e.g. *"Stripe Checkout was chosen in Mar 2023 because Embedded Checkout lacked
feature X; X shipped Nov 2025; nobody has revisited this."* Push arrives without being asked,
making Icarus a daily/weekly-touch tool instead of break-glass. **Stale-decision detection is
therefore not "far future" — it is the strategic answer to the frequency risk** and should be
treated as first-class, even if it ships later.

### 2. Capture is the moat, not more data sources
The highest-value questions ("why Kafka not RabbitMQ?") are usually **never written in a PR** —
they live in heads, Slack threads, and unrecorded meetings. Our honesty gate means Icarus will
correctly say "no one wrote this down" on exactly those questions. So **retrieval alone has a
low hit-rate where the money is.** The unlock is **capture**: getting the *why* recorded at
decision time, and ingesting where it actually lives. Adding Slack/Notion/Linear is table
stakes; the **capture loop is the defensible moat** nobody does well. (VISION §6 already names
this; this elevates it.)

## The cost the roadmap hides
"Private repos" is not a toggle — it is the trigger for the **paid/private-model + hosting
decision** (free models may train on inputs, so they can't touch private code). It changes the
unit economics (you now pay for inference) and the business model. It is the right next step
*because* private repos are where the real pain is — but it is a money/architecture decision,
gated, see [2026-06-30-unified-cloud-per-tenant-isolation.md](2026-06-30-unified-cloud-per-tenant-isolation.md)
and the public-repo-MVP direction.

## Positioning (adopt)
Stop pitching "AI that explains repositories." Pitch the memory:
- **"Git remembers what changed. Icarus remembers why."** (primary)
- "Ask why your codebase became the way it is."
- "Every engineering decision has a memory. Icarus helps you find it."

Value props people actually buy: **reduced onboarding time, preserved institutional knowledge,
faster debugging, confidence to change things** — not "explanations."

## Roadmap emphasis (sharpens BUILD_ORDER, doesn't replace it)
- **v1 (now):** explanation wedge — public GitHub, cited answer / honest unknown, hotkey app.
- **v2:** private repos (gated on the paid/private-model + hosting decision).
- **v3:** multiple repos (a question's answer spans frontend/backend/shared/infra).
- **v4:** beyond GitHub — Slack, Notion, Linear, Confluence, meeting/design docs → reconstruct
  engineering *history*, not just code.
- **v5:** **stale-assumption detection** (push). The frequency unlock; arguably the real
  product.

## Productization gaps to close (from the eval)
- **Manual brain startup** ("open Terminal, run backend, launch app") is demo-acceptable, not
  customer-acceptable — folds into the one-unified-cloud hosting work.
- **Single repo / public only** — addressed by v2/v3.

## What does NOT change
- The deterministic cite-or-unknown honesty gate — it's the brand, on every tier.
- Capture/honesty mean we never fabricate a decision rationale to raise the hit-rate.
