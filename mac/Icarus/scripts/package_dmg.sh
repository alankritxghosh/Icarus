#!/usr/bin/env bash
# Build an Icarus.dmg stamped with the hosted brain URL. Local builds may remain
# self/ad-hoc signed; a final-user build sets ICARUS_CODESIGN_IDENTITY to an
# exact Developer ID Application identity and ICARUS_NOTARY_PROFILE to a
# notarytool Keychain profile. ICARUS_REQUIRE_DEVELOPER_ID=1 and
# ICARUS_REQUIRE_NOTARIZATION=1 turn either missing prerequisite into a hard
# failure rather than an alpha artifact.
#
# Usage:
#   ICARUS_BRAIN_URL=https://your-brain.example scripts/package_dmg.sh
#
# Without ICARUS_BRAIN_URL the app falls back to the LOCAL brain (127.0.0.1:8000)
# — only useful for a local test build, not for sharing.
#
# Notarization credentials are read only from the named Keychain profile; this
# script never accepts an Apple password or API private key on argv.
set -euo pipefail

cd "$(dirname "$0")/.."          # mac/Icarus
ROOT="$(pwd)"
APP="Icarus.app"
PLIST="${APP}/Contents/Info.plist"
DMG="Icarus.dmg"
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' Icarus-Info.plist 2>/dev/null || echo 0.1.0)"
VOLNAME="Icarus ${VERSION}"

# 1) Build + assemble + sign the release .app.
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
    # The feed and public key are normally BAKED INTO Icarus-Info.plist -- they
    # are identical for every build, and an env var you forget would silently
    # ship an app that can never update itself. The env vars above exist only
    # to override that (e.g. pointing a test build at a staging feed).
    FEED="$(/usr/libexec/PlistBuddy -c 'Print :SUFeedURL' "${PLIST}" 2>/dev/null || true)"
    KEY="$(/usr/libexec/PlistBuddy -c 'Print :SUPublicEDKey' "${PLIST}" 2>/dev/null || true)"
    if [ -n "${FEED}" ] && [ -n "${KEY}" ]; then
        echo "==> update feed from Info.plist: ${FEED}"
    else
        echo "warning: no update feed — recipients of this build will have to" >&2
        echo "         re-download by hand for every future change." >&2
        echo "         Run scripts/make_update_keys.sh once, then add SUFeedURL" >&2
        echo "         and SUPublicEDKey to Icarus-Info.plist." >&2
    fi
fi

if [ -n "${NEEDS_RESIGN}" ]; then
    # Re-sign with the SAME identity bundle.sh used. Re-signing ad-hoc here
    # would silently undo a stable certificate and hand every user another
    # Keychain prompt -- the exact problem make_signing_cert.sh exists to fix.
    IDENTITY="${ICARUS_CODESIGN_IDENTITY:-Icarus Self-Signed}"
    if [ -n "${ICARUS_CODESIGN_IDENTITY:-}" ]; then
        security find-identity -v -p codesigning \
            | grep -Fq "\"${IDENTITY}\"" || {
                echo "error: requested code-signing identity is unavailable: ${IDENTITY}" >&2
                exit 1
            }
        echo "==> re-signing after Info.plist edit (${IDENTITY})"
        codesign --force --options runtime --timestamp --sign "${IDENTITY}" "${APP}"
    elif security find-certificate -c "${IDENTITY}" >/dev/null 2>&1; then
        echo "==> re-signing after Info.plist edit (${IDENTITY})"
        codesign --force --options runtime --sign "${IDENTITY}" "${APP}" 2>/dev/null \
            || codesign --force --sign "${IDENTITY}" "${APP}"
    else
        echo "==> re-signing after Info.plist edit (ad-hoc)"
        codesign --force --deep --sign - "${APP}"
    fi
    codesign --verify --verbose "${APP}"
    codesign -d -r- "${APP}" 2>&1 | tail -1
fi

# Say plainly which of the two kinds of artifact this is.
#
# Ad-hoc packaging is ALLOWED and is the accepted alpha model, but it is not
# distributable: an ad-hoc signature makes the app's designated requirement its
# own cdhash, which changes on EVERY build, so the login Keychain treats each
# update as a different app and re-prompts for the saved GitHub token -- and a
# background `Icarus --mcp` launch can end up waiting on a prompt nobody can
# see. This warning was removed along with the hard refusal in 4900025; the
# refusal is deliberately not coming back (it would block the alpha), but the
# artifact must not be able to look distributable when it is not.
# `site/release-dmg.sh` refuses to PUBLISH an ad-hoc build unless explicitly
# overridden, which is where the decision belongs.
AUTHORITY="$(codesign -dv --verbose=2 "${APP}" 2>&1 \
    | sed -n 's/^Authority=//p' | head -1)"
DEVELOPER_ID_SIGNED=""
if [[ "${AUTHORITY}" == "Developer ID Application:"* ]]; then
    DEVELOPER_ID_SIGNED=1
fi
if [ -n "${AUTHORITY}" ]; then
    echo "==> signing identity: ${AUTHORITY}"
else
    echo "" >&2
    echo "*** TEST ARTIFACT ONLY — ad-hoc signed, do not distribute. ***" >&2
    echo "    The signature changes on every build, so each update looks like" >&2
    echo "    a different app: users are re-prompted for their Keychain token," >&2
    echo "    and a headless MCP launch can hang on an invisible prompt." >&2
    echo "    Run mac/Icarus/scripts/make_signing_cert.sh once to fix this." >&2
    echo "" >&2
fi
if [ "${ICARUS_REQUIRE_DEVELOPER_ID:-0}" = "1" ] \
   && [ -z "${DEVELOPER_ID_SIGNED}" ]; then
    echo "error: final-user packaging requires a Developer ID Application signature" >&2
    exit 1
fi

# 3) Stage a drag-to-Applications layout + a first-open README, then build the DMG.
STAGE="$(mktemp -d)"
trap 'rm -rf "${STAGE}"' EXIT
cp -R "${APP}" "${STAGE}/"
ln -s /Applications "${STAGE}/Applications"
if [ -n "${DEVELOPER_ID_SIGNED}" ]; then
cat > "${STAGE}/READ ME FIRST.txt" <<'TXT'
Icarus — installation
=====================

1. Drag Icarus onto the Applications folder shown next to it.
2. Open Icarus from Applications.
3. Sign in with GitHub, connect a repository, then press Command-Shift-I to
   type a question or hold the Right Option key to speak.

Answers include clickable GitHub receipts, or an honest "no one wrote this
down" when the reason was never recorded.
TXT
else
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
fi

rm -f "${DMG}"
hdiutil create -volname "${VOLNAME}" -srcfolder "${STAGE}" -ov -format UDZO "${DMG}"

# 4) Optional final-user notarization. Apple requires a Developer ID signature,
# hardened runtime and timestamp before submission. `--wait` makes a rejected
# submission fail this build; stapling makes the ticket travel with the DMG.
if [ -n "${ICARUS_NOTARY_PROFILE:-}" ]; then
    [ -n "${DEVELOPER_ID_SIGNED}" ] || {
        echo "error: notarization requires a Developer ID Application signature" >&2
        exit 1
    }
    echo "==> submitting ${DMG} for Apple notarization"
    xcrun notarytool submit "${DMG}" \
        --keychain-profile "${ICARUS_NOTARY_PROFILE}" --wait
    xcrun stapler staple "${DMG}"
    xcrun stapler validate "${DMG}"
    spctl -a -vv -t open --context context:primary-signature "${DMG}"
elif [ "${ICARUS_REQUIRE_NOTARIZATION:-0}" = "1" ]; then
    echo "error: final-user packaging requires ICARUS_NOTARY_PROFILE" >&2
    exit 1
fi

echo "==> done: ${ROOT}/${DMG}"
echo "    Verify independently before promotion:"
echo "        \"${ROOT}/scripts/verify_distribution.sh\" \"${ROOT}/${DMG}\""
echo "    Then follow docs/LAUNCH_CANARY.md Gate 6. The retired"
echo "    site/release-dmg.sh targets the old alpha/Vercel asset path and must not"
echo "    be used for the current GitHub Releases distribution."
