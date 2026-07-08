// extension/render.js
// Pure HTML-string builders for the answer overlay -- no DOM access, no
// chrome.* APIs, so these are unit-testable (extension/render.test.js) the
// same way lib.js is. Mirrors demo/index.html's own renderAnswer/
// renderUnknown/renderLoading structure and copy, so the extension and the
// web demo speak with the same voice ("grounded answer" / "No one wrote this
// down." / citation chips grouped by source type).
//
// Deliberate divergence from demo/index.html: that page's badge reads
// "private · paid writer — 0 trained on your code". The 2026-07-08 billing
// investigation (see docs/HANDOFF.md) found the "paid"/"no-training"
// guarantee does NOT currently hold as described -- the key named
// GEMINI_PAID_API_KEY isn't genuinely on a separate billed project yet. That
// is a known, already-flagged inaccuracy in the EXISTING surfaces; this new
// surface must not copy it verbatim and make the problem worse. The badge
// here states only the verifiable fact (is this GitHub repo private or
// public?) and drops the paid/training claim until that's actually true.

function escapeHtml(s) {
  return (s || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function sourceOf(ref) {
  const p = (ref || "").split(":")[0];
  return ["pr", "issue", "code", "doc", "config"].includes(p) ? p : "ref";
}

function renderLoadingHtml() {
  return '<div class="icarus-block"><p class="icarus-label icarus-muted">thinking…</p></div>';
}

function renderSignedOutHtml() {
  return (
    '<div class="icarus-block"><p class="icarus-label">not signed in</p>' +
    "<p>Sign in with GitHub from the Icarus toolbar icon to ask questions here.</p></div>"
  );
}

function renderErrorHtml(message) {
  return (
    '<div class="icarus-block"><p class="icarus-label icarus-danger">something went wrong</p>' +
    `<p>${escapeHtml(message)}</p></div>`
  );
}

function renderAnswerHtml(payload, isPrivate) {
  const chips = (payload.citations || [])
    .map((c) => {
      const s = sourceOf(c.ref);
      const inner = `<span class="icarus-src icarus-src-${s}">${escapeHtml(s)}</span>${escapeHtml(c.ref)}`;
      return c.url
        ? `<a class="icarus-chip" href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${inner}</a>`
        : `<span class="icarus-chip">${inner}</span>`;
    })
    .join("");
  const repoLabel = isPrivate ? "private repo" : "public repo";
  return (
    '<div class="icarus-block">' +
    '<p class="icarus-label icarus-grounded">grounded answer</p>' +
    `<div class="icarus-answer-prose">${escapeHtml(payload.answer)}</div>` +
    '<div class="icarus-evidence">' +
    '<p class="icarus-label icarus-muted">evidence — one glance away</p>' +
    `<div class="icarus-cites">${chips}</div>` +
    "</div>" +
    `<div class="icarus-repo-label">${escapeHtml(repoLabel)}</div>` +
    "</div>"
  );
}

function renderUnknownHtml(payload) {
  const n = (payload.searched || []).length;
  return (
    '<div class="icarus-unknown">' +
    '<p class="icarus-label">honest answer</p>' +
    "<h2>No one wrote this down.</h2>" +
    "<p>The evidence doesn’t record a reason, so Icarus won’t invent one.</p>" +
    `<div class="icarus-searched">searched ${n} source${n === 1 ? "" : "s"}</div>` +
    "</div>"
  );
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    escapeHtml,
    sourceOf,
    renderLoadingHtml,
    renderSignedOutHtml,
    renderErrorHtml,
    renderAnswerHtml,
    renderUnknownHtml,
  };
}
