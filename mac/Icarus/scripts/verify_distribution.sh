#!/usr/bin/env bash
# Fail closed unless a DMG is a final-user Apple distribution artifact.
set -euo pipefail

DMG="${1:-}"
[ -n "${DMG}" ] || { echo "usage: $0 /path/to/Icarus.dmg" >&2; exit 2; }
[ -f "${DMG}" ] || { echo "error: DMG not found: ${DMG}" >&2; exit 1; }

xcrun stapler validate "${DMG}"
spctl -a -vv -t open --context context:primary-signature "${DMG}"

MOUNT="$(mktemp -d)"
cleanup() {
    if mount | grep -Fq " on ${MOUNT} "; then
        hdiutil detach "${MOUNT}" -quiet || true
    fi
    rmdir "${MOUNT}" 2>/dev/null || true
}
trap cleanup EXIT

hdiutil attach -readonly -nobrowse -mountpoint "${MOUNT}" "${DMG}" >/dev/null
APP="${MOUNT}/Icarus.app"
[ -d "${APP}" ] || { echo "error: DMG does not contain Icarus.app" >&2; exit 1; }

codesign --verify --deep --strict --verbose=2 "${APP}"
DETAIL="$(codesign -dv --verbose=4 "${APP}" 2>&1)"
AUTHORITY="$(printf '%s\n' "${DETAIL}" | sed -n 's/^Authority=//p' | head -1)"
TEAM="$(printf '%s\n' "${DETAIL}" | sed -n 's/^TeamIdentifier=//p' | head -1)"

[[ "${AUTHORITY}" == "Developer ID Application:"* ]] || {
    echo "error: not signed with Developer ID Application: ${AUTHORITY:-none}" >&2
    exit 1
}
[ -n "${TEAM}" ] && [ "${TEAM}" != "not set" ] || {
    echo "error: Developer ID TeamIdentifier is missing" >&2
    exit 1
}
printf '%s\n' "${DETAIL}" | grep -Eq 'flags=.*runtime|Runtime Version=' || {
    echo "error: hardened runtime is not present" >&2
    exit 1
}
printf '%s\n' "${DETAIL}" | grep -q '^Timestamp=' || {
    echo "error: trusted signing timestamp is missing" >&2
    exit 1
}

ENTITLEMENTS="$(codesign -d --entitlements :- "${APP}" 2>&1 || true)"
if printf '%s\n' "${ENTITLEMENTS}" \
    | grep -A1 -F 'com.apple.security.get-task-allow' \
    | grep -q '<true/>'; then
    echo "error: release enables com.apple.security.get-task-allow" >&2
    exit 1
fi

spctl -a -vv -t exec "${APP}"
echo "distribution verification passed: ${AUTHORITY} (${TEAM})"
