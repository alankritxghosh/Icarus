// extension/render.test.js
// Node's built-in test runner. Pure HTML-string assertions -- no DOM needed.

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  escapeHtml,
  sourceOf,
  renderLoadingHtml,
  renderSignedOutHtml,
  renderErrorHtml,
  renderAnswerHtml,
  renderUnknownHtml,
} = require("./render.js");

test("escapeHtml: escapes the five dangerous characters", () => {
  assert.equal(escapeHtml(`<script>alert("x")&'y'</script>`), "&lt;script&gt;alert(&quot;x&quot;)&amp;'y'&lt;/script&gt;");
});

test("escapeHtml: null/undefined -> empty string, never throws", () => {
  assert.equal(escapeHtml(null), "");
  assert.equal(escapeHtml(undefined), "");
});

test("sourceOf: recognizes every real source prefix", () => {
  assert.equal(sourceOf("pr:1435"), "pr");
  assert.equal(sourceOf("issue:280"), "issue");
  assert.equal(sourceOf("code:llm/tools.py#L1-L5"), "code");
  assert.equal(sourceOf("doc:README.md"), "doc");
  assert.equal(sourceOf("config:pyproject.toml"), "config");
});

test("sourceOf: an unrecognized prefix falls back to 'ref'", () => {
  assert.equal(sourceOf("mystery:1"), "ref");
});

test("renderLoadingHtml: contains a loading indicator", () => {
  assert.match(renderLoadingHtml(), /thinking/i);
});

test("renderSignedOutHtml: tells the user how to sign in, not a silent no-op", () => {
  // This is the real bug D3 had: a signed-out click silently did nothing.
  // D4 must show something actionable instead.
  const html = renderSignedOutHtml();
  assert.match(html, /sign in/i);
});

test("renderErrorHtml: surfaces the real error message, escaped", () => {
  const html = renderErrorHtml('<b>network down</b>');
  assert.match(html, /network down/);
  assert.doesNotMatch(html, /<b>network down<\/b>/); // must be escaped, not injected raw
});

test("renderAnswerHtml: includes the answer prose, escaped", () => {
  const html = renderAnswerHtml({ answer: "It <returns> the time.", citations: [] }, false);
  assert.match(html, /It &lt;returns&gt; the time\./);
});

test("renderAnswerHtml: renders every citation as a clickable link when a URL is present", () => {
  const payload = {
    answer: "x",
    citations: [
      { ref: "code:llm/errors.py", url: "https://github.com/simonw/llm/blob/94769b8/llm/errors.py" },
      { ref: "pr:1435", url: "https://github.com/simonw/llm/pull/1435" },
    ],
  };
  const html = renderAnswerHtml(payload, false);
  assert.match(html, /<a class="icarus-chip" href="https:\/\/github\.com\/simonw\/llm\/blob\/94769b8\/llm\/errors\.py"/);
  assert.match(html, /<a class="icarus-chip" href="https:\/\/github\.com\/simonw\/llm\/pull\/1435"/);
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener"/); // no reverse-tabnabbing on an external link
});

test("renderAnswerHtml: a citation with no URL renders as plain text, not a broken link", () => {
  const html = renderAnswerHtml({ answer: "x", citations: [{ ref: "code:weird", url: null }] }, false);
  assert.doesNotMatch(html, /<a /);
  assert.match(html, /code:weird/);
});

test("renderAnswerHtml: labels the public alpha", () => {
  assert.match(renderAnswerHtml({ answer: "x", citations: [] }), /public repository alpha/);
});

test("renderAnswerHtml: a private repo is not labelled public", () => {
  // Hardcoded "public repository alpha" stopped being true when private repos
  // were re-enabled (2026-07-16) — the panel must state the real kind.
  const html = renderAnswerHtml({ answer: "x", citations: [] }, { isPrivate: true });
  assert.match(html, /private repository alpha/);
  assert.doesNotMatch(html, /public repository alpha/);
});

test("renderAnswerHtml: does not make paid-writer or training claims", () => {
  const html = renderAnswerHtml({ answer: "x", citations: [] });
  assert.doesNotMatch(html, /paid writer/i);
  assert.doesNotMatch(html, /trained/i);
});

test("renderUnknownHtml: the honest-unknown headline, matching the web demo's voice", () => {
  const html = renderUnknownHtml({ searched: ["code:a", "code:b"],
    reason: "no_recorded_reason" });
  assert.match(html, /No one wrote this down\./);
  assert.match(html, /searched 2 sources/);
});

test("renderUnknownHtml: singular 'source' for exactly one", () => {
  assert.match(renderUnknownHtml({ searched: ["code:a"] }), /searched 1 source(?!s)/);
});

test("renderUnknownHtml: zero searched still renders cleanly, no crash", () => {
  assert.match(renderUnknownHtml({ searched: [] }), /searched 0 sources/);
});

test("renderUnknownHtml: a missing entity is not mislabeled undocumented", () => {
  const html = renderUnknownHtml({ verdict: "unknown", reason: "entity_absent",
    searched: [], citations: [] });
  assert.match(html, /not found/i);
  assert.doesNotMatch(html, /No one wrote this down/i);
});

test("renderUnknownHtml: no evidence does not claim nobody documented it", () => {
  const html = renderUnknownHtml({ verdict: "unknown", reason: "no_evidence",
    searched: [], citations: [] });
  assert.match(html, /enough evidence/i);
  assert.doesNotMatch(html, /No one wrote this down/i);
});

test("renderUnknownHtml: a named ref is called out, and not double-counted", () => {
  const html = renderUnknownHtml({ searched: ["issue:6952", "code:a"], anchored: ["issue:6952"] });
  assert.match(html, /you named: issue:6952/);
  assert.match(html, /then searched 1 source(?!s)/);
});

test("renderUnknownHtml: an older brain with no anchored field reads as before", () => {
  const html = renderUnknownHtml({ searched: ["code:a", "code:b"] });
  assert.doesNotMatch(html, /you named/);
  assert.match(html, /searched 2 sources/);
});

// --- index: citations are Icarus's OWN index, not something a person wrote ---
// Added 2026-08-06 with the index-as-evidence brick. `index:overview` carries no
// URL (there is no GitHub page for "what Icarus read"), so before this it
// rendered as a bare grey chip reading `index:overview` beside `pr:1482` and
// `code:llm/utils.py` -- visually identical to a human-authored source. The
// whole point of the honesty boundary is that a reader can tell the difference.

test("sourceOf recognises index as its own source, not a generic ref", () => {
  assert.equal(sourceOf("index:overview"), "index");
});

test("an index citation is labelled in words, not as a raw ref", () => {
  const html = renderAnswerHtml(
    { answer: "Python.", citations: [{ ref: "index:overview", url: null }] }, {});
  assert.match(html, /Icarus&#039;s own index|Icarus's own index/);
  assert.ok(!html.includes("index:overview"),
    "the raw ref must not be shown -- it reads as a document someone wrote");
});

test("an index citation never renders as a link", () => {
  const html = renderAnswerHtml(
    { answer: "Python.", citations: [{ ref: "index:overview", url: "https://evil" }] }, {});
  assert.ok(!html.includes("<a"), "index evidence has no source page to link to");
});

test("ordinary citations are untouched by the index labelling", () => {
  const html = renderAnswerHtml(
    { answer: "x", citations: [{ ref: "pr:1482", url: "https://github.com/a/b/pull/1482" }] }, {});
  assert.ok(html.includes("pr:1482"));
  assert.ok(html.includes("<a"));
});
