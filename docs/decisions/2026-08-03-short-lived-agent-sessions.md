# Short-lived public-read sessions for coding agents

**Status:** Accepted for the first agent-authentication brick, 2026-08-03.

## Decision

The signed-in Mac app exchanges its existing GitHub bearer once for a
short-lived Icarus agent session. Coding agents receive only that scoped Icarus
token; they never receive or read the GitHub credential stored in Keychain.

An agent session:

- expires after ten minutes and lives only in server memory;
- stores the verified GitHub user id and active repository, never the GitHub
  token;
- may call only `/status`, `/ask`, and `/explain`;
- may read only the repository GitHub confirmed public when the session was
  issued, while that same repository remains active and recorded public;
- cannot connect, disconnect, ingest, read team ledgers, or access onboarding,
  maps, briefings, or private repositories;
- fails closed when public visibility cannot be verified.

The Mac app remains the credential owner. The MCP adapter can request a fresh
session from the installed app when needed, while explicit environment
configuration remains a development override.

## Why

Reading the long-lived Keychain token directly from the Python MCP process would
remove setup friction by widening the credential boundary. A remote OAuth MCP
server is the cleaner long-term distribution surface, but it requires a durable
authorization server, refresh/revocation policy, and multi-replica session
storage that the current alpha does not have.

This bridge is smaller and recoverable: a leaked agent token has a short life,
cannot mutate state, and cannot cross the private-code boundary.

## Consequences

- Installing and signing into the Mac app becomes the normal agent
  authentication experience.
- The server must distinguish GitHub bearers from agent sessions and enforce the
  route and public-visibility scope itself; client-side checks remain defense in
  depth.
- Sign-out does not instantly revoke already-issued agent sessions. The accepted
  exposure is the remaining token lifetime, bounded to ten minutes and public
  read-only access. Explicit revocation can be added when durable sessions exist.
- A repository can change visibility at GitHub during that ten-minute window.
  The session does not retain the GitHub credential needed to recheck on every
  request, so the residual exposure is bounded by the remaining lifetime. The
  server still refuses immediately if Icarus's active-repo state becomes private
  or switches repositories.
- Sessions are process-local. A server restart invalidates them, and a request
  routed to a different replica cannot verify them. The adapter retries one 401
  by obtaining a fresh session, which contains ordinary restarts but does not
  make a multi-replica deployment reliable. Before agent access is distributed,
  choose either stateless signed grants with a dedicated shared signing secret,
  a shared session store, or an explicit single-replica constraint.
- Remote OAuth remains the later team-scale path; this decision does not attempt
  to simulate a full OAuth authorization server in the current stdlib service.
