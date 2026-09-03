import { cookies } from "next/headers";

// The GitHub token lives ONLY in an httpOnly cookie -- never in client JS,
// never in localStorage. It can write real pull requests (public_repo
// scope, see demo/github_oauth.py), so it gets the same treatment a password
// would: unreadable to any script running on the page, including our own.
const COOKIE_NAME = "icarus_session";
const MAX_AGE_SECONDS = 60 * 60 * 24 * 30; // 30 days

export async function setSessionCookie(token: string) {
  const store = await cookies();
  store.set(COOKIE_NAME, token, {
    httpOnly: true,
    // Not `secure` in dev: `next dev` serves plain http://localhost, and a
    // secure cookie is silently dropped there -- this would make local
    // sign-in look broken rather than actually be insecure (dev never
    // touches the production domain).
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    path: "/",
    maxAge: MAX_AGE_SECONDS,
  });
}

export async function getSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(COOKIE_NAME)?.value ?? null;
}

export async function clearSessionCookie() {
  const store = await cookies();
  store.delete(COOKIE_NAME);
}
