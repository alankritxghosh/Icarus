# evals/entities.py
"""Relationships between repository entities, DERIVED from the corpus already
in memory -- never stored, never guessed.

`demo/repo_map.py` describes what Icarus indexed and `demo/structure.py`
describes how the code is arranged. This is the third member of that family and
follows the same discipline: chunks in, dict out, pure -- no model call, no
network, no filesystem, no re-ingest. It exists because an investigation has to
be able to walk from a pull request to the issue it closes, to the files it
touched, to what happened to those files afterwards; today none of that is
reachable at answer time even though every fact needed to derive it is sitting
in chunk text.

## The one rule

**Every edge names the indexed chunk whose text proves it.** An edge that cannot
point at its own proof is not emitted. This is the same rule `structure.py`
arrived at the hard way -- its first generic resolver invented a `pkg -> demo`
dependency across 566 files of lazygit that was indistinguishable from the true
edges beside it. A wrong relationship is not a worse answer, it is a confident
lie about the reader's own repository.

So there is no fallback resolver here either. An edge is read off literal text
in a chunk (a `Files changed:` line, a `#372` mention, a `(#400)` commit
subject) or it does not exist.

## Honest ceilings, disclosed rather than hidden

- `changed_files` comes from ingest's `Files changed (N): ...` line, which lists
  at most `_MAX_FILES_LISTED` (30) paths. A PR that touched more is marked
  `truncated`, so a traversal can never read as exhaustive when it is not.
- `linked_issues` comes from `#N` mentions in the PR's own text. GitHub's exact
  `closingIssuesReferences` IS fetched during ingest and then discarded
  (evals/ingest.py), so an issue linked only through GitHub's UI and never
  mentioned in prose is invisible here. Under-reporting, never invention.
- `commits` relies on the `(#400)` squash-merge subject convention. A repository
  that does not squash-merge yields none -- correctly, since nothing in its
  commit messages records the link.
- `subsequent_prs` is ordered by PR NUMBER, which is monotonic in creation time
  on GitHub. It means "opened later and touched a file this one touched", not
  "caused by".
- Dependency edges are not RESOLVED here. `demo/structure.py` already does that,
  correctly and per-language; pass its output in via `structure=` and it is
  exposed under this interface rather than reimplemented. What is added is the
  proof: structure returns path pairs, so each edge is matched to the importing
  file's own indexed window that names the import, and dropped when no window
  does -- an edge is never cited to lines that do not contain it.
- A relationship with a file targets the file's PATH. `chunks_for(path)` expands
  it when a caller wants text to read. See `Edge`.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

# ingest renders "Files changed (12): a.py (+1/-2) · b.py (+0/-3) · … and 5 more
# files". Anchored to the line start so a comment quoting the phrase mid-sentence
# cannot produce file edges.
_FILES_LINE = re.compile(r"^Files changed \((\d+)\): (.+)$", re.MULTILINE)
_FILE_ENTRY = re.compile(r"^(.+?) \(\+\d+/-\d+\)$")
_TRUNCATION = re.compile(r"…\s*and \d+ more file")

# A bare "#372". The lookbehind rejects `owner/repo#372` (another repository's
# issue) and `abc#372`, both of which would otherwise resolve to a local issue
# that has nothing to do with the mention.
_LOCAL_REF = re.compile(r"(?<![\w/#-])#(\d+)\b")

# A squash-merge commit subject: "Fix chunking on large repos (#400)". Only the
# FIRST line is scanned -- a commit body routinely quotes other PR numbers as
# context, and treating those as "this commit belongs to that PR" would attach
# a commit to a PR it was never part of.
_SUBJECT_PR = re.compile(r"\(#(\d+)\)\s*$")

EDGE_LINKED_ISSUES = "linked_issues"
EDGE_CHANGED_FILES = "changed_files"
EDGE_COMMITS = "commits"
EDGE_MENTIONED_BY = "mentioned_by"
EDGE_SUBSEQUENT_PRS = "subsequent_prs"
EDGE_DEPENDENTS = "dependents"
EDGE_DEPENDENCIES = "dependencies"

EDGE_KINDS = (
    EDGE_LINKED_ISSUES, EDGE_CHANGED_FILES, EDGE_COMMITS, EDGE_MENTIONED_BY,
    EDGE_SUBSEQUENT_PRS, EDGE_DEPENDENTS, EDGE_DEPENDENCIES,
)

# A sweeping PR can touch every file in a repository, and a popular file can be
# touched by hundreds of PRs. Both would swamp an investigation's evidence
# budget with the least specific evidence available, so both are bounded -- and
# the bound is REPORTED (see EntityIndex.truncated_edges) rather than silently
# applied.
_MAX_SUBSEQUENT = 20

_FILE_SOURCES = ("code", "doc", "config")


@dataclass(frozen=True)
class Edge:
    """One relationship, and the chunk whose literal text proves it.

    A relationship whose other end is a FILE targets the file's repository PATH,
    never one of its chunks. Two reasons, both learned from real data:

    - A file is indexed as many overlapping windows. Fanning an edge out across
      them turned 30 real import edges into 56,056 emitted ones on the committed
      corpus -- quadratic in windows per file, and it buries "12 files changed"
      under 78 near-duplicate refs.
    - Naming ONE window as the target would be a guess about which part of the
      file the relationship concerns. `demo/structure.py` learned this the
      expensive way when picking a package's alphabetically-first file stated
      18.1% of sampled edges wrongly.

    So a path is the honest granularity, and `EntityIndex.chunks_for` expands it
    when a caller actually wants evidence to read. `indexed` says whether Icarus
    holds that file at all -- a pull request genuinely names files ingest never
    indexed (a `.json`, a since-deleted file), and dropping them would
    under-report while inventing refs for them would be worse.
    """

    kind: str
    source_ref: str
    target: str
    evidence_ref: str
    indexed: bool = True


def _path_of(ref: str) -> Optional[str]:
    """The repository path a file-addressable ref points at, or None."""
    source, sep, rest = ref.partition(":")
    if not sep or source not in _FILE_SOURCES:
        return None
    return rest.partition("#")[0]


def _first_line(text: str) -> str:
    return (text or "").split("\n", 1)[0]


def _own_number(ref: str) -> Optional[str]:
    source, sep, rest = ref.partition(":")
    return rest if sep and source in ("pr", "issue") and rest.isdigit() else None


class EntityIndex:
    """Derived edges over one corpus. Read-only, cheap to build, safe to rebuild
    per request -- it holds refs and short strings, never chunk text."""

    def __init__(self, edges: List[Edge], truncated: Dict[str, int],
                 limitations: List[str], paths: Dict[str, List[str]] = None):
        self._by_source = defaultdict(list)
        for edge in edges:
            self._by_source[(edge.source_ref, edge.kind)].append(edge)
        self._paths = dict(paths or {})
        self.truncated_edges = dict(truncated)
        self.limitations = list(limitations)

    def edges(self, ref: str, kind: str) -> List[Edge]:
        """Every edge of `kind` out of `ref`, deterministically ordered. An
        unknown ref or an edge kind nothing derived returns [] -- a traversal
        that finds nothing says so rather than raising.

        A FILE entity is identified by its repository path, so a caller holding
        a chunk ref (`code:llm/cli.py#L1-L300`) may pass either -- the ref is
        normalized to its path rather than silently matching nothing."""
        if kind not in EDGE_KINDS:
            raise ValueError(f"unknown edge kind: {kind!r}")
        hit = self._by_source.get((ref, kind))
        if hit is None:
            hit = self._by_source.get((_path_of(ref) or ref, kind), ())
        return list(hit)

    def targets(self, ref: str, kind: str, indexed_only: bool = True) -> List[str]:
        """Just the targets -- what a `trace()` probe actually consumes."""
        return [e.target for e in self.edges(ref, kind)
                if e.indexed or not indexed_only]

    def chunks_for(self, path: str) -> List[str]:
        """Every indexed chunk ref covering a repository path, in ref order.

        This is where a file-level relationship becomes something to read. Kept
        separate from `targets()` on purpose: deciding to walk an edge and
        deciding to spend evidence budget on a file's windows are two different
        decisions, and only the second is expensive."""
        return list(self._paths.get(path, ()))

    def is_truncated(self, ref: str, kind: str) -> bool:
        """Did this edge list hit a ceiling? A caller that reports "the files it
        changed" must be able to tell an exhaustive list from a clipped one."""
        return self.truncated_edges.get(f"{ref}|{kind}", 0) > 0


def build_entity_index(chunks, structure=None) -> EntityIndex:
    """Derive every provable relationship in `chunks`.

    `structure` is `demo.structure.build_structure(chunks)`'s output, passed in
    rather than imported: `demo` depends on `evals`, never the other way round,
    and file-dependency resolution is already solved there per-language. Omit it
    and dependency edges are simply absent (and said to be, in `limitations`).
    """
    by_ref = {}
    paths = defaultdict(list)          # repo path -> indexed refs, sorted
    for chunk in sorted(chunks, key=lambda c: c.ref):
        by_ref[chunk.ref] = chunk
        path = _path_of(chunk.ref)
        if path is not None:
            paths[path].append(chunk.ref)

    edges: List[Edge] = []
    truncated: Dict[str, int] = {}
    files_by_pr: Dict[str, List[str]] = {}

    for ref, chunk in by_ref.items():
        if chunk.source not in ("pr", "issue", "commit"):
            continue
        if chunk.source == "commit":
            m = _SUBJECT_PR.search(_first_line(chunk.text))
            if m and f"pr:{m.group(1)}" in by_ref:
                edges.append(Edge(EDGE_COMMITS, f"pr:{m.group(1)}", ref, ref))
            continue

        mine = _own_number(ref)
        # -- #N mentions -> linked issues (and the reverse edge) --------------
        for number in dict.fromkeys(_LOCAL_REF.findall(chunk.text)):
            if number == mine:
                continue          # a PR body restating its own number
            target = f"issue:{number}"
            if target not in by_ref:
                # Either a PR (a different relationship), a foreign reference,
                # or an issue outside the indexed slice. Nothing provable here.
                continue
            edges.append(Edge(EDGE_LINKED_ISSUES, ref, target, ref))
            edges.append(Edge(EDGE_MENTIONED_BY, target, ref, ref))

        # -- the Files changed line -> changed files --------------------------
        if chunk.source != "pr":
            continue
        m = _FILES_LINE.search(chunk.text)
        if not m:
            continue
        listed = []
        for entry in m.group(2).split(" · "):
            entry = entry.strip()
            hit = _FILE_ENTRY.match(entry)
            if not hit:
                continue          # the "… and N more files" tail, or a clipped line
            listed.append(hit.group(1))
        for path in dict.fromkeys(listed):
            edges.append(Edge(EDGE_CHANGED_FILES, ref, path, ref,
                              indexed=path in paths))
        files_by_pr[ref] = listed
        # The declared count exceeding the listed one, or ingest's own marker,
        # both mean this list is clipped. Either is enough.
        declared = int(m.group(1))
        if declared > len(listed) or _TRUNCATION.search(m.group(2)):
            truncated[f"{ref}|{EDGE_CHANGED_FILES}"] = declared - len(listed)

    # -- PRs that touched the same file later --------------------------------
    # Number order is creation order on GitHub, so "higher number" is "opened
    # afterwards". This is co-occurrence, not causation, and says so.
    by_path_prs = defaultdict(list)
    for pr_ref, listed in files_by_pr.items():
        for path in listed:
            by_path_prs[path].append(pr_ref)
    for pr_ref, listed in files_by_pr.items():
        mine = int(_own_number(pr_ref))
        later = {}
        for path in listed:
            for other in by_path_prs[path]:
                other_n = int(_own_number(other))
                if other_n > mine and other not in later:
                    later[other] = path
        ordered = sorted(later, key=lambda r: int(_own_number(r)))
        for other in ordered[:_MAX_SUBSEQUENT]:
            edges.append(Edge(EDGE_SUBSEQUENT_PRS, pr_ref, other, pr_ref))
        if len(ordered) > _MAX_SUBSEQUENT:
            truncated[f"{pr_ref}|{EDGE_SUBSEQUENT_PRS}"] = len(ordered) - _MAX_SUBSEQUENT

    limitations = [
        "Relationships are read from the text of chunks Icarus indexed. An edge "
        "that no indexed text states is absent here -- never inferred.",
        "Changed-file lists come from the pull request's own summary, which "
        "ingest caps at 30 paths. A clipped list is reported by is_truncated() "
        "and must not be presented as everything the change touched.",
        "Linked issues come from #N mentions in the pull request's own text. An "
        "issue linked only through GitHub's interface, and never written down, "
        "is not visible.",
        "Commits attach to a pull request only when the commit subject carries "
        "the (#N) squash-merge convention. A repository that merges differently "
        "correctly yields none.",
        "subsequent_prs means a later-numbered pull request touched a file this "
        "one touched. It is co-occurrence in time, not a causal link.",
        "A relationship with a file names the file's path, not one of its "
        "indexed windows -- use chunks_for(path) to read it. Naming a single "
        "window would guess which part of the file the relationship concerns.",
    ]

    if structure:
        exact_proofs = {
            (record.get("source"), record.get("target")): record.get("ref")
            for record in structure.get("file_edge_evidence", ())
            if isinstance(record, dict)
        }
        for importer, imported in structure.get("file_edges", ()):
            # structure.py only ever emits edges between files it INDEXED, but
            # this must not assume that: an edge naming a path with no chunk
            # would be a dependency on something Icarus cannot show.
            if importer not in paths or imported not in paths:
                continue
            # WHICH window of the importer proves it. structure.py resolved the
            # edge but its file_edges carry no chunk, and pointing at the file's
            # first window would send a reader to lines that may hold no import
            # at all. Locate the window whose text actually names the imported
            # module; if none does (the import fell outside every indexed
            # window), drop the edge rather than cite the wrong lines.
            proof = exact_proofs.get((importer, imported))
            if proof is None and "file_edge_evidence" not in structure:
                # Compatibility with older pre-proof structure payloads. New
                # build_structure output always carries the exact window.
                stem = imported.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                proof = next((r for r in paths[importer]
                              if stem in by_ref[r].text), None)
            if proof not in paths[importer]:
                proof = None
            if proof is None:
                continue
            edges.append(Edge(EDGE_DEPENDENCIES, importer, imported, proof))
            edges.append(Edge(EDGE_DEPENDENTS, imported, importer, proof))
        limitations.append(
            "File dependencies are import edges from demo/structure.py: which "
            "file depends on which, not which function calls which, and only "
            "for the languages it analyses."
        )
    else:
        limitations.append(
            "No dependency structure was supplied, so dependents/dependencies "
            "are empty -- nothing looked, rather than nothing found."
        )

    edges.sort(key=lambda e: (e.source_ref, e.kind, e.target))
    return EntityIndex(edges, truncated, limitations, paths)
