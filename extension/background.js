// extension/background.js
// MV3 service worker: the GitHub sign-in flow via chrome.identity.
// launchWebAuthFlow, using demo/github_oauth.py's "extension" OAuth mode
// (see the plan doc's D3 auth-foundation status note for the full design:
// GitHub still redirects only to the brain's own registered callback; the
// brain then 302s a second time to THIS extension's own
// https://<id>.chromiumapp.org/ redirect_target, which is what
// launchWebAuthFlow is watching for).
//
// ALL fetches to the brain live HERE, not in content.js, for a real reason
// found by live-testing (docs/HANDOFF.md): a content script's fetch() runs
// inside the GitHub page's own document, so it's subject to the page's CORS
// policy and, since github.com is https and the brain can be a loopback
// address, Chrome's Private Network Access preflight too -- our brain has no
// CORS/OPTIONS handling, so that fetch fails with a bare "Failed to fetch"
// before any response arrives, silently (caught, content.js just sees null).
// A service worker is not a "document" at all, so neither restriction
// applies -- exactly why signIn()'s fetches below already worked while
// content.js's direct fetches didn't. content.js now messages this worker
// for every brain call instead of fetching directly.

importScripts("background_bridge.js");

const BRAIN_URL = "https://icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io"; // TODO: configurable (post-demo per CLAUDE.md); hardcoded to the live Azure Container Apps deploy

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message && message.action === "signIn") {
    signIn().then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true; // keep the message channel open for the async response
  }
  if (message && message.action === "fetchStatus") {
    fetchStatus(message.token).then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
  if (message && message.action === "fetchExplain") {
    fetchExplain(message.token, message.payload).then(sendResponse).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
  if (message && message.action === "bridgePing") {
    IcarusBridge.sendNativeMessage({ action: "ping" })
      .then(sendResponse)
      .catch((e) => sendResponse({ ok: false, unavailable: true, error: String(e) }));
    return true;
  }
});

async function fetchStatus(token) {
  const response = await IcarusBridge.bridgeFirst(
    { action: "status" },
    () => fetchStatusWithOAuth(token)
  );
  if (response.ok && !IcarusBridge.validateStatusResponse(response.data)) {
    return { ok: false, status: 502, error: "Icarus returned an invalid status response" };
  }
  return response;
}

async function fetchStatusWithOAuth(token) {
  if (!token) {
    return {
      ok: false,
      status: 401,
      error: "Connect the Icarus Mac app or sign in with GitHub",
    };
  }
  const res = await fetch(`${BRAIN_URL}/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return { ok: false, status: res.status };
  const data = await res.json();
  return { ok: true, data };
}

async function fetchExplain(token, payload) {
  const response = await IcarusBridge.bridgeFirst(
    { action: "explain", payload },
    () => fetchExplainWithOAuth(token, payload)
  );
  if (response.ok && !IcarusBridge.validateExplainResponse(response.data)) {
    return { ok: false, status: 502, error: "Icarus returned an invalid explanation" };
  }
  return response;
}

async function fetchExplainWithOAuth(token, payload) {
  if (!token) {
    return {
      ok: false,
      status: 401,
      error: "Connect the Icarus Mac app or sign in with GitHub",
    };
  }
  const res = await fetch(`${BRAIN_URL}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(payload),
  });
  const data = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, data };
}

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
