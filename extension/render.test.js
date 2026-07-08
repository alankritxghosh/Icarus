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

test("renderAnswerHtml: shows 'public repo' for a public repo", () => {
  assert.match(renderAnswerHtml({ answer: "x", citations: [] }, false), /public repo/);
});

test("renderAnswerHtml: shows 'private repo' for a private repo", () => {
  assert.match(renderAnswerHtml({ answer: "x", citations: [] }, true), /private repo/);
});

test("renderAnswerHtml: does NOT claim 'paid writer' or 'trained' -- the known-inaccurate claim it deliberately avoids", () => {
  // Guards against silently reintroducing demo/index.html's badge copy,
  // which docs/HANDOFF.md records as not currently true.
  const html = renderAnswerHtml({ answer: "x", citations: [] }, true);
  assert.doesNotMatch(html, /paid writer/i);
  assert.doesNotMatch(html, /trained/i);
});

test("renderUnknownHtml: the honest-unknown headline, matching the web demo's voice", () => {
  const html = renderUnknownHtml({ searched: ["code:a", "code:b"] });
  assert.match(html, /No one wrote this down\./);
  assert.match(html, /searched 2 sources/);
});

test("renderUnknownHtml: singular 'source' for exactly one", () => {
  assert.match(renderUnknownHtml({ searched: ["code:a"] }), /searched 1 source(?!s)/);
});

test("renderUnknownHtml: zero searched still renders cleanly, no crash", () => {
  assert.match(renderUnknownHtml({ searched: [] }), /searched 0 sources/);
});
