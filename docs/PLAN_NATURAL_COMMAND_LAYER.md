# Plan: Natural Repo Command Layer

Status: proposed. Verdict from architect review was **CHANGE → GO** once the four
identity-safety constraints below are honored. This plan encodes them.

## Goal

Let a user ask a plain-English question from inside (or pointing at) a local git
checkout without typing a GitHub URL, a checkout path, `PYTHONPATH`, or
`--repositories-root`:

```sh
jarvis-engineering "Why was the event bus introduced?"
```

## Non-negotiable constraints (from review)

1. `--github-url` is an **optional override**, never an always-on inference that
   makes `REMOTE_MISMATCH` vacuous.
2. When the URL is inferred from `remote.origin.url`, the report carries an
   explicit **"identity derived, not verified"** warning.
3. If origin is absent or non-canonical and no `--github-url` is given, the tool
   **errors** — it never fabricates a URL.
4. `protected_root` stays **explicitly configured** (`_default_protected_root`
   reads `JARVIS_PROTECTED_ROOT`) and is never inferred from cwd, origin,
   package layout, or repositories-root.

## Architecture (thinnest viable)

No change to `inspect_repository` (`inspector.py:97`), `resolve_target`,
`contracts.py` gates, or evidence. The entire feature is a resolver in front of
the existing entry point.

### A. Drop `PYTHONPATH` — packaging only, zero code

`pyproject.toml` already defines the console script
(`jarvis_engineering.cli:main`). Document `pip install -e .`; the
`jarvis-engineering` command then resolves with no `PYTHONPATH`. No source edit.

### B. New resolver module: `src/jarvis_engineering/resolve.py`

Pure stdlib (`pathlib`, reuse `isolation.run_git`). One function:

```
resolve_invocation(path_arg, github_url_flag, repositories_root_flag, *, timeout)
    -> (github_url: str, checkout: str, repositories_root: str, derived_identity: bool)
```

Steps:
1. **Checkout**: start from `path_arg` if given, else `Path.cwd()`. Run
   `git rev-parse --show-toplevel` via `run_git` to get the repo root. This is
   subdirectory/monorepo correct and detached-HEAD safe. Non-git cwd → the
   `GIT_COMMAND_FAILED` from `run_git` is translated to `NOT_GIT_REPOSITORY`
   (the code already exists, `contracts.py:18`).
2. **github_url**:
   - If `--github-url` provided → use it verbatim, `derived_identity = False`.
     The existing `REMOTE_MISMATCH` gate runs unchanged and stays meaningful.
   - Else infer: `read_origin` → `normalize_remote_url` (`isolation.py:219`,
     `232`). On a canonical GitHub origin, use it; `derived_identity = True`.
   - If inference yields `None` (no origin / non-GitHub) → raise
     `INVALID_ARGUMENTS` telling the user to pass `--github-url`. No fabrication.
3. **repositories-root**: `--repositories-root` if given, else the toplevel's
   parent directory. (Override stays available so `CHECKOUT_OUTSIDE_ROOT`
   remains reachable.)
4. Return the four strings; never compute or pass a `protected_root` here.

### C. `cli.py` wiring

- Restructure args: `question` positional; optional `path` positional;
  `--github-url`, `--repositories-root` optional. (Safe: no test invokes
  `cli.main`; all tests call `inspect_repository` directly, so the API contract
  — criterion 12 — is preserved.)
- Call `resolve_invocation`, then `inspect_repository(...)` exactly as today with
  `protected_root=_default_protected_root()`.
- When `derived_identity` is True, append the warning to the report's
  `warnings` list before emit. Cleanest: have the resolver/CLI pass a flag and
  append in `cli.main` after a successful report, so `inspector.py` stays
  untouched. (If we'd rather the warning live with other identity warnings in
  `inspector.py:128-140`, that is a one-line option but does touch src; default
  to appending in the CLI to keep the inspector frozen.)

## Out of scope (must NOT absorb)

- Network / GitHub API / reachability checks (already declared unverified,
  `inspector.py:145`).
- Multi-repo discovery or walking `repositories_root` for repos.
- Config files / dotfiles / env precedence chains.
- Auto-deriving `protected_root` from cwd, origin, repositories-root, or package layout.
- Subdirectory evidence scoping (inferring toplevel is fine; restricting
  evidence to the invoking subdir is a new behavior).
- Interactive prompts / TTY detection.

## Risks (carried from review)

- **REMOTE_MISMATCH vacuity** — mitigated by constraint 1 + 2: gate runs on the
  asserted URL; inferred identity is flagged as unverified.
- **CHECKOUT_OUTSIDE_ROOT vacuity** when root defaults to the checkout's parent —
  acceptable because `protected_root` is the real boundary; gate stays reachable
  via explicit `--repositories-root`.
- **protected_root survives** because it is explicitly configured and containment
  runs on the resolved checkout (`isolation.py:135-142`); running from inside the
  protected workspace correctly hits `PROTECTED_ROOT_ACCESS`.
- Symlinks → resolve toplevel before deriving parent; `resolve(strict=True)` in
  `resolve_target` still catches symlinked checkouts pointing into the protected
  root.
- Non-git cwd → clean `NOT_GIT_REPOSITORY` JSON, no traceback.

## Acceptance criteria (unittest)

New behavior — add `tests/test_resolve.py` / `tests/test_cli_inference.py`:

1. cwd inside a git checkout with canonical GitHub origin under a non-protected
   root → `ok: true`, no `--github-url` / `--repositories-root` flags needed.
2. Invocation from a subdirectory resolves to the git toplevel (reported
   `checkout_path` == toplevel, not the subdir).
3. Non-git cwd → JSON error, code `NOT_GIT_REPOSITORY`, exit 2, no traceback.
4. Inferred identity adds a warning stating the URL was derived from origin and
   not verified.
5. No canonical origin and no `--github-url` → `INVALID_ARGUMENTS` instructing
   the user to pass `--github-url`; no fabricated URL in output.

Re-proven safety invariants — explicit tests, not assumed:

6. Explicit `--github-url` disagreeing with origin still raises `REMOTE_MISMATCH`
   (mirror `test_day2_safety.py:337`).
7. Checkout whose toplevel resolves inside the explicitly configured protected root is
   blocked with `PROTECTED_ROOT_ACCESS` even when repositories-root is inferred.
8. `protected_root` is read from `JARVIS_PROTECTED_ROOT`, not cwd/origin/root or
   package location.
9. `CHECKOUT_OUTSIDE_ROOT` still reachable via explicit `--repositories-root`
   pointing elsewhere.
10. `.jsonl` / `brain/` / `../` blocks intact for inferred or passed paths
    (`JSONL_ACCESS_DENIED` / `ISOLATION_VIOLATION_BLOCKED`).
11. No network and no new deps: `pyproject.toml` dependencies unchanged; only
    local `git config` / `git rev-parse` subprocesses occur.
12. `inspect_repository` API unchanged → the existing 64-test suite stays green.

## Files touched

- New: `src/jarvis_engineering/resolve.py`
- Edit: `src/jarvis_engineering/cli.py` (arg surface + resolver call + derived
  warning append)
- New tests: `tests/test_resolve.py` (and/or `tests/test_cli_inference.py`)
- Docs: `README.md` (pip install -e ., new usage), `docs/PROJECT_STATE.md`
- Unchanged: `inspector.py`, `isolation.py`, `contracts.py`, `evidence.py`

## Verification

```sh
PYTHONPATH=src python3 -m unittest discover tests -v
```
