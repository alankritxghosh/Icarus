# Positioning — what the account stands for

Derived from `README.md`, `docs/VISION.md`, `CLAUDE.md` (repo root), and the
vault's Product Philosophy. Nothing here is invented.

## The account's one sentence

> An engineer building the memory layer that code and coding agents don't have —
> and publishing the measurements as he goes.

Two halves, both load-bearing. The first is the product. The second is the
differentiator: measurements, published, with sample sizes.

## The product, in the plain-language form we repeat

> Engineering memory for software teams and their coding agents. It reads a
> repository's code and GitHub history and returns cited context, or an honest
> "no one wrote this down", before someone changes the code.

Repeat it until replies show unaided understanding. Assume zero awareness every
time (`outputs/growth/2026-08-12-distribution-plan.md`).

## The wedge claim, and its exact limit

**Claim:** a merged pull request leaves a commit; a refused one leaves nothing.
`git log`, `git blame`, and the working tree are structurally blind to it —
so an agent reading the repo reconstructs a history that is missing every path
somebody already tried and abandoned.

**Evidence:** three independently-recorded runs where an agent working from code
and git alone reached a materially worse conclusion; twice it was about to
resubmit work already closed (`docs/experiments/2026-08-10-agent-mode-exp-d*.md`).

**Limit that must travel with it:** a closed-unmerged PR is evidence of an
*attempted path*, not proof the team rejected the idea. Measured on 60 real
`meilisearch-swift` PRs: of 11 closed unmerged, only 2 carried a reviewer asking
for changes, 3 were approved and closed anyway.

## The honesty position — the thing nobody else can copy cheaply

Icarus is built to refuse. Groundedness is provable in code: every emitted
citation resolves to genuinely-retrieved evidence with a contained line window.
Abstention when nothing was recorded is code-enforced for the clear case and
writer-reliant beyond it.

**Never say "I don't know is always provable in code."** That overclaims, and
overclaiming here is the same sin as bluffing. The publicly-stated version is
the Aug 17 post: *"Icarus can prove a citation is real. It cannot prove it's
true."*

This is a positioning asset, not just a caveat. In a market where every AI
product overclaims, a founder who publishes his product's exact epistemic
boundary is doing something structurally uncopyable by anyone who does not have
one.

## Who we are not

- Not a coding agent. Icarus is read-only by design and does not implement
  changes.
- Not a code search tool. Search finds what exists; the product is about *why*.
- Not "AI for developers" in general. The category is engineering memory.
- Not a founder-journey account. The journey is the delivery vehicle for
  findings, not the subject.

## Competing framings we have rejected

| Framing | Why not |
|---|---|
| "Documentation that writes itself" | Icarus never invents rationale; a human supplies it through a reviewed PR. |
| "Never lose context again" | Implies retrieval of reasons nobody recorded. Guardrailed against. |
| "Cursor/Copilot for X" | Anchors us to code generation, which is the abundant half. |
| The overlay as the product | It is one client over a shared brain. |

## The thesis the account can own

From the Aug 14 post, which is the strongest strategic framing produced so far:

> AI is making code abundant. So what becomes scarce? Context. Trust. Judgment.
> The winner won't be whoever produces the most code. It'll be whoever gives
> that code meaning.

Every pillar in `content-pillars.md` is downstream of that sentence. It is the
one idea the account should still be associated with in six months.
