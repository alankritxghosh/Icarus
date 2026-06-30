# Decision: One unified cloud we operate, with per-tenant data isolation

- **Date:** 2026-06-30
- **Status:** Accepted (direction). Not built yet — gated on the demo and the
  paid/private-model decision.
- **Supersedes:** the earlier default of *"per-company private cloud"* as the v1
  deployment model (in `docs/VISION.md` §4–5, `CLAUDE.md`, and — still to be
  reconciled — `docs/STRATEGY.md` / `docs/ARCHITECTURE.md`).

## Context

The hosting question came up while planning the macOS app and AWS. There were two
ends of a spectrum:

1. **Per-company private cloud** — a separate stack per customer (or deployed into
   the customer's own cloud). Maximum isolation; heavy to build, distribute, and
   operate. This is what the docs currently imply as the default.
2. **One unified cloud (multi-tenant SaaS)** — one deployment we operate for every
   customer. Simplest to build, cheapest, fastest to a usable product; what
   comparable tools (Glean, Unblocked, Greptile) actually run.

The tension: Icarus's whole pitch is privacy-first, and `CLAUDE.md` carries the
hard constraint *"Personal and commercial stay isolated."* A naive unified cloud
puts multiple companies' private code in one system where isolation is enforced
only by our software — and one isolation bug would be company-ending for a trust
product. But per-company private cloud as the *default* is expensive and slow, and
delays getting to first customers.

## Decision

**Operate one control plane; isolate the data per tenant.**

- One unified cloud **we** run, update, and monitor — build and ops stay simple.
- Every company's corpus, embeddings, and provider keys live in **physically
  separate stores** (separate buckets/prefixes, separate vector stores, separate
  encryption keys), with a **tenant ID stamped on everything**. Data is never
  pooled across customers.
- **True single-tenant** (a customer's own isolated stack, or deployed into the
  customer's own cloud, or fully local for air-gapped) becomes a **premium
  enterprise tier / upsell** — offered to buyers who contractually require it, not
  the default.
- **Namespace by tenant from day one**, even while there is exactly one tenant, so
  "add a second company with real isolation" is config, not a rebuild.

## Why

- Cheapest, simplest, fastest path to a product other people can use — the right
  call for reaching first customers.
- Keeps the privacy promise *literally true*: "your code is isolated and never
  trained on" is delivered by per-tenant separation, not by marketing.
- Matches how the field actually ships, while reserving genuine single-tenant for
  the enterprise buyers who demand (and will pay for) it.

## Consequences

- **Positioning must change to match.** Stop calling "private cloud per company"
  the default. Say *"your code is isolated and never trained on."* Saying "private
  cloud" while running shared would be the company-level form of bluffing — the one
  thing Icarus must never do. (`VISION.md` and `CLAUDE.md` updated alongside this
  doc; `STRATEGY.md` / `ARCHITECTURE.md` still to reconcile.)
- **Isolation is now load-bearing engineering**, not a deployment afterthought:
  separate stores + keys per tenant, tested.
- **The free-model gate still applies and gets sharper.** The moment real *private*
  code flows through the brain, free tiers that may train on inputs are off the
  table — and in a unified cloud we are the data controller for many companies at
  once. Unified hosting does not soften this; it forces the paid/private-model
  decision.
- **Server hardening is a prerequisite to going public** regardless of topology:
  auth, TLS, rate-limiting, and locking down the `/connect` ingest endpoint (it
  shells out to `git`/`gh`, safe on localhost, dangerous exposed).

## Not affected (unchanged)

- The deterministic cite-or-unknown honesty gate — independent of deployment
  topology; preserved on every tier.
- "Never train on customer code; discard after each request."
- Nothing here is needed for the demo or the first public-repo version (no private
  data to isolate yet). This is a post-demo step.

## When (rough sequence)

Record demo locally → decide paid/private model → harden the server → stand up the
unified cloud with per-tenant isolation (likely AWS App Runner/Lightsail + S3 for
corpus + Secrets Manager for keys, per the AWS discussion).
