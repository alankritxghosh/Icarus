# Icarus — Competitive Landscape

How the closest comparables were actually built, what we steal, and what we
deliberately avoid. This is the research behind [STRATEGY.md](STRATEGY.md).

Last researched: 2026-06-28.

---

## The map

There are two product families that each own half of what Icarus is:

- **The brain** (codebase / enterprise Q&A with citations): Unblocked, Glean,
  Greptile, Sourcegraph Cody.
- **The face** (hotkey + voice + overlay + cloud-trust): Wispr Flow.

Nobody owns both. That gap is the wedge.

---

## The brain comparables

### Unblocked — *the closest competitor* (Icarus without voice)
- **What it is:** a "context engine" for engineering teams. Ask anything about
  your codebase, architecture, or past decisions; get a grounded answer with
  sources drawn from code, PRs, Slack, Jira, Confluence, Notion, GitHub/GitLab.
- **How it's built:** server-side context engine + a knowledge graph across all
  those systems; maps relationships, resolves contradictions, enforces
  permissions, ranks relevance. PRs/issues/discussions appear as cited sources.
- **Where it's going:** a single MCP server that feeds context to coding agents
  (Claude Code, Cursor, Copilot) — pivoting toward the agent ecosystem.
- **What we steal:** citations-as-sources UX; the long-term knowledge-graph idea.
- **What we do differently:** they go *broad* (every tool, every surface, now
  agents). We go *narrow and deep* — GitHub-only, the "why," a voice+overlay
  interface they don't have, and a deterministic honesty guarantee as the brand.
- Sources: [getunblocked.com](https://getunblocked.com/),
  [Show HN](https://news.ycombinator.com/item?id=37748737).

### Glean — the org-wide version (~$7.2B)
- **What it is:** enterprise search / work assistant across 100+ SaaS sources.
- **How it's built:** knowledge graph + RAG; **custom-trained embeddings,
  retrained ~monthly** to track company-specific language; a governance engine
  that mirrors every source app's permissions in real time so users only see what
  they're allowed to.
- **What we learn:** (1) per-company embedding tuning is the real *quality* lever,
  later. (2) **Permissions fidelity is both the moat and the heaviest burden** —
  validates the category economics, and warns us not to take on per-user
  permission scoping too early.
- Sources: [Glean RAG](https://www.glean.com/blog/what-is-a-rag-ai-agent),
  [Glean embedding fine-tuning lessons](https://jxnl.co/writing/2025/03/06/fine-tuning-embedding-models-for-enterprise-rag-lessons-from-glean/).

### Greptile — codebase Q&A focused on review
- **What it is:** AI code review + natural-language codebase questions
  ("how does auth flow work?") with references to specific files/functions.
- **How it's built:** **index-first** — embeds every file, function, and comment
  into a vector store; treats review and Q&A as a *search* problem; a feedback
  loop stores up/down-voted comments as embeddings partitioned per team.
- **What we steal:** the index-first architecture; per-customer data isolation;
  "treat it as search, retrieval is the hard part."
- Source: [Greptile semantic search](https://www.greptile.com/blog/semantic-codebase-search).

---

## The face comparable

### Wispr Flow — the interface + cloud-trust playbook
- **What it is:** cloud voice dictation; hold a hotkey, speak, get cleaned-up
  text inserted anywhere. Won a privacy-sensitive market.
- **How it's built:** cloud-only; fine-tuned **Llama hosted on Baseten/AWS**; the
  entire pipeline (speech recognition → Llama transcript cleanup) runs **end-to-end
  under 700ms at p99**, using TensorRT-LLM and a multi-step "Chains" pipeline.
  Built on open models specifically to *own and customize* the system.
- **What we steal:** rent the inference infra, own the pipeline; treat latency as
  a hard engineering target; the hotkey/push-to-talk interaction; the "model
  transforms, never invents" cleanup pattern (their Llama cleanup ≈ our grounded
  synthesis).
- **What we avoid — two cautionary tales:**
  1. **Cloud-only with no fallback** — an outage took every user offline at once.
     Icarus needs a graceful "can't reach the brain" state, never silence.
  2. **Silent active-window screenshots** became its biggest trust wound (it
     reportedly banned a user who asked about the privacy implications). For a
     product handling *other companies' source code*, silent screen capture is
     fatal. We never capture the screen silently — opt-in and explicit, always.
- Sources: [Baseten × Wispr Flow](https://www.baseten.co/resources/customers/wispr-flow/),
  [Wispr privacy incident](https://embertype.com/blog/the-day-wispr-flow-banned-a-user/).

---

## Technique findings that shape our build

- **Code chunking:** AST / function-level chunking (cAST) measurably beats naive
  line-based splitting for code retrieval; attach citation metadata to every
  chunk. Retrieval — not generation — is the 2026 bottleneck.
  Source: [cAST paper](https://arxiv.org/html/2506.15655v1).
- **macOS overlay:** native AppKit `NSPanel` with the right collection-behavior
  flags floats over full-screen apps; alpha gives translucency; global hotkey via
  `CGEvent.tapCreate` / `NSEvent.addGlobalMonitorForEvents` or libs like `HotKey`
  / `MASShortcut`. Well-trodden, not a research risk.
  Source: [Translucent overlay in Swift](https://gaitatzis.medium.com/create-a-translucent-overlay-window-on-macos-in-swift-67d5e000ce90).

---

## One-line takeaways

- The category is **proven and paid** — we are not inventing demand.
- Our edge is **combination + honesty + interface**, not raw capability.
- **Go narrow and deep** (GitHub, the "why," provable honesty) — breadth is how we
  lose to incumbents.
- **Rent the commodities, own the moat** (ingest, honesty gate, evals, the app).
