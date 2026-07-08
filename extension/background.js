// extension/background.js
// MV3 service worker: the GitHub sign-in flow via chrome.identity.
// launchWebAuthFlow, using demo/github_oauth.py's "extension" OAuth mode
// (see the plan doc's D3 auth-foundation status note for the full design:
// GitHub still redirects only to the brain's own registered callback; the
// brain then 302s a second time to THIS extension's own
// https://<id>.chromiumapp.org/ redirect_target, which is what
// launchWebAuthFlow is watching for).

const BRAIN_URL = "http://127.0.0.1:8000"; // TODO: configurable once the brain is hosted (post-demo per CLAUDE.md)

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.action === "signIn") {
    signIn().then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true; // keep the message channel open for the async response
  }
});

async function signIn() {
  const redirectTarget = chrome.identity.getRedirectURL();
  const beginRes = await fetch(`${BRAIN_URL}/auth/github/begin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "extension", redirect_target: redirectTarget }),
  });
  if (!beginRes.ok) {
    const body = await beginRes.json().catch(() => ({}));
    throw new Error(body.error || "could not start GitHub sign-in");
  }
  const { authorize_url } = await beginRes.json();

  const finalUrl = await chrome.identity.launchWebAuthFlow({
    url: authorize_url,
    interactive: true,
  });
  if (!finalUrl) throw new Error("sign-in was cancelled or blocked");
  const session = new URL(finalUrl).searchParams.get("session");
  if (!session) throw new Error("sign-in did not return a session");

  const redeemRes = await fetch(`${BRAIN_URL}/auth/github/redeem`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session }),
  });
  if (!redeemRes.ok) throw new Error("could not redeem the sign-in session");
  const { token } = await redeemRes.json();

  // The token is stored in chrome.storage.local -- extension-scoped storage,
  // never accessible to the github.com page itself (a content script's world
  // is isolated from the page's own JS, but chrome.storage is additionally
  // gated to the extension's own origin regardless).
  await chrome.storage.local.set({ icarus_token: token });
  return { ok: true };
}
