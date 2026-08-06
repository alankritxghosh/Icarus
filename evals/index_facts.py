"""Icarus's own index, expressed as citable EVIDENCE.

Every other evidence chunk in the corpus is something a PERSON wrote -- code,
a PR body, an issue, a doc. That left a whole class of true statements Icarus
could not make: nobody writes "this project is in TypeScript" in a document,
because it is not a claim anyone records. It is a property of the files, and
Icarus measures it during ingest.

Found live 2026-08-06 on muxinc/media-chrome: "what coding languages does the
codebase contain" returned "No one wrote this down", while `/map` had already
computed the languages and the guided tour had rendered them. The ask path only
searched written text, and the word "languages" lexically matched an i18n file
(`docs/src/languages.ts`) about HUMAN languages -- so retrieval surfaced nothing
an answer could be drawn from, and the honesty gate did the correct thing with
the wrong evidence.

The fix is deliberately NOT a router ("if the question mentions languages, call
the map"). That is the permutations trap one branch at a time. Instead the index
becomes one ordinary evidence chunk offered on every ask, so ANY phrasing that
retrieval routes toward it can be answered from it -- and cited, like anything
else Icarus says.

Honesty boundary, load-bearing: this chunk describes what Icarus READ. It is
never evidence of intent. Its wording deliberately avoids reason-stating prose
so gate.py's (b) guard cannot mistake a file listing for a recorded rationale
(pinned by test_index_facts.test_never_reads_as_a_recorded_rationale and
test_index_evidence_wiring.IndexCannotLaunderAnUnrecordedWhyTests).
"""

from typing import List, Optional

from .corpus import Chunk

# The reserved ref. `index:` is its own source, so demo/links.ref_to_url yields
# no URL for it (there is no GitHub page for "what Icarus read") and a renderer
# can label it differently from a human-authored citation.
INDEX_REF = "index:overview"

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


def language_for(path: str) -> str:
    """The language a path's extension implies, or the extension itself when the
    table doesn't know it -- never a guess, and never silently dropped, so per
    language totals always sum to the file count."""
    name = path.rsplit("/", 1)[-1]
    dot = name.rfind(".")
    ext = name[dot:].lower() if dot > 0 else ""
    return _LANGUAGE_BY_EXT.get(ext, ext or "(no extension)")


def _path_of(ref: str) -> Optional[str]:
    """The repository path a ref addresses, or None for pr/issue/commit refs
    (which are not file-addressable)."""
    source, sep, body = ref.partition(":")
    if not sep or source not in ("code", "doc", "config"):
        return None
    return body.split("#", 1)[0]


def build_index_chunk(chunks: List[Chunk]) -> Optional[Chunk]:
    """One evidence chunk describing what Icarus indexed, or None for an empty
    corpus -- a corpus with nothing in it should say nothing, not assert zeroes.

    Pure: chunks in, Chunk out. No model, no network, no filesystem, no re-read
    of chunks.jsonl -- the caller already holds them in memory, so this costs
    nothing per request.
    """
    if not chunks:
        return None

    paths, languages, by_source = set(), {}, {}
    for c in chunks:
        by_source[c.source] = by_source.get(c.source, 0) + 1
        path = _path_of(c.ref)
        if path:
            paths.add(path)
    for path in paths:
        lang = language_for(path)
        languages[lang] = languages.get(lang, 0) + 1

    # Biggest first, then alphabetical -- deterministic regardless of input order.
    lang_line = ", ".join(f"{name} {n}" for name, n in
                          sorted(languages.items(), key=lambda kv: (-kv[1], kv[0])))
    src_line = ", ".join(f"{n} {name}" for name, n in sorted(by_source.items()))

    # Wording note: plain counts only, and every word checked against gate.py's
    # _RATIONALE_MARKERS. An earlier draft ended "...and they say nothing about
    # intent" -- a DISCLAIMER of intent, which the marker list (substring
    # "intent") read as a STATEMENT of one, so a "why was TypeScript chosen?"
    # could be grounded on a file listing. The (b) guard cannot tell a
    # disclaimer from a claim, so this text simply never uses those words.
    # test_index_facts pins it against the real marker list, not a hand-copy.
    text = (
        "What Icarus read when it indexed this repository. These are counts "
        "measured from the files themselves, not something a person wrote "
        "down.\n"
        f"- Distinct files indexed: {len(paths)}\n"
        f"- Languages by file count: {lang_line or 'none'}\n"
        f"- Evidence indexed: {src_line}\n"
    )
    return Chunk(INDEX_REF, "index", text)
