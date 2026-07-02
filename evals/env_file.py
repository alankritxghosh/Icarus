# evals/env_file.py
"""Load a gitignored .env file into os.environ. Stdlib only, no dependency.

Keys (GROQ_API_KEY, GEMINI_API_KEY, ...) can live in a .env at the repo root
instead of being retyped on every launch. .env is gitignored, so the credential
never enters the repo. An env var already set in the real environment ALWAYS
wins (setdefault), so an inline `GROQ_API_KEY=... python3 -m demo.server` still
overrides the file. Never commit a real .env — commit only .env.example.
"""

import os
from pathlib import Path


def load_env_file(path) -> dict:
    """Parse KEY=VALUE lines from `path` into os.environ without overriding
    already-set vars. Ignores blanks, `#` comments, and an optional `export `
    prefix; strips one layer of surrounding quotes. Returns what was parsed
    (for logging/tests). A missing file is a no-op returning {}."""
    p = Path(path)
    if not p.exists():
        return {}
    parsed = {}
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, sep, val = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        parsed[key] = val
        os.environ.setdefault(key, val)  # real env wins over the file
    return parsed
