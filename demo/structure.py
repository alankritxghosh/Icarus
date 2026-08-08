# demo/structure.py
"""How a codebase is arranged -- read off its own imports, never guessed.

"How is this structured?" is the question the onboarding probe measured worst:
`architecture` answered 2 of 10 real repositories, the lowest of any candidate
step, and anchoring it to the README the way `purpose` and `conventions` were
anchored did not move it at all. The reason is not retrieval tuning. A README
says what a project is FOR, not how its code is arranged -- and in most
repositories nobody ever wrote the arrangement down. It exists only in the
code.

So this module DERIVES it, under the same discipline as `entry_points.py`:

    file_edges          (importer, imported) pairs, both INDEXED code files
    package_edges       (importer, package DIRECTORY) -- Go imports a package,
                        not a file, and saying which file would be a guess
    components[].path   a directory, the unit a developer actually reasons in
    components[].evidence_refs  the indexed chunks that prove its edges
    most_depended_on_files      the centre of the codebase by in-degree
    unresolved_import_count     imports seen and NOT placed -- published, so
                                the map can never read as complete when it is not
    unanalysed_languages        indexed languages nothing here looked at

Pure: chunks in, dict out. No model call, no network, no filesystem.

## Why every resolver here is language-specific

A first probe pass used ONE generic resolver that matched an import against
any indexed path by name. Over ten real repositories it produced, among true
edges and indistinguishable from them, a `pkg -> demo` dependency spanning 566
files of jesseduffield/lazygit. It was pure fiction: Go's
`github.com/.../pkg/config` had matched an unrelated `demo/config.yml` on the
bare final segment. Nothing about the output said it was less trustworthy than
the real edges beside it.

That is the whole hazard of this feature in one example. A wrong structural
claim is not a worse answer, it is a confident lie about the reader's own
codebase -- so there is no generic fallback here. An import resolves by its own
language's rules to a file of its own language, or it does not resolve and is
counted as unresolved.

## Honest limits, measured rather than assumed

- **Python, JavaScript/TypeScript and Go are resolved. Rust, Java, Ruby, Swift
  and the rest are not**, and are NAMED in `unanalysed_languages` rather than
  silently returning nothing -- an empty result for a Rust repository must read
  as "nothing looked", never as "this project has no structure".
- **Measured coverage: 8 of the 10 probe repositories yield structure.** The
  two that do not are honest: koalaman/shellcheck is Haskell, which ingest does
  not index at all, and rust-lang/mdBook is Rust, which says so.
- **Every emitted edge was verified against real source.** 199 edges sampled
  across the ten repositories, 0 unverified -- each traced to a literal import
  statement in the importing file's own indexed text.
- Same-package Go files never import each other, so a flat single-package Go
  repository yields little (spf13/cobra: 11 edges from 36 files). That is the
  true answer for it, not a failure.
- Imports are read from indexed chunk TEXT, so a file whose import block fell
  outside every indexed window contributes nothing. Under-reporting, never
  invention.
"""

import re

# Only a code chunk describes a file whose imports are structure. A pr/issue
# body can quote an import statement all day -- that is discussion about code,
# not code, and treating it as an edge is the `entry_points.py` lesson repeated.
_CODE = "code"

_PY = (".py",)
_JS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
_GO = (".go",)

# `from .x import y` / `from ..pkg.x import y` / `import a.b.c`
_PY_FROM = re.compile(r"^[ \t]*from[ \t]+(\.*)([\w.]*)[ \t]+import[ \t]", re.M)
_PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+([\w.]+)", re.M)

# `import x from './y.js'` / `export * from '../z'` / `require('./y')`
_JS_FROM = re.compile(r"""^[ \t]*(?:import|export)\b[^;\n]*?from[ \t]*['"]([^'"]+)['"]""", re.M)
_JS_SIDE_EFFECT = re.compile(r"""^[ \t]*import[ \t]*['"]([^'"]+)['"]""", re.M)
_JS_REQUIRE = re.compile(r"""require\([ \t]*['"]([^'"]+)['"][ \t]*\)""")

# A quoted path on its own line inside a Go import block, or a single-line
# `import "path"`. Go's own grammar makes this unambiguous enough to match
# textually; the module-domain rule below is what keeps it honest.
_GO_IMPORT = re.compile(r"""^[ \t]*(?:import[ \t]+)?(?:[\w.]+[ \t]+)?"([^"]+)"[ \t]*$""", re.M)

_JS_RESOLUTION_SUFFIXES = ("", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx",
                           "/index.js", "/index.ts", "/index.mjs", "/index.tsx")

# Indexed code languages with no resolver here. Named in the output so a
# repository written in one of them shows "nothing was analysed", never
# "nothing was found". Mirrors evals/ingest.py's code extensions minus the
# three resolved above.
_UNANALYSED_LANGUAGES = {
    ".rs": "Rust", ".java": "Java", ".rb": "Ruby", ".c": "C", ".h": "C/C++",
    ".cpp": "C++", ".m": "Objective-C", ".mm": "Objective-C++",
    ".swift": "Swift", ".kt": "Kotlin", ".php": "PHP", ".cs": "C#",
    ".scala": "Scala", ".sh": "Shell",
}

# How many core files to name. A capped list is a summary; an uncapped one is
# just the corpus again, and a reader scanning for "where is the centre of this
# codebase" gets nothing from 400 entries.
_MOST_DEPENDED_ON_LIMIT = 10

_ROOT = "."


def _language(path):
    if path.endswith(_PY):
        return "py"
    if path.endswith(_JS):
        return "js"
    if path.endswith(_GO):
        return "go"
    return None


def _path_of(chunk):
    """The repo-relative path a CODE chunk describes, or None. The line window
    is stripped, so every window of one file maps to that one file."""
    source, _, rest = chunk.ref.partition(":")
    if source != _CODE or not rest:
        return None
    return rest.split("#", 1)[0]


def _directory(path):
    head, sep, _ = path.rpartition("/")
    return head if sep else _ROOT


def _python_targets(text):
    for match in _PY_FROM.finditer(text):
        yield match.group(1), match.group(2)
    for match in _PY_IMPORT.finditer(text):
        yield "", match.group(1)


def _resolve_python(dots, module, src_path, by_path):
    """A Python import -> an indexed `.py` file, or None.

    Relative imports are resolved against the importing file's own package,
    which is the only way `from .store import save` can mean anything; absolute
    ones try the src-layout that roughly half of packaged Python uses.
    """
    rel = module.replace(".", "/")
    if dots:
        parts = src_path.split("/")[:-1]
        # One dot is "this package"; each extra dot climbs one level.
        for _ in range(len(dots) - 1):
            parts = parts[:-1]
        if parts and parts[-1] == "":
            return None
        base = "/".join(parts + ([rel] if rel else []))
        candidates = [f"{base}.py", f"{base}/__init__.py"]
    elif not rel:
        return None
    else:
        candidates = [f"{rel}.py", f"{rel}/__init__.py",
                      f"src/{rel}.py", f"src/{rel}/__init__.py"]
    for candidate in candidates:
        if by_path.get(candidate) == "py":
            return candidate
    return None


def _resolve_js(target, src_path, by_path):
    """A JavaScript/TypeScript import -> an indexed file, or None.

    Only a RELATIVE specifier can name a file in this repository. A bare
    specifier (`import execa from 'execa'`) is a package dependency, and
    resolving it against a same-named local file is exactly the cross-boundary
    guess that produced the fabricated edge described above.
    """
    if not target.startswith("."):
        return None
    parts = src_path.split("/")[:-1]
    for segment in target.split("/"):
        if segment in (".", ""):
            continue
        if segment == "..":
            parts = parts[:-1]
        else:
            parts.append(segment)
    base = "/".join(parts)
    if not base:
        return None
    for suffix in _JS_RESOLUTION_SUFFIXES:
        candidate = base + suffix
        if by_path.get(candidate) == "js":
            return candidate
    # `./run` where the file is `run.js` and the specifier dropped `.js`
    stem = base.rsplit(".", 1)[0]
    for suffix in _JS_RESOLUTION_SUFFIXES[1:]:
        candidate = stem + suffix
        if by_path.get(candidate) == "js":
            return candidate
    return None


def _resolve_go(target, by_directory):
    """A Go import -> a file in the imported package directory, or None.

    Go imports a PACKAGE DIRECTORY, not a file, and its path is absolute from
    the module root (`github.com/owner/repo/pkg/gui`), so the repo-relative
    part is everything after `host/owner/repo` -- an EXACT directory, not a
    suffix to search for.

    The first segment must contain a dot. That one rule excludes the entire
    standard library (`path/filepath`, `os/exec`) without a hardcoded package
    list, because a module path always begins with a domain.

    An earlier version walked progressively shorter suffixes instead. It was
    both less accurate and less complete: it could not reach a package
    directory at the repository root (charmbracelet/glow keeps `ui/` and
    `utils/` there and scored zero), while still leaving room for a shorter
    suffix to match some unrelated directory. Computing the exact
    repo-relative path fixes both at once.

    Returns the DIRECTORY, never a file inside it. Resolving a package to one
    of its files means choosing one, and choosing meant taking the
    alphabetically-first -- which sampling against real source caught stating
    `cobra` imports `active_help.go` (19 of 20 sampled edges) and `glow`
    imports `config_cmd.go` (12 of 12). The package edge was true throughout;
    only the file-level precision was invented.
    """
    segments = target.split("/")
    if "." not in segments[0]:
        return None
    if len(segments) < 3:
        return None  # not a host/owner/repo module path
    relative = "/".join(segments[3:]) or _ROOT
    return relative if relative in by_directory else None


def _edges_for(chunk, path, by_path, by_directory):
    """Every `(kind, target)` an import in this chunk produced, where `kind` is
    "file", "package", or None for an import that did not resolve.

    An unresolved import still yields, so the unresolved total is a real
    observation rather than a silence. The KIND matters: Python and JavaScript
    imports name a file, Go's name a package directory, and flattening the two
    is what let a directory-level truth be published as a file-level fiction.
    """
    language = _language(path)
    if language == "py":
        for dots, module in _python_targets(chunk.text):
            if not dots and not module:
                continue
            yield "file", _resolve_python(dots, module, path, by_path)
    elif language == "js":
        seen = set()
        for pattern in (_JS_FROM, _JS_SIDE_EFFECT, _JS_REQUIRE):
            for match in pattern.finditer(chunk.text):
                target = match.group(1)
                if target in seen:
                    continue
                seen.add(target)
                yield "file", _resolve_js(target, path, by_path)
    elif language == "go":
        for match in _GO_IMPORT.finditer(chunk.text):
            yield "package", _resolve_go(match.group(1), by_directory)


def build_structure(chunks):
    """The internal dependency structure of one corpus.

    Everything published is derived from imports that resolved to a file
    Icarus actually indexed, so any component named here can also be shown.
    A corpus with no resolvable imports yields empty lists -- never a
    plausible-looking guess at what the components might be.
    """
    by_path, by_directory, code_chunks = {}, {}, []
    unanalysed = set()
    for chunk in sorted(chunks, key=lambda c: c.ref):
        path = _path_of(chunk)
        if path is None:
            continue
        language = _language(path)
        if language is None:
            # Named rather than skipped in silence. Reporting no structure for
            # a Rust or Java repository without saying that nothing looked for
            # it reads as "this project has no internal structure" -- false,
            # and exactly the over-claim this module exists to avoid.
            name = _UNANALYSED_LANGUAGES.get(path[path.rfind("."):].lower())
            if name:
                unanalysed.add(name)
            continue
        code_chunks.append((chunk, path))
        by_path[path] = language
        if language == "go":
            by_directory.setdefault(_directory(path), set()).add(path)

    file_edges, package_edges, evidence, unresolved = set(), set(), {}, 0
    for chunk, path in code_chunks:
        for kind, target in _edges_for(chunk, path, by_path, by_directory):
            if target is None:
                unresolved += 1
                continue
            if kind == "file":
                if target == path:
                    continue  # a file does not depend on itself
                file_edges.add((path, target))
            else:
                if target == _directory(path):
                    continue  # a package does not depend on itself
                package_edges.add((path, target))
            evidence.setdefault((path, target), chunk.ref)

    depends_on, depended_on_by, refs, file_counts = {}, {}, {}, {}
    for source, target in file_edges | package_edges:
        # A file edge's component is its target's directory; a package edge
        # already names the directory itself.
        a = _directory(source)
        b = _directory(target) if (source, target) in file_edges else target
        refs.setdefault(a, set()).add(evidence[(source, target)])
        if a == b:
            continue  # within one component: real, but not a component edge
        depends_on.setdefault(a, set()).add(b)
        depended_on_by.setdefault(b, set()).add(a)

    for path in by_path:
        directory = _directory(path)
        if directory in refs or directory in depends_on or directory in depended_on_by:
            file_counts[directory] = file_counts.get(directory, 0) + 1

    components = [
        {
            "path": directory,
            "file_count": file_counts.get(directory, 0),
            "depends_on": sorted(depends_on.get(directory, ())),
            "depended_on_by": sorted(depended_on_by.get(directory, ())),
            "evidence_refs": sorted(refs.get(directory, ())),
        }
        for directory in sorted(set(refs) | set(depends_on) | set(depended_on_by))
    ]
    components.sort(key=lambda c: (-len(c["depended_on_by"]), c["path"]))

    # The component graph is not an answer on its own for a single-package
    # repository: 77 of psf/requests' 105 edges sit INSIDE one component, so
    # the graph shows `src/requests`, `tests`, `docs` and hides the actual
    # arrangement. In-degree over file edges recovers it, and recovers exactly
    # the modules a maintainer would name -- models.py, compat.py,
    # structures.py for requests; db.py, utils.py for sqlite-utils.
    importers = {}
    for source, target in sorted(file_edges):
        importers.setdefault(target, []).append(source)
    most_depended_on_files = sorted(
        ({"path": target,
          "depended_on_by_count": len(sources),
          "evidence_ref": evidence[(sources[0], target)]}
         for target, sources in importers.items()),
        key=lambda entry: (-entry["depended_on_by_count"], entry["path"]),
    )[:_MOST_DEPENDED_ON_LIMIT]

    return {
        "file_edges": sorted(file_edges),
        # Exact indexed window that contained the import. Path pairs alone are
        # insufficient evidence when a file spans overlapping chunks: a module
        # name may appear in an earlier comment while the import is later.
        "file_edge_evidence": [
            {"source": source, "target": target,
             "ref": evidence[(source, target)]}
            for source, target in sorted(file_edges)
        ],
        "package_edges": sorted(package_edges),
        "components": components,
        "most_depended_on_files": most_depended_on_files,
        "unresolved_import_count": unresolved,
        "unanalysed_languages": sorted(unanalysed),
        "limitations": [
            "This structure is derived from import statements in the code "
            "Icarus indexed. It is not a call graph: it shows which files "
            "depend on which, not which functions call which.",
            "Only Python, JavaScript/TypeScript and Go imports are analysed. "
            "Any other indexed language is named in unanalysed_languages and "
            "was not examined at all -- so an empty result for such a "
            "repository means nothing looked, not that nothing is there.",
            "unresolved_import_count counts every import that did not resolve "
            "to another indexed file in this repository. Most of them are "
            "third-party and standard-library imports, which are external by "
            "definition -- a large number there is normal and does not mean "
            "anything is missing from the arrangement below.",
            "A repository whose code lives in a single flat package has no "
            "internal imports to read, and correctly shows no components "
            "rather than an invented arrangement.",
            "Only imports appearing in indexed chunks are seen. Nothing here "
            "is a claim about code Icarus did not read.",
        ],
    }
