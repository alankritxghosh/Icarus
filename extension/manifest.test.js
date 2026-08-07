// extension/manifest.test.js
// The manifest is a set of PATHS. Chrome resolves them at load time, so a wrong
// one is not a subtle bug: the extension refuses to load, and the Web Store
// rejects the upload. Nothing checked them until 2026-08-06, which is when four
// icon paths were added at once.
//
// The second half is the more valuable half. package.sh ships an explicit
// allowlist, so it is possible for the manifest to reference a file the zip
// does not contain -- which works perfectly when loaded unpacked from a source
// checkout and fails only for people who install the packaged build. That is
// the worst shape of bug this project can ship: invisible to whoever built it.

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const DIR = __dirname;
const manifest = JSON.parse(fs.readFileSync(path.join(DIR, "manifest.json"), "utf8"));

/** Every path the manifest tells Chrome to load. */
function referencedFiles(m) {
  const out = [];
  for (const p of Object.values(m.icons || {})) out.push(p);
  for (const p of Object.values((m.action && m.action.default_icon) || {})) out.push(p);
  if (m.action && m.action.default_popup) out.push(m.action.default_popup);
  if (m.background && m.background.service_worker) out.push(m.background.service_worker);
  for (const cs of m.content_scripts || []) for (const js of cs.js || []) out.push(js);
  return [...new Set(out)];
}

test("manifest is valid MV3 with a version", () => {
  assert.equal(manifest.manifest_version, 3);
  assert.match(manifest.version, /^\d+\.\d+\.\d+$/);
  assert.ok(manifest.name && manifest.description);
});

test("the Mac bridge permission and worker dependency ship together", () => {
  assert.ok(
    (manifest.permissions || []).includes("nativeMessaging"),
    "nativeMessaging permission is required for the Mac app bridge"
  );
  const bg = fs.readFileSync(path.join(DIR, "background.js"), "utf8");
  const imported = bg.match(/importScripts\("([^"]+)"\)/);
  assert.ok(imported, "background.js must load its bridge policy");
  assert.ok(fs.existsSync(path.join(DIR, imported[1])), `missing ${imported[1]}`);
  const packageScript = fs.readFileSync(path.join(DIR, "package.sh"), "utf8");
  assert.match(packageScript, new RegExp(`^\\s*${imported[1]}\\s*$`, "m"));
});

test("every file the manifest references exists on disk", () => {
  for (const rel of referencedFiles(manifest)) {
    assert.ok(fs.existsSync(path.join(DIR, rel)), `manifest references missing file: ${rel}`);
  }
});

test("the 128px icon the Web Store requires is present and square", () => {
  const rel = (manifest.icons || {})["128"];
  assert.ok(rel, "Web Store submission is rejected without a 128x128 icon");
  const buf = fs.readFileSync(path.join(DIR, rel));
  // PNG IHDR: width/height are big-endian uint32 at byte 16 and 20.
  assert.equal(buf.toString("ascii", 1, 4), "PNG", `${rel} is not a PNG`);
  assert.equal(buf.readUInt32BE(16), 128, `${rel} width`);
  assert.equal(buf.readUInt32BE(20), 128, `${rel} height`);
});

test("package.sh ships every file the manifest references", () => {
  // The "works unpacked, broken when installed" guard. Reads the real
  // allowlist rather than a copy of it, so the two cannot drift.
  const sh = fs.readFileSync(path.join(DIR, "package.sh"), "utf8");
  const block = sh.match(/^FILES=\(\n([\s\S]*?)^\)/m);
  assert.ok(block, "could not find the FILES=( ... ) allowlist in package.sh");
  const shipped = new Set(
    block[1].split("\n").map((l) => l.trim()).filter((l) => l && !l.startsWith("#"))
  );
  assert.ok(shipped.has("manifest.json"), "the manifest itself must be shipped");
  for (const rel of referencedFiles(manifest)) {
    assert.ok(shipped.has(rel), `manifest references ${rel}, but package.sh does not ship it`);
  }
});

test("the brain host permission matches the URL background.js actually calls", () => {
  // A host permission that does not cover the fetch target fails at runtime,
  // silently, only once a user asks something -- and only in a packaged build
  // where you cannot just open devtools on someone else's machine.
  const bg = fs.readFileSync(path.join(DIR, "background.js"), "utf8");
  const brain = bg.match(/const BRAIN_URL = "([^"]+)"/);
  assert.ok(brain, "background.js has no BRAIN_URL");
  const origin = new URL(brain[1]).origin;
  const covered = (manifest.host_permissions || []).some(
    (p) => p.startsWith(origin) || p === `${origin}/*`
  );
  assert.ok(covered, `no host_permission covers ${origin}`);
});

test("no content script runs outside GitHub file pages", () => {
  // The privacy claim made on the website and in the store listing: it acts
  // only on blob pages. If a match pattern ever widens, that copy becomes false.
  for (const cs of manifest.content_scripts || []) {
    for (const m of cs.matches || []) {
      assert.match(m, /^https:\/\/github\.com\/\*\/\*\/blob\/\*$/, `unexpected match pattern: ${m}`);
    }
  }
});
