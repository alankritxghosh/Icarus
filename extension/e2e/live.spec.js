// The real extension, real Chromium, real github.com, and the real deployed
// Azure brain -- no stubs anywhere. extension.spec.js proves the extension's
// OWN logic against a controlled brain; this proves the whole chain actually
// works end to end against the live system a user hits.
//
// Costs a real writer call and needs a real GitHub token, so it is NOT part of
// `npm test` (see package.json) -- it runs on request:
//
//   ICARUS_LIVE=1 npx playwright test live.spec.js
//
// The token comes from `gh auth token` (this machine's own gh identity, the
// same one CLAUDE.md's leak-safe rules apply to elsewhere in this project):
// never written to a file, never passed as a CLI arg, read once into the
// worker's storage and nowhere else.
const { execSync } = require("node:child_process");
const { test, expect, signIn } = require("./fixtures");

test.skip(!process.env.ICARUS_LIVE, "live test -- set ICARUS_LIVE=1 to run (hits the real brain)");

const REPO = "muxinc/media-chrome";
// A real file in the connected repo, picked because it is plain data (no
// framework magic) so a "what does this do" answer is easy to sanity-check
// without reading the whole library.
const FILE = "src/js/constants.ts";
const LINES = "#L1-L3";

test("the live extension explains real selected lines on github.com, using the deployed brain", async ({ context, worker, page }) => {
  const token = execSync("gh auth token", { encoding: "utf8" }).trim();
  await signIn(worker, token);
  // No context.route() -- every request reaches the real network.

  await page.goto(`https://github.com/${REPO}/blob/main/${FILE}${LINES}`, {
    waitUntil: "domcontentloaded",
  });

  // The trigger only appears once /status confirms THIS repo is connected --
  // a real network round trip, so this is also the live proof that the
  // extension's dormant-by-default gate opens for the right repo.
  await expect(page.locator(".icarus-trigger-bar")).toBeVisible({ timeout: 20_000 });

  await page.locator(".icarus-ask-btn").click();

  const panel = page.locator(".icarus-panel");
  // The panel appears IMMEDIATELY in a "thinking…" state (askIcarus's loading
  // render), so asserting only `toBeVisible` passes at once and reads the
  // loading text -- found by this test failing against a real, correct
  // answer. Wait for it to actually RESOLVE: either evidence renders or the
  // honest-unknown headline appears.
  await expect(async () => {
    const t = await panel.innerText();
    expect(
      t.includes("EVIDENCE") || t.includes("No one wrote this down") || t.includes("haven't finished"),
      `still thinking after the wait:\n${t}`
    ).toBe(true);
  }).toPass({ timeout: 60_000 }); // real writer latency

  const text = await panel.innerText();
  console.log("--- live answer ---\n" + text);

  // Either a grounded answer or an honest unknown is a PASS -- this is a
  // real repo Icarus has not been specifically prepared for, so it proving
  // out an honest "no one wrote this down" is not a failure of the product.
  // What must never happen is silence: no panel, or a panel with neither
  // voice, is the one outcome that means something actually broke.
  const grounded = await panel.locator(".icarus-evidence").count();
  const unknown = text.includes("No one wrote this down") || text.includes("haven't finished");
  expect(grounded > 0 || unknown, `panel showed neither an answer nor an honest unknown:\n${text}`).toBe(true);

  if (grounded > 0) {
    // Groundedness, checked exactly as the honesty gate defines it: a real
    // citation, resolvable on GitHub, not an invented pointer.
    const hrefs = await panel.locator("a.icarus-chip").evaluateAll((as) => as.map((a) => a.href));
    expect(hrefs.length, "answer rendered with zero clickable citations").toBeGreaterThan(0);
    for (const href of hrefs) {
      expect(href, `citation link is not a real GitHub URL: ${href}`).toMatch(
        new RegExp(`^https://github\\.com/${REPO}/`)
      );
    }
  }
});

test("a repo the account has not connected shows nothing, live", async ({ context, worker, page }) => {
  const token = execSync("gh auth token", { encoding: "utf8" }).trim();
  await signIn(worker, token);

  // torvalds/linux is real, public, and (as of writing) not the account's
  // connected repo -- so this is the live proof of the same gate
  // extension.spec.js checks against a stub, this time against the real
  // /status response.
  await page.goto("https://github.com/torvalds/linux/blob/master/README", {
    waitUntil: "domcontentloaded",
  });
  await page.waitForTimeout(4000); // real network round trip to /status
  await expect(page.locator(".icarus-trigger-bar")).toHaveCount(0);
});
