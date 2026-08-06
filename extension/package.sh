#!/usr/bin/env bash
# Package the Chrome extension for distribution.
#
# WHY THIS EXISTS
#
# Until now the extension had no packaging at all: the only way anyone ran it
# was `chrome://extensions -> Load unpacked` pointed at this directory. That
# works for the person who wrote it and nobody else, and it silently ships the
# test files and whatever else happens to be lying in the folder.
#
# WHAT CHROME ACTUALLY ALLOWS (checked, not assumed)
#
# A self-hosted .crx cannot be installed by a normal user on macOS or Windows --
# Chrome removed that path outside enterprise policy. So there are exactly two
# real channels:
#
#   1. The Chrome Web Store. The only one a non-technical user can use. Needs a
#      developer account, a listing, and review.
#   2. This zip, unzipped and side-loaded via Load unpacked with developer mode
#      on. Works today, for people willing to do that, and Chrome will keep
#      nagging them about developer-mode extensions.
#
# This script produces the artifact BOTH channels need: the Web Store upload is
# this same zip.
#
# Usage:  ./package.sh            -> dist/icarus-extension-<version>.zip
set -euo pipefail
cd "$(dirname "$0")"

VERSION="$(python3 -c 'import json;print(json.load(open("manifest.json"))["version"])')"
OUT="dist/icarus-extension-${VERSION}.zip"

# An explicit allowlist, not an exclude-list. A new file is not shipped until
# someone adds it here -- the failure mode of a glob-with-exclusions is that
# tomorrow's stray file (a scratch note, a key, a .env) ships silently.
FILES=(
  manifest.json
  background.js
  content.js
  lib.js
  render.js
  popup.html
  popup.js
)

for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "missing file listed in package.sh: $f" >&2; exit 1; }
done

# Refuse to ship a build pointed at a local brain -- it would install fine for
# whoever built it and fail for every user, remotely and with no obvious cause.
# Same guard the DMG release script applies (Icarus-Website/release-dmg.sh).
if ! grep -q 'const BRAIN_URL = "https://' background.js; then
  echo "background.js BRAIN_URL is not an https URL -- refusing to package." >&2
  exit 1
fi

rm -rf dist
mkdir -p dist
zip -q -X "$OUT" "${FILES[@]}"

echo "built $OUT"
echo "  version : $VERSION"
# Read the BRAIN_URL line specifically, not the first https:// in the file --
# the first match is a chromiumapp.org URL inside a comment, so a bare grep
# reported a brain this build does not talk to.
echo "  brain   : $(grep -oE 'const BRAIN_URL = "[^"]+"' background.js | sed 's/.*"\(.*\)"/\1/')"
echo "  sha256  : $(shasum -a 256 "$OUT" | cut -d' ' -f1)"
echo "  size    : $(( ($(wc -c < "$OUT") + 512) / 1024 )) KB"
echo
echo "Install (side-load): unzip, then chrome://extensions -> Developer mode"
echo "-> Load unpacked -> pick the unzipped folder."
