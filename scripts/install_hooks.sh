#!/usr/bin/env bash
# One-time: point git at the repo's committed hooks. Run from anywhere in the repo.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
git -C "$ROOT" config core.hooksPath .githooks
chmod +x "$ROOT/.githooks/pre-commit" "$ROOT/scripts/scan_secrets.sh"
echo "Installed: core.hooksPath -> .githooks (pre-commit security gate active)."
