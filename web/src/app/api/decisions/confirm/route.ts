import { NextResponse } from "next/server";
import { BRAIN_URL } from "@/lib/brain";
import { clearSessionCookie, getSessionToken } from "@/lib/session";

type Body = {
  candidate_id?: unknown;
  selection?: unknown;
  alternative_index?: unknown;
  other_text?: unknown;
};

const ALLOWED_SELECTIONS = new Set(["recommended", "alternative", "other", "not_sure", "reject"]);

/**
 * The one write action on this page. Forwards to the brain's
 * /agent-mode/confirm with the caller's OWN token attached server-side (never
 * by the client) -- demo/server.py's handler uses that exact token to create
 * the real branch/commit/PR via GitHubMemoryWriter.record_decision, so a
 * public_repo-scoped sign-in is required (demo/github_oauth.py's _WEB_SCOPE).
 */
export async function POST(request: Request) {
  const token = await getSessionToken();
  if (!token) {
    return NextResponse.json({ error: "sign in with GitHub to continue" }, { status: 401 });
  }

  let body: Body;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "invalid request" }, { status: 400 });
  }
  if (typeof body.candidate_id !== "string" || !body.candidate_id) {
    return NextResponse.json({ error: "missing candidate_id" }, { status: 400 });
  }
  if (typeof body.selection !== "string" || !ALLOWED_SELECTIONS.has(body.selection)) {
    return NextResponse.json({ error: "invalid selection" }, { status: 400 });
  }
  const forwarded: Record<string, unknown> = {
    candidate_id: body.candidate_id,
    selection: body.selection,
  };
  if (body.selection === "alternative") {
    if (typeof body.alternative_index !== "number") {
      return NextResponse.json({ error: "missing alternative_index" }, { status: 400 });
    }
    forwarded.alternative_index = body.alternative_index;
  }
  if (body.selection === "other") {
    if (typeof body.other_text !== "string" || !body.other_text.trim()) {
      return NextResponse.json({ error: "missing other_text" }, { status: 400 });
    }
    forwarded.other_text = body.other_text;
  }

  let res: Response;
  try {
    res = await fetch(`${BRAIN_URL}/agent-mode/confirm`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(forwarded),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "could not reach the brain" }, { status: 502 });
  }
  const data = await res.json().catch(() => ({}));
  // A 401 here means the cookie's token is stale or was revoked on GitHub's
  // side -- clear it so the client can tell "you are signed out now" apart
  // from "that write failed," rather than retrying the same dead token.
  if (res.status === 401) {
    await clearSessionCookie();
  }
  return NextResponse.json(data, { status: res.status });
}
