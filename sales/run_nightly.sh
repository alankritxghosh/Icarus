#!/bin/bash
# Unattended nightly lead run. Driven by launchd (see sales/README.md).
# One headless Claude pass; sales/nightly.md is the standing instruction.
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
mkdir -p outputs/leads/logs
LOG="outputs/leads/logs/$(date +%F).log"

# launchd gives a bare PATH; claude, gh and git all live outside it.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

{
  echo "=== start $(date) ==="
  claude -p "$(cat sales/nightly.md)" \
      --permission-mode acceptEdits \
      --allowedTools "Bash,Read,Write,Edit,Glob,Grep"
  echo "=== end $(date) rc=$? ==="
} >>"$LOG" 2>&1
