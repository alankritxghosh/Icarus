# Engineering memory loop, Mac–extension bridge, and extension stress plan

> **Status:** Implemented and locally verified. The installed personal-Chrome
> bridge check remains unobserved because browser control was unavailable.
> Alankrit authorized a commit, push, and pull request; deployment and publishing
> remain out of scope.

## Outcome

An engineer can turn a genuine shared Memory Gap into a repository-owned,
reviewed Markdown record; after merge and re-index, the same question returns a
cited answer and the gap is resolved. The Mac app no longer displays the
**Ask by voice** or **Privacy boundary** navigation sections. The Chrome
extension can use the installed Mac app as its credential-owning bridge, and
the extension survives adversarial testing across varied GitHub repository and
code shapes.

## Product and trust decisions

1. Follow
   [`2026-08-07-engineering-memory-records.md`](../decisions/2026-08-07-engineering-memory-records.md).
2. No knowledge-health percentage ships. The first surface reports observable
   open, proposed, recurring, and resolved gap counts.
3. No confidence stars ship. Answers continue to state their evidence basis;
   related inference never becomes a weaker factual answer.
4. The app–extension bridge proxies bounded `status` and `explain` requests
   through the signed app binary. The GitHub credential remains in Keychain and
   never enters extension storage or a native-message response.
5. The bridge is explicitly installed from the extension using its exact
   `chrome-extension://<id>/` origin. The generated native-host manifest
   allowlists only that origin.
6. Existing extension OAuth remains a fallback only for Chrome's explicit
   “native host not found” result. A host crash, malformed response, app
   refusal, or transport error is authoritative and visible.
7. Removing the two app sections removes only their sidebar/frontend routes.
   Voice, privacy controls, and disclosures outside those sections remain.

## Brick 1 — Prove and expose the memory lifecycle

**Red tests**

- A later cited answer resolves an earlier exact-text genuine gap.
- A typo/entity-absent unknown is not an actionable memory gap.
- An open memory pull request moves a gap to `proposed`; it does not resolve it.
- The API returns open, proposed, and resolved gaps without recording an asker.

**Implementation**

- Add deterministic gap aggregation to `demo/ledger.py`.
- Return structured gaps from the authenticated, entitlement-checked ledger
  endpoint.
- Decode and render open/resolved counts in the Mac app.

## Brick 2 — Record engineering memory

**Red tests**

- Missing/blank/oversized rationale is rejected before GitHub is called.
- A non-gap or non-actionable gap cannot create a record.
- A caller without push permission cannot create repository content.
- The GitHub writer creates only a new branch, one new Markdown file, and one
  pull request; it never writes the default branch or merges.
- Retrying before or after a lost GitHub response returns the deterministic
  proposal for that gap and cannot create a second branch, file, or pull request.
- Every GitHub failure returns an honest failure or partial-result URL.
- The Mac client sends the server's opaque gap ID and renders the observed
  pull-request URL. A proposed gap links to that URL and cannot be submitted
  again.

**Implementation**

- Add a stdlib-only GitHub memory-record writer with injected transport.
- Add an authenticated, entitlement-checked `POST /memory-gaps/record`.
- Add **Record engineering memory** to actionable gaps and a structured sheet
  for rationale, tradeoffs, and related evidence.
- Persist the observed proposal before returning success and refresh shared gap
  state. The gap remains proposed until a later cited answer actually resolves
  it.

## Brick 3 — Remove two frontend sections

- Delete `askByVoice` and `privacyBoundary` from `ShellSurface`.
- Remove their routing cases and dead view code.
- Keep the global push-to-talk/overlay behavior and every privacy/trust control.
- Update navigation tests before production code.

## Brick 4 — Mac–extension bridge

**Protocol**

- Chrome native messaging, one bounded request per helper process.
- Actions: `status`, `explain`, and a writer-free `ping`.
- Maximum message body: 64 KiB.
- Response shape matches the extension's existing `{ok,status,data,error}`
  contract.
- The helper reads the Keychain token and calls the existing brain. It never
  emits the token.

**Red tests**

- Malformed, oversized, and unknown-action input fails closed. The production
  host deliberately processes one framed request per helper process; a second
  frame belongs to a separate process and is not part of this protocol.
- A signed-out app returns a clear unauthorized result.
- `status` and `explain` preserve the server response shape.
- The generated native-host manifest validates the exact Chrome extension
  origin and executable path.
- The extension prefers the bridge and falls back to its own OAuth only when
  Chrome explicitly reports the host is not installed—not when the bridge
  crashes, returns malformed data, or returns a real refusal.

## Brick 5 — Adversarial Chrome extension matrix

Use the real unpacked extension on real GitHub pages with a stubbed brain first,
then the real deployed brain only where the currently connected repository
allows it.

Cover at least:

- Python (`simonw/llm`);
- TypeScript/web components (`muxinc/media-chrome`);
- C/kernel-style repository (`torvalds/linux`);
- a nested monorepo path;
- filenames containing spaces or URL escapes;
- default branches named `main` and `master`;
- rapid SPA file navigation and rapid line-selection changes;
- repository switching while the page remains open;
- double-submit and response-arrives-after-navigation races;
- answer, honest unknown, indexing, auth refusal, entitlement refusal, malformed
  server body, and transport failure.

For each reproduced product defect: add a failing automated test, make the
smallest fix, and verify the mutation would have failed before the fix.

## Verification

- Focused red→green modules after every brick.
- `.venv/bin/python -m unittest discover -t . -s evals`
- `.venv/bin/python -m unittest discover -t . -s demo`
- `node --test extension/*.test.js`
- `(cd extension/e2e && npm test)`
- `(cd mac/Icarus && swift test)`
- Browser-controlled Chrome checks on the varied live GitHub pages.
- Live writer/deployed-brain calls only when credentials and the active repo
  make the check relevant; skipped live checks remain unknown.
- Regenerate `general_index.md` and `detailed_index.md` for structural changes.
