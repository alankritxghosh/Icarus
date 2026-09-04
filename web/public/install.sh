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
#   curl -fLO https://github.com/alankritxghosh/Icarus-Website/releases/download/v0.1.7/Icarus.dmg
#   shasum -a 256 Icarus.dmg          # compare with the checksum below
#   open Icarus.dmg                   # drag Icarus to Applications

set -eu

DMG_URL="https://github.com/alankritxghosh/Icarus-Website/releases/download/v0.1.12/Icarus.dmg"
EXPECTED_SHA="d9956de2f5d353220e3e77c633c95e4fa30d7212d3a53bc34b5d98a876df3bf2"
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
# User scope registers it for every project rather than the current directory,
# which is what someone running an installer expects. A known legacy Icarus
# Python adapter is migrated because it depends on one developer checkout and
# is not a portable user installation. Any other server named `icarus` is left
# alone rather than silently overwritten.
if command -v claude >/dev/null 2>&1; then
  # `claude mcp get` reads configuration; `claude mcp list` CONNECTS to every
  # configured server and took 16.7s on a real machine (measured), which is not
  # something an installer may spend to answer a yes/no question.
  MCP_DETAILS="$(claude mcp get icarus 2>&1 || true)"
  if printf '%s' "$MCP_DETAILS" | grep -Fq "Scope: User config" \
     && printf '%s' "$MCP_DETAILS" | grep -Fq "Command: $DEST/$APP/Contents/MacOS/Icarus" \
     && printf '%s' "$MCP_DETAILS" | grep -Fq "Args: --mcp"; then
    echo "Claude Code: connected (MCP server 'icarus', available in every project)."
  elif printf '%s' "$MCP_DETAILS" | grep -Fq "Scope: User config" \
       && printf '%s' "$MCP_DETAILS" | grep -Fq "demo.mcp_server"; then
    echo "Claude Code: replacing the checkout-only Icarus connector with the installed app."
    claude mcp remove icarus --scope user >/dev/null 2>&1 || true
    if claude mcp add --transport stdio --scope user icarus -- \
         "$DEST/$APP/Contents/MacOS/Icarus" --mcp >/dev/null 2>&1; then
      echo "Claude Code: connected (MCP server 'icarus', available in every project)."
    else
      echo "Claude Code: could not repair automatically. Open Icarus -> Settings to retry."
    fi
  elif printf '%s' "$MCP_DETAILS" | grep -Fq 'No MCP server named'; then
    if claude mcp add --transport stdio --scope user icarus -- \
         "$DEST/$APP/Contents/MacOS/Icarus" --mcp >/dev/null 2>&1; then
      echo "Claude Code: connected (MCP server 'icarus', available in every project)."
    else
      echo "Claude Code: could not register automatically. Open Icarus -> Settings to retry."
    fi
  else
    echo "Claude Code: a different MCP server named 'icarus' already exists; leaving it unchanged."
    echo "Open Icarus -> Settings for details."
  fi
fi

echo "Open it from $DEST, or run:  open -a Icarus"
echo
echo "First run: sign in with GitHub, connect a repo, then press Cmd-Shift-I"
echo "anywhere and ask a question. Problems -> alankritghosh05@gmail.com"
