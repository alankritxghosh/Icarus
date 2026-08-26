#!/usr/bin/env bash
# Pull the PUBLISHED release binaries into web/public/ and verify them.
#
# The DMG and the extension zip are gitignored, so a fresh clone has neither and
# `vercel --prod` would publish a site whose download button 404s. That is not
# hypothetical: it is the exact state the site shipped in until 2026-08-26.
#
# Rather than putting binaries in git history, this fetches the ones already
# serving and checks them against release.json. If they do not match, it fails
# and leaves nothing behind -- a half-downloaded DMG must never be deployable.
set -euo pipefail
cd "$(dirname "$0")/.."

URL=$(python3 -c 'import json;print(json.load(open("release.json"))["url"])')
BASE=$(dirname "$URL")
mkdir -p web/public
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

for name in Icarus.dmg icarus-extension.zip; do
  echo "fetching $name from $BASE"
  curl -fsSL --max-time 300 -o "$tmp/$name" "$BASE/$name"
done

# Verify BEFORE moving into place, so a bad download cannot be deployed.
python3 - "$tmp" <<'PY'
import hashlib, json, pathlib, sys
tmp = pathlib.Path(sys.argv[1])
m = json.loads(pathlib.Path("release.json").read_text())
bad = []
for key in ("dmg", "extension"):
    spec, f = m[key], tmp / m[key]["name"]
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    if f.stat().st_size != spec["bytes"] or digest != spec["sha256"]:
        bad.append(f"{spec['name']}: got {f.stat().st_size} bytes / {digest[:12]}…, "
                   f"release.json says {spec['bytes']} / {spec['sha256'][:12]}…")
if bad:
    print("\nfetched assets do NOT match release.json:")
    for b in bad:
        print("  ✗", b)
    print("\nEither the published build moved on and release.json is stale, or the\n"
          "download was corrupted. Nothing has been written to web/public/.")
    sys.exit(1)
PY

mv "$tmp"/Icarus.dmg "$tmp"/icarus-extension.zip web/public/
echo "verified against release.json and placed in web/public/"
