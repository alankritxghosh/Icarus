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

const BRAIN_URL = "https://icarus-brain.onrender.com"; // TODO: configurable (post-demo per CLAUDE.md); hardcoded to the live Render deploy for D5 live testing

let lastOwnerRepo = null; // "owner/repo" last checked, so /status is only
let connectedRepoStatus = null; // {repo, private} | null -- re-fetched when
                                 // the repo actually changes, not on every
                                 // line-selection hash change.
let widgetEl = null; // the single on-page element: either the "Ask Icarus"
                      // trigger button, or the full answer panel -- never both.

const STYLE_ID = "icarus-style";
const STYLE_CSS = `
  .icarus-trigger{position:fixed;bottom:24px;right:24px;z-index:2147483647;
    padding:8px 14px;background:#16181D;color:#F7F6F2;border-radius:6px;
    border:1px solid #444;cursor:pointer;font-size:13px;
    font-family:-apple-system,BlinkMacSystemFont,sans-serif;}
  .icarus-panel{position:fixed;bottom:24px;right:24px;z-index:2147483647;
    width:340px;max-height:70vh;overflow:auto;background:#F7F6F2;color:#16181D;
    border:1.5px solid #16181D;border-radius:8px;padding:16px;
    font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;
    box-shadow:4px 4px 0 #16181D;}
  .icarus-panel .icarus-close{position:absolute;top:8px;right:10px;
    cursor:pointer;background:none;border:none;font-size:16px;color:#6B7280;}
  .icarus-label{font:600 11px monospace;letter-spacing:.05em;
    text-transform:uppercase;margin:0 0 6px;}
  .icarus-grounded{color:#0F7B53;} .icarus-muted{color:#6B7280;}
  .icarus-danger{color:#B23A2E;}
  .icarus-answer-prose{margin:0 0 12px;line-height:1.5;}
  .icarus-cites{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px;}
  .icarus-chip{display:inline-flex;align-items:center;gap:6px;
    font-family:monospace;font-size:12px;border:1.5px solid #16181D;
    border-radius:4px;padding:4px 8px;background:#fff;color:#16181D;
    text-decoration:none;}
  .icarus-src{font:600 9px sans-serif;letter-spacing:.06em;
    text-transform:uppercase;color:#fff;background:#16181D;padding:1px 4px;
    border-radius:3px;}
  .icarus-repo-label,.icarus-searched{margin-top:10px;font-size:11px;
    color:#6B7280;}
  .icarus-unknown h2{font-size:15px;margin:6px 0;}
`;

function ensureStyleInjected() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = STYLE_CSS;
  document.head.appendChild(style);
}
// Inject once at script load, not lazily inside showTrigger/showPanel: a
// live-testing bug found exactly this -- injecting only inside showPanel()
// left the FIRST "Ask Icarus" trigger a user ever sees completely unstyled
// (no fixed position, no z-index, no colors) because the stylesheet hadn't
// been added yet at that point in the lifecycle.
ensureStyleInjected();

async function getToken() {
  const { icarus_token } = await chrome.storage.local.get("icarus_token");
  return icarus_token || null;
}

async function fetchConnectedRepoStatus(token) {
  if (!token) return null;
  try {
    const res = await fetch(`${BRAIN_URL}/status`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.repo ? { repo: data.repo, private: !!data.private } : null;
  } catch {
    return null; // network error -> stay dormant, never break the GitHub page
  }
}

function removeWidget() {
  if (widgetEl) {
    widgetEl.remove();
    widgetEl = null;
  }
}

function showTrigger(selection) {
  removeWidget();
  const btn = document.createElement("button");
  btn.textContent = "Ask Icarus";
  btn.className = "icarus-trigger";
  btn.addEventListener("click", () => askIcarus(selection));
  document.body.appendChild(btn);
  widgetEl = btn;
}

function showPanel(html) {
  removeWidget();
  const panel = document.createElement("div");
  panel.className = "icarus-panel";
  // No inline position style here -- .icarus-panel's own `position:fixed`
  // (in STYLE_CSS) is already a valid containing block for .icarus-close's
  // `position:absolute`. A live-testing bug found that setting an inline
  // `position:relative` "to anchor the close button" SILENTLY OVERRODE the
  // class's `position:fixed` (inline styles beat stylesheet rules), making
  // the whole panel render in its normal document-flow position instead of
  // fixed to the viewport -- confirmed live: panel.getBoundingClientRect()
  // showed the panel's left edge at -24px (partially off-screen) in a
  // 1440px-wide viewport, not anchored to the bottom-right corner at all.
  panel.innerHTML = html;
  const close = document.createElement("button");
  close.className = "icarus-close";
  close.textContent = "×";
  close.addEventListener("click", removeWidget);
  panel.appendChild(close);
  document.body.appendChild(panel);
  widgetEl = panel;
}

async function askIcarus(selection) {
  showPanel(renderLoadingHtml());
  const token = await getToken();
  if (!token) {
    showPanel(renderSignedOutHtml());
    return;
  }
  let payload;
  try {
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
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      showPanel(renderErrorHtml(body.error || `request failed (${res.status})`));
      return;
    }
    payload = await res.json();
  } catch (e) {
    showPanel(renderErrorHtml("could not reach Icarus -- check your connection"));
    return;
  }
  // Stashed for D5's live guard / manual inspection, same as before -- the
  // panel below is the real, user-facing rendering.
  window.__icarusLastExplain = payload;
  const isPrivate = !!(connectedRepoStatus && connectedRepoStatus.private);
  showPanel(
    payload.verdict === "answer" ? renderAnswerHtml(payload, isPrivate) : renderUnknownHtml(payload)
  );
}

async function handleLocationChange(pathname, hash) {
  const blob = parseBlobPath(pathname);
  if (!blob) {
    removeWidget();
    return;
  }
  const ownerRepo = `${blob.owner}/${blob.repo}`;
  if (ownerRepo !== lastOwnerRepo) {
    lastOwnerRepo = ownerRepo;
    connectedRepoStatus = await fetchConnectedRepoStatus(await getToken());
  }
  const connectedRepo = connectedRepoStatus ? connectedRepoStatus.repo : null;
  if (!isConnectedRepo(blob.owner, blob.repo, connectedRepo)) {
    removeWidget();
    return;
  }
  const lines = parseLineHash(hash);
  if (!lines) {
    removeWidget();
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
