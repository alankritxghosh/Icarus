"use client";

import { useEffect, useState } from "react";

/**
 * Runs once on mount. GitHub's redirect lands the browser back here as
 * `/decisions?session=<id>` (demo/github_oauth.py's `web` mode: `Location: /
 * ?session=...`, which resolves against THIS page because the whole OAuth
 * round trip is same-origin -- see next.config.ts's callback rewrite). This
 * exchanges that one-time id for a real (httpOnly-cookied) session, then
 * reloads with the query param gone -- a `?session=` sitting in the address
 * bar is bookmarkable and shareable, and it's already been spent by the time
 * the user sees it either way.
 */
export function SessionRedeemer() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const session = params.get("session");
    if (!session) return;

    (async () => {
      try {
        const res = await fetch("/api/auth/session", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session }),
        });
        const data = await res.json();
        if (!res.ok) {
          setError(data.error || "Sign-in did not complete.");
          return;
        }
        window.location.replace(window.location.pathname);
      } catch {
        setError("Could not reach the brain from this browser.");
      }
    })();
  }, []);

  if (!error) return null;
  return <p className="font-mono text-[12px] text-unknown">{error}</p>;
}
