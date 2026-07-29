# demo/repo_map.py
"""The repository map: what Icarus has INDEXED, said before anyone asks.

This is the first surface that speaks first, which makes it the first surface
that can over-claim. The whole design constraint follows from one honest
distinction:

    a corpus-derived map describes what Icarus READ.
    It does not describe what EXISTS in the repository.

Nothing here is a claim about the customer's repo. Every field is named
`indexed_*`, every count is derived from refs the corpus actually holds, and the
ingest deny-lists are reported as RULES THAT WERE APPLIED rather than as
evidence about particular files -- because `evals.ingest.classify_file` returns
None and the walk moves on, recording nothing about what it skipped. Publishing
an excluded-file count would be fabricated precision, which is the same class of
failure as a bluffed citation.

Pure: chunks in, dict out. No model call, no network, no filesystem -- the
corpus is already in memory (`GatedPipeline.indexed_chunks`), so a 50k-chunk
repo costs no re-read. A future ingestion-manifest brick can add genuinely OBSERVED discovered
/eligible/excluded/failed counts; until then those numbers do not exist and are
not published.
"""

from evals.ingest import (
    _DENY_DIR_SEGMENTS,
    _DENY_FILENAMES,
    _DENY_FILENAME_SUFFIXES,
    _MAX_FILE_BYTES,
)

from .entry_points import detect_entry_points, is_auxiliary_path

# Sources whose ref carries a repo-relative PATH (`code:llm/cli.py#L1-L300`).
# pr/issue/commit refs carry an identifier instead and have no file at all.
_FILE_SOURCES = ("code", "doc", "config")

# Extension -> the name a human would use. Display only: it never affects
# ingest, retrieval or the gate. An unmapped extension falls back to the
# extension itself, so a file can never vanish from the totals just because
# this table doesn't know its language (the totals must equal
# indexed_file_count, and a test pins that).
_LANGUAGE_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript", ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".rb": "Ruby", ".c": "C", ".h": "C/C++ header", ".cpp": "C++",
    ".m": "Objective-C", ".mm": "Objective-C++", ".swift": "Swift",
    ".kt": "Kotlin", ".php": "PHP", ".cs": "C#", ".scala": "Scala",
    ".sh": "Shell", ".md": "Markdown", ".rst": "reStructuredText",
    ".txt": "Text", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".cfg": "Config", ".ini": "Config", ".sql": "SQL",
    ".gradle": "Gradle", ".podspec": "Podspec",
}

_ROOT = "."  # the directory bucket for a file with no directory component


def _split(ref):
    """`code:llm/cli.py#L1-L300` -> ("code", "llm/cli.py"). A ref with no path
    component (pr/issue/commit) returns its source and None."""
    source, _, rest = ref.partition(":")
    if source not in _FILE_SOURCES or not rest:
        return source, None
    return source, rest.split("#", 1)[0]


def _language(path):
    dot = path.rfind(".")
    ext = path[dot:].lower() if dot > path.rfind("/") else ""
    return _LANGUAGE_BY_EXT.get(ext, ext or "(no extension)")


def _top_directory(path):
    head, sep, _ = path.partition("/")
    return head if sep else _ROOT


def _readme(doc_paths):
    """The shallowest README, or None. Sorted by (depth, path) so the choice is
    deterministic and a root README beats a nested one. Never falls back to
    "some other doc that looks a bit like a readme" -- a missing README is a
    fact about the corpus and is reported as one."""
    candidates = [p for p in doc_paths if p.rsplit("/", 1)[-1].lower().startswith("readme")]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: (p.count("/"), p))[0]


def _exclusion_rules():
    """The rules ingest applied, derived from ingest's own constants so they
    cannot drift out of sync with what the walk really does. These describe
    POLICY, not observations."""
    return [
        f"Directories skipped anywhere in a path: {', '.join(sorted(_DENY_DIR_SEGMENTS))}.",
        f"Filenames skipped: {', '.join(sorted(_DENY_FILENAMES))}.",
        f"Filename suffixes skipped: {', '.join(sorted(_DENY_FILENAME_SUFFIXES))}.",
        "Only an allow-listed set of source, documentation and configuration "
        "extensions is indexed; other extensions (including .json) are not.",
        f"Any single file larger than {_MAX_FILE_BYTES // 1024} KB is skipped.",
        "Files whose first bytes contain a null byte are treated as binary and skipped.",
    ]


def build_map(chunks, status):
    """The repository map for one connected repo.

    `chunks` is the loaded corpus (`GatedPipeline.indexed_chunks()`); `status`
    is a `Library.status_snapshot()`. Both are already in memory, so this is
    cheap enough to serve per request -- nothing is re-read from disk.

    Chunks rather than refs because entry-point detection has to READ a
    manifest (`pyproject.toml`'s declared console scripts) and a file's own
    text; refs alone cannot carry that. Everything else here still needs only
    the ref.
    """
    paths, chunks_by_source = {}, {}
    for chunk in chunks:
        source, path = _split(chunk.ref)
        chunks_by_source[source] = chunks_by_source.get(source, 0) + 1
        if path:
            paths[path] = source  # distinct FILE, however many chunks it made

    languages, directories = {}, {}
    for path in paths:
        lang = _language(path)
        languages[lang] = languages.get(lang, 0) + 1
        top = _top_directory(path)
        directories[top] = directories.get(top, 0) + 1

    docs = sorted(p for p, s in paths.items() if s == "doc")
    truncated = bool(status.get("truncated", False))
    entry_points = detect_entry_points(chunks)
    # Committed test data is LABELLED beside the totals, never subtracted from
    # them. Found by running the tour on this repo: 348 of 500 indexed files
    # sat under `evals/fixtures/`, so the map read as an Objective-C++/Kotlin/
    # Swift mobile codebase. Every number was true and the impression was
    # false -- the same failure this product exists to avoid, moved out of
    # answers and into a summary. Excluding them would "fix" it by breaking
    # the map's one contract: that it describes what Icarus READ.
    auxiliary = sum(1 for p in paths if is_auxiliary_path(p))

    limitations = [
        "This map describes what Icarus INDEXED, not what exists in the "
        "repository. It cannot report how many files the repository has.",
        "The exclusion rules below are the rules that were applied. Icarus did "
        "not record which particular files they skipped, so it cannot say how "
        "many files were excluded or name them.",
        "Entry points are found by explicit rules only, and each one names the "
        "rule and the evidence that produced it. A repository whose entry point "
        "no rule recognises will show none rather than a guess -- and "
        "package.json is not indexed, so JavaScript and TypeScript entry points "
        "are recognised by conventional filename only.",
    ]
    if truncated:
        limitations.append(
            "A size cap truncated this ingest, so parts of the repository were "
            "not read at all. Anything Icarus says about coverage stops here.")
    if status.get("indexing"):
        limitations.append(
            "Semantic indexing is still running. Search works, but it is "
            "keyword-only for now and answers are measurably worse until it "
            "finishes -- an abstention right now may mean Icarus has not "
            "finished reading, not that nobody wrote it down.")

    return {
        "repo": status.get("repo"),
        "commit": status.get("commit"),
        "indexed_file_count": len(paths),
        "indexed_languages": dict(sorted(languages.items(), key=lambda kv: (-kv[1], kv[0]))),
        "indexed_directories": dict(sorted(directories.items(), key=lambda kv: (-kv[1], kv[0]))),
        "indexed_documentation": {"files": docs, "readme": _readme(docs)},
        "indexed_entry_points": entry_points,
        "indexed_auxiliary": {
            "file_count": auxiliary,
            "rule": "Counted within the totals above, and named here because a "
                    "large committed test tree makes a repository look like "
                    "something it is not: files under a test, tests, testing, "
                    "spec, fixture, fixtures, testdata or __fixtures__ "
                    "directory, or named test_*/*_test. The same rule keeps "
                    "them out of the entry points.",
        },
        "indexed_chunks_by_source": dict(sorted(chunks_by_source.items())),
        "lexical_search_ready": bool(chunks_by_source),
        "semantic_indexing_in_progress": bool(status.get("indexing", False)),
        "corpus_truncated": truncated,
        "exclusion_rules": _exclusion_rules(),
        "limitations": limitations,
    }
