#!/usr/bin/env bash
# Build a distributable Icarus.dmg: the release .app (ad-hoc signed) stamped with
# the hosted brain URL, plus a drag-to-Applications layout and first-open notes.
#
# Usage:
#   ICARUS_BRAIN_URL=https://your-brain.example scripts/package_dmg.sh
#
# Without ICARUS_BRAIN_URL the app falls back to the LOCAL brain (127.0.0.1:8000)
# — only useful for a local test build, not for sharing.
#
# NOT notarized (no paid Apple Developer ID): recipients take a one-time Gatekeeper
# step — see the bundled "READ ME FIRST.txt" and docs/DISTRIBUTION.md.
set -euo pipefail

cd "$(dirname "$0")/.."          # mac/Icarus
ROOT="$(pwd)"
APP="Icarus.app"
PLIST="${APP}/Contents/Info.plist"
DMG="Icarus.dmg"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' Icarus-Info.plist 2>/dev/null || echo 0.1.0)"
VOLNAME="Icarus ${VERSION}"

# 1) Build + assemble + ad-hoc sign the release .app.
"${ROOT}/scripts/bundle.sh"

# 2) Stamp the hosted brain URL into the bundle's Info.plist, then RE-SIGN
#    (editing Info.plist invalidates the signature the bundler just applied).
if [ -n "${ICARUS_BRAIN_URL:-}" ]; then
    echo "==> stamping ICARUS_BRAIN_URL=${ICARUS_BRAIN_URL}"
    /usr/libexec/PlistBuddy -c "Delete :ICARUS_BRAIN_URL" "${PLIST}" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Add :ICARUS_BRAIN_URL string ${ICARUS_BRAIN_URL}" "${PLIST}"
    echo "==> re-signing after Info.plist edit"
    codesign --force --deep --sign - "${APP}"
    codesign --verify --verbose "${APP}"
else
    echo "warning: ICARUS_BRAIN_URL not set — the app will point at the LOCAL brain" >&2
    echo "         (127.0.0.1:8000). Do not share this build; it can't reach a cloud brain." >&2
fi

# 3) Stage a drag-to-Applications layout + a first-open README, then build the DMG.
STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT
cp -R "${APP}" "${STAGE}/"
ln -s /Applications "${STAGE}/Applications"
cat > "${STAGE}/READ ME FIRST.txt" <<'TXT'
Icarus — first-open instructions
================================

Icarus is not signed with a paid Apple Developer ID, so macOS asks you to
confirm it once before the first launch. This is expected for this alpha.

1. Drag Icarus onto the Applications folder shown next to it.
2. Open your Applications folder and try to open Icarus. macOS may say it
   "cannot be opened because Apple cannot check it for malicious software."
3. Open System Settings -> Privacy & Security, scroll down, and click
   "Open Anyway" next to the Icarus message, then confirm.
   (On older macOS you can instead right-click Icarus -> Open.)

If no "Open Anyway" button appears, open the Terminal app and run:
   xattr -dr com.apple.quarantine /Applications/Icarus.app
then open Icarus normally.

You only do this once. After that, Icarus opens like any other app.

Using Icarus: click "Sign in with GitHub", connect a public repo (for example
simonw/llm), then press Command-Shift-I anywhere and type a question — or hold
the Right Option key and speak it. Answers come with clickable GitHub receipts,
or an honest "no one wrote this down" when the reason was never recorded.
TXT

rm -f "${DMG}"
hdiutil create -volname "${VOLNAME}" -srcfolder "${STAGE}" -ov -format UDZO "${DMG}"

echo "==> done: ${ROOT}/${DMG}"
echo "    share this file. Recipients follow the bundled READ ME FIRST.txt."
