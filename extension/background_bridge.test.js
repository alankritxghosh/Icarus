const test = require("node:test");
const assert = require("node:assert/strict");
const {
  bridgeFirst,
  validateStatusResponse,
  validateExplainResponse,
} = require("./background_bridge.js");

test("uses the Mac bridge without touching OAuth fallback", async () => {
  let fallbackCalls = 0;
  const result = await bridgeFirst(
    { action: "status" },
    async () => {
      fallbackCalls += 1;
      return { ok: true, data: { repo: "wrong/repo" } };
    },
    async () => ({ ok: true, status: 200, data: { repo: "acme/api" } })
  );
  assert.equal(result.data.repo, "acme/api");
  assert.equal(fallbackCalls, 0);
});

test("a real bridge refusal never falls back to the extension token", async () => {
  let fallbackCalls = 0;
  const result = await bridgeFirst(
    { action: "status" },
    async () => {
      fallbackCalls += 1;
      return { ok: true };
    },
    async () => ({ ok: false, status: 403, error: "repo refused" })
  );
  assert.equal(result.status, 403);
  assert.equal(fallbackCalls, 0);
});

test("falls back only when Chrome says the native host is unavailable", async () => {
  const result = await bridgeFirst(
    { action: "status" },
    async () => ({ ok: true, data: { repo: "oauth/repo" } }),
    async () => {
      throw new Error("Specified native messaging host not found.");
    }
  );
  assert.equal(result.data.repo, "oauth/repo");
});

test("a native host crash is surfaced and never switches to OAuth", async () => {
  let fallbackCalls = 0;
  const result = await bridgeFirst(
    { action: "status" },
    async () => {
      fallbackCalls += 1;
      return { ok: true, data: { repo: "oauth/repo" } };
    },
    async () => {
      throw new Error("Native host has exited.");
    }
  );

  assert.equal(result.ok, false);
  assert.equal(result.status, 502);
  assert.match(result.error, /exited/i);
  assert.equal(fallbackCalls, 0);
});

test("an invalid native response is an error, not permission to fall back", async () => {
  let fallbackCalls = 0;
  const result = await bridgeFirst(
    { action: "status" },
    async () => {
      fallbackCalls += 1;
      return { ok: true };
    },
    async () => ({ surprise: "not the bridge contract" })
  );
  assert.equal(result.ok, false);
  assert.equal(result.status, 502);
  assert.equal(fallbackCalls, 0);
});

test("status and explain success bodies must match the product contract", () => {
  assert.equal(validateStatusResponse({ repo: "acme/api", state: "ready" }), true);
  assert.equal(validateStatusResponse({ surprise: true }), false);

  assert.equal(validateExplainResponse({
    verdict: "unknown",
    answer: "",
    citations: [],
    searched: ["pr:1"],
  }), true);
  assert.equal(validateExplainResponse({
    verdict: "answer",
    answer: "Because.",
    citations: [{ ref: "pr:1", url: "https://github.com/acme/api/pull/1" }],
    searched: ["pr:1"],
  }), true);
  assert.equal(validateExplainResponse({}), false);
  assert.equal(validateExplainResponse({
    verdict: "answer", answer: "Unsupported.", citations: [], searched: [],
  }), false);
});
