#!/bin/sh
# Icarus installer.
#
# Why this exists: Icarus is not notarized by Apple (that needs a paid
# Developer ID). A browser marks its downloads with com.apple.quarantine,
# which is what makes macOS refuse to open the app. Files fetched with curl
# are not marked, so installing from the terminal avoids that entirely.
#
# This script does nothing clever: it downloads the same disk image the
# website serves, checks it against a known checksum, and copies the app
# into /Applications. Read it before running it — you should read anything
# you pipe into a shell.
#
# Manual alternative, if you would rather not pipe to sh:
#   curl -fLO https://icarus-website-kappa.vercel.app/Icarus.dmg
#   shasum -a 256 Icarus.dmg          # compare with the checksum below
#   open Icarus.dmg                   # drag Icarus to Applications

set -eu

DMG_URL="https://icarus-website-kappa.vercel.app/Icarus.dmg"
EXPECTED_SHA="d15af5a2364fe40be2763c1c512e9bd3b8c908aed040a3964c87231e350eb9b2"
DEST="${ICARUS_DEST:-/Applications}"
APP="Icarus.app"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "Icarus is a macOS app; this machine is not running macOS." >&2
  exit 1
fi

if pgrep -qf "$DEST/$APP/Contents/MacOS/Icarus" 2>/dev/null; then
  echo "Icarus is currently running. Quit it first, then run this again." >&2
  exit 1
fi

TMP="$(mktemp -d)"
MNT="$TMP/mnt"
cleanup() {
  [ -d "$MNT" ] && hdiutil detach "$MNT" -quiet 2>/dev/null || true
  rm -rf "$TMP"
}
trap cleanup EXIT

echo "Downloading Icarus..."
curl -fsSL "$DMG_URL" -o "$TMP/Icarus.dmg"

echo "Verifying download..."
ACTUAL="$(shasum -a 256 "$TMP/Icarus.dmg" | cut -d ' ' -f 1)"
if [ "$ACTUAL" != "$EXPECTED_SHA" ]; then
  echo "Checksum mismatch - not installing." >&2
  echo "  expected: $EXPECTED_SHA" >&2
  echo "  actual:   $ACTUAL" >&2
  echo "Either the download was corrupted, or the published build changed." >&2
  exit 1
fi

echo "Installing to $DEST ..."
mkdir -p "$MNT"
hdiutil attach "$TMP/Icarus.dmg" -nobrowse -quiet -mountpoint "$MNT"

if [ ! -w "$DEST" ]; then
  echo "No write permission for $DEST." >&2
  echo "Re-run with a different target, e.g.:  ICARUS_DEST=\"\$HOME/Applications\" sh -" >&2
  exit 1
fi

rm -rf "${DEST:?}/$APP"
cp -R "$MNT/$APP" "$DEST/"

# Belt and braces: curl does not set the quarantine flag, but if this script
# was ever run on an image obtained some other way, clear it so the copy in
# /Applications opens without the Gatekeeper prompt.
xattr -dr com.apple.quarantine "$DEST/$APP" 2>/dev/null || true

echo
echo "Installed: $DEST/$APP"

# Wire the app into Claude Code as an MCP server, if Claude Code is installed.
# Done here rather than printed as a command to copy: every step a person has to
# perform by hand is a step they can abandon, and this one is a fixed string we
# already know. Skipped silently when `claude` is absent -- most people
# installing Icarus are not using Claude Code, and telling them about a tool
# they do not have is noise.
#
# `-s user` registers it for every project rather than the current directory,
# which is what someone running an installer expects. Re-running is safe: the
# add is idempotent for an identical entry, and a pre-existing `icarus` server
# is left alone rather than silently rewritten -- if someone configured it by
# hand, theirs wins.
if command -v claude >/dev/null 2>&1; then
  # `claude mcp get` reads configuration; `claude mcp list` CONNECTS to every
  # configured server and took 16.7s on a real machine (measured), which is not
  # something an installer may spend to answer a yes/no question.
  if claude mcp get icarus >/dev/null 2>&1; then
    echo "Claude Code: an MCP server named 'icarus' is already configured, leaving it as is."
  elif claude mcp add -s user icarus -- "$DEST/$APP/Contents/MacOS/Icarus" --mcp >/dev/null 2>&1; then
    echo "Claude Code: connected (MCP server 'icarus', available in every project)."
  else
    echo "Claude Code: could not register automatically. To do it by hand:"
    echo "  claude mcp add -s user icarus -- \"$DEST/$APP/Contents/MacOS/Icarus\" --mcp"
  fi
fi

echo "Open it from $DEST, or run:  open -a Icarus"
echo
echo "First run: sign in with GitHub, connect a repo, then press Cmd-Shift-I"
echo "anywhere and ask a question. Problems -> alankritghosh05@gmail.com"
