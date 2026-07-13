// extension/render.js
// Pure HTML-string builders for the answer overlay -- no DOM access, no
// chrome.* APIs, so these are unit-testable (extension/render.test.js) the
// same way lib.js is. Mirrors demo/index.html's own renderAnswer/
// renderUnknown/renderLoading structure and copy, so the extension and the
// web demo speak with the same voice ("grounded answer" / "No one wrote this
// down." / citation chips grouped by source type).

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

function renderAnswerHtml(payload) {
  const chips = (payload.citations || [])
    .map((c) => {
      const s = sourceOf(c.ref);
      const inner = `<span class="icarus-src icarus-src-${s}">${escapeHtml(s)}</span>${escapeHtml(c.ref)}`;
      return c.url
        ? `<a class="icarus-chip" href="${escapeHtml(c.url)}" target="_blank" rel="noopener">${inner}</a>`
        : `<span class="icarus-chip">${inner}</span>`;
    })
    .join("");
  return (
    '<div class="icarus-block">' +
    '<p class="icarus-label icarus-grounded">grounded answer</p>' +
    `<div class="icarus-answer-prose">${escapeHtml(payload.answer)}</div>` +
    '<div class="icarus-evidence">' +
    '<p class="icarus-label icarus-muted">evidence — one glance away</p>' +
    `<div class="icarus-cites">${chips}</div>` +
    "</div>" +
    '<div class="icarus-repo-label">public repository alpha</div>' +
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
