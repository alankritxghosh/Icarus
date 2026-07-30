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

// The three small states share one wrapper: a label line plus a body. Only
// the label's class/text and the body vary.
function block(labelClass, label, bodyHtml) {
  return `<div class="icarus-block"><p class="icarus-label ${labelClass}">${label}</p>${bodyHtml}</div>`;
}

function renderLoadingHtml() {
  return block("icarus-muted", "thinking…", "");
}

function renderSignedOutHtml() {
  return block("", "not signed in",
    "<p>Sign in with GitHub from the Icarus toolbar icon to ask questions here.</p>");
}

function renderErrorHtml(message) {
  return block("icarus-danger", "something went wrong", `<p>${escapeHtml(message)}</p>`);
}

function renderAnswerHtml(payload, opts) {
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
    `<div class="icarus-repo-label">${repoLabel(opts)}</div>` +
    "</div>"
  );
}

// The connected repo's real kind, from the brain's /status -- this used to be a
// hardcoded "public repository alpha", which stopped being true when private
// repos were re-enabled (2026-07-16). Defaults to public: never over-claim that
// a repo is private code.
function repoLabel(opts) {
  return opts && opts.isPrivate ? "private repository alpha" : "public repository alpha";
}

function renderUnknownHtml(payload) {
  const named = payload.anchored || [];
  const rest = (payload.searched || []).filter((r) => !named.includes(r));
  // Say what the QUESTION named, separately from what search suggested: a bare
  // count made a refusal that looked up the named ref first indistinguishable
  // from one that ignored the question (reported live 2026-07-28).
  const namedLine = named.length
    ? `<div class="icarus-searched">you named: ${escapeHtml(named.join(" · "))}</div>`
    : "";
  const lead = named.length ? "then searched" : "searched";
  // An abstention while the index is still building is "I haven't finished
  // reading", not "no one wrote this down" -- only the latter is a claim about
  // the repository, and conflating them is what this product must never do.
  const head = payload.indexing
    ? '<p class="icarus-label">still indexing</p>' +
      "<h2>I haven’t finished reading this repo.</h2>" +
      "<p>Search is keyword-only until indexing finishes — ask again shortly.</p>"
    : '<p class="icarus-label">honest answer</p>' +
      "<h2>No one wrote this down.</h2>" +
      "<p>The evidence doesn’t record a reason, so Icarus won’t invent one.</p>";
  return (
    '<div class="icarus-unknown">' +
    head +
    namedLine +
    `<div class="icarus-searched">${lead} ${rest.length} source${rest.length === 1 ? "" : "s"}</div>` +
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
