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

echo "==> ad-hoc code signing"
codesign --force --deep --sign - "${APP}"
codesign --verify --verbose "${APP}"

echo "==> done: ${ROOT}/${APP}"
echo "    launch with:  open \"${ROOT}/${APP}\""
