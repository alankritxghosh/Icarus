import { NextResponse } from "next/server";
import { getSessionToken } from "@/lib/session";

// Whether a session cookie exists -- never whether it's still VALID against
// GitHub. Checking that here would be a redundant round trip on every page
// load; a stale/revoked token is instead caught the first time it's actually
// used against the brain (a real /agent-mode/* call), and that 401 is what
// clears the cookie -- see the decisions page's client-side handling.
export async function GET() {
  const token = await getSessionToken();
  return NextResponse.json({ signedIn: token !== null });
}
