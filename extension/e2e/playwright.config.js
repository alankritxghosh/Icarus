// Chrome extensions need a PERSISTENT context with --load-extension, so each
// spec launches its own context (see fixtures.js) rather than using Playwright's
// default browser fixture. Everything here is therefore about reporting and
// timeouts, not browser setup.
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: ".",
  // A real Chromium launch plus a real github.com page load. Generous, because a
  // flaky timeout here reads as "the extension broke" and would be chased for
  // an hour before anyone suspects the network.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,   // one Chromium with one loaded extension at a time
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: { actionTimeout: 10_000 },
});
