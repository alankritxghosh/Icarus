# Private repos, safely — per-user isolation + a paid no-training writer (Implementation Plan)

- **Date:** 2026-07-04
- **Status:** Scoped, not started. Supersedes the shelved
  [2026-06-28-brick-8-9-private-repos.md](2026-06-28-brick-8-9-private-repos.md)
  (that plan was *local / single-tenant*; this one is **hosted, multi-user** —
  the harder problem the [unified-cloud + per-tenant-isolation decision](../decisions/2026-06-30-unified-cloud-per-tenant-isolation.md)
  now demands).
- **Goal:** let an engineer connect their **own private repo** and get a cited
  answer (or an honest unknown), on the hosted brain, safely — so we can put it in
  front of real teams and test PMF.
- **Executable plan:** the task-by-task TDD expansion of this doc is
  [2026-07-04-private-repos-implementation.md](2026-07-04-private-repos-implementation.md)
  — build from that one.

> **For Claude/Codex building this:** red→green per task (WORKFLOWS.md). **Never
> weaken a test or the honesty gates. Never commit a private corpus, a token, or
> any customer code. Never send private code to a model that isn't marked
> private-safe. Never let one user see another user's repo, corpus, or answers.**
> Every commit ends with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
> Isolated worktree per CLAUDE.md.

---

## 1. Why this is different from the shelved plan

The old Bricks 8&9 assumed **one repo, one machine, one operator** — isolation was
free because there was only ever one user (you). The current product is **hosted
and multi-user**: the brain runs on Render, GitHub-bearer-gated, and several people
sign in. Three things that didn't exist before are now load-bearing:

1. **Isolation.** Today there is exactly **one global `Library`** with **one active
   repo** shared by everyone (`demo/library.py`; `connect_sync` swaps it globally).
   The moment two people use it, one person's `/connect` changes the other's
   answers, and one person's corpus is readable by the other. Fine for a public-repo
   demo; **disqualifying for private code.**
2. **Access control.** With public repos, "connect anything" is safe — it's already
   public. With private repos we must prove **this caller is allowed to read this
   repo** before we ingest it, or we become an exfiltration tool.
3. **A private-safe writer.** Free Gemini/Groq may train on inputs. Private code can
   only ever reach a model under a **no-training** agreement, enforced
   **deterministically in code** — the same spirit as the honesty gate.

Everything the honesty gate does is unchanged. This plan adds *isolation* and
*egress control* around it; it never touches cite-or-unknown.

---

## 2. The non-negotiables this plan must preserve

1. **Cite-or-unknown is untouched.** A better/paid writer may answer more, but the
   deterministic gate still forbids bluffing. No gate code changes.
2. **Private code never touches a training model.** A private corpus + a
   non-private-safe provider ⇒ **hard refusal in code**, never a silent send. A
   deterministic *trust interlock*.
3. **One user never sees another user's data.** Corpus, active repo, answers, and
   status are per-user; cross-user read is impossible by construction and proven by
   test. (Per-tenant isolation from the decision doc, instantiated per GitHub user.)
4. **A caller can only ingest a repo they can actually read.** Verified against
   GitHub with the caller's own token before any clone.
5. **Nothing private enters git.** Private corpora + tokens live only in git-ignored
   local paths / env / the persistent disk. A committed private corpus or token is a
   build failure.
6. **The writer is the only egress of private code.** Retrieval is local BM25; the
   judge is eval-only and never in the serve path. This invariant is asserted, not
   assumed.

---

## 3. Decisions (made here; flag if you disagree before building)

- **Isolation unit = the authenticated GitHub user** (stable numeric `id` from
  `GET /user`, not the mutable `login`). Simplest strictly-safe choice for a beta of
  individual engineers: you only ever see corpora *you* connected.
  **Deferred:** org/company-level sharing (two engineers at one company sharing a
  corpus) — it adds cross-user authz and is an optimization, not a safety need.
- **Private-safe writer = a billing-enabled, no-training provider built from a
  *dedicated* key env** (per the handoff: paid Gemini; Anthropic Claude is an
  equally valid drop-in). Critical design point: `private_safe` must be a
  **construction-time property**, not inferred from the key string — free and paid
  Gemini share `GeminiProvider` + `GEMINI_API_KEY`, so the code cannot tell them
  apart. The private-safe provider is therefore built **only** from a separate env
  (`GEMINI_PAID_API_KEY` / `ANTHROPIC_API_KEY`) and flagged `private_safe=True`; the
  free provider stays `private_safe=False`.
- **Private-repo read = OAuth `repo` scope** for the beta (fast path). It's a broad
  scope; the narrower **GitHub App with per-repo selection** is the hardening path,
  deferred. Called out again in Brick D so the consent tradeoff is explicit.
- **Storage = per-user directories on the server's local disk; no database.**
  Everything Icarus keeps is files (`chunks.jsonl`/`meta.json` per user+repo) — the
  user→corpus mapping *is* the directory tree, and OAuth state is transient, so a
  database adds nothing today. **Decision 2026-07-04: stay on Render's free tier
  for the close beta.** Its disk is **ephemeral** — every deploy/restart/idle-sleep
  wipes it, so a user re-connects (re-ingests) their repo afterwards. Accepted: it
  degrades convenience, never isolation or honesty. First upgrade when it hurts:
  durable object storage (S3/R2 per-user prefix — R2 has a free tier) or a paid
  Render disk; if structured state ever appears, SQLite (stdlib) before any cloud
  DB. **At traction the brain moves to AWS** (per the unified-cloud decision doc);
  Render is the interim host.
- **Writer model version is a quality dial, not the safety mechanism.** Bumping
  Gemini 2.5 → 3.x is a one-line default change in `GeminiProvider`, gated by the
  eval board (gates 100%, quality ≥ baseline; verify the exact model id against the
  live API — don't guess it). What makes a writer *private-safe* is the **billing
  tier's data-use terms** (paid = not used for training), never the model number —
  a free-tier Gemini 3 key is still not private-safe.

---

## Task 0 — Owner prerequisites (HUMAN; before the live parts)

None of the offline tasks need these; the live/hosted tasks self-skip without them.

- [x] ~~Enable billing on a Gemini API key~~ **Already done (confirmed by Alankrit
  2026-07-04): the current Gemini key is billing-enabled.** Two small follow-ups
  remain:
  - [ ] **Record the paid-tier no-training policy link** in this doc (verify in
    writing that billed Gemini API usage is not used to train — don't rely on
    memory of the terms).
  - [ ] **Set `GEMINI_PAID_API_KEY`** in Render + `.env` — it may be the *same
    secret* as `GEMINI_API_KEY`. The separate env name is the point, not a
    separate key: placing a key there is the operator's explicit attestation
    "this key is paid/no-train", which is what the deterministic interlock
    trusts. The model on it can be Gemini 3.x (eval board picks).
  - [ ] Because this key now carries **billing**, the stale handoff item gets
    sharper: if the Gemini/Groq keys exposed in an earlier transcript were never
    rotated, rotate them — an exposed billed key is a money risk, not just quota.
- [x] ~~Upgrade Render off the free tier~~ **Decision 2026-07-04: stay on the free
  tier for the close beta.** Known costs, all convenience not safety: idle-sleep
  cold starts (~1 min), OAuth state wiped by a restart mid-sign-in (retry once
  warm), per-user corpora wiped by every restart (users re-connect), and 512 MB
  RAM bounding repo size + concurrent users. Revisit when re-connecting annoys
  the beta users.
- [ ] **Update the GitHub OAuth app** to expect the `repo` scope; confirm you're
  comfortable with the broader consent screen for beta users.
- [ ] Pick **one small private repo** as the test subject; the tester's GitHub
  account must have read access to it.

---

## Brick A — Identity: turn the bearer gate from "valid?" into "who?"

Isolation needs a key. Today the gate only returns a bool.

**Files:** `demo/auth.py`, `demo/test_auth.py`; `demo/server.py`,
`demo/test_server.py`.

- `GitHubTokenVerifier.verify(token)` → return a **stable user id** (`str(id)` from
  `GET /user`) on success, else `None`. Cache token→id (keep the TTL + fail-safe:
  any error/non-200 ⇒ `None`).
- `StaticTokenVerifier` → map allowed tokens to ids (test double).
- Server: `_authenticated()` returns the identity (or `None`); the handler uses it
  to pick the caller's library. Unauthenticated ⇒ 401 as today.

**RED:** verifier returns the id on a 200 (stubbed), `None` on error/non-200/no
token; the handler rejects with 401 when identity is `None`. **GREEN:** implement.
**Commit:** `Bearer gate returns the caller's GitHub identity, not just a bool`.

---

## Brick B — Per-user library registry (the isolation core)

Replace the single global `Library` with a registry of per-user libraries.

**Files:** new `demo/registry.py`, `demo/test_registry.py`; modify `demo/server.py`,
`demo/test_server.py`; new per-user corpus root under a git-ignored path.

- `LibraryRegistry(storage_root, default_corpus_dir, default_repo, …)`:
  `library_for(user_id) -> Library`, lazily creating an **isolated** `Library` per
  user with its **own** corpus root (`<storage_root>/<user_id>/…`), lock, and active
  repo. Bound the number of live libraries (LRU/evict idle) to cap memory.
- `/connect`, `/ask`, `/status` all resolve `library_for(identity)` first — a user
  only ever touches their own state. The built-in public `simonw/llm` demo repo can
  stay a shared read-only default each user starts from.
- Add **`POST /disconnect`**: delete the caller's corpus for the active repo and
  reset their library (honors "discard"; a trust product must let a user delete).

**RED:** two user ids get two independent libraries; user A's `connect` never
changes user B's `status`/`provenance`; `/ask` uses the caller's pipeline;
`disconnect` deletes only the caller's corpus. **GREEN:** implement.
**Commit:** `Per-user library registry — isolate active repo + corpus by GitHub identity`.

> This is the brick that makes the current shared instance safe to point at private
> code. Do not merge private-repo *read* (Brick D) before this lands.

---

## Brick C — A private-safe writer + the trust interlock

**Files:** `evals/provider.py`, `evals/test_provider.py`; new `evals/trust.py`,
`evals/test_trust.py`; new skippable `evals/test_paid_writer_eval.py`.

- Add `private_safe: bool = False` to `Provider`. Build the private-safe writer from
  a **dedicated** env (`GEMINI_PAID_API_KEY` or `ANTHROPIC_API_KEY`) and set
  `private_safe=True` on that instance only. Free Gemini/Groq/OpenRouter stay
  `False`. `StaticProvider` is `True` (offline, nothing leaves).
- `assert_safe_for_private(provider)` in `evals/trust.py` → raise `PrivateDataError`
  if `not provider.private_safe`. Pure, auditable.
- A **private** library (Brick B) is constructed with the private-safe provider, and
  `Library`/`GatedPipeline`'s private answer path calls `assert_safe_for_private`
  **before any model call**.

**RED:** the flags are set as specified; the interlock raises for a free provider
and passes for the paid/static one; a private library refuses to answer if handed a
free provider. **GREEN:** implement. Live board (skippable, public corpus, paid
writer): **both gates stay 100%**, quality ≥ the free-stack baseline.
**Commit:** `Private-safe writer + deterministic trust interlock (private code -> no-train model only)`.

---

## Brick D — Private-repo access control + authenticated, leak-safe ingest

**Files:** new `evals/github_access.py`, `evals/test_github_access.py`; modify
`evals/ingest.py`, `evals/test_ingest_args.py`/`test_ingest_repo.py`;
`demo/github_oauth.py` (scope); modify `demo/registry.py`/`demo/server.py` (wire the
access check + private path); new skippable `evals/test_private_ingest_live.py`.

- **Access check (new deterministic gate):** before ingesting a repo the caller
  marked private, call `GET /repos/{owner}/{repo}` with **the caller's token**. 200 ⇒
  allowed; 403/404/anything-else ⇒ **refuse** (fail-safe, like the honesty gate). No
  clone happens without a proven 200.
- **Leak-safe clone:** authenticate with
  `git -c http.extraHeader="Authorization: Bearer <token>"` — **never** a
  token-in-URL (leaks into `git remote`, process lists, logs). PRs/issues via `gh`
  with the token in a **per-call** `GH_TOKEN` env, not the server's ambient token.
  The token is never written to disk, never logged, never in a `__repr__`.
- **Private output path:** ingest writes to a git-ignored per-user path
  (`<storage_root>/<user_id>/private/<owner>__<repo>/`); add it to `.gitignore`.
- **OAuth scope → `repo`** in `github_oauth.py` so the token can read private
  contents. (Tradeoff restated: broad scope now; GitHub App per-repo selection is
  the deferred hardening.)

**RED:** access check refuses on 403/404 and permits on 200 (stubbed); clone args
carry the Authorization header and the token is **never** in the URL or any
log/repr; `read_token` raises when unset; the private corpus path is matched by
`.gitignore`. **GREEN:** implement. Live (skippable, needs a real private repo +
token): ingest → cited answer via the paid writer; the free provider **raises**
`PrivateDataError`. **Commit:** `Private-repo read: caller-authorized, leak-safe PAT ingest, gated by the interlock`.

---

## Brick E — Isolation & egress proofs (the conscience)

The decision doc: *"isolation is now load-bearing engineering, tested."* This brick
is that test suite — it must exist and stay green.

**Files:** new `demo/test_isolation.py`, `evals/test_egress_invariants.py`.

- **Cross-user:** user A connects repo X; user B's `/status`, `/ask`, `/provenance`
  show **no trace** of X; B cannot read A's corpus path. A's `/disconnect` leaves B
  untouched.
- **Egress:** a private library's pipeline is wired to a **private-safe** provider
  and **no judge**; forcing a free provider into the private answer path raises. A
  synthetic "private" chunk never appears in any argument to a non-private-safe
  provider (spy provider) or the judge.
- **Git hygiene:** the per-user private path is git-ignored; the secrets scan
  (`scripts/scan_secrets.sh`) still passes; no token appears in logs.
- **Deletion:** after `/disconnect`, the corpus files are gone from disk.

**Commit:** `Isolation + egress invariants proven (cross-user, no-leak, deletion)`.

---

## Brick F — Hosted storage, ops, docs

Depends on Task 0 (the paid key).

**Files:** `render.yaml`, `Dockerfile`, `.env.example`, `.gitignore`; `CLAUDE.md`,
`docs/DISTRIBUTION.md`, `docs/HANDOFF.md`; regenerate `general_index.md` +
`detailed_index.md`.

- `storage_root` = a per-user tree on the instance's local (**ephemeral**,
  free-tier) disk — corpora are a **cache**, rebuilt by re-connecting after any
  restart. The registry must handle "directory vanished" gracefully (status →
  not connected, never a crash). Durable storage (S3/R2 per-user prefix, or a
  paid Render disk) is the named upgrade path — deferred.
- New env: `GEMINI_PAID_API_KEY` (or `ANTHROPIC_API_KEY`), `ICARUS_STORAGE_ROOT`;
  add to `render.yaml` as `sync:false` and to `.env.example` (no real values).
- **Rate-limit** `/connect` + `/ask` per user (ingest shells out to git/gh — bound
  it). At minimum a per-user in-flight + simple token-bucket; note that auth is the
  only lever today.
- Docs: a "connect a private repo" recipe, the data-policy link, and the loud
  warnings (never commit private corpora/tokens; public repo ⇒ free writer, private
  ⇒ paid private-safe writer). **Commit:** `Hosted private-repo storage + ops + docs; regenerate indexes`.

---

## Brick G — Mac app surface (small follow-on; brain-first)

After the brain is proven, the app needs: request the `repo` OAuth scope, a
"connect a private repo" affordance (mark private), a per-user "disconnect / delete
my data" control, and a clear **public vs private** indicator (which writer is in
use). Keep the app a thin client — it renders the brain's verdict verbatim and
re-implements nothing. Scoped as its own brick; not detailed here until the brain
lands.

---

## Definition of done

- A signed-in engineer connects **their own private repo** on the hosted brain and
  gets **cited** answers from the **paid private-safe** writer, or an honest unknown.
- **Isolation proven:** user A cannot observe or read user B's repo/corpus/answers
  (Brick E green).
- **Access proven:** ingesting a repo the caller can't read is refused (200-only).
- **Interlock proven:** private code on a non-private-safe provider raises, in code.
- **Egress proven:** private text reaches only the private-safe writer — never the
  free provider, the judge, git, or logs.
- **Deletion works:** `/disconnect` removes the caller's corpus from disk.
- Offline suites green; live tests self-skip without keys; the honesty gate is
  byte-for-byte unchanged; **no new runtime dependency** (stdlib `urllib` for the
  paid API, as with the others).

## Honest limits after this (so the beta's scope is clear)

- **One private repo per user at a time, Python code only**, manual connect, held
  on the server's **ephemeral** disk — a restart/sleep wipes it and the user
  re-connects (per-user delete is provided; true discard-after-request is later).
- **Per-user** isolation, not per-org sharing; **OAuth `repo`** scope, not a GitHub
  App; **persistent disk**, not S3-per-tenant-key. All three are the beta's
  deliberate simplifications with a named hardening path.
- **Cost:** the paid writer bills per request (no free 50/day cap, but real $).
- **Prompt-injection via ingested content remains disclosed** (docs/EVALUATION.md):
  the gate proves provenance, not faithfulness. Onboard only repos the user trusts.

## Build order

Task 0 (owner) → **A → B → E(partial: cross-user)** can land and ship value on
*public* repos first (multi-user isolation is worth having regardless). Then
**C → D → E(egress/private) → F**, then **G** (app). A/B/C are offline-testable and
don't need the paid key or Render upgrade — start there.
