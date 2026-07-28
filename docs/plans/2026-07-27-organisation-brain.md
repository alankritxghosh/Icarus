# The Organisation Brain (shared per-repo memory + live access checks) — Plan

> **STATUS: T1–T6 LANDED 2026-07-27/28.** Live on `icarus-brain--0000022`
> (image `alpha-20260728-org-brain`). demo 239 · evals 462 · IcarusKit 80.
> Live-verified: the ledger records asks with verdicts and citations and NO
> identity, `?unknowns=1` returns the gap, an unreadable private repo refuses
> (403), and an absent/garbage token refuses (401).
>
> **What could NOT be verified live, stated rather than glossed:** two entitled
> identities sharing one index, and revocation cutting a real user off. Both
> need a second GitHub account with different repo access, which this machine
> does not have. Both are proven in tests (`SharedPrivateCorpusTests`,
> `RevokedAccessLosesTheSharedCorpusTests`) including by disabling the guard and
> watching them fail — but tests are not the same as a live second user, and the
> first design partner is the real proof.

> **For Claude:** Red→green per task; never weaken a test or the honesty gates.
> The honesty gate is NOT touched by this plan — if a change here requires
> altering `evals/gate.py`, stop and re-scope. Every commit message ends with:
> `Co-Authored-By: Claude <noreply@anthropic.com>`

**Goal:** Three engineers at the same company point Icarus at the same repo and
get **one shared brain** — a single index, and a shared record of every question
asked and every gap found — instead of three isolated personal copies.

**Why now:** Icarus has zero users. Changing the storage model and the privacy
promise costs nothing today and becomes a breaking, trust-damaging migration the
moment one real team relies on it. This is the cheapest hour this change will
ever cost. (Decided 2026-07-27 with Alankrit; the earlier caution about moving a
published trust boundary was calibrated for a product that had users.)

**What this is in one line:** the unit of memory changes from **a person** to
**a codebase**.

## Architecture

Today `LibraryRegistry` keys everything by GitHub **user id** — storage at
`<storage_root>/<user_id>/`, one `Library` per identity, `_last_repo` per user.
Public repo *corpora* are shared via `_public_cache`; everything else is not.

After this plan, the tenant is the **repo** (`owner/name`), and authorisation is
answered by GitHub rather than modelled by us:

- **Storage** is keyed `<storage_root>/repos/<owner>/<repo>/`. One ingest per
  repo, read by everyone entitled to it.
- **Authorisation** is `evals.github_access.repo_info(repo, token)` — "can THIS
  caller read THIS repo, right now" — applied to **reads**, not just `/connect`.
  Cached for **5 minutes** (decided; see Decisions).
- **No org/team/member model is built.** GitHub is the authority on who may see
  a repo. We never hold a membership list, so we can never hold a stale one.
  Offboarding is automatic: access revoked at GitHub → next check fails.
- **The ask ledger** records every question, verdict, and citation per repo. The
  subset with `verdict: "unknown"` is the product's most valuable artifact — a
  live map of what the organisation never wrote down.

**Tech stack:** Python 3 stdlib only. Tests: `unittest`, offline by default.

Run tests from the repo root (the `-t .` matters — package-relative imports):
```bash
python3 -m unittest discover -t . -s demo
python3 -m unittest discover -t . -s evals
```

## Decisions (made 2026-07-27, with reopen triggers)

| # | Decision | Why | Reopen if |
|---|---|---|---|
| D1 | Tenant = repo owner/name, **not** a modelled org | GitHub is authoritative; a membership list we maintain can go stale and become a breach | A customer needs cross-repo org memory that repo-level scoping cannot express |
| D2 | Authorise via live `repo_info`, **5-minute TTL** | Instant-enough revocation without hammering GitHub's rate limit | A security review demands zero-window revocation, or GitHub rate limits bite |
| D3 | **Store question text** | It is the whole value of the ledger and of the unknowns map | — (requires the privacy promise to say so, T5) |
| D4 | `/disconnect` no longer deletes shared data | One person leaving must not delete their team's brain | — |
| D5 | No migration of existing per-user corpora | There are no real users; a migration would be code written for nobody | — |

**D2's accepted risk, stated plainly:** a caller whose GitHub access is revoked
can still receive answers for up to 5 minutes. Accepted deliberately; it is the
cost of not checking GitHub on every single request.

**D4 in detail:** today `/disconnect` deletes the caller's own storage. Under
shared storage that would let one person destroy their whole team's index. It
becomes "forget MY active repo", never "delete the shared corpus". Deleting a
shared corpus is a separate, deliberate action and is **out of scope here**.

## Corrections made after reading the code (2026-07-27, before any code)

**Public corpora are ALREADY shared.** `demo/registry.py`'s `_public_cache`
ingests each public repo once into `<storage_root>/public.cache/<slug>/` and
reuses it for everyone — a public index is a deterministic function of public
input, so per-user copies would be waste, not privacy. The duplication this plan
set out to fix therefore applies **only to PRIVATE repos**, which is where it
actually matters, since companies keep their code private. Scope is narrower than
originally written.

**The original task order would have opened a security hole.** Today, what keeps
one tenant's private corpus away from another is that it is filed under their
user id — the *storage layout is the isolation*; there is no read-side access
check because nothing is shared. Moving private corpora to shared per-repo
storage BEFORE the access check exists would leave a window in which any
signed-in caller could query another company's private index.

**So the order is reversed: build the doorman before removing the walls.**
T2 (verifier) and T3 (enforcement) land first and change nothing a user sees.
Only once enforcement is proven does T1 merge private storage.

## Tasks

Each task is red→green: write the failing test first, then the code.
**Order matters — see the correction above. T2 → T3 → T1 → T4 → T5 → T6.**

### T1 — Shared per-repo PRIVATE storage (LANDS AFTER T3, NOT FIRST)
`demo/registry.py`. Private corpora move from `<storage_root>/<user_id>/private/`
to a per-repo path shared by everyone entitled to read that repo. Public corpora
already work this way and are untouched.
- **Precondition:** T3 is green. Do not land this while reads are unguarded.
- **Test (red first):** two *different* identities connecting the same private
  repo resolve to the **same** corpus directory — one ingest, not two.
- **Test:** two different repos stay separate.
- **Test:** hostile repo names cannot escape the storage root (path traversal) —
  the existing hostile-id rejection test is the model.
- **Test:** an identity WITHOUT access cannot reach it (this is T3's guard, and
  it must be re-proven at this layer once storage is genuinely shared).

### T2 — Repo access verifier with a 5-minute TTL
`demo/auth.py` (mirror the shape of `GitHubTokenVerifier`, which already caches
identity with a TTL — reuse that pattern rather than inventing a second one).
- **Test:** allows when `repo_info` returns 200.
- **Test:** denies on 404 / 403 / network error / no token — **fail safe to
  denied**, never to allowed.
- **Test:** a second call inside the TTL does not hit the network.
- **Test:** a call after the TTL re-checks (injectable clock, as `RateLimiter`
  does).

### T3 — Enforce access on reads
`demo/server.py`. `/ask`, `/explain`, `/status` currently trust that a caller
owns their library. With shared storage they must verify entitlement.
- **Test:** identity B, who cannot read repo R, gets **403** from `/ask` even
  though R's library exists and is loaded.
- **Test:** identity B *who can* read R gets a normal answer — no re-ingest.
- **Test:** the check runs **before** the writer is called, so a refused request
  never bills the paid model.

### T4 — The ask ledger
New `demo/ledger.py`, per-repo, append-only, server-side.
- Records: timestamp, asker identity, question text, verdict, citation refs.
- **Test:** an ask appends exactly one entry to the right repo's ledger.
- **Test:** entries are per-repo — a question about A never appears under B.
- **Test:** unknowns are filterable (this is the artifact that matters).
- **Test:** a caller who cannot read the repo cannot read its ledger.
- **Test:** the ledger survives a registry eviction (it is on disk, not memory).

### T5 — The privacy promise, BEFORE deploy
`site/index.html` + the website repo + `docs/`. Icarus will now store question
text, which it never did before, and the site does not currently say so.
- Say what is stored, who can read it, and why it exists.
- **This ships before or with T4 — never after.** A product whose entire claim
  is honesty does not quietly begin retaining something new.

### T6 — Deploy + live verification
Build, push to ACR, `az containerapp update`, then verify against production:
two identities, one repo, one shared index, a refused third identity, and a
populated unknowns list.

## Risks

- **A repo flips public → private after indexing.** The shared corpus would then
  hold private content that was fetched while public. The live `repo_info` check
  on reads (T3) is what contains this: entitlement is re-evaluated per request,
  so a user who cannot read the now-private repo is refused. Worth an explicit
  test.
- **Ingest credentials.** The corpus is built with whichever caller connected
  first. That is the same content any other entitled reader could fetch
  themselves, so it leaks nothing across the boundary — but it should be stated,
  not assumed.
- **Cost shape changes.** One ingest per repo instead of per user is *cheaper*.
  But shared access means more askers per index, and every ask bills the paid
  writer. The per-identity rate limit still applies; watch whether it needs a
  per-repo ceiling too.
- **The honesty gate is untouched.** If any task appears to require changing
  `evals/gate.py`, that is a signal the scope is wrong — stop and re-scope.
