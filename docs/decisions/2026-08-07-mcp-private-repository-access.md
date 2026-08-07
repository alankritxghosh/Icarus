# Decision: private repositories are served over MCP

- **Date:** 2026-08-07
- **Status:** Accepted. Reverses the public-only restriction shipped with the
  first MCP adapter (`docs/decisions/2026-08-07-engineering-memory-records.md`
  era, `demo/mcp_server.py`).
- **Decided by:** Alankrit, with the exposure below stated explicitly first.

## Decision

`demo/mcp_server.py` no longer refuses when the connected repository is
private. Both coding-agent tools (`get_change_context`, `explain_code_context`)
answer about public and private repositories alike, for any MCP client.

The preflight still refuses a **repository mismatch** — a tool call naming a
repo other than the connected one, or a corpus swap between the preflight and
the answer. That check is about answering the question that was actually
asked, and is unrelated to privacy.

## What this gives up

The removed check was the only thing preventing private evidence from crossing
a boundary Icarus cannot see past.

Icarus's deterministic trust interlock (`evals/trust.py`) governs **Icarus's
own writer calls** — it proves the model Icarus sends private code to is
`private_safe=True`. It has never been able to reach past the MCP boundary. An
MCP client forwards tool output into whatever coding model it is configured
with, and the protocol offers no way for that client to attest its training,
logging, or retention posture. Previously Icarus resolved that uncertainty by
failing closed. Now it does not.

Concretely, after this change: a private repository's source, PR discussion and
internal rationale can reach a model provider Icarus has not verified, chosen
by whoever configured the MCP client — including a free tier that trains on
inputs. Icarus cannot detect this, cannot prevent it, and cannot retract it
after the fact.

## Why it was accepted anyway

The restriction made the coding-agent surface close to useless for its actual
audience: a company's engineers work in private repositories, and an agent
integration that only answers about public code does not serve them. A
capability nobody can use has its own cost.

The exposure is therefore **transferred, not eliminated**. Whoever configures
an MCP client against Icarus owns the decision about what that client's model
does with private evidence. Icarus states this in both tool descriptions rather
than implying a guarantee it cannot make.

## What this does NOT change

- The trust interlock still governs Icarus's own writer calls. Private repos
  are still answered by a `private_safe=True` provider inside Icarus.
- Per-tenant data isolation is unchanged.
- Cite-or-abstain is unchanged. This decision is about *who may receive*
  evidence, never about inventing it.
- The Mac app and browser extension are unaffected; they were never restricted
  this way, because Icarus controls the model on both paths.

## Revisit when

MCP grows a way for a client to attest its data-use posture (a signed client
identity, a declared retention/training policy, or an allowlist of clients
whose posture is known). At that point this can become a verified boundary
instead of a transferred risk, and the refusal should return for clients that
cannot attest.

## Proof

`demo/test_mcp_server.py::test_private_repo_is_served_like_any_other` asserts a
private repository is answered, so reinstating a private-repo block breaks a
named test rather than silently passing.
`test_repo_switch_during_answer_still_refuses` pins that the mismatch check
survived this change.
