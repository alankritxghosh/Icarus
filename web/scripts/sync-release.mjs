// Copy the repo's release manifest into the app before every build and dev run.
//
// The website used to hardcode the sha256 and the "~2352 KB" size in its own
// source, so a new release meant editing the page by hand and nothing noticed
// when nobody did. Now the page renders whatever release.json says, and
// scripts/check_release.py proves release.json matches the published release.
//
// The fallback matters. A CLI `vercel --prod` uploads only web/, so the repo
// root -- and release.json with it -- is not on the build machine. The first
// version assumed the monorepo was always there, the copy threw, `npm run
// build` exited 1, and the deploy failed on Vercel while working locally.
// So: use the root manifest when it exists, otherwise keep the committed copy,
// and fail loudly only when there is neither.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../release.json");
const dst = resolve(here, "../src/generated/release.json");

if (existsSync(src)) {
  mkdirSync(dirname(dst), { recursive: true });
  copyFileSync(src, dst);
  console.log("synced release.json -> web/src/generated/release.json");
} else if (existsSync(dst)) {
  console.log("no repo-root release.json (standalone build); using committed copy");
} else {
  console.error("no release.json at the repo root and no committed copy in src/generated/");
  process.exit(1);
}
