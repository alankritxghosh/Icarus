#!/usr/bin/env bash
# Assemble the SwiftPM executable into a signed Icarus.app bundle.
#
# Why this exists: macOS TCC will not grant microphone access to a bare Mach-O
# executable. It needs an .app bundle carrying an Info.plist with a mic usage
# string, plus a code signature, before it will even show the permission prompt.
# `swift build` cannot produce an .app, so we wrap its output here.
#
# Usage:  scripts/bundle.sh            # release build -> mac/Icarus/Icarus.app
#         open Icarus.app              # launch it (or double-click in Finder)
#
# Not for distribution: ad-hoc signature, no hardened runtime, no notarization.
set -euo pipefail

cd "$(dirname "$0")/.."          # mac/Icarus
ROOT="$(pwd)"
CONFIG="release"
BUILD_DIR=".build/${CONFIG}"
APP="Icarus.app"
CONTENTS="${APP}/Contents"

echo "==> swift build -c ${CONFIG}"
swift build -c "${CONFIG}"

BIN="${BUILD_DIR}/Icarus"
[ -x "${BIN}" ] || { echo "error: ${BIN} not found — did the build succeed?" >&2; exit 1; }

echo "==> assembling ${APP}"
rm -rf "${APP}"
mkdir -p "${CONTENTS}/MacOS" "${CONTENTS}/Resources"

cp "${BIN}" "${CONTENTS}/MacOS/Icarus"
cp "${ROOT}/Icarus-Info.plist" "${CONTENTS}/Info.plist"
printf 'APPL????' > "${CONTENTS}/PkgInfo"

# Sparkle ships as a real dynamic framework, and SwiftPM does not embed it --
# there is no "Embed Frameworks" phase outside Xcode, so the binary links
# @rpath/Sparkle.framework and would simply fail to launch. Copy it in and add
# the rpath ourselves.
#
# Nested code is signed FIRST and separately: `codesign --deep` is documented
# by Apple as a fallback for repairing bundles, not a way to sign one properly,
# and Sparkle's XPC helpers inside the framework need valid signatures of their
# own for the updater to run.
SPARKLE_FW="$(find .build -type d -name Sparkle.framework -path "*${CONFIG}*" -print -quit 2>/dev/null || true)"
if [ -n "${SPARKLE_FW}" ]; then
    echo "==> embedding Sparkle.framework"
    mkdir -p "${CONTENTS}/Frameworks"
    rm -rf "${CONTENTS}/Frameworks/Sparkle.framework"
    cp -R "${SPARKLE_FW}" "${CONTENTS}/Frameworks/"
    # SwiftPM's binary already carries an @rpath entry pointing at its build
    # dir; the bundle needs one pointing at its own Frameworks folder.
    install_name_tool -add_rpath "@executable_path/../Frameworks" \
        "${CONTENTS}/MacOS/Icarus" 2>/dev/null || true
else
    echo "warning: Sparkle.framework not found — in-app updates will be unavailable" >&2
fi

# Bake the static app icon from IconArt (same drawing the running app uses) so the
# Dock/Finder/DMG aren't a blank tile before first launch. The binary renders the
# .iconset headlessly; iconutil turns it into Resources/AppIcon.icns (CFBundleIconFile).
echo "==> generating AppIcon.icns from IconArt"
ICONSET_DIR="$(mktemp -d)/AppIcon.iconset"
mkdir -p "${ICONSET_DIR}"
"${CONTENTS}/MacOS/Icarus" --render-iconset "${ICONSET_DIR}"
iconutil -c icns -o "${CONTENTS}/Resources/AppIcon.icns" "${ICONSET_DIR}"
rm -rf "$(dirname "${ICONSET_DIR}")"

# SwiftPM emits per-target resource bundles (e.g. KeyboardShortcuts localizations,
# later WhisperKit assets). Bundle.module resolves them from the app's Resources.
shopt -s nullglob
for b in "${BUILD_DIR}"/*.bundle; do
    echo "    + resource bundle $(basename "$b")"
    cp -R "$b" "${CONTENTS}/Resources/"
done
shopt -u nullglob

# Warn (don't fail) if the binary picked up dynamic deps that need embedding —
# today everything links statically, but WhisperKit could change that.
EXTERNAL="$(otool -L "${CONTENTS}/MacOS/Icarus" | tail -n +2 | grep -vE '/usr/lib|/System/Library|@rpath|@executable_path' || true)"
if [ -n "${EXTERNAL}" ]; then
    echo "warning: binary links external dylibs — may need embedding in Contents/Frameworks:" >&2
    echo "${EXTERNAL}" >&2
fi

# Sign with the STABLE self-signed identity when it exists, else ad-hoc.
#
# Ad-hoc signatures have no certificate, so macOS derives the designated
# requirement from the binary's own hash -- which changes on every build, so
# the login Keychain treats each update as a different app and re-asks the
# user to authorise their saved GitHub token. A certificate makes the
# requirement stable. See scripts/make_signing_cert.sh.
#
# Detection is BEHAVIOURAL, not a policy query: a self-signed certificate is
# not "valid" to `security find-identity -p codesigning` (it has no trusted
# anchor) even though `codesign` will happily sign with it. So we try, and
# fall back -- a fresh clone or CI with no certificate still builds.
IDENTITY="Icarus Self-Signed"

# Sign nested code before the app that contains it -- an outer signature seals
# the inner ones, so signing the app first would immediately invalidate it.
sign_one() {
    codesign --force --options runtime --sign "$1" "$2" 2>/dev/null \
        || codesign --force --sign "$1" "$2" 2>/dev/null
}
sign_nested() {
    [ -d "${CONTENTS}/Frameworks/Sparkle.framework" ] || return 0
    find "${CONTENTS}/Frameworks/Sparkle.framework" \
         \( -name "*.xpc" -o -name "*.app" -o -name "*.framework" \) -depth \
        | while read -r nested; do sign_one "$1" "${nested}"; done
    sign_one "$1" "${CONTENTS}/Frameworks/Sparkle.framework"
}

if security find-certificate -c "${IDENTITY}" >/dev/null 2>&1 \
   && sign_nested "${IDENTITY}" && codesign --force --sign "${IDENTITY}" "${APP}" 2>/dev/null; then
    echo "==> signed with '${IDENTITY}' (stable designated requirement)"
else
    echo "==> ad-hoc code signing (no '${IDENTITY}' certificate found)"
    echo "    users will be re-prompted for Keychain access on every update;"
    echo "    run scripts/make_signing_cert.sh once to fix that."
    sign_nested -
    codesign --force --deep --sign - "${APP}"
fi
codesign --verify --verbose "${APP}"
codesign -d -r- "${APP}" 2>&1 | tail -1

echo "==> done: ${ROOT}/${APP}"
echo "    launch with:  open \"${ROOT}/${APP}\""
