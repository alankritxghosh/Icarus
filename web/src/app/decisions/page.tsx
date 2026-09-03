import type { Metadata } from "next";
import { BRAIN_URL } from "@/lib/brain";
import { clearSessionCookie, getSessionToken } from "@/lib/session";
import { Mark } from "@/components/Chrome";
import { SignInButton } from "./SignInButton";
import { SessionRedeemer } from "./SessionRedeemer";
import { DecisionGraph } from "./DecisionGraph";
import type { Candidate, Confirmed } from "./types";

export const metadata: Metadata = { title: "Decisions — Icarus" };

/**
 * Gated by a real (httpOnly-cookied) GitHub session -- the first private
 * surface this marketing site has ever had. Fetches BOTH real endpoints
 * server-side, with the token attached as a header (never by client JS):
 * pending candidates and already-confirmed/merged decisions, exactly as
 * demo/decision_ledger.py reports them -- nothing here is invented, and an
 * empty list is rendered as an empty list, never a fabricated example.
 */
export default async function DecisionsPage() {
  const token = await getSessionToken();
  if (!token) {
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-6">
        <SessionRedeemer />
        <Header />
        <h1 className="text-3xl font-semibold text-ink">
          Review what your coding agent decided.
        </h1>
        <p className="max-w-md text-lg text-muted">
          Sign in to see the decisions Claude made in your repository, and confirm or
          reject them for real — each one becomes a genuine, reviewable pull request.
        </p>
        <SignInButton />
      </main>
    );
  }

  const [candidates, confirmed, signedOut] = await fetchDecisions(token);
  if (signedOut) {
    // The token in the cookie no longer works against the brain (expired or
    // revoked on GitHub's side). Clear it and fall back to the sign-in view
    // rather than showing an empty graph that looks like "no decisions."
    await clearSessionCookie();
    return (
      <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-6">
        <Header />
        <p className="max-w-md text-lg text-muted">
          Your sign-in expired. Sign in again to continue.
        </p>
        <SignInButton />
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <div className="pointer-events-none fixed left-6 top-6 z-10 flex items-center gap-2.5">
        <Mark className="size-6 text-sun" />
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
          Decisions
        </span>
      </div>
      <DecisionGraph candidates={candidates} confirmed={confirmed} />
    </main>
  );
}

function Header() {
  return (
    <div className="flex items-center gap-2.5">
      <Mark className="size-6 text-sun" />
      <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
        Decisions
      </span>
    </div>
  );
}

async function fetchDecisions(
  token: string,
): Promise<[Candidate[], Confirmed[], boolean]> {
  const headers = { Authorization: `Bearer ${token}` };
  const [candidatesRes, contextRes] = await Promise.all([
    fetch(`${BRAIN_URL}/agent-mode/candidates`, { headers, cache: "no-store" }),
    fetch(`${BRAIN_URL}/agent-mode/context`, { headers, cache: "no-store" }),
  ]);
  if (candidatesRes.status === 401 || contextRes.status === 401) {
    return [[], [], true];
  }
  const candidatesData = candidatesRes.ok ? await candidatesRes.json() : { candidates: [] };
  const contextData = contextRes.ok ? await contextRes.json() : { decisions: [] };
  return [candidatesData.candidates ?? [], contextData.decisions ?? [], false];
}
