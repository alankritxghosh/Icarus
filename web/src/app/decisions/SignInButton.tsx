"use client";

import { useState } from "react";
import { GitPullRequest } from "lucide-react";

/** Starts the web GitHub login: mint an authorize URL server-side, then send
 * the whole tab there (not a popup -- GitHub's own consent screen is the
 * thing that must be trusted, not an embedded frame of it). */
export function SignInButton() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/begin", { method: "POST" });
      const data = await res.json();
      if (!res.ok || typeof data.authorize_url !== "string") {
        setError(data.error || "Sign-in is not available right now.");
        setBusy(false);
        return;
      }
      window.location.href = data.authorize_url;
    } catch {
      setError("Could not reach the brain from this browser.");
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        onClick={start}
        disabled={busy}
        className="group flex items-center gap-2 rounded-full bg-sun px-4 py-2 text-[13px] font-semibold text-deep transition hover:brightness-110 disabled:opacity-60"
      >
        <GitPullRequest className="size-4" />
        {busy ? "Redirecting to GitHub…" : "Sign in with GitHub"}
      </button>
      {error && <p className="mt-2 font-mono text-[12px] text-unknown">{error}</p>}
    </div>
  );
}
