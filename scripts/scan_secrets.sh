#!/usr/bin/env bash
# scan_secrets.sh — block committed credentials.
#
# Scans tracked working-tree files (default) or only staged changes (--staged)
# for provider token shapes and secret-looking assignments. Exits NON-ZERO on a
# hit so it can gate a commit (pre-commit hook) or a build (CI). History is NOT
# scanned here (that's advisory, not blocking) to avoid false positives from old
# test fixtures.
#
#   bash scripts/scan_secrets.sh            # scan tracked files
#   bash scripts/scan_secrets.sh --staged   # scan only staged additions (hook)
set -uo pipefail

MODE="${1:-tracked}"

# Provider-specific token shapes (high signal). Data corpora (*.jsonl/*.csv) and
# Markdown docs are excluded — they hold ingested content / examples, not source.
PATTERNS='(AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16})'
PATTERNS+='|(gh[pousr]_[A-Za-z0-9]{36,})'
PATTERNS+='|(github_pat_[A-Za-z0-9_]{22,})'
PATTERNS+='|(AIza[0-9A-Za-z_\-]{35})'
PATTERNS+='|(gsk_[A-Za-z0-9]{20,})'
PATTERNS+='|(sk-(or-)?[A-Za-z0-9]{20,})'
PATTERNS+='|(xox[baprs]-[A-Za-z0-9-]{10,})'
PATTERNS+='|(-----BEGIN[A-Z ]*PRIVATE KEY-----)'

GENERIC='(api[_-]?key|secret|token|passwd|password)["'"'"' ]*[:=]["'"'"' ]*[A-Za-z0-9_\-]{16,}'

hit=0

if [ "$MODE" = "--staged" ]; then
    # Only the added lines in the staged diff (skip data/docs).
    ADDED="$(git diff --cached --unified=0 -- ':!*.jsonl' ':!*.csv' ':!*.md' \
             | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
    if printf '%s' "$ADDED" | grep -EiI "$PATTERNS"; then
        echo "  ^ BLOCKED: provider token shape in staged changes." >&2; hit=1
    fi
    if printf '%s' "$ADDED" | grep -EiI "$GENERIC"; then
        echo "  ^ BLOCKED: secret-looking assignment in staged changes." >&2; hit=1
    fi
else
    if git grep -nIiE "$PATTERNS" -- ':!*.jsonl' ':!*.csv' ':!*.md' 2>/dev/null; then
        echo "  ^ BLOCKED: provider token shape in tracked files." >&2; hit=1
    fi
    if git grep -nIiE "$GENERIC" -- ':!*.jsonl' ':!*.csv' ':!*.md' 2>/dev/null; then
        echo "  ^ BLOCKED: secret-looking assignment in tracked files." >&2; hit=1
    fi
fi

if [ "$hit" -ne 0 ]; then
    echo "secrets scan FAILED — remove the credential (or move it to an env var) and retry." >&2
    exit 1
fi
echo "secrets scan clean."
exit 0
