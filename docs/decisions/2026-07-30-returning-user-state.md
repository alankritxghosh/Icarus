# Decision: Icarus remembers a returning user, and exactly four facts about them

- **Date:** 2026-07-30
- **Status:** Accepted. Written BEFORE implementation, per Alankrit's own
  condition on this brick ("documented as a deliberate privacy decision before
  implementation").
- **Scope:** brick 3 of the four assigned 2026-07-30 — "remember you"
  (returning-user briefings).
- **Relates to:** [`demo/ledger.py`](../../demo/ledger.py)'s opposite decision
  (the ask ledger deliberately records no identity), and
  [2026-06-30-unified-cloud-per-tenant-isolation.md](2026-06-30-unified-cloud-per-tenant-isolation.md).

## Context

Until now Icarus has been strictly stateless about people. It knows which repo
a caller has connected only for as long as the process lives — the registry's
`_last_repo`/`_last_private` are in-process dictionaries that do not survive a
deploy — and the one durable per-team record, the ask ledger, was designed
specifically so that **who asked is never recorded**.

That statelessness is not an accident, and this decision does not casually
reverse it.

The product reason to change it: onboarding is the acquisition wedge, and
returning-user briefings are the retention layer that follows it. A tool that
says *"since you were last here, this repository moved 31 commits"* is a tool
someone opens on a Monday. A tool that greets every visit identically is one
they open once.

The reason to be careful: the moment a system stores *(person, activity, time)*
it can answer questions about a person's behaviour. "Alice asked about auth
fourteen times" and "Bob has not looked at this repo in three weeks" are
questions a manager will eventually want answered, and a system that *can*
answer them will be asked to. The ledger's docstring already names this
distinction — surveillance of a team versus memory for it — and this decision
is bound by the same line.

## Decision

Icarus stores, per user, **exactly four facts** and no others:

| field | why it is needed |
|---|---|
| user identity | the stable GitHub user id already used for storage isolation |
| repository identity | which repo the briefing is about |
| last-seen repository commit | the anchor a briefing is computed FROM |
| last-visit timestamp | so "since you were last here" can be said in words |

**Nothing else is stored.** Specifically and permanently excluded:

- **No questions.** Not the text, not a count, not a hash. The ask ledger
  records questions against the REPO with no identity; this store records
  identity with no questions. **Neither one alone can produce a per-person
  question history, and they must never be joined.** That separation is the
  whole safety property, and it is why this is a new store rather than an
  identity column added to the ledger.
- **No answer or citation history per person.**
- **No activity log.** One current record per (user, repo) that is
  overwritten, never an append-only trail of visits. A history of timestamps
  IS an activity log even if each row looks harmless.
- **No derived engagement metrics** — no visit counts, no streaks, no "last
  active" leaderboard. These are the raw material of exactly the product we
  are refusing to build.

### Properties the implementation must hold

1. **Tenant-isolated.** Stored under the caller's own per-user storage root,
   the same isolation boundary as their private corpus.
2. **Deletable, and actually deleted.** `POST /disconnect` already deletes a
   user's storage; it must delete this too, in the same operation. Deletion
   must not require asking us.
3. **Visible in the product.** A user can see exactly what is stored about
   them. A privacy promise nobody can verify is marketing.
4. **Never on the answering path.** A failure to read or write this state must
   never degrade or block an answer. It is an asset, not a dependency — the
   same rule the ledger holds to.
5. **Outside the corpus directory.** Ingest republishes a corpus with
   `os.replace()`, which swaps the whole directory; anything stored inside is
   destroyed by the next re-index.

## Consequences

**Accepted costs, stated plainly:**

- Icarus cannot answer "who on the team has looked at this?" or "how engaged
  is this user?". Those are deliberately unanswerable, permanently, and that
  is the point rather than a gap to close later.
- A briefing is per-person, so unlike the ledger it does not accumulate into a
  team artifact. Two people returning to the same repo get two briefings and
  the organisation learns nothing from the pair. Accepted.
- Overwriting rather than appending means we cannot answer "how often does
  this user return". Also deliberate.

**What would need a NEW decision, not an extension of this one:** storing
anything per-person beyond the four fields above; joining this store to the
ask ledger; retaining any visit history; or exposing any per-user field to
anyone other than that user.

## Note on the honesty boundary

A briefing is a claim about a repository ("31 commits landed since you were
last here"), and it is subject to the same rule as every other claim Icarus
makes: it is computed from evidence, and when it cannot be computed it says so
rather than guessing. The freshness work in brick 2 established the pattern —
`up_to_date` is three-valued and "I could not check" never renders as a
confident answer. A briefing inherits that: an unknown comparison produces an
honest "I can't tell you what changed", not a cheerful empty summary that
reads as "nothing changed".
