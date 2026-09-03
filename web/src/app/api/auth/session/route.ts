import { NextResponse } from "next/server";
import { BRAIN_URL } from "@/lib/brain";
import { setSessionCookie } from "@/lib/session";

// The GitHub callback lands the browser back on `/decisions?session=<id>`
// (a one-time, short-lived id -- never the token itself, see
// demo/github_oauth.py). This exchanges it for the real token SERVER-SIDE and
// stores it in an httpOnly cookie; the token itself never reaches the
// response body a browser script could read.
export async function POST(request: Request) {
  let session: unknown;
  try {
    ({ session } = await request.json());
  } catch {
    return NextResponse.json({ error: "invalid request" }, { status: 400 });
  }
  if (typeof session !== "string" || !session) {
    return NextResponse.json({ error: "missing session" }, { status: 400 });
  }

  let res: Response;
  try {
    res = await fetch(`${BRAIN_URL}/auth/github/redeem`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "could not reach the brain" }, { status: 502 });
  }
  if (!res.ok) {
    // A session id is single-use with a short TTL (OAuthFlow.redeem) -- a 404
    // here is the ordinary "already used or expired" case, not exceptional.
    return NextResponse.json({ error: "sign-in session expired or already used" }, { status: 404 });
  }
  const data = await res.json();
  if (typeof data.token !== "string" || !data.token) {
    return NextResponse.json({ error: "sign-in did not return a token" }, { status: 502 });
  }
  await setSessionCookie(data.token);
  return NextResponse.json({ ok: true });
}
