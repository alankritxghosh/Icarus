#!/usr/bin/env bash
# Create the STABLE code-signing identity Icarus builds with.
#
# WHY THIS EXISTS
#
# `bundle.sh` signs ad-hoc (`codesign -s -`). An ad-hoc signature has no
# certificate, so macOS derives the app's "designated requirement" from the
# binary's own hash:
#
#     designated => cdhash H"877f0a45…"
#
# That hash changes on every single build. The login Keychain grants access to
# a stored item based on that requirement, so every time you ship an update,
# macOS decides it is looking at a different application and re-asks the user
# to authorise access to their saved GitHub token. Measured on this machine,
# not assumed.
#
# Signing with a certificate instead makes the requirement key on the
# CERTIFICATE, which does not change between builds:
#
#     designated => identifier "com.alankrit.icarus" and certificate leaf = H"…"
#
# One prompt, ever -- instead of one per update.
#
# WHAT THIS DOES NOT DO
#
# It does NOT get you past Gatekeeper. A self-signed certificate is not an
# Apple Developer ID and the app is still not notarized; recipients still take
# the one-time step in the DMG's "READ ME FIRST.txt". This fixes the Keychain
# re-prompt for people who already have Icarus installed, nothing else.
#
# RUN THIS YOURSELF, INTERACTIVELY. It writes to your login keychain and macOS
# may ask for your password. Run it once; then `bundle.sh` picks the identity
# up automatically on every future build.
#
#   ./scripts/make_signing_cert.sh
#
# To undo: open Keychain Access, find "Icarus Self-Signed" under login, delete
# it. Builds then fall back to ad-hoc exactly as before.

set -eu

IDENTITY="Icarus Self-Signed"
DIR="${HOME}/.icarus-signing"
KEY="${DIR}/icarus-codesign.key.pem"
CERT="${DIR}/icarus-codesign.cert.pem"
P12="${DIR}/icarus-codesign.p12"
# The p12 is a transport format only -- the private key ends up in your login
# keychain, which is what protects it. This passphrase guards a file that
# exists for the length of one import.
P12_PASS="icarus-import"

if security find-certificate -c "${IDENTITY}" >/dev/null 2>&1; then
    echo "'${IDENTITY}' already exists in your keychain."
    echo
    echo "Nothing to do. Re-creating it would issue a DIFFERENT certificate,"
    echo "which changes the designated requirement and costs every existing"
    echo "user one more Keychain prompt -- the exact thing this prevents."
    echo "Delete it in Keychain Access first if you really mean to replace it."
    exit 0
fi

echo "This will create a self-signed code-signing certificate named"
echo "'${IDENTITY}' and add it to your LOGIN keychain."
echo "macOS may ask for your password. Ctrl-C now to abort."
echo
printf "Continue? [y/N] "
read -r reply
case "${reply}" in [yY]*) ;; *) echo "Aborted."; exit 1 ;; esac

mkdir -p "${DIR}"
chmod 700 "${DIR}"

# codeSigning EKU is required, or `codesign` will not accept the identity.
cat > "${DIR}/openssl.cnf" <<'CNF'
[req]
distinguished_name = dn
x509_extensions = v3
prompt = no
[dn]
CN = Icarus Self-Signed
O  = Icarus
[v3]
basicConstraints = critical,CA:false
keyUsage = critical,digitalSignature
extendedKeyUsage = critical,codeSigning
CNF

echo "==> generating a 10-year self-signed certificate"
openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
    -keyout "${KEY}" -out "${CERT}" -config "${DIR}/openssl.cnf" >/dev/null 2>&1
chmod 600 "${KEY}"

# OpenSSL 3 defaults to a PKCS#12 MAC that Apple's Security framework rejects
# with "MAC verification failed" -- the legacy parameters below are required,
# not stylistic. Found by hitting it.
echo "==> packaging it for import"
openssl pkcs12 -export -inkey "${KEY}" -in "${CERT}" -out "${P12}" \
    -name "${IDENTITY}" -passout "pass:${P12_PASS}" \
    -macalg sha1 -certpbe PBE-SHA1-3DES -keypbe PBE-SHA1-3DES -legacy >/dev/null 2>&1
chmod 600 "${P12}"

echo "==> importing into your login keychain (macOS may prompt)"
security import "${P12}" -k "${HOME}/Library/Keychains/login.keychain-db" \
    -P "${P12_PASS}" -T /usr/bin/codesign

# Without this, `codesign` fails with errSecInternalComponent when it tries to
# use the key without a GUI prompt. Also found by hitting it.
echo "==> allowing codesign to use the key (macOS may prompt again)"
security set-key-partition-list -S apple-tool:,apple:,codesign: \
    -s -k "" "${HOME}/Library/Keychains/login.keychain-db" >/dev/null 2>&1 || {
    echo
    echo "Could not set the key partition list automatically."
    echo "Run this yourself and enter your LOGIN password when asked:"
    echo
    echo "  security set-key-partition-list -S apple-tool:,apple:,codesign: \\"
    echo "      -s -k <your-login-password> ~/Library/Keychains/login.keychain-db"
    echo
}

rm -f "${P12}" "${DIR}/openssl.cnf"

echo
echo "Done. '${IDENTITY}' is in your login keychain."
echo "Private key: ${KEY} (chmod 600, OUTSIDE the repo -- never commit it)."
echo
echo "Next: run scripts/package_dmg.sh as usual. It will pick this up"
echo "automatically, and print which identity it signed with."
echo
echo "Verify a build with:  codesign -d -r- Icarus.app"
echo "You want to see 'certificate leaf', not 'cdhash'."
