#!/bin/sh
# Publish a new Icarus.dmg.
#
# The disk image's SHA-256 is pinned in FOUR places across two repositories:
# install.sh, index.html, and the Homebrew cask's sha256 and version. Every one
# of them refuses or misrepresents a build that does not match, so updating some
# and not others does not fail loudly -- it leaves one install path serving the
# previous build while the others move on. This script stamps all four from a
# single source of truth: the image itself.
#
# Works with a DMG from either source -- a local build
# (mac/Icarus/scripts/package_dmg.sh) or the dmg.yml CI workflow artifact.
#
# Usage:
#   ./release-dmg.sh /path/to/Icarus.dmg
#   ./release-dmg.sh /path/to/Icarus.dmg --skip-cask
#
# The Homebrew cask lives in a separate repository. This script looks for it at
# $ICARUS_TAP_DIR, then at ../../homebrew-icarus (this script lives in
# jarvis_engineering/site, so that resolves to a sibling of jarvis_engineering
# itself), and REFUSES to publish if it finds neither -- leaving the tap stale
# has to be a decision (--skip-cask), not an accident of which directories
# happen to be checked out.
#
# jarvis_engineering/site is the deploy source of truth (2026-08-07 -- this
# repo previously diverged from a separate Icarus-Website repo whose git-push
# auto-deployed over CLI-deployed changes here; that git integration was
# disconnected). Deploy is `vercel --prod` from this directory, NOT a git
# push -- site/Icarus.dmg is gitignored on purpose (avoid binary bloat in this
# repo's history), so nothing here triggers an auto-deploy. install.sh,
# index.html, and appcast.xml ARE tracked and should be committed after a
# release; the DMG bytes themselves only ever live in the Vercel deployment.

set -eu

echo "error: site/release-dmg.sh is retired; it targets the old Vercel-hosted," >&2
echo "self-signed alpha release path and does not update release.json or the" >&2
echo "GitHub Release assets used by the current website." >&2
echo "Follow docs/LAUNCH_CANARY.md Gate 6 with a verified notarized artifact." >&2
exit 1

SRC=""
SKIP_CASK=0
# Publishing an ad-hoc-signed build must be a DECISION, never a default --
# see the signature check further down for what it costs a user.
ALLOW_ADHOC=0
for arg in "$@"; do
  case "$arg" in
    --skip-cask) SKIP_CASK=1 ;;
    --allow-adhoc) ALLOW_ADHOC=1 ;;
    -*) echo "unknown option: $arg" >&2; exit 1 ;;
    *) SRC="$arg" ;;
  esac
done

[ -n "$SRC" ] || { echo "usage: $0 /path/to/Icarus.dmg [--skip-cask] [--allow-adhoc]" >&2; exit 1; }
[ -f "$SRC" ] || { echo "no such file: $SRC" >&2; exit 1; }

# Resolve SRC before cd, so a relative path still works.
SRC="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")"
cd "$(dirname "$0")"

# Locate the cask BEFORE touching anything. Stamping the website first and only
# then discovering the tap is missing would leave exactly the half-updated state
# this script exists to prevent.
CASK=""
if [ "$SKIP_CASK" -eq 0 ]; then
  TAP="${ICARUS_TAP_DIR:-../../homebrew-icarus}"
  CASK="$TAP/Casks/icarus.rb"
  if [ ! -f "$CASK" ]; then
    echo "Cannot find the Homebrew cask at: $CASK" >&2
    echo >&2
    echo "The tap pins this same hash. Publishing without updating it leaves" >&2
    echo "'brew install' serving the PREVIOUS build while every other install" >&2
    echo "path moves to the new one -- quietly, and only for brew users." >&2
    echo >&2
    echo "Clone it beside jarvis_engineering:" >&2
    echo "    git clone https://github.com/alankritxghosh/homebrew-icarus ../../homebrew-icarus" >&2
    echo "or point ICARUS_TAP_DIR at an existing checkout," >&2
    echo "or pass --skip-cask to leave the tap stale deliberately." >&2
    exit 1
  fi
fi

TMP="$(mktemp -d)"
MNT="$TMP/mnt"
cleanup() {
  [ -d "$MNT" ] && hdiutil detach "$MNT" -quiet 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

# Guard against publishing a build that points at a local brain. Such a build
# installs and launches perfectly for whoever built it, and fails for every
# tester — remotely, and without an obvious cause. Catch it here instead.
echo "Checking the disk image..."
mkdir -p "$MNT"
hdiutil attach "$SRC" -nobrowse -quiet -mountpoint "$MNT"
[ -d "$MNT/Icarus.app" ] || { echo "No Icarus.app inside $SRC — not an Icarus disk image." >&2; exit 1; }

PLIST="$MNT/Icarus.app/Contents/Info.plist"
BRAIN="$(/usr/libexec/PlistBuddy -c 'Print :ICARUS_BRAIN_URL' "$PLIST" 2>/dev/null || echo '')"
case "$BRAIN" in
  https://*) : ;;
  '')
    echo "This build has no ICARUS_BRAIN_URL stamped, so it falls back to" >&2
    echo "127.0.0.1:8000 and cannot reach a hosted brain. Refusing to publish." >&2
    echo "Rebuild with: ICARUS_BRAIN_URL=https://... scripts/package_dmg.sh" >&2
    exit 1 ;;
  *)
    echo "This build points at '$BRAIN', which is not a hosted https brain." >&2
    echo "Refusing to publish." >&2
    exit 1 ;;
esac
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST" 2>/dev/null || echo '?')"

# Validate the SIGNATURE, not just where the build points.
#
# `package_dmg.sh` falls back to ad-hoc signing when no stable identity is on
# the machine (the accepted alpha model), so a fresh runner silently produces
# an artifact whose designated requirement is its own cdhash. That changes on
# every build: the login Keychain treats each update as a different app and
# re-prompts for the saved GitHub token, and a background `Icarus --mcp`
# launch can wait on a prompt nobody can see. Nothing checked this before
# publishing, so the difference was invisible until a user hit it.
#
# Refused by default rather than warned about, because the failure lands on
# someone else's Mac. `--allow-adhoc` publishes anyway for a deliberate test
# release -- the point is that it becomes a decision, not a default.
if ! codesign --verify --deep --strict "$MNT/Icarus.app" 2>/dev/null; then
  echo "The app inside $SRC fails codesign --verify. Refusing to publish a" >&2
  echo "broken or tampered bundle." >&2
  hdiutil detach "$MNT" -quiet || true
  exit 1
fi
# The LEAF CERTIFICATE, not the display name. Accepting any non-empty
# Authority= only proves "something signed this": a newly generated
# self-signed certificate with the same common name passes while changing the
# app's designated requirement, which is the exact Keychain re-prompt /
# invisible-headless-prompt problem this check exists to prevent --
# make_signing_cert.sh warns about precisely that. Raised in review.
#
# A certificate fingerprint is public information, so pinning it here is safe.
# Rotating the certificate is a real (rare) event: set
# ICARUS_SIGNING_CERT_SHA256 to the new fingerprint deliberately, knowing every
# installed copy will prompt once for its Keychain token.
EXPECTED_CERT_SHA256="${ICARUS_SIGNING_CERT_SHA256:-8624652617bcf4aeddfd5f6e598bc2acdc019b6bc39067be02756fa2797a509e}"

# Extract into $TMP: codesign writes the DER files into the CURRENT directory,
# and this script has already cd'd into site/.
( cd "$TMP" && codesign -d --extract-certificates=leaf "$MNT/Icarus.app" ) \
  >/dev/null 2>&1 || true
CERT_SHA=""
[ -f "$TMP/leaf0" ] && CERT_SHA="$(shasum -a 256 "$TMP/leaf0" | cut -d ' ' -f 1)"

if [ -z "$CERT_SHA" ]; then
  # No leaf certificate at all: an ad-hoc signature.
  if [ "$ALLOW_ADHOC" = 1 ]; then
    echo "WARNING: publishing an AD-HOC signed build because --allow-adhoc was" >&2
    echo "         given. Every future update will re-prompt users for their" >&2
    echo "         Keychain token. Test release only." >&2
  else
    echo "This build is AD-HOC signed, so its identity changes on every build:" >&2
    echo "each update looks like a different app, users are re-prompted for the" >&2
    echo "GitHub token in their Keychain, and a headless MCP launch can hang on" >&2
    echo "a prompt they cannot see. Refusing to publish." >&2
    echo "" >&2
    echo "Fix: run mac/Icarus/scripts/make_signing_cert.sh once on the build" >&2
    echo "machine, then rebuild. To publish a deliberate TEST release anyway:" >&2
    echo "  $0 $SRC --allow-adhoc" >&2
    hdiutil detach "$MNT" -quiet || true
    exit 1
  fi
elif [ "$CERT_SHA" != "$EXPECTED_CERT_SHA256" ]; then
  echo "This build is signed by a DIFFERENT certificate than the published" >&2
  echo "releases:" >&2
  echo "  expected $EXPECTED_CERT_SHA256" >&2
  echo "  found    $CERT_SHA" >&2
  echo "" >&2
  echo "Its display name may match, but a different leaf certificate means a" >&2
  echo "different designated requirement: every installed copy will treat the" >&2
  echo "update as a new app and prompt again for its Keychain token, and a" >&2
  echo "headless MCP launch can hang on a prompt nobody can see." >&2
  echo "" >&2
  echo "If the signing certificate was rotated on purpose, publish with:" >&2
  echo "  ICARUS_SIGNING_CERT_SHA256=$CERT_SHA $0 $SRC" >&2
  hdiutil detach "$MNT" -quiet || true
  exit 1
else
  echo "Signing certificate: $CERT_SHA (pinned)"
fi

hdiutil detach "$MNT" -quiet

cp "$SRC" Icarus.dmg

# Regenerate the Sparkle update feed. Without this, a published DMG is
# invisible to every already-installed copy of Icarus -- they poll appcast.xml
# and would keep seeing the previous release forever, which looks exactly like
# "updates don't work" and is impossible to notice from this side.
#
# generate_appcast signs each build with the PRIVATE EdDSA key in the login
# keychain, so this can only run on the machine that holds it. It lives in the
# Icarus repo's SwiftPM artifacts; point ICARUS_APPCAST_TOOL at it to override.
APPCAST_TOOL="${ICARUS_APPCAST_TOOL:-}"
if [ -z "$APPCAST_TOOL" ]; then
  APPCAST_TOOL="$(find "$(dirname "$SRC")/.." -type f -name generate_appcast -perm -u+x -print -quit 2>/dev/null || true)"
fi
if [ -n "$APPCAST_TOOL" ] && [ -x "$APPCAST_TOOL" ]; then
  FEED_DIR="$(mktemp -d)"
  cp Icarus.dmg "$FEED_DIR/"
  # Deliberately NOT carrying the previous appcast forward. Every release is
  # published to the SAME URL (/Icarus.dmg), so an older entry would keep
  # pointing at that URL while the bytes behind it are now a newer build --
  # an item whose length and signature no longer describe what downloading it
  # actually gets you. One DMG URL means one entry. If multiple versions ever
  # need to stay downloadable, the filename has to carry the version first.
  if "$APPCAST_TOOL" --download-url-prefix "https://icarus-website-kappa.vercel.app/" "$FEED_DIR" >/dev/null 2>&1; then
    cp "$FEED_DIR/appcast.xml" appcast.xml
    STAMPED_FEED="appcast.xml"
  else
    echo "error: could not sign the update feed -- is the Sparkle private key" >&2
    echo "       in this machine's login keychain? Publishing a DMG without a" >&2
    echo "       matching appcast entry means nobody can update to it." >&2
    rm -rf "$FEED_DIR"
    exit 1
  fi
  rm -rf "$FEED_DIR"
else
  echo "warning: generate_appcast not found -- appcast.xml NOT regenerated," >&2
  echo "         so installed copies will not be offered this build." >&2
  STAMPED_FEED="NOT UPDATED"
fi
SHA="$(shasum -a 256 Icarus.dmg | cut -d ' ' -f 1)"
KB="$(( ($(wc -c < Icarus.dmg) + 512) / 1024 ))"

sed -i '' -E "s/^EXPECTED_SHA=.*/EXPECTED_SHA=\"$SHA\"/" install.sh
# Anchored to the DMG's OWN elements. The previous patterns matched any 64-hex
# <code> and every "~N KB" on the page, so both silently overwrote the browser
# EXTENSION's checksum and size with the disk image's -- shipping a checksum
# that reports every good download as corrupted, which is worse than publishing
# none. Live for at least two releases before it was noticed (2026-08-11).
# If these ids ever disappear from index.html the guards below fail loudly.
sed -i '' -E "s#<code id=\"dmg-sha\">[0-9a-f]{64}</code>#<code id=\"dmg-sha\">$SHA</code>#" index.html
sed -i '' -E "s#(id=\"dmg-size\">[^~]*~)[0-9]+ KB#\1$KB KB#" index.html

STAMPED_CASK="no (--skip-cask)"
if [ "$SKIP_CASK" -eq 0 ]; then
  sed -i '' -E "s/^  version \".*\"\$/  version \"$VERSION\"/" "$CASK"
  sed -i '' -E "s/^  sha256 \"[0-9a-f]{64}\"\$/  sha256 \"$SHA\"/" "$CASK"
  STAMPED_CASK="$CASK"
fi

# Prove every stamp actually landed, rather than trusting that sed matched.
STAMPED="$(sed -n -E 's/^EXPECTED_SHA="([0-9a-f]{64})"$/\1/p' install.sh)"
[ "$STAMPED" = "$SHA" ] || { echo "install.sh was not stamped correctly — fix before committing." >&2; exit 1; }
grep -q "<code id=\"dmg-sha\">$SHA</code>" index.html || { echo "index.html dmg-sha was not stamped correctly — fix before committing." >&2; exit 1; }
grep -q "id=\"dmg-size\">[^<]*~$KB KB" index.html || { echo "index.html dmg-size was not stamped correctly — fix before committing." >&2; exit 1; }
# The extension is a DIFFERENT artifact with a different checksum, and this
# script must never touch it. Proven, not assumed: its published hash has to
# match the zip sitting beside it.
# The page must point people at THIS install.sh, not a copy in another repo.
# Found live 2026-08-11: index.html told users to curl the installer from
# raw.githubusercontent.com/.../Icarus-Website, which had gone stale and still
# pinned an OLD DMG checksum -- so the recommended install path downloaded the
# CURRENT image, failed its own integrity check, and aborted. A second copy of
# a stamped file is a second thing to forget; there is now one.
if grep -q "raw.githubusercontent.com/[^\"]*install.sh" index.html; then
  echo "index.html points at an install.sh in another repository — that copy is" >&2
  echo "       not stamped by this script and will pin a stale checksum." >&2
  exit 1
fi

if [ -f icarus-extension.zip ]; then
  EXT_SHA="$(shasum -a 256 icarus-extension.zip | cut -d ' ' -f 1)"
  grep -q "$EXT_SHA" index.html || {
    echo "index.html publishes the wrong icarus-extension.zip checksum." >&2
    echo "       expected $EXT_SHA — did a stamp overwrite it again?" >&2
    exit 1
  }
fi
sh -n install.sh || { echo "install.sh is no longer valid shell — fix before committing." >&2; exit 1; }

if [ "$SKIP_CASK" -eq 0 ]; then
  CASK_SHA="$(sed -n -E 's/^  sha256 "([0-9a-f]{64})"$/\1/p' "$CASK")"
  CASK_VER="$(sed -n -E 's/^  version "(.*)"$/\1/p' "$CASK")"
  [ "$CASK_SHA" = "$SHA" ] || { echo "cask sha256 was not stamped correctly ($CASK_SHA) — fix before committing." >&2; exit 1; }
  [ "$CASK_VER" = "$VERSION" ] || { echo "cask version was not stamped correctly ($CASK_VER) — fix before committing." >&2; exit 1; }
  # Optional: brew is not required to publish, but if it is here, let it check
  # the cask still parses rather than discovering that on someone's install.
  if command -v brew >/dev/null 2>&1; then
    brew style "$CASK" >/dev/null 2>&1 || {
      echo "warning: 'brew style $CASK' is unhappy — run it and look before committing." >&2
    }
  fi
fi

echo
echo "Published Icarus $VERSION"
echo "  brain:    $BRAIN"
echo "  size:     ${KB} KB"
echo "  sha256:   $SHA"
echo "  stamped:  install.sh, index.html"
echo "  feed:     ${STAMPED_FEED:-unchanged}"
echo "  cask:     $STAMPED_CASK"
echo
echo "Next:"
echo "  1. cd $(pwd) && vercel --prod   (this directory deploys via CLI, not git push)"
echo "  2. git add install.sh index.html appcast.xml && git commit   (Icarus.dmg is gitignored here, deploy only)"
if [ "$SKIP_CASK" -eq 0 ]; then
  echo "  3. git commit + push in the homebrew-icarus tap"
else
  echo "  NOTE: the Homebrew cask was NOT updated and now points at an older build."
fi
