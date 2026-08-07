// extension/lib.test.js
// Node's BUILT-IN test runner (node:test / node:assert) -- zero npm installs,
// mirrors the project's own "stdlib only" philosophy on the Python side. Run:
//   node --test extension/lib.test.js

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  parseLineHash,
  parseBlobPath,
  isConnectedRepo,
  createLatestOnly,
} = require("./lib.js");

test("parseLineHash: single line", () => {
  assert.deepEqual(parseLineHash("#L5"), { start: 5, end: 5 });
});

test("parseLineHash: a range", () => {
  assert.deepEqual(parseLineHash("#L1-L4"), { start: 1, end: 4 });
});

test("parseLineHash: no hash at all -> null (no selection)", () => {
  assert.equal(parseLineHash(""), null);
});

test("parseLineHash: an unrelated hash -> null", () => {
  assert.equal(parseLineHash("#readme"), null);
  assert.equal(parseLineHash("#L"), null);
  assert.equal(parseLineHash("#L1-L"), null);
});

test("parseLineHash: an inverted range (end before start) -> null", () => {
  // GitHub itself never produces this via click+shift-click, but a
  // hand-crafted/malicious hash could -- fail closed, not silently swap.
  assert.equal(parseLineHash("#L10-L1"), null);
});

test("parseLineHash: zero and unsafe integer ranges fail closed", () => {
  assert.equal(parseLineHash("#L0"), null);
  assert.equal(parseLineHash("#L9007199254740993"), null);
});

test("parseBlobPath: a real blob-view path", () => {
  assert.deepEqual(
    parseBlobPath("/simonw/llm/blob/94769b8b076cde9392059d76bd766453cf900180/llm/cli.py"),
    { owner: "simonw", repo: "llm", ref: "94769b8b076cde9392059d76bd766453cf900180", path: "llm/cli.py" }
  );
});

test("parseBlobPath: a nested file path", () => {
  const got = parseBlobPath("/simonw/llm/blob/main/llm/default_plugins/openai_models.py");
  assert.equal(got.path, "llm/default_plugins/openai_models.py");
});

test("parseBlobPath: decodes URL-escaped filenames before sending them to the brain", () => {
  assert.deepEqual(
    parseBlobPath("/acme/web/blob/main/packages/ui/hello%20world.tsx"),
    {
      owner: "acme",
      repo: "web",
      ref: "main",
      path: "packages/ui/hello world.tsx",
    }
  );
});

test("parseBlobPath: supports both main and master default branch URLs", () => {
  assert.equal(parseBlobPath("/acme/web/blob/main/src/a.ts").ref, "main");
  assert.equal(parseBlobPath("/acme/legacy/blob/master/src/a.c").ref, "master");
});

test("parseBlobPath: malformed URL encoding fails closed", () => {
  assert.equal(parseBlobPath("/acme/web/blob/main/src/%ZZ.ts"), null);
});

test("parseBlobPath: NOT a blob view (e.g. the repo root) -> null", () => {
  assert.equal(parseBlobPath("/simonw/llm"), null);
});

test("parseBlobPath: a PR-diff view -> null (explicitly out of scope, D0's finding)", () => {
  assert.equal(parseBlobPath("/simonw/llm/pull/1442/files"), null);
});

test("isConnectedRepo: matches the caller's connected repo", () => {
  assert.equal(isConnectedRepo("simonw", "llm", "simonw/llm"), true);
});

test("isConnectedRepo: case-insensitive (GitHub repo names are)", () => {
  assert.equal(isConnectedRepo("SimonW", "LLM", "simonw/llm"), true);
});

test("isConnectedRepo: a different repo does not match", () => {
  assert.equal(isConnectedRepo("octocat", "hello", "simonw/llm"), false);
});

test("isConnectedRepo: no connected repo at all -> false, never a crash", () => {
  assert.equal(isConnectedRepo("simonw", "llm", null), false);
  assert.equal(isConnectedRepo("simonw", "llm", undefined), false);
});

test("latest-only gate invalidates responses from an older navigation or ask", () => {
  const gate = createLatestOnly();
  const first = gate.begin();
  assert.equal(gate.isCurrent(first), true);
  const second = gate.begin();
  assert.equal(gate.isCurrent(first), false);
  assert.equal(gate.isCurrent(second), true);
  gate.invalidate();
  assert.equal(gate.isCurrent(second), false);
});
