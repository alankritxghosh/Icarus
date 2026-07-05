# Brick G — the Mac app's private-repo surface (2026-07-06)

The brain fully supports private repos over HTTP (per-user isolation, trust
interlock, paid writer — see `docs/plans/2026-07-04-private-repos-implementation.md`).
The Mac app doesn't surface any of it. This brick closes that gap **app-side
only — zero brain changes**: the brain's `/status` already reports
`"private": true/false` and `POST /disconnect` already returns a fresh status
snapshot.

Folded in (decided this session): **persist the connected repo across launches**
(HANDOFF §7 item 5) — it's exactly the state the eviction-downgrade signal
needs, so building them together is cheaper than separately.

## Decisions
- **Eviction/restart downgrade signal is client-side.** The app remembers what
  it connected (repo + private flag); if `/status` later reports "ready" on a
  *different* repo, the server dropped the session (Render restart, LRU
  eviction). The app shows an explicit banner + one-click Reconnect instead of
  silently displaying the public default as if nothing happened. No server-side
  flag — the proven brain stays untouched.
- **Reconnect is a real `/connect`**, not registry resume: the app *has* the
  caller's bearer token, so it can legitimately re-connect a private repo the
  server-side registry could not (the registry never holds tokens).
- **Testable logic lives in `IcarusKit`** (the only tested target): the
  decode, the client call, the saved-connection store, and the pure
  lost-connection check. The `@Observable` app models stay thin.

## Tasks (TDD, red → green each)

1. **`RepoStatus` gains the private flag** — `IcarusKit/Models.swift`: decode
   `"private"` (Swift keyword → `isPrivate` via CodingKeys), optional and
   defaulting to `false` (absent = public default, which is the truthful
   fallback). Tests: `ModelsTests` decode true / false / absent.
2. **`BrainClient.disconnect()`** — POST `/disconnect` with the bearer, decode
   the returned `RepoStatus`. Tests: `BrainClientTests` (URLProtocol stub) —
   path, method, bearer present/absent, decoded snapshot.
3. **`SavedConnection`** (new `IcarusKit/SavedConnection.swift`) — persist the
   last successfully connected repo + private flag (injectable `UserDefaults`),
   plus the pure downgrade check:
   `isLost(status:)` — true only when a saved expectation exists, status is
   `ready`, and `status.repo` ≠ expected (case-insensitive). Indexing/error
   states are never "lost" (a connect in flight shows the old repo). Tests:
   round-trip, clear, and every branch of `isLost`.
4. **`ConnectModel` grows up** (app target, thin over Kit):
   - `.ready(repo:isPrivate:)` carries the private flag (from `/status`).
   - Saves the connection on ready; `disconnect()` calls the client, clears the
     save, returns to `.idle`.
   - `noteStatus(_:)` — fed by the shell from `StatusModel`'s poll; flips to a
     new `.lost(repo:isPrivate:)` state when `SavedConnection.isLost` fires.
   - `resumeSaved()` — called at launch when signed in: prefill + reconnect the
     saved repo (repo persistence across launches; cache hit on the server, so
     cheap).
5. **UI — honest indicators + controls:**
   - Sidebar footer: PRIVATE/PUBLIC badge with the writer tier it implies
     ("private · paid writer" / "public · free writer"), from real `/status`
     data; a "Disconnect" control (deletes the server-side data) when connected.
   - Home header pill shows the private badge too.
   - `SetupView`: copy updated (public **or private** repo; private needs the
     `repo`-scoped sign-in), and a lost-connection banner state with prefilled
     repo + "Reconnect".
6. **Verify:** `swift test` (new tests red first, then green), both Python
   suites untouched-and-green, `scripts/bundle.sh` builds, live smoke against
   the local brain (`/status` shape, `/disconnect`), update `general_index.md`.

## Out of scope
Notarization, bundled fonts, demo recording, any brain change, server-side
downgrade signaling.
