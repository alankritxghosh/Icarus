#!/usr/bin/env bash
# Create the EdDSA key pair that signs Icarus's update feed. Run ONCE, ever.
#
# WHY THIS IS SEPARATE FROM THE BUILD
#
# The PRIVATE half is written to your login keychain by Sparkle's own tool, and
# never leaves this machine. The PUBLIC half is stamped into every shipped app,
# and is what lets a user's copy of Icarus prove an update really came from you
# before it installs anything.
#
# That makes this key the entire security of the update path. Sparkle does not
# rely on Apple's notarization, so nothing else is checking. If the private key
# is lost you cannot ship updates to anyone who already installed Icarus --
# they will keep refusing your new builds, correctly. If it leaks, whoever has
# it can push code to every installed copy.
#
#   RUN THIS YOURSELF, INTERACTIVELY. It writes to your login keychain.
#   BACK THE PRIVATE KEY UP somewhere you would still have after losing this
#   laptop -- a password manager, not this repo.
#
#   ./scripts/make_update_keys.sh
#
# Then put the printed public key in your environment when packaging:
#
#   export ICARUS_UPDATE_PUBLIC_KEY="<the printed value>"
#   export ICARUS_UPDATE_FEED_URL="https://<your site>/appcast.xml"
#   scripts/package_dmg.sh
#
# Without both, the shipped app simply has no updater (see Sources/Icarus/
# Updater.swift) -- it does not fall back to an unverified one.

set -eu
cd "$(dirname "$0")/.."          # mac/Icarus

echo "==> locating Sparkle's key tool"
# Sparkle ships generate_keys inside its SPM artifact bundle; a build has to
# have resolved the package at least once for it to exist.
GEN="$(find .build -type f -name generate_keys -perm -u+x -print -quit 2>/dev/null || true)"
if [ -z "${GEN}" ]; then
    echo "error: generate_keys not found. Run 'swift build' once first, so"
    echo "       SwiftPM downloads the Sparkle artifact bundle." >&2
    exit 1
fi

echo
echo "This writes a PRIVATE update-signing key into your login keychain."
echo "It is the only thing proving future updates came from you."
echo "Back it up after this finishes. Ctrl-C now to abort."
echo
printf "Continue? [y/N] "
read -r reply
case "${reply}" in [yY]*) ;; *) echo "Aborted."; exit 1 ;; esac

"${GEN}"

echo
echo "Copy the public key printed above (the 'SUPublicEDKey' value), then:"
echo
echo "  export ICARUS_UPDATE_PUBLIC_KEY=\"<that value>\""
echo "  export ICARUS_UPDATE_FEED_URL=\"https://icarus-website-kappa.vercel.app/appcast.xml\""
echo
echo "To export the PRIVATE key for backup (it prints to your terminal --"
echo "put it in a password manager, never in this repo):"
echo
echo "  $(dirname "${GEN}")/generate_keys -x -"
