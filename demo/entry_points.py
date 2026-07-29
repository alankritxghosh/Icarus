# demo/entry_points.py
"""Where to start reading a repository -- by explicit rule, never by score.

"Where do I start?" is the second question anyone has about an unfamiliar repo.
It is also the first question where a confident wrong answer costs more than no
answer: send a new engineer to the wrong file and they lose an afternoon and
their trust in the tool at the same time.

So every detection here is a RULE a person can check:

    path            the file, which must be one Icarus actually indexed
    rules[].rule    the rule id that fired
    rules[].evidence_ref  the indexed chunk that proves it -- citable, like any
                    other claim Icarus makes
    rules[].detail  the same thing in words

Nothing is ranked, weighted or scored. When no rule fires the answer is an
empty list, not a best guess -- an opaque importance score presented as truth is
exactly what this product exists not to do.

Pure: chunks in, list out. No model call, no network, no filesystem.

Two honest gaps, disclosed rather than papered over:
- **`package.json` is not indexed at all** (`.json` is excluded corpus-wide by
  `evals/ingest.py`'s `_EXTENSION_SOURCES`, because Xcode asset catalogs and
  i18n bundles skew BM25). So `main`/`bin`/`scripts.start` cannot be read, and
  JavaScript/TypeScript entry points fall back to conventional filenames only.
  Writing a package.json rule now would be dead code.
- `setup.py`'s `entry_points=` is executable Python, not data. Parsing it
  reliably means running it or matching brittle regexes; both are worse than
  saying nothing. `pyproject.toml` is the modern declaration and is read.
"""

import re
import tomllib

# Sources whose ref carries a repo-relative path. A pr/issue/commit chunk can
# quote `func main()` in its body all day; it is discussion, not a file.
_FILE_SOURCES = ("code", "doc", "config")

# Filenames that are entry points BY CONVENTION alone. Deliberately excludes
# any name a dedicated content rule already covers (main.go, main.rs) -- two
# rules for one fact is noise, and the content rule is the stronger evidence.
_CONVENTIONAL_FILENAMES = {
    "__main__.py", "main.py", "cli.py", "app.py", "manage.py",
    "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts",
    "main.swift", "Main.java", "main.kt",
}

# Anchored to the start of a line (leading indentation allowed), NOT a plain
# substring search. Found by running the rules over this repo: this very file
# matched itself, because it contains the guard as a string literal inside a
# tuple. Same class as evals/pipeline.py's "a hex-shaped English word is not a
# commit SHA" guard -- any substring match on source eventually matches the
# code that describes it.
_MAIN_GUARD = re.compile(r"^[ \t]*if\s+__name__\s*==\s*['\"]__main__['\"]", re.MULTILINE)

# Test files are excluded from EVERY rule. Not a taste call: measured against
# this repo, `if __name__ == "__main__": unittest.main()` is boilerplate in all
# 60+ test files, so the main-guard rule returned 70 "entry points" and buried
# the four that a new engineer actually wants. The rule was not wrong -- each
# file really does run directly -- it was answering a different question. A
# test's entry point runs the test, not the product.
_TEST_DIR_SEGMENTS = {"test", "tests", "testing", "__tests__", "spec"}


def _is_test_file(path):
    parts = path.split("/")
    if set(parts) & _TEST_DIR_SEGMENTS:
        return True
    name = parts[-1]
    stem = name.rsplit(".", 1)[0]
    return name.startswith("test_") or stem.endswith("_test") or stem.endswith("Test")


def _path_of(chunk):
    """The repo-relative path a chunk describes, or None if it describes no
    file (pr/issue/commit) -- the line window is stripped, so every window of
    one file maps to that one file."""
    source, _, rest = chunk.ref.partition(":")
    if source not in _FILE_SOURCES or not rest:
        return None
    return rest.split("#", 1)[0]


def _script_targets(text):
    """`[project.scripts]` from a pyproject.toml, as {name: "module:attr"}.

    Anything that doesn't parse yields nothing. A manifest we cannot read is a
    manifest we say nothing about."""
    try:
        data = tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError, TypeError):
        return {}
    scripts = ((data.get("project") or {}).get("scripts") or {})
    if not isinstance(scripts, dict):
        return {}
    return {k: v for k, v in scripts.items() if isinstance(v, str)}


def _module_candidates(target):
    """`llm.cli:cli` -> the paths that module could live at, most conventional
    first. Only one that was actually INDEXED is ever emitted, so guessing wide
    here costs nothing and covers the src-layout that half of Python uses."""
    module = target.split(":", 1)[0].strip()
    if not module:
        return []
    rel = module.replace(".", "/")
    return [f"{rel}.py", f"{rel}/__init__.py", f"src/{rel}.py", f"src/{rel}/__init__.py"]


def detect_entry_points(chunks):
    """Entry points for one corpus, grouped by file and sorted by path.

    Multiple rules on the same file collapse into ONE entry with several rules,
    so a count of entry points is a count of FILES -- the same
    chunks-versus-files honesty the repository map holds to.
    """
    # Sorted once, so every rule below sees the same order and the output can
    # never depend on how the corpus happened to be laid out on disk.
    ordered = sorted(chunks, key=lambda c: c.ref)
    indexed_paths, hits = set(), {}

    def _hit(path, rule, evidence_ref, detail):
        # The groundedness guard: a rule may only ever name a file that is in
        # the indexed corpus, so anything Icarus points at, it can also show.
        if path not in indexed_paths or _is_test_file(path):
            return
        for existing in hits.setdefault(path, []):
            if existing["rule"] == rule:
                return  # first evidence wins; one rule states its case once
        hits[path].append({"rule": rule, "evidence_ref": evidence_ref, "detail": detail})

    for chunk in ordered:
        path = _path_of(chunk)
        if path is not None:
            indexed_paths.add(path)

    # -- rule: a console script declared in pyproject.toml ------------------
    for chunk in ordered:
        path = _path_of(chunk)
        if path is None or path.rsplit("/", 1)[-1] != "pyproject.toml":
            continue
        if "#" in chunk.ref:
            continue  # a windowed half of a manifest is not the manifest
        for name, target in sorted(_script_targets(chunk.text).items()):
            for candidate in _module_candidates(target):
                _hit(candidate, "pyproject-console-script", chunk.ref,
                     f'pyproject.toml declares the console script "{name}" -> {target}')

    # -- rule: a Python __main__ guard --------------------------------------
    for chunk in ordered:
        path = _path_of(chunk)
        if path is None or not path.endswith(".py"):
            continue
        if _MAIN_GUARD.search(chunk.text):
            _hit(path, "python-main-guard", chunk.ref,
                 'contains an if __name__ == "__main__" block, so it runs directly')

    # -- rule: a Go main package with a main function -----------------------
    # Both halves can land in different windows of one file, so they are
    # tracked per PATH rather than per chunk.
    go_package, go_func = {}, {}
    for chunk in ordered:
        path = _path_of(chunk)
        if path is None or not path.endswith(".go"):
            continue
        if "package main" in chunk.text:
            go_package.setdefault(path, chunk.ref)
        if "func main(" in chunk.text:
            go_func.setdefault(path, chunk.ref)
    for path, ref in sorted(go_func.items()):
        if path in go_package:
            _hit(path, "go-main-function", ref,
                 "declares package main and func main(), Go's executable entry point")

    # -- rule: Rust's conventional binary crate root ------------------------
    for path in sorted(indexed_paths):
        if path == "src/main.rs" or path.endswith("/src/main.rs"):
            ref = next((c.ref for c in ordered if _path_of(c) == path), None)
            _hit(path, "rust-main-file", ref,
                 "src/main.rs is Cargo's conventional binary crate root")

    # -- rule: a conventional filename --------------------------------------
    for chunk in ordered:
        path = _path_of(chunk)
        if path is None:
            continue
        name = path.rsplit("/", 1)[-1]
        if name in _CONVENTIONAL_FILENAMES:
            _hit(path, "conventional-filename", chunk.ref,
                 f"named {name}, a conventional entry point for its ecosystem")

    return [{"path": path, "rules": sorted(rules, key=lambda r: r["rule"])}
            for path, rules in sorted(hits.items())]
