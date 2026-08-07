// What this covers that `node --test extension/*.test.js` cannot.
//
// Those 41 tests are pure functions: string parsing and HTML-string building.
// Every bug the extension has actually shipped lived outside them, and was
// found by loading it in a browser:
//
//   - the stylesheet was injected lazily inside showPanel, so the FIRST trigger
//     a user ever saw was completely unstyled;
//   - an inline style.position="relative" silently overrode the CSS class's
//     position:fixed, putting the panel off-screen at left:-24px;
//   - a content script's own fetch() is bound by the GitHub page's CORS and
//     Private Network Access rules, so every brain call failed with a bare
//     "Failed to fetch" until they were relayed through the service worker.
//
// None of those are visible without Chrome. This file runs the real unpacked
// extension in real Chromium against real github.com, with only the brain
// stubbed.

const fs = require("node:fs");
const path = require("node:path");
const { test, expect, signIn, stubBrain, blobUrl, BRAIN_ORIGIN, EXT_DIR } =
  require("./fixtures");

const FILE = "llm/utils.py";

test("the stub targets the origin background.js actually calls", async () => {
  // Guard against this harness quietly testing nothing: if BRAIN_URL moves and
  // the stub does not, every route falls through to the real network and the
  // failures would look like product bugs.
  const bg = fs.readFileSync(path.join(EXT_DIR, "background.js"), "utf8");
  const url = bg.match(/const BRAIN_URL = "([^"]+)"/)[1];
  expect(new URL(url).origin).toBe(BRAIN_ORIGIN);
});

test("the extension loads and its service worker starts", async ({ worker }) => {
  // A manifest path Chrome cannot resolve, or a service worker that throws on
  // load, never produces a worker. This is the check the static manifest tests
  // only approximate.
  expect(worker.url()).toContain("background.js");
});

test("a line selection on the connected repo shows the Ask bar", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context);
  await page.goto(blobUrl("simonw/llm", FILE, "#L149-L153"), { waitUntil: "domcontentloaded" });

  const bar = page.locator(".icarus-trigger-bar");
  await expect(bar).toBeVisible();
  await expect(page.locator(".icarus-ask-btn")).toHaveText("Ask Icarus");
  // The input is the primary path (it feeds better neighbour evidence), so its
  // presence is part of the contract, not decoration.
  await expect(page.locator(".icarus-question-input")).toBeVisible();
});

test("the trigger is styled and on-screen", async ({ context, worker, page }) => {
  // Both of these reproduce real shipped bugs. Asserting "visible" alone would
  // have passed while the panel sat at left:-24px in a 1440px viewport.
  await signIn(worker);
  await stubBrain(context);
  await page.goto(blobUrl("simonw/llm", FILE, "#L149-L153"), { waitUntil: "domcontentloaded" });

  const bar = page.locator(".icarus-trigger-bar");
  await expect(bar).toBeVisible();

  const box = await bar.boundingBox();
  const size = page.viewportSize();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.y).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(size.width);

  // Styled, not raw DOM: the stylesheet must be injected by the time the FIRST
  // trigger renders, not lazily when a panel later opens.
  //
  // Checked on properties the stylesheet actually sets. The BAR is a
  // transparent flex container by design, so asserting a background on it
  // failed against correct code -- the button is what carries the paint.
  expect(await bar.evaluate((el) => getComputedStyle(el).position)).toBe("fixed");
  const btn = await page.locator(".icarus-ask-btn").evaluate((el) => {
    const cs = getComputedStyle(el);
    return { bg: cs.backgroundColor, radius: cs.borderRadius };
  });
  expect(btn.bg).toBe("rgb(22, 24, 29)");   // #16181D
  expect(btn.radius).toBe("6px");
});

test("asking renders a cited answer, with the index citation labelled", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context, {
    explain: {
      verdict: "answer",
      answer: "It returns an httpx.Client configured for logging.",
      citations: [
        { ref: "code:llm/utils.py#L149-L153", url: "https://github.com/simonw/llm/blob/x/llm/utils.py#L149-L153" },
        { ref: "index:overview", url: null },
      ],
      searched: ["code:llm/utils.py#L149-L153"],
      anchored: ["code:llm/utils.py#L149-L153"],
    },
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L149-L153"), { waitUntil: "domcontentloaded" });

  await page.locator(".icarus-ask-btn").click();

  const panel = page.locator(".icarus-panel");
  await expect(panel).toBeVisible();
  await expect(panel).toContainText("httpx.Client configured for logging");

  // Today's honesty fix, verified where a user actually sees it: the index
  // citation reads as words and is NOT a link, while a real ref still links.
  await expect(panel).toContainText("Icarus's own index");
  await expect(panel).not.toContainText("index:overview");
  const hrefs = await panel.locator("a.icarus-chip").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  expect(hrefs.some((h) => h && h.includes("llm/utils.py"))).toBe(true);
  expect(hrefs.some((h) => h && h.includes("index"))).toBe(false);
});

test("an honest unknown renders as an unknown, not an empty panel", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context, {
    explain: {
      verdict: "unknown", answer: "", citations: [],
      searched: ["pr:1", "pr:2"], anchored: [],
    },
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L149-L153"), { waitUntil: "domcontentloaded" });
  await page.locator(".icarus-ask-btn").click();

  await expect(page.locator(".icarus-panel")).toContainText("No one wrote this down");
});

test("a repo that is not the connected one shows nothing", async ({ context, worker, page }) => {
  // The gate that keeps Icarus off every other repository on GitHub.
  await signIn(worker);
  await stubBrain(context, { repo: "someone/else" });
  await page.goto(blobUrl("simonw/llm", FILE, "#L149-L153"), { waitUntil: "domcontentloaded" });

  await page.waitForTimeout(1500);
  await expect(page.locator(".icarus-trigger-bar")).toHaveCount(0);
});

test("a non-blob GitHub page shows nothing", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context);
  await page.goto("https://github.com/simonw/llm/issues", { waitUntil: "domcontentloaded" });

  await page.waitForTimeout(1500);
  await expect(page.locator(".icarus-trigger-bar")).toHaveCount(0);
});

test("a blob page with no line selection shows nothing", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context);
  await page.goto(blobUrl("simonw/llm", FILE), { waitUntil: "domcontentloaded" });

  await page.waitForTimeout(1500);
  await expect(page.locator(".icarus-trigger-bar")).toHaveCount(0);
});

test("signed out, nothing is injected", async ({ context, page }) => {
  // No signIn(): getToken returns null, fetchConnectedRepoStatus short-circuits.
  await stubBrain(context);
  await page.goto(blobUrl("simonw/llm", FILE, "#L149-L153"), { waitUntil: "domcontentloaded" });

  await page.waitForTimeout(1500);
  await expect(page.locator(".icarus-trigger-bar")).toHaveCount(0);
});

test("activates across Python, TypeScript, and C repositories on main and master", async ({ context, worker, page }) => {
  await signIn(worker);
  let connectedRepo = "simonw/llm";
  await stubBrain(context, { repo: () => connectedRepo });
  const cases = [
    ["simonw/llm", "llm/utils.py", "main"],
    ["muxinc/media-chrome", "src/js/constants.ts", "main"],
    ["torvalds/linux", "kernel/sched/core.c", "master"],
  ];

  for (const [repo, file, ref] of cases) {
    connectedRepo = repo;
    await page.goto(blobUrl(repo, file, "#L1-L3", ref), {
      waitUntil: "domcontentloaded",
    });
    await expect(page.locator(".icarus-trigger-bar"), `${repo} (${ref})`).toBeVisible({
      timeout: 20_000,
    });
  }
});

test("double-submit produces exactly one explain request", async ({ context, worker, page }) => {
  await signIn(worker);
  let explainCalls = 0;
  await stubBrain(context, {
    onExplain: () => { explainCalls += 1; },
    explain: {
      verdict: "unknown", answer: "", citations: [],
      searched: ["code:llm/utils.py#L1-L3"], anchored: [],
    },
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1-L3"), {
    waitUntil: "domcontentloaded",
  });

  await page.locator(".icarus-ask-btn").dblclick();
  await expect(page.locator(".icarus-panel")).toContainText("No one wrote this down");
  expect(explainCalls).toBe(1);
});

test("a malformed successful server body is an error, never an honest unknown", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context, { explainRaw: "{definitely-not-json" });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1-L3"), {
    waitUntil: "domcontentloaded",
  });

  await page.locator(".icarus-ask-btn").click();
  const panel = page.locator(".icarus-panel");
  await expect(panel).toContainText("invalid explanation");
  await expect(panel).not.toContainText("No one wrote this down");
});

test("an explain transport failure is an error, never an honest unknown", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context, { abortExplain: true });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1-L3"), {
    waitUntil: "domcontentloaded",
  });

  await page.locator(".icarus-ask-btn").click();
  const panel = page.locator(".icarus-panel");
  await expect(panel).toContainText(/fetch|network/i);
  await expect(panel).not.toContainText("No one wrote this down");
});

test("rechecks the app's connected repo while the GitHub tab remains open", async ({ context, worker, page }) => {
  await signIn(worker);
  let connectedRepo = "simonw/llm";
  await stubBrain(context, { repo: () => connectedRepo });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1"), {
    waitUntil: "domcontentloaded",
  });
  await expect(page.locator(".icarus-trigger-bar")).toBeVisible();

  connectedRepo = "muxinc/media-chrome";
  await page.evaluate(() => { location.hash = "#L2"; });
  await expect(page.locator(".icarus-trigger-bar")).toHaveCount(0);
});

test("an explain response arriving after line navigation cannot overwrite the new trigger", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context, {
    explainDelay: 1_500,
    explain: {
      verdict: "answer",
      answer: "This answer belongs to the old line.",
      citations: [{ ref: "code:llm/utils.py#L1", url: null }],
      searched: ["code:llm/utils.py#L1"],
      anchored: [],
    },
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1"), {
    waitUntil: "domcontentloaded",
  });
  await page.locator(".icarus-ask-btn").click();
  await page.evaluate(() => { location.hash = "#L2"; });

  await expect(page.locator(".icarus-trigger-bar")).toBeVisible();
  await page.waitForTimeout(1_800);
  await expect(page.locator(".icarus-panel")).toHaveCount(0);
  await expect(page.locator(".icarus-trigger-bar")).toBeVisible();
});

test("a slower old status response cannot erase a newer selection", async ({ context, worker, page }) => {
  await signIn(worker);
  let statusCalls = 0;
  await stubBrain(context, {
    statusDelay: () => {
      statusCalls += 1;
      return statusCalls === 1 ? 1_500 : 0;
    },
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1"), {
    waitUntil: "domcontentloaded",
  });
  await page.evaluate(() => { location.hash = "#L2"; });

  await expect(page.locator(".icarus-trigger-bar")).toBeVisible();
  await page.waitForTimeout(1_800);
  await expect(page.locator(".icarus-trigger-bar")).toBeVisible();
});

test("an indexing abstention says Icarus has not finished reading", async ({ context, worker, page }) => {
  await signIn(worker);
  await stubBrain(context, {
    explain: {
      verdict: "unknown", answer: "", citations: [], searched: [],
      anchored: [], indexing: true,
    },
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1"), {
    waitUntil: "domcontentloaded",
  });
  await page.locator(".icarus-ask-btn").click();
  await expect(page.locator(".icarus-panel")).toContainText("haven’t finished reading");
});

test("auth and entitlement refusals remain distinct", async ({ context, worker, page }) => {
  await signIn(worker);
  let refusal = 403;
  await stubBrain(context, {
    explainStatus: () => refusal,
    explain: () => ({
      error: refusal === 403
        ? "your GitHub account can't read the connected repo"
        : "sign in with GitHub to continue",
    }),
  });
  await page.goto(blobUrl("simonw/llm", FILE, "#L1"), {
    waitUntil: "domcontentloaded",
  });

  await page.locator(".icarus-ask-btn").click();
  await expect(page.locator(".icarus-panel")).toContainText("can't read the connected repo");

  refusal = 401;
  await page.evaluate(() => { location.hash = "#L2"; });
  await expect(page.locator(".icarus-trigger-bar")).toBeVisible();
  await page.locator(".icarus-ask-btn").click();
  await expect(page.locator(".icarus-panel")).toContainText("Sign in with GitHub");
});
