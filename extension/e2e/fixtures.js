// Launching the real, unpacked extension in a real Chromium, plus the two
// things it needs before it will do anything at all:
//
//   1. A token in chrome.storage.local. content.js's fetchConnectedRepoStatus
//      returns null immediately without one, so an unseeded extension stays
//      dormant on every page and every test would pass by doing nothing.
//   2. A stubbed brain. The extension only shows its trigger when /status
//      reports a connected repo MATCHING the page, so with no stub there is
//      nothing to see. Stubbing also keeps these tests off the live brain and
//      off a paid writer.
//
// The extension directory loaded is the REAL one, not a copy with test edits:
// the point of this harness is to catch things that only break once Chrome
// itself resolves the manifest and runs the service worker.

const path = require("node:path");
const { test: base, chromium, expect } = require("@playwright/test");

// The real extension by default. ICARUS_EXT_DIR points it at a copy, which is
// how these tests are themselves verified: mutate a throwaway copy to
// reintroduce a bug that actually shipped, and confirm the relevant test goes
// red. A harness nobody has seen fail is not evidence of anything.
const EXT_DIR = process.env.ICARUS_EXT_DIR
  ? path.resolve(process.env.ICARUS_EXT_DIR)
  : path.resolve(__dirname, "..");

// Must match background.js's BRAIN_URL. Asserted below rather than trusted, so
// this file cannot silently stub an origin the extension no longer calls.
const BRAIN_ORIGIN =
  "https://icarus-brain.whitecliff-26814629.centralindia.azurecontainerapps.io";

const CONNECTED_REPO = "simonw/llm";

const test = base.extend({
  context: async ({}, use) => {
    const context = await chromium.launchPersistentContext("", {
      channel: "chromium",
      args: [
        `--disable-extensions-except=${EXT_DIR}`,
        `--load-extension=${EXT_DIR}`,
      ],
    });
    await use(context);
    await context.close();
  },

  // The extension's service worker, once Chrome has actually started it. Its
  // mere existence is a real assertion: a manifest with a bad path, or a
  // service worker that throws on load, never gets here.
  worker: async ({ context }, use) => {
    let [worker] = context.serviceWorkers();
    if (!worker) worker = await context.waitForEvent("serviceworker");
    await use(worker);
  },
});

/** Put a token where content.js looks for it. */
async function signIn(worker, token = "test-token") {
  await worker.evaluate(async (t) => {
    await chrome.storage.local.set({ icarus_token: t });
  }, token);
}

/**
 * Stub the brain. `explain` is the /explain payload to return; `repo` is what
 * /status reports as connected (null = no repo, i.e. the dormant case).
 */
async function stubBrain(context, {
  repo = CONNECTED_REPO,
  explain = null,
  statusCode = 200,
  explainStatus = 200,
  statusDelay = 0,
  explainDelay = 0,
  explainRaw = null,
  onExplain = null,
  abortExplain = false,
} = {}) {
  await context.route(`${BRAIN_ORIGIN}/**`, async (route) => {
    const url = route.request().url();
    if (url.includes("/status")) {
      const delay = typeof statusDelay === "function"
        ? statusDelay(route.request())
        : statusDelay;
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
      const connected = typeof repo === "function" ? repo() : repo;
      return route.fulfill({
        status: statusCode,
        contentType: "application/json",
        body: JSON.stringify(
          connected ? { repo: connected, private: false, state: "ready" } : {}
        ),
      });
    }
    if (url.includes("/explain")) {
      if (abortExplain) return route.abort("failed");
      if (onExplain) onExplain(route.request());
      const delay = typeof explainDelay === "function"
        ? explainDelay(route.request())
        : explainDelay;
      if (delay) await new Promise((resolve) => setTimeout(resolve, delay));
      const body = typeof explain === "function"
        ? await explain(route.request())
        : (explain || {});
      const responseStatus = typeof explainStatus === "function"
        ? explainStatus(route.request())
        : explainStatus;
      return route.fulfill({
        status: responseStatus,
        contentType: "application/json",
        body: explainRaw === null ? JSON.stringify(body) : explainRaw,
      });
    }
    return route.fulfill({ status: 404, body: "{}" });
  });
}

const blobUrl = (repo, file, hash = "", ref = "main") =>
  `https://github.com/${repo}/blob/${ref}/${file}${hash}`;

module.exports = { test, expect, signIn, stubBrain, blobUrl, BRAIN_ORIGIN, CONNECTED_REPO, EXT_DIR };
