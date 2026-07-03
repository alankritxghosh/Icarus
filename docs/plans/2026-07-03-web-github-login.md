# Web GitHub Login (Google-style) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the device-code + Keychain login with a seamless web login: click
"Sign in with GitHub" → GitHub's login page appears in a sheet → authorize → you're
in. No code-pasting, no Keychain — the session lives in memory.

**Why this shape:** GitHub (unlike Google) still requires the client **secret** at
token exchange even with PKCE, so a native app can't complete the flow alone. GitHub
also only accepts **loopback** callback URLs for desktop apps (not custom schemes).
So the callback points at the **brain** (which holds the secret), the brain does the
exchange, and it bounces the auth sheet closed with an `icarus://` redirect the app
captures. The app never sees the secret; the token is held in memory only.

**Decided:** web redirect flow · in-memory session (no Keychain).

---

## The flow (end to end)

1. App → `POST /auth/github/begin` → brain returns `{ authorize_url }` (it minted a
   `state` for CSRF and remembered it).
2. App starts `ASWebAuthenticationSession(url: authorize_url, callbackURLScheme:
   "icarus")`. GitHub's login page shows in the sheet.
3. User authorizes → GitHub redirects to `http://127.0.0.1:8000/auth/github/callback?
   code=…&state=…` (loaded inside the sheet).
4. Brain callback: validate `state`, `POST` to GitHub's token endpoint with
   `client_secret` → access token; store it under a one-time `session` id; **302 →
   `icarus://auth?session=<id>`**.
5. `ASWebAuthenticationSession` sees `icarus://…`, auto-closes, hands the app the URL.
6. App → `POST /auth/github/redeem { session }` → `{ token }` (single-use). App keeps
   the token **in memory** and sends it as `Authorization: Bearer` (the existing
   `GitHubTokenVerifier` validates it). Quit = signed out.

Only a one-time `session` id crosses the `icarus://` redirect — never the token.

---

## What YOU (Alankrit) must do on GitHub — the blocker

On your OAuth App (github.com → Settings → Developer settings → OAuth Apps):
1. Set **Authorization callback URL** to exactly `http://127.0.0.1:8000/auth/github/callback`.
2. **Generate a client secret** (Client ID stays public).
3. Put both in the brain's gitignored `.env`:
   `GITHUB_CLIENT_ID=…` and `GITHUB_CLIENT_SECRET=…`.

The app also needs the (public) Client ID — it already reads `ICARUS_GH_CLIENT_ID`;
we'll keep that, or the brain can hand it to the app in `begin`.

---

## Phase 1 — Brain (Python, offline-testable)

### Task 1: `demo/github_oauth.py`
- `new_state() -> str` — URL-safe random CSRF token.
- `authorize_url(client_id, redirect_uri, state, scope="read:user") -> str` — pure.
- `exchange_code(code, *, client_id, client_secret, redirect_uri, opener=urlopen)
  -> str` — POST GitHub's token endpoint; return `access_token`; raise on error.
  `opener` injected so tests are offline.
- `class OAuthFlow` — in-memory: `begin() -> (state, authorize_url)`, `complete(state,
  code) -> session_id` (validates pending state, exchanges, stores token), `redeem(
  session_id) -> token | None` (single-use), with a short TTL sweep. Holds `client_id`
  /`client_secret`/`redirect_uri`.
- Tests (`demo/test_github_oauth.py`): authorize-url contents; exchange parses token
  and fails safe on error body (stubbed opener); begin→complete→redeem happy path;
  unknown/expired state rejected; redeem is single-use; no secret ⇒ error.

### Task 2: wire endpoints in `demo/server.py`
- `POST /auth/github/begin` → `{authorize_url}` (503 if secret unset).
- `GET /auth/github/callback?code&state` → `complete` then `302 icarus://auth?session=…`
  (plus a tiny HTML fallback body). Loopback-only (existing Host guard already covers).
- `POST /auth/github/redeem {session}` → `{token}` or 404.
- Build `OAuthFlow` in `serve()` from `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET` env.
- Tests in `demo/test_server.py`: begin returns a github.com URL; callback with a
  stubbed flow redirects to `icarus://`; redeem returns the token; bad state → 400.

## Phase 2 — App (Swift)

### Task 3: register the URL scheme
- `Icarus-Info.plist`: add `CFBundleURLTypes` with scheme `icarus`.

### Task 4: `WebGitHubAuth` + rework `AuthModel`
- New `IcarusKit` helper for the pure bits (parse `session` from the `icarus://` URL;
  build the begin/redeem requests) — unit-tested.
- `AuthModel`: replace the device-flow/Keychain path with `ASWebAuthenticationSession`
  driving `begin → session → redeem`, storing the token in memory. Keep the same
  `state`/`isSignedIn` surface so `SetupView` is unchanged.
- Presentation context provider off the shell window.

### Task 5: in-memory token source
- Replace the Keychain-backed `tokenReader` in `AppDelegate` with the in-memory token
  from `AuthModel`. Remove `KeychainTokenStore` usage (delete if fully unreferenced).
- `BrainClient` unchanged (still sends the bearer).

### Task 6: retire device flow
- Remove `GitHubAuth.swift` device-flow + its test if fully replaced (confirm no refs).

## Phase 3 — Verify
- Brain: `python3 -m unittest discover -t . -s demo` green.
- App: `swift build && swift test`.
- Live (needs your OAuth config): launch → Sign in → GitHub sheet → authorize → sheet
  closes signed in → connect a repo → ask. Quit → relaunch → one-click re-login.

---

## Security notes
- Client **secret** only in the brain's gitignored `.env`; never in the app or git.
- `state` is single-use CSRF protection; `session` id is single-use, short TTL.
- The GitHub token never rides in a redirect URL — only the one-time `session` id does.
- In-memory only: no token on disk, none in Keychain.
- Loopback callback per GitHub's native-app guidance; the server's existing Host/Origin
  guard already rejects non-loopback callers.

## Deferred
- Persisting the session across launches (would reintroduce secure storage — out of
  scope by choice).
- Real product: the brain is cloud-hosted, so the secret lives server-side properly
  and the callback becomes the hosted URL.
