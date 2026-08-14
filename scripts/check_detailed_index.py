#!/usr/bin/env python3
"""Fail the build when `detailed_index.md` stops describing the real code.

The index exists so a reader -- human or coding agent -- can reference REAL
names instead of guessing them. When it rots it does the opposite: it hands out
confident, wrong API names. That is not hypothetical. Regenerating it on
2026-08-15 found it documenting 31 of 52 modules, plus three references to
functions that do not exist:

    `_extract_json`          -> gate.py's helper is public, `extract_json`
    judge.py's `_JSON`       -> that constant lives in gate.py
    `_checked_public_repo`   -> renamed `_checked_repo` on 2026-08-07

Each of those would have sent someone to call a function that isn't there.
`CLAUDE.md` already says to regenerate after any structural change; nothing
checked, so the instruction quietly stopped being followed.

Three checks, all stdlib, no network:

  1. every `## <path>.py` section names a file that exists
  2. every backticked symbol in a section appears in that module's source
  3. every non-test module under evals/ and demo/ has a section

Disclosed limits, so nobody reads a pass as more than it is:

  - Check 2 is a SUBSTRING test, not a resolution: it catches renames, typos
    and deletions -- the failure modes that actually happen -- but a doc naming
    `foo` when the source only has `_foo` passes. Prose is prose; proving a
    description is accurate is not something a script can do.
  - Only `evals/` and `demo/` are covered. The file also documents a few
    IcarusKit Swift types, which are not checked here.
  - Nothing here checks that a DESCRIPTION is true, only that the symbol is real.

Run:  python3 scripts/check_detailed_index.py
      python3 scripts/check_detailed_index.py --selftest
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "detailed_index.md"
PACKAGES = ("evals", "demo")

_SECTION = re.compile(r"^## (\S+\.py)", re.M)
# `name(` for a callable, `CONSTANT` for a module constant. Deliberately narrow:
# a 3+ char lower_snake name followed by "(", or a 4+ char SHOUTY name in ticks.
_CALLABLE = re.compile(r"`(_?[a-z][a-z0-9_]{2,})\(")
_CONSTANT = re.compile(r"`(_?[A-Z][A-Z0-9_]{3,})`")


def _sections(text):
    """(module path, section body) for every documented Python module."""
    out = []
    for part in re.split(r"^## ", text, flags=re.M):
        match = re.match(r"((?:%s)/\S+\.py)" % "|".join(PACKAGES), part)
        if match:
            out.append((match.group(1), part))
    return out


def check(index_text, root=ROOT):
    """Return a list of problem strings. Empty means the index is honest."""
    problems = []
    documented = set()

    for path_str, body in _sections(index_text):
        documented.add(path_str)
        path = root / path_str
        if not path.exists():
            problems.append(f"{path_str}: documented but the file does not exist")
            continue
        source = path.read_text()
        symbols = set(_CALLABLE.findall(body)) | set(_CONSTANT.findall(body))
        for symbol in sorted(symbols):
            if symbol not in source:
                problems.append(f"{path_str}: `{symbol}` is documented but not in the source")

    present = {
        f"{package}/{f.name}"
        for package in PACKAGES
        for f in sorted((root / package).glob("*.py"))
        if not f.name.startswith("test_")
    }
    for missing in sorted(present - documented):
        problems.append(f"{missing}: exists but has no section in detailed_index.md")

    return problems


def _selftest():
    """Prove the checker can FAIL.

    A checker that silently passes is worse than none, and this repository has
    shipped two of those (a guard whose decoy was rejected before the rule under
    test was reached; a fixture whose newlines did not match the real writer).
    So: feed it an index that is wrong in each of the three ways and require it
    to say so.
    """
    real_module = f"{PACKAGES[0]}/gate.py"
    cases = [
        ("nonexistent file",
         "## evals/does_not_exist.py\n- `foo()` — x\n",
         "does not exist"),
        ("invented symbol",
         f"## {real_module}\n- `a_function_nobody_wrote()` — x\n",
         "not in the source"),
        ("undocumented module",
         f"## {real_module}\n- `gate()` — x\n",
         "no section"),
    ]
    failures = []
    for name, text, expected in cases:
        found = check(text)
        if not any(expected in p for p in found):
            failures.append(f"selftest: {name!r} was not detected (got {found[:2]})")

    # And the converse: the REAL index must pass, or the checker is just noisy.
    if INDEX.exists() and check(INDEX.read_text()):
        failures.append("selftest: the committed index does not pass its own check")

    for line in failures:
        print(line, file=sys.stderr)
    print("selftest: ok" if not failures else "selftest: FAILED", file=sys.stderr)
    return 1 if failures else 0


def main(argv):
    if "--selftest" in argv:
        return _selftest()
    if not INDEX.exists():
        print("detailed_index.md is missing", file=sys.stderr)
        return 1
    problems = check(INDEX.read_text())
    if problems:
        print(f"detailed_index.md is out of step with the code ({len(problems)}):",
              file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print("\nUpdate detailed_index.md (CLAUDE.md: regenerate after any "
              "structural change). It is what stops an agent citing a function "
              "that does not exist.", file=sys.stderr)
        return 1
    documented = len(_sections(INDEX.read_text()))
    print(f"detailed_index.md: {documented} modules, every symbol resolves.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
