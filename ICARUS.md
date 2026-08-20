# ICARUS.md

Engineering context for this repository: the things a person or an agent cannot
work out by reading the code.

**This file holds only what is not derivable.** File counts, languages,
structure, entry points and dependencies are computed correctly and
automatically — `GET /map` (`demo/repo_map.py`), `demo/structure.py`,
`demo/entry_points.py`. Writing them here would create a second copy that goes
stale. If you can compute it, do not record it.

```
last-verified-against: db2aff6 (2026-08-21)
```

**Read that stamp before trusting anything below.** A stale line in this file
produces a confident, fully cited, *wrong* answer — the citation resolves, so
groundedness passes it happily. Groundedness proves a citation is real, never
that it is true. If this file is many commits behind HEAD, treat it as a lead,
not as evidence, and re-verify against the code before acting.

---

## Why this system exists

Code shows what exists. It does not show why it exists, what was already tried,
or what was refused. **A merged pull request leaves a commit; a refused one
leaves nothing at all** — so `git log`, `git blame` and the working tree are
structurally blind to every path a team already walked down and abandoned.

Icarus reads a repository's code *and* its GitHub history and answers *why*,
with citations, or says "no one wrote this down" when the reason was never
recorded. That refusal is the product, not a limitation of it.

Measured, three times independently, in `docs/experiments/`: an agent working
from code and git history alone reached a materially worse conclusion every
time — twice it was about to submit a change somebody had already submitted and
had closed.

## Things that must not be changed casually

The highest-value section. Nothing in the code says these are load-bearing;
several look like ordinary defaults.

- **The honesty gate's fail-safe direction** (`evals/gate.py`). Every ambiguous
  path resolves to abstention. A change that makes the gate more helpful by
  making it less certain is a product change, not a bug fix.
- **`evals/trust.py`'s interlock.** It refuses any provider not declaring
  `private_safe=True`, and never infers safety from a key string. There is only
  one writer now, which is exactly why this stays: it is what makes "the only
  writer happens to be safe" a guarantee rather than a coincidence.
- **`demo/ledger.py` records no identity; `demo/visits.py` records no
  questions.** The separation is the entire safety property. `visits.record()`
  takes no question/answer/verdict parameter *at all* — a signature that cannot
  accept one is stronger than a policy saying we will not pass one. Do not
  "simplify" these into one store.
- **Analytics are counts-only unless the caller sends
  `X-Icarus-Share-Content: 1`.** Absent, `0`, or malformed all mean no. The
  repository slug is hashed with a salt, and omitted entirely when no salt is
  set — a weak hash would look like protection.
- **Three-valued unknowns.** `demo/freshness.py`'s `up_to_date` is
  `True`/`False`/`None`, and every failure path lands on `None`. Telling someone
  their index is current *because the check failed* is the same class of failure
  as a bluffed citation. The same rule governs `sales/send_log.py`'s delivery
  state. Never let a failed measurement render as a number.
- **The eval board is frozen on purpose.** `evals/corpus/` is pinned to
  `simonw/llm @ 94769b8` and is permanently behind upstream; `/status` reports
  `pinned: true` so that deliberate choice does not read as neglect. Do not
  refresh it to be helpful.

## Known constraints

- **One model for all production serving**: `gemini-paid`, for public and
  private repositories alike. The free/paid writer split was killed 2026-07-13
  and there is no free-tier serving path. The eval harness keeps separate
  free dials (Groq/Gemini/OpenRouter) for cost-free iteration — those never
  touch serving, and confusing the two is a real mistake people make here.
- **Python standard library only**, except three lazily-imported packages:
  `fastembed` (semantic retrieval) and `tree-sitter` + `tree-sitter-language-pack`
  (AST chunking). All three are imported inside the functions that need them, so
  everything else runs pure-stdlib. Adding a dependency is a decision, not an
  implementation detail. Note that `general_index.md` still calls `fastembed`
  "the sole Python dependency" — it has been wrong since `0a76ba7` (2026-07-18).
- **The Mac app is the credential broker** for the MCP surface. Anything
  claiming to work without it needs a credential story first (see the open
  universal-connector question).
- **The alpha is not notarized.** Ad-hoc signing changes the app's Keychain
  identity on every build, which is why a self-signed certificate exists and
  why the publish gate pins the leaf certificate's SHA-256 rather than
  accepting any non-empty authority.
- **`site/` deploys by `vercel --prod` from the folder, not from git.** A stale
  local file silently replaces a good production one. Diff every asset against
  live before deploying.
- **Deploys run on GitLab, not GitHub.** Two remotes; `.github/` holds only the
  security workflow, so a GitHub-only look concludes there is no deploy
  automation. Run `git remote -v` before any claim about CI here.

## Decisions, and where the reasons live

Reasons are recorded, not summarised here — read the record before reversing
anything.

| Decision | Where |
|---|---|
| One unified cloud, per-tenant data isolation | `docs/decisions/2026-06-30-unified-cloud-per-tenant-isolation.md` |
| Organizational memory as the position; explanation as the wedge | `docs/decisions/2026-06-30-organizational-memory-positioning.md` |
| Engineering memory records: one proposal, one branch, one PR, never an automatic merge | `docs/decisions/2026-08-07-engineering-memory-records.md` |
| MCP serves private repos; the exposure is transferred to whoever configures the client, not verified by Icarus | `docs/decisions/2026-08-07-mcp-private-repository-access.md` |
| Short-lived agent sessions | `docs/decisions/2026-08-03-short-lived-agent-sessions.md` |
| Returning-user state: four facts and no fifth | `docs/decisions/2026-07-30-returning-user-state.md` |

**Three reversals worth knowing**, because each one looks like an inconsistency
until you know it was deliberate: private repos were shelved and then re-enabled
once they were understood as the product; the MCP private-repo refusal was
fail-closed and became a deliberate transfer of the decision; analytics sharing
was default-on with an opt-out and is now default-off with an opt-in.

## Known unknowns

Stated because "no one wrote this down" is the product's own standard.

- **The ICP is not sharp** — team size, repo age, language, pain trigger.
- **Pricing is untouched.** So is trust/legal: what a design partner needs to
  see before connecting a private repository has never been written down.
- **One active repo, or answers across repos?** Multi-repo is explicitly last
  and untouched until this is answered.
- **Are unprompted MCP calls durable?** 4/4 on four tasks in one measured
  session; outside that window, unknown.
- **The q07 edge case** — one in sixty on the paid writer trips the
  weak-verdict-trust path. A grounded, non-fabricating *what*-answer, not a
  bluff, but a decision is owed.
- **`/context` costs ~55s median.** The 60s timeout that hid it is fixed; the
  latency is disclosed and untouched.
- **AST chunking** is proven and wired behind `ICARUS_AST_CHUNKING`, but
  per-language recall evals are only partly done.

## Where context is frequently lost

The places this repository has actually forgotten things, so look here first.

- **Negative results.** `docs/experiments/` keeps them deliberately — including
  a detector that was built, measured, found anti-correlated with truth, and
  deleted. Check there before rebuilding something.
- **`docs/experiments/PROTOCOL.md`** is one rule per failure that actually
  happened, each naming the run it cost.
- **`docs/HANDOFF.md` is the only doc kept current session to session.** Read it
  before treating anything in `CLAUDE.md` as today's priority.
- **The index files drift.** `general_index.md` and `detailed_index.md` describe
  every file and symbol; regenerate them after any structural change.
  `scripts/check_detailed_index.py` gates the parts that can be checked
  mechanically — it has already caught three documented functions that did not
  exist.

## Where to look for deeper context

- `CLAUDE.md` — standing orders and the honesty boundary, precisely stated.
- `AGENTS.md` — the shared engineering constitution.
- `docs/HANDOFF.md` — current state; read first, every session.
- `general_index.md` — every file, one or two lines each.
- `detailed_index.md` — every class and function; large, read on demand.
- `docs/WORKFLOWS.md` — red → green, never weaken the eval, report results.

## For Icarus itself

- Treat this file as **ordinary evidence, cited as `doc:ICARUS.md`** — it earns
  no privileged status over the repository's own pull requests, issues and
  code. Where this file and the code disagree, **the code wins** and this file
  is wrong.
- Do not write to this file. Surface a memory gap instead; a human reviews it
  and it lands through one pull request. A system that writes its own evidence
  and then cites it is grading its own homework.
- The stamp at the top is the age of these claims. Prefer a dated record in
  `docs/decisions/` over a summary here whenever both exist.
