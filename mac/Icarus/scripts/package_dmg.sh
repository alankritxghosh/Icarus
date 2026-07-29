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

# 2) Stamp the hosted brain URL and the update feed into the bundle's
#    Info.plist, then RE-SIGN (editing Info.plist invalidates the signature
#    the bundler just applied).
stamp() {   # stamp KEY VALUE
    /usr/libexec/PlistBuddy -c "Delete :$1" "${PLIST}" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Add :$1 string $2" "${PLIST}"
}

NEEDS_RESIGN=""

if [ -n "${ICARUS_BRAIN_URL:-}" ]; then
    echo "==> stamping ICARUS_BRAIN_URL=${ICARUS_BRAIN_URL}"
    stamp ICARUS_BRAIN_URL "${ICARUS_BRAIN_URL}"
    NEEDS_RESIGN=1
else
    echo "warning: ICARUS_BRAIN_URL not set — the app will point at the LOCAL brain" >&2
    echo "         (127.0.0.1:8000). Do not share this build; it can't reach a cloud brain." >&2
fi

# In-app updates. BOTH the feed and the public key are required: a feed with no
# key would let Sparkle fetch an update it cannot verify, and the app refuses
# to start an updater in that state rather than degrading into one that trusts
# whatever it downloads. See Sources/Icarus/Updater.swift.
if [ -n "${ICARUS_UPDATE_FEED_URL:-}" ] && [ -n "${ICARUS_UPDATE_PUBLIC_KEY:-}" ]; then
    echo "==> stamping update feed ${ICARUS_UPDATE_FEED_URL}"
    stamp SUFeedURL "${ICARUS_UPDATE_FEED_URL}"
    stamp SUPublicEDKey "${ICARUS_UPDATE_PUBLIC_KEY}"
    /usr/libexec/PlistBuddy -c "Delete :SUEnableAutomaticChecks" "${PLIST}" 2>/dev/null || true
    /usr/libexec/PlistBuddy -c "Add :SUEnableAutomaticChecks bool true" "${PLIST}"
    NEEDS_RESIGN=1
elif [ -n "${ICARUS_UPDATE_FEED_URL:-}" ] || [ -n "${ICARUS_UPDATE_PUBLIC_KEY:-}" ]; then
    echo "error: set BOTH ICARUS_UPDATE_FEED_URL and ICARUS_UPDATE_PUBLIC_KEY, or neither." >&2
    echo "       Half a configuration is how an unverified update gets installed." >&2
    exit 1
else
    echo "warning: no update feed configured — recipients of this build will have to" >&2
    echo "         re-download by hand for every future change." >&2
    echo "         Run scripts/make_update_keys.sh once, then set" >&2
    echo "         ICARUS_UPDATE_FEED_URL and ICARUS_UPDATE_PUBLIC_KEY." >&2
fi

if [ -n "${NEEDS_RESIGN}" ]; then
    # Re-sign with the SAME identity bundle.sh used. Re-signing ad-hoc here
    # would silently undo a stable certificate and hand every user another
    # Keychain prompt -- the exact problem make_signing_cert.sh exists to fix.
    IDENTITY="Icarus Self-Signed"
    if security find-certificate -c "${IDENTITY}" >/dev/null 2>&1; then
        echo "==> re-signing after Info.plist edit (${IDENTITY})"
        codesign --force --sign "${IDENTITY}" "${APP}"
    else
        echo "==> re-signing after Info.plist edit (ad-hoc)"
        codesign --force --deep --sign - "${APP}"
    fi
    codesign --verify --verbose "${APP}"
    codesign -d -r- "${APP}" 2>&1 | tail -1
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
echo
echo "    To publish it, do NOT copy it across by hand — this image's SHA-256 is"
echo "    pinned in four places across two repos (install.sh, index.html, and the"
echo "    Homebrew cask's sha256 + version), and each one refuses or misreports a"
echo "    build that doesn't match. Run the website repo's release script instead:"
echo "        ./release-dmg.sh ${ROOT}/${DMG}"
echo "    which restamps all four. It needs the tap checked out beside the website"
echo "    repo (or \$ICARUS_TAP_DIR set), and refuses to publish without it rather"
echo "    than leaving 'brew install' on the previous build."
