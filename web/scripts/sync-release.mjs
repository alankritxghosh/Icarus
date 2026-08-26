// Copy the repo's release manifest into the app before every build and dev run.
//
// The website used to hardcode the sha256 and the "~2352 KB" size in its own
// source, so a new release meant editing the page by hand and nothing noticed
// when nobody did. Now the page renders whatever release.json says, and
// scripts/check_release.py proves release.json matches the real binary.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, "../../release.json");
const dst = resolve(here, "../src/generated/release.json");
mkdirSync(dirname(dst), { recursive: true });
copyFileSync(src, dst);
console.log("synced release.json -> web/src/generated/release.json");
