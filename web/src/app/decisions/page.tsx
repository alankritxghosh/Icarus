import type { Metadata } from "next";
import { getSessionToken } from "@/lib/session";
import { Mark } from "@/components/Chrome";
import { SignInButton } from "./SignInButton";
import { SessionRedeemer } from "./SessionRedeemer";

export const metadata: Metadata = { title: "Decisions — Icarus" };

/**
 * Gated by a real (httpOnly-cookied) GitHub session -- the first private
 * surface this marketing site has ever had. `getSessionToken` only proves a
 * cookie EXISTS, not that it's still valid; a stale/revoked token is caught
 * the first time the graph actually calls `/agent-mode/*` (Brick 3), which is
 * where the real 401 handling lives, not here.
 */
export default async function DecisionsPage() {
  const token = await getSessionToken();

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-6">
      <SessionRedeemer />
      <div className="flex items-center gap-2.5">
        <Mark className="size-6 text-sun" />
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
          Decisions
        </span>
      </div>
      {token ? (
        <p className="max-w-md text-lg text-ink">
          Signed in with GitHub. The decision graph lands next.
        </p>
      ) : (
        <>
          <h1 className="text-3xl font-semibold text-ink">
            Review what your coding agent decided.
          </h1>
          <p className="max-w-md text-lg text-muted">
            Sign in to see the decisions Claude made in your repository, and confirm or
            reject them for real — each one becomes a genuine, reviewable pull request.
          </p>
          <SignInButton />
        </>
      )}
    </main>
  );
}
