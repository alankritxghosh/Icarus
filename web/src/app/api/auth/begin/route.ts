import { NextResponse } from "next/server";
import { BRAIN_URL } from "@/lib/brain";

// Starts the web GitHub login (demo/github_oauth.py's "web" mode, public_repo
// scope since 2026-09-03 -- it now creates real pull requests, see
// github_oauth.py's own comment on _WEB_SCOPE). Client id/secret never reach
// this file or the browser; the brain builds the ready-to-use authorize URL
// and this just relays it.
export async function POST() {
  let res: Response;
  try {
    res = await fetch(`${BRAIN_URL}/auth/github/begin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: "web" }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "could not reach the brain" }, { status: 502 });
  }
  if (!res.ok) {
    return NextResponse.json({ error: "GitHub sign-in is not available right now" }, { status: 503 });
  }
  const data = await res.json();
  if (typeof data.authorize_url !== "string" || !data.authorize_url) {
    return NextResponse.json({ error: "sign-in did not return a redirect" }, { status: 502 });
  }
  return NextResponse.json({ authorize_url: data.authorize_url });
}
