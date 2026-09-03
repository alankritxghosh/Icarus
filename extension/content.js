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

let connectedRepoStatus = null;
let widgetEl = null; // the single on-page element: either the "Ask Icarus"
                      // trigger button, or the full answer panel -- never both.
const navigationGate = createLatestOnly();
const askGate = createLatestOnly();

const STYLE_ID = "icarus-style";
const STYLE_CSS = `
  .icarus-trigger-bar{position:fixed;bottom:24px;right:24px;z-index:2147483647;
    display:flex;gap:8px;align-items:center;
    font-family:-apple-system,BlinkMacSystemFont,sans-serif;}
  .icarus-question-input{padding:8px 10px;border-radius:6px;border:1px solid #444;
    background:#16181D;color:#F7F6F2;font-size:13px;width:220px;
    font-family:-apple-system,BlinkMacSystemFont,sans-serif;}
  .icarus-question-input::placeholder{color:#8A8F98;}
  .icarus-ask-btn{padding:8px 14px;background:#16181D;color:#F7F6F2;border-radius:6px;
    border:1px solid #444;cursor:pointer;font-size:13px;white-space:nowrap;
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
  try {
    // Routed through the background worker, not fetched here directly -- a
    // content script's own fetch is bound by the GitHub page's CORS/Private
    // Network Access restrictions and fails outright (see background.js).
    const response = await chrome.runtime.sendMessage({ action: "fetchStatus", token });
    if (!response || !response.ok) return null;
    const data = response.data;
    // `private` comes from the brain's own /status, never guessed from the
    // repo name -- it decides the panel's public/private label.
    return data.repo ? { repo: data.repo, private: data.private === true } : null;
  } catch {
    return null; // messaging error -> stay dormant, never break the GitHub page
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
  const bar = document.createElement("div");
  bar.className = "icarus-trigger-bar";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "icarus-question-input";
  // NOT labelled "(optional)". Typing a question is the BETTER path, not the
  // skippable one: explain() searches for surrounding context using the typed
  // question, and falls back to the selected code's own text when there isn't
  // one -- measured to find worse evidence (see GatedPipeline.explain). Calling
  // the stronger path optional pushed users onto the weaker one.
  input.placeholder = "Ask about this line…";

  const btn = document.createElement("button");
  btn.textContent = "Ask Icarus";
  btn.className = "icarus-ask-btn";

  // Empty input -> the server's default explain question ("what does this code
  // do, and how is it used in this codebase?" -- deliberately NOT compound; the
  // old "...and why is it here?" made an unrecorded why abstain the answerable
  // what). A typed question is passed through to /explain's `question` field,
  // unchanged on the server side.
  let submitting = false;
  const submit = () => {
    if (submitting) return;
    submitting = true;
    btn.disabled = true;
    input.disabled = true;
    askIcarus(selection, input.value.trim() || undefined);
  };
  btn.addEventListener("click", submit);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
  });

  bar.appendChild(input);
  bar.appendChild(btn);
  document.body.appendChild(bar);
  widgetEl = bar;
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
  close.addEventListener("click", () => {
    askGate.invalidate();
    removeWidget();
  });
  panel.appendChild(close);
  document.body.appendChild(panel);
  widgetEl = panel;
}

async function askIcarus(selection, question) {
  const requestID = askGate.begin();
  showPanel(renderLoadingHtml());
  const token = await getToken();
  if (!askGate.isCurrent(requestID)) return;
  const explainPayload = {
    repo: `${selection.owner}/${selection.repo}`,
    path: selection.path,
    start: selection.start,
    end: selection.end,
  };
  if (question) explainPayload.question = question;
  let response;
  try {
    // Routed through the background worker -- see fetchConnectedRepoStatus's
    // comment; the same CORS/Private Network Access restriction applies here.
    response = await chrome.runtime.sendMessage({ action: "fetchExplain", token, payload: explainPayload });
  } catch (e) {
    if (!askGate.isCurrent(requestID)) return;
    showPanel(renderErrorHtml("could not reach Icarus -- check your connection"));
    return;
  }
  if (!askGate.isCurrent(requestID)) return;
  if (!response || !response.ok) {
    if (response && response.status === 401) {
      showPanel(renderSignedOutHtml());
      return;
    }
    const errMsg = (response && response.error)
      || (response && response.data && response.data.error)
      || `request failed${response && response.status ? ` (${response.status})` : ""}`;
    showPanel(renderErrorHtml(errMsg));
    return;
  }
  const payload = response.data;
  // Stashed for D5's live guard / manual inspection, same as before -- the
  // panel below is the real, user-facing rendering.
  window.__icarusLastExplain = payload;
  showPanel(
    payload.verdict === "answer"
      ? renderAnswerHtml(payload, { isPrivate: connectedRepoStatus && connectedRepoStatus.private })
      : renderUnknownHtml(payload)
  );
}

async function handleLocationChange(pathname, hash) {
  const navigationID = navigationGate.begin();
  askGate.invalidate();
  const blob = parseBlobPath(pathname);
  if (!blob) {
    removeWidget();
    return;
  }
  // Re-read status on each real selection/navigation. The Mac app can switch
  // repositories while this GitHub tab stays open; caching by page repo made
  // that switch invisible until a full reload.
  connectedRepoStatus = await fetchConnectedRepoStatus(await getToken());
  if (!navigationGate.isCurrent(navigationID)) return;
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
    // Some navigation types (certain traversals, cross-origin) carry an empty
    // or invalid destination URL, so new URL() can throw. A throw here would
    // skip the cleanup below (removeWidget on leaving a blob page), leaving a
    // stale trigger/panel on screen -- so parse defensively and treat a bad
    // destination as "navigated away": tear the widget down.
    let url;
    try {
      url = new URL(event.destination.url);
    } catch {
      removeWidget();
      return;
    }
    handleLocationChange(url.pathname, url.hash);
  });
}
handleLocationChange(location.pathname, location.hash);
