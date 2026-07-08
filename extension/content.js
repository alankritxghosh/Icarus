// extension/content.js
// Runs on github.com/*/*/blob/* pages (see manifest.json's content_scripts).
// Uses the pure functions in lib.js (loaded first as a plain global -- no
// build step, no ES modules, so the SAME file also runs unmodified under
// node --test). D0/D3 live-testing findings drove this design (see the plan
// doc's D0/D3 status notes, docs/plans/2026-07-06-tester-feedback-deeper-
// comprehension.md):
//
//  - GitHub blob-view line selection is click+shift-click, which sets
//    location.hash to "#L5" or "#L1-L4" (GitHub's own line-link convention).
//    Drag-selection does NOT set the hash (live-verified) -- v1 only
//    supports the click+shift-click gesture, which is real GitHub muscle
//    memory, not something this extension invents.
//  - GitHub's SPA navigation (clicking a different file in the sidebar) does
//    NOT fire popstate, hashchange, or any Turbo/pjax event (all four
//    checked live, none fired) -- but the standards-based Navigation API's
//    `navigate` event DOES fire reliably for BOTH SPA file-to-file
//    navigation and hash-only line-selection changes (live-verified against
//    the real GitHub UI). One listener covers both cases; no polling needed.
//    Chrome-only today, which matches this extension's explicit "Chrome
//    first" v1 scope (Firefox/Safari deferred).
//  - The extension only activates on a repo already connected to Icarus
//    (checked via GET /status) -- it has an index there, so it has
//    something to cite. Everywhere else it stays dormant, per the plan's
//    scope guard: no "answer anything on any GitHub page."

const BRAIN_URL = "http://127.0.0.1:8000"; // TODO: configurable once the brain is hosted (post-demo per CLAUDE.md)

let lastOwnerRepo = null; // "owner/repo" last checked, so /status is only
let connectedRepoCache = null; // re-fetched when the repo actually changes,
                                // not on every line-selection hash change.
let triggerEl = null;

async function getToken() {
  const { icarus_token } = await chrome.storage.local.get("icarus_token");
  return icarus_token || null;
}

async function fetchConnectedRepo(token) {
  if (!token) return null;
  try {
    const res = await fetch(`${BRAIN_URL}/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.repo || null;
  } catch {
    return null; // network error -> stay dormant, never break the GitHub page
  }
}

function removeTrigger() {
  if (triggerEl) {
    triggerEl.remove();
    triggerEl = null;
  }
}

function showTrigger(selection) {
  removeTrigger();
  const btn = document.createElement("button");
  btn.textContent = "Ask Icarus";
  btn.className = "icarus-ask-trigger";
  // Inline styles deliberately -- no separate stylesheet/build step for a
  // single fixed-position button. D4 owns the real answer-overlay styling.
  btn.style.cssText =
    "position:fixed;bottom:24px;right:24px;z-index:2147483647;padding:8px 14px;" +
    "background:#000;color:#fff;border-radius:6px;border:1px solid #444;" +
    "cursor:pointer;font-size:13px;font-family:-apple-system,sans-serif;";
  btn.addEventListener("click", () => askIcarus(selection));
  document.body.appendChild(btn);
  triggerEl = btn;
}

async function askIcarus(selection) {
  const token = await getToken();
  if (!token) return; // D4 renders a real "sign in" prompt; v1 no-ops rather than guess a UX
  const res = await fetch(`${BRAIN_URL}/explain`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      repo: `${selection.owner}/${selection.repo}`,
      path: selection.path,
      start: selection.start,
      end: selection.end,
    }),
  });
  const payload = await res.json();
  // D3 is "capture + call" only -- D4 renders this as a real cited-answer
  // overlay. Stashed here (not silently discarded, not fake-rendered) so
  // D4's live guard has a real, inspectable value to build against.
  window.__icarusLastExplain = payload;
}

async function handleLocationChange(pathname, hash) {
  const blob = parseBlobPath(pathname);
  if (!blob) {
    removeTrigger();
    return;
  }
  const ownerRepo = `${blob.owner}/${blob.repo}`;
  if (ownerRepo !== lastOwnerRepo) {
    lastOwnerRepo = ownerRepo;
    connectedRepoCache = await fetchConnectedRepo(await getToken());
  }
  if (!isConnectedRepo(blob.owner, blob.repo, connectedRepoCache)) {
    removeTrigger();
    return;
  }
  const lines = parseLineHash(hash);
  if (!lines) {
    removeTrigger();
    return;
  }
  showTrigger({ ...blob, ...lines });
}

if (typeof navigation !== "undefined") {
  // Read the target pathname/hash straight from the navigation event's
  // destination URL, NOT a re-read of `location` -- the `navigate` event
  // fires DURING the navigation (live-verified), before `location` itself
  // has necessarily updated, so re-reading `location` on a deferred timer
  // would be a timing assumption; the destination URL is exact and available
  // immediately.
  navigation.addEventListener("navigate", (event) => {
    const url = new URL(event.destination.url);
    handleLocationChange(url.pathname, url.hash);
  });
}
handleLocationChange(location.pathname, location.hash);
