# Decision: engineering memory is recorded in GitHub through review

- **Date:** 2026-08-07
- **Status:** Accepted for the first closed engineering-memory loop.
- **Scope:** Turning a genuine shared Memory Gap into durable, citable company
  knowledge.

## Decision

Icarus may create a draft engineering-memory record only after an explicit
human presses **Record engineering memory** and supplies the rationale. The
record is Markdown owned by the repository, proposed on a new branch, and
submitted as a GitHub pull request. Icarus never merges it.

The first record format lives under `docs/engineering-memory/` and states:

- the question the team could not answer;
- the recorded rationale;
- the tradeoffs or consequences accepted;
- related evidence supplied by the author;
- that this is a retrospective record unless the author explicitly says the
  decision is being captured contemporaneously.

GitHub remains the authority for authorship, review, branch protection, and
merge history. A pull request is a proposed memory, not an accepted one. It
becomes part of Icarus's answerable corpus only after merge and re-index.

## Trust boundary

- The caller's existing GitHub OAuth token is used in memory for this one
  explicit write. It is never logged, persisted by the brain, or returned to a
  client.
- The server verifies that the caller can read the active repository and that
  GitHub reports push permission before creating anything.
- The action is bounded to one new branch, one Markdown file, and one pull
  request. It cannot modify an existing file, push to the default branch, merge,
  close, delete, or edit unrelated content.
- Partial failure is reported truthfully with the recoverable branch or file
  URL when GitHub created one. Success is never claimed unless the pull request
  URL was observed.
- Proposal creation is idempotent per gap. The gap's opaque ID deterministically
  names the branch and record path, and retries discover and return the existing
  pull request instead of creating another one. Icarus never overwrites a
  different file at that path.
- The existing cite-or-unknown gate is unchanged. A draft or open pull request
  is not injected into the answer corpus.

## Gap identity and resolution

The first brick groups questions only by trimmed Unicode-casefolded exact text.
The server derives an opaque SHA-256 gap ID from the repository and that
normalized question. Clients submit only this ID when recording memory; the
server resolves it back to the canonical gap, so display-text normalization
cannot select a different question. It deliberately does not cluster
paraphrases: merging distinct questions would silently overstate demand and
could resolve the wrong gap.

A gap is `open` after a `no_recorded_reason` result. Once GitHub returns an
observed pull-request URL and the server durably appends that proposal, the gap
becomes `proposed` and returns the existing proposal to every retry. It becomes
`resolved` only when a later ask of that same normalized question returns a
cited answer after the record has been merged and the repository re-indexed.
Opening a pull request does not resolve it.

## Accepted limitations

- Repositories where the caller cannot push receive a clear unsupported result;
  fork-based pull requests are a later brick.
- The first loop uses the existing explicit **Re-read repository** action after
  merge. Automatic webhook-driven re-indexing requires a GitHub App and is not
  smuggled into this change.
- A retrospective record is evidence that the organization recorded a rationale
  now. It is not proof that the rationale was written at the time of the
  original decision.

## Reopen triggers

Revisit the storage format when a design partner already has a durable ADR
convention that `docs/engineering-memory/` cannot respect. Revisit the write
path when Icarus moves from broad classic OAuth to a per-repository GitHub App.
