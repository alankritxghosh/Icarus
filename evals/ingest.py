# evals/ingest.py
"""Generate a corpus from a public GitHub repo into evals/corpus/chunks.jsonl.

One-time generation tool (needs `gh` + `git`). Sources: PR descriptions + linked
issues (the "why"), and Python source files (the "what"). Run from the repo root:

    python3 -m evals.ingest                         # the pinned simonw/llm corpus
    python3 -m evals.ingest --repo OWNER/REPO       # any public repo (HEAD)
    python3 -m evals.ingest --repo OWNER/REPO --commit SHA --code-dir src

With no args it reproduces the pinned simonw/llm corpus exactly (so the eval
board stays reproducible). Any --repo override ingests that repo and writes a
meta.json recording the provenance, which the demo reads for citation links.
Public repos only while on free models (see CLAUDE.md).
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from .corpus import Chunk
from .corpus_meta import write_meta
from .synth import _MAX_CODE_CHUNK_CHARS as _CHUNK_MAX_CHARS

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"
PR_LIMIT = 200  # recent PRs (any state); the 6 gold PRs are well within this range
ISSUE_LIMIT = 500  # all open+closed issues; generous headroom over a typical repo's issue count
OUT = Path(__file__).resolve().parent / "corpus" / "chunks.jsonl"
META = Path(__file__).resolve().parent / "corpus" / "meta.json"

ISSUE_REF = re.compile(r"#(\d+)")

# Resource bounds so a huge or hostile repo can't fill disk / hang / OOM.
_SUBPROCESS_TIMEOUT = 120       # seconds, per git/gh call
_MAX_FILE_BYTES = 512 * 1024    # skip any single file bigger than this
# Stop reading code past this total. Raised 25 MB -> 100 MB (2026-07-13) so a
# large repo isn't artificially truncated. NOTE: on the hosted (Azure Container
# Apps) path this is NOT the binding limit -- the 240s ingress timeout caps a
# sync connect at ~1,900-2,000 chunks (docs/HANDOFF.md), which a repo this large
# hits first. Lifting this cap helps local ingest and any host without that
# timeout; the embed-time bottleneck is tracked separately.
_MAX_TOTAL_BYTES = 100 * 1024 * 1024
# Hard cap on how many CODE/doc/config chunks one repo can yield, independent of
# bytes. Guards the memory/CPU of the (non-backgrounded) lexical stage-1 BM25
# build: a hostile 100 MB repo of many short lines could otherwise produce
# ~190k 300-line windows and OOM a small container (flagged in a 2026-07-13
# review). 50k is far above any real repo we can actually serve -- the 240s
# embed ceiling caps a usable repo at ~2k chunks -- so it only ever trips on a
# pathological/hostile tree. PRs/issues are separately bounded (PR_LIMIT/
# ISSUE_LIMIT), so this need only bound the code walk. Approximate: the walk
# stops at the next file boundary, so it can overshoot by one file's windows.
_MAX_TOTAL_CHUNKS = 50_000

# Extension allowlist -> citation source tag (Task A1). Tight and Phase-1-scale
# on purpose: enough languages/formats to cover a typical mixed repo, not a
# general-purpose language database. Extend this table, not the logic below,
# if a new extension needs a home.
_EXTENSION_SOURCES = {
    # code
    ".py": "code", ".js": "code", ".ts": "code", ".tsx": "code", ".go": "code",
    ".rs": "code", ".java": "code", ".rb": "code", ".c": "code", ".h": "code",
    ".cpp": "code", ".swift": "code", ".kt": "code", ".php": "code",
    ".cs": "code", ".scala": "code", ".sh": "code",
    # code -- Objective-C/C++ implementations. `.h` was already here, so before
    # these landed a React Native repo indexed every iOS DECLARATION and zero
    # implementations: measured 2026-07-17 on wix/react-native-navigation, 280
    # .h indexed against 298 .mm silently dropped (its whole ios/ tree). That
    # asymmetry is worse than dropping both -- the corpus looks like it covers
    # the module, so an honest "no one wrote this down" was really "nobody
    # showed me the file". `.m` is also MATLAB, which is likewise code.
    ".m": "code", ".mm": "code",
    # code -- JS dialects the .js/.ts entries missed. `.jsx` is rare in modern
    # RN (which is .tsx) but standard in plain React; .mjs/.cjs are how real
    # tooling config (eslint.config.mjs, metro.config.cjs) is written.
    ".jsx": "code", ".mjs": "code", ".cjs": "code",
    # doc
    ".md": "doc", ".rst": "doc", ".txt": "doc",
    # config
    ".yaml": "config", ".yml": "config", ".toml": "config", ".cfg": "config",
    ".ini": "config", ".sql": "config",
    # config -- the mobile-native build manifests, same role .toml plays for
    # Python: hand-written, low-volume, and where build/dependency decisions
    # (minSdkVersion, native deps) are actually recorded.
    ".gradle": "config", ".podspec": "config",
    # NOT here, deliberately: `.json`. It was the single biggest dropped
    # extension on a real RN app (mattermost-mobile: 123 files, 5.9MB), but the
    # volume is Xcode asset catalogs (30x Contents.json) and i18n locale
    # bundles -- machine-authored or pure translation data, zero "why" signal --
    # against ~8 real package.json. Indexing it would skew BM25/IDF corpus-wide.
    # If package.json ever needs to be evidence, allowlist that FILENAME.
}

# Path segments that exclude a file regardless of extension (vendored/build/VCS
# noise -- never signal, just volume).
_DENY_DIR_SEGMENTS = {".git", "node_modules", "vendor", "dist", "build", ".venv"}

# Specific noisy filenames/patterns skipped even though their extension would
# otherwise pass: generated lockfiles (huge, machine-authored, zero "why"
# signal) and minified assets (unreadable, and always a build artifact of
# source we already ingest separately).
_DENY_FILENAMES = {
    "package-lock.json", "yarn.lock", "Pipfile.lock", "poetry.lock", "Cargo.lock",
}
_DENY_FILENAME_SUFFIXES = (".min.js", ".min.css")

_BINARY_SNIFF_BYTES = 8192  # how much of the file head to check for a null byte

# Line-window chunking (Task A2). A window of 300 lines is small enough for a
# BM25/embedding retriever to score a chunk as a coherent unit and for a writer
# prompt to consume several chunks without blowing its context, while staying
# large enough that most functions/classes fit inside one window rather than
# being fragmented on every chunk boundary. 40 lines of overlap (~13% of the
# window) is enough that a definition straddling a boundary is still whole in
# at least one of the two windows, without materially inflating chunk count.
# Both are plain module constants, not derived from any measurement -- if a
# future eval shows retrieval quality wants different numbers, change these.
_CHUNK_WINDOW_LINES = 300
_CHUNK_OVERLAP_LINES = 40
assert _CHUNK_OVERLAP_LINES < _CHUNK_WINDOW_LINES, (
    "overlap must be smaller than the window, or chunk_text's stride "
    "would be <= 0 and its while loop would never advance"
)


def chunk_text(text: str, ref_prefix: str) -> List[dict]:
    """Split `text` into size-bounded, overlapping line-windows.

    `ref_prefix` is the ref a caller would have used for a single whole-file
    chunk (e.g. `f"{source}:{rel_path}"`, exactly what `fetch_code` builds
    today). Returns a list of `{"ref": ..., "text": ...}` dicts -- no
    `"source"` key, by design: the caller already has the source tag baked
    into `ref_prefix` and builds the rest of the chunk dict itself (matching
    how `fetch_prs`/`fetch_issues`/`fetch_code` all assemble
    `{"ref": ..., "source": ..., "text": ...}` at their own call sites); this
    keeps `chunk_text` ignorant of the source taxonomy entirely.

    If `text` has at most `_CHUNK_WINDOW_LINES` lines, returns exactly ONE
    chunk with `ref_prefix` unchanged (no line range) -- this is today's
    existing whole-file ref format and must not gain a spurious line range
    just because it went through this function. Otherwise splits into
    consecutive windows of `_CHUNK_WINDOW_LINES` lines with
    `_CHUNK_OVERLAP_LINES` lines of overlap between neighbors, each ref
    carrying a 1-indexed, inclusive `#Lstart-Lend` suffix (GitHub's own
    line-link convention, so a later citation-link update can parse it
    directly). The last window ends exactly at the real last line -- no
    padding past end-of-file, no phantom trailing window.

    Pure and offline: no filesystem, no network. `splitlines()` (not a raw
    split on "\n") so a missing/extra trailing newline in `text` doesn't
    produce a spurious empty final "line".

    `ref_prefix` must not itself contain "#" -- a real repo-relative path
    never does, so this is a caller-contract assertion, not a real-world
    case: a downstream ref parser (e.g. a citation-link builder recovering
    the path via `ref.split("#")[0]`) would otherwise silently see a
    malformed two-`#` ref for a windowed chunk instead of a caller bug
    failing loudly here.
    """
    assert "#" not in ref_prefix, f"ref_prefix must not contain '#': {ref_prefix!r}"

    lines = text.splitlines()
    total = len(lines)

    if total <= _CHUNK_WINDOW_LINES and len(text) <= _CHUNK_MAX_CHARS:
        return [{"ref": ref_prefix, "text": text}]

    chunks = []
    start = 0  # 0-indexed line offset into `lines`
    while start < total:
        # Grow the window up to _CHUNK_WINDOW_LINES lines, but stop early if
        # the joined text would exceed _CHUNK_MAX_CHARS -- a short-but-dense
        # file (long docstrings, generated tables) can blow the char budget
        # well before the line budget, and a chunk this large would just be
        # silently truncated by synth.py's build_prompt anyway, even though
        # it was retrieved and reached the writer's top-k. Floor of one line
        # of progress so a single pathological oversized line can't stall
        # the loop.
        end = start + 1
        joined = lines[start]
        line_cap = min(start + _CHUNK_WINDOW_LINES, total)
        while end < line_cap:
            candidate = joined + "\n" + lines[end]
            if len(candidate) > _CHUNK_MAX_CHARS:
                break
            joined = candidate
            end += 1
        if len(joined) > _CHUNK_MAX_CHARS:
            # The floor-of-one-line-of-progress guarantee above means `joined`
            # can still be over budget here -- but ONLY if lines[start] alone
            # already was (the inner loop never lets a window grow past the
            # budget otherwise). Found live 2026-07-17: a machine-generated
            # ~250,000-char single line (one object literal spanning almost no
            # real newlines) made a whole 125-line file into ONE oversized
            # chunk, since the file's LINE count never tripped any limit.
            # Truncate rather than skip: both downstream consumers already
            # silently ignore anything past this point today (synth.py caps
            # code chunks at this same _CHUNK_MAX_CHARS for the writer; the
            # embedder truncates at 512 tokens regardless) -- so this makes an
            # EXISTING effective truncation honest and logged once at ingest,
            # instead of silently repeated by two different downstream layers.
            print(f"ingest: line {start + 1} of {ref_prefix!r} is "
                  f"{len(joined)} chars, exceeds the {_CHUNK_MAX_CHARS}-char "
                  f"chunk budget alone; truncating", file=sys.stderr)
            joined = joined[:_CHUNK_MAX_CHARS] + " …[truncated]"
        ref = f"{ref_prefix}#L{start + 1}-L{end}"
        chunks.append({"ref": ref, "text": joined + "\n"})
        if end == total:
            break
        # Overlap measured from wherever this window actually ended, not a
        # fixed additive stride -- degrades to the exact previous behavior
        # whenever a window is never char-bound-limited (the common case).
        start = max(start + 1, end - _CHUNK_OVERLAP_LINES)
    return chunks


# T4 of docs/plans/2026-07-17-ast-chunking-all-languages.md: dispatch a CODE
# chunk's text to the best available chunker for its extension, behind an env
# flag so the switch can be rolled back without a redeploy if a real repo
# surfaces a problem T1-T3's proof didn't catch. Default OFF -- the committed
# `simonw/llm` board and every existing corpus keep chunking exactly as before
# until this is deliberately turned on.
ICARUS_AST_CHUNKING_ENV = "ICARUS_AST_CHUNKING"

# T6: the value stamped into meta.json's "chunking" field, so a later connect
# can tell whether a corpus already on disk was chunked by the scheme
# currently active -- see `ast_chunking_enabled` and demo/library.py's
# staleness check in `Library._resolve`.
CHUNKING_SCHEME_AST = "ast"
CHUNKING_SCHEME_LINE_WINDOW = "chunk_text"


def ast_chunking_enabled() -> bool:
    """The single source of truth for whether ICARUS_AST_CHUNKING is on.
    Shared by `_chunk_code` (what actually chunks a file) and `ingest_repo`
    (what stamps meta.json's "chunking" field) so the two can never silently
    disagree about which scheme was really used for a given corpus -- a
    duplicated truthy-parsing implementation in each caller would be exactly
    the kind of drift that makes a staleness check lie."""
    return os.environ.get(ICARUS_AST_CHUNKING_ENV, "").strip().lower() in ("1", "true", "yes")


def _chunk_code(text: str, ref_prefix: str, ext: str) -> List[dict]:
    """Split a CODE file's text with the best chunker available for `ext`,
    when `ICARUS_AST_CHUNKING` is enabled -- otherwise identical to calling
    `chunk_text` directly. Doc/config sources never reach this function; only
    the `fetch_code` code-walk source is code-structured enough for a
    function/class-boundary chunker to make sense of.

    `ast_chunk`/`ts_chunk` are imported HERE, not at this module's top level,
    because both import FROM `ingest` (`chunk_text`, `_CHUNK_MAX_CHARS`,
    `_CHUNK_WINDOW_LINES`) -- importing them eagerly at import time would be a
    circular import. This also keeps `ingest.py` importable without
    tree-sitter-language-pack installed even when the flag is on: `ts_chunk`'s
    own lazy import inside `_get_parser` falls back to `chunk_text` per file,
    it never raises.
    """
    if not ast_chunking_enabled():
        return chunk_text(text, ref_prefix)
    if ext == ".py":
        from .ast_chunk import ast_chunk
        return ast_chunk(text, ref_prefix)
    from .ts_chunk import _LANGUAGE_BY_EXT, ts_chunk
    if ext in _LANGUAGE_BY_EXT:
        return ts_chunk(text, ref_prefix, ext)
    return chunk_text(text, ref_prefix)


def classify_file(path: Path, root: Path) -> Optional[str]:
    """Decide whether `path` (a file somewhere under `root`) should be
    ingested, and under which citation source tag.

    Returns "code" / "doc" / "config" if the file should be ingested, or None
    if it should be skipped. Pure and offline -- no filesystem writes, no
    network. Per-file only: does not enforce the total-byte ingest budget
    (that's `_MAX_TOTAL_BYTES`, a stateful concern for the caller walking a
    tree); it only rejects a file already larger than `_MAX_FILE_BYTES`.

    `root` lets deny-listed directory segments (e.g. `node_modules`) be
    checked against the path relative to the repo root, matching how
    `fetch_code` already computes `path.relative_to(root)` for citation refs.
    Contract: `path` must be under `root` -- callers walk a tree (e.g. via
    `rglob`) rooted there. `path.relative_to(root)` raises `ValueError` on a
    misuse (a path outside the walked root) rather than silently falling back
    to scanning the absolute path's own segments, which could spuriously
    match a deny-listed name (e.g. a real filesystem prefix containing
    `vendor` or `.git`) and misclassify a file relative to the wrong tree.

    Extension matching is case-INSENSITIVE: `Script.PY` and `README.MD`
    classify the same as `Script.py`/`README.md`. Found live (2026-07-13)
    against `id-Software/wolf3d` -- classic DOS 8.3 uppercase filenames
    (`ID_CA.C`, `ID_MM.C`) made an entire real, historically significant C
    codebase silently invisible (code: 0, no error), so "rare enough to skip"
    was wrong even for one of the most well-known legacy releases on GitHub.
    The citation ref itself still uses the file's real on-disk case -- only
    the extension LOOKUP is case-folded, never the stored path.
    """
    rel = path.relative_to(root)

    if set(rel.parts) & _DENY_DIR_SEGMENTS:
        return None

    name = path.name
    if name in _DENY_FILENAMES:
        return None
    if name.endswith(_DENY_FILENAME_SUFFIXES):
        return None

    source = _EXTENSION_SOURCES.get(path.suffix.lower())
    if source is None:
        return None

    try:
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
    except OSError:
        return None

    try:
        with path.open("rb") as f:
            head = f.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return None
    if b"\x00" in head:
        return None

    return source


def _git_env(token=None):
    """Subprocess env for git. A token authenticates via GIT_CONFIG_* env
    (http.extraHeader with Basic x-access-token) -- never argv (visible in ps),
    never the URL (lands in git config). The token is never logged."""
    env = dict(os.environ)
    if token:
        basic = base64.b64encode(f"x-access-token:{token}".encode()).decode()
        env.update({
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "http.extraHeader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {basic}",
        })
    return env


def _gh_env(token=None):
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token  # per-call, never the server's ambient identity
    return env


def _safe_code_dir(clone_dir, code_dir):
    """Resolve code_dir inside clone_dir; refuse anything that escapes it
    (absolute paths, ``..``). Prevents ingesting files outside the clone."""
    root = Path(clone_dir).resolve()
    target = (root / code_dir).resolve()
    if root != target and root not in target.parents:
        raise ValueError(f"code_dir escapes the clone: {code_dir!r}")
    return target


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Ingest a public GitHub repo into the corpus")
    p.add_argument("--repo", default=REPO, help="owner/name of a public repo")
    p.add_argument("--commit", default=None, help="commit SHA to pin (default: repo HEAD)")
    p.add_argument("--code-dir", default=None,
                    help="subtree to walk (default: 'llm' for the pinned repo, "
                         "the whole clone root for any other repo)")
    return p.parse_args(argv)


def resolve_commit(repo: str, commit, token=None) -> str:
    """Explicit --commit wins; the default repo without one keeps the pinned SHA
    (reproducible board); any other repo resolves its HEAD via git ls-remote."""
    if commit:
        return commit
    if repo == REPO:
        return COMMIT
    out = subprocess.run(
        ["git", "ls-remote", f"https://github.com/{repo}.git", "HEAD"],
        check=True, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT,
        env=_git_env(token),
    ).stdout
    return out.split()[0]


def resolve_code_dir(repo: str, code_dir) -> str:
    """Explicit --code-dir wins; the default repo without one keeps its
    historical 'llm' subtree (byte-scope-reproducible board -- same repo,
    commit, and subtree, per the resolved Brick A ambiguity); any other repo
    walks the whole clone root. Mirrors resolve_commit's shape exactly."""
    if code_dir:
        return code_dir
    if repo == REPO:
        return "llm"
    return "."


def _gh_json(args, token=None):
    out = subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, timeout=_SUBPROCESS_TIMEOUT,
        env=_gh_env(token),
    ).stdout
    return json.loads(out) if out.strip() else None


# A single PR/issue's title + body + discussion can be large; bound one ref's
# chunk so it can't dominate memory or the writer prompt. Matches the writer's
# own per-chunk budget (synth._MAX_CODE_CHUNK_CHARS), so a chunk that fits here
# is fully visible to the writer rather than silently re-clipped downstream.
_REF_DETAIL_MAX_CHARS = 10000

# A sweeping refactor can touch thousands of files. The list is context for the
# discussion, not the point of the chunk -- an unbounded one would crowd the
# actual reasoning out of the writer's 10k-char view of this ref.
_MAX_FILES_LISTED = 30

# The fields worth asking for on a PR. `gh pr list --json` returns ALL of these
# in the SAME single request that already fetched title+body (verified against
# `gh pr list --json` on gh 2.x), so the discussion costs no extra round trips --
# the N+1 that made ingest slow in the first place is not reintroduced.
_PR_JSON_FIELDS = ("number,title,body,closingIssuesReferences,state,author,"
                   "mergedAt,labels,files,comments,reviews")
_ISSUE_JSON_FIELDS = "number,title,body,state,author,labels,comments"


def _login(actor):
    """A gh actor object -> its login. Absent/null actor (a deleted account, a
    field the caller's token can't see) reads as unattributed, never a crash."""
    return (actor or {}).get("login") or "unknown"


def _pr_or_issue_text(data, source):
    """One PR/issue's full evidence text: description, what changed, and the
    DISCUSSION -- the part that actually records why.

    Ordering is deliberate. Title and description come FIRST because both
    retrieval and the writer read a chunk from its head, and the embedder only
    sees roughly its first 512 tokens: the discussion must EXTEND the
    description, never displace it. Empty sections are omitted entirely rather
    than rendered as bare headers -- a header repeated across every PR in the
    corpus is a term with no discriminating power that dilutes BM25's idf.

    Bounded by `_REF_DETAIL_MAX_CHARS` with a visible marker, the same cap the
    live path has always used, so an indexed ref and a live-fetched one read
    alike instead of one being mysteriously richer than the other.

    Honest ceiling: `files` is the changed-file LIST with line counts, not diff
    hunks. Hunks need a per-PR `gh pr diff` (one call each -- the N+1 this
    deliberately avoids); a named commit SHA still resolves to a real diff via
    fetch_commit_detail.
    """
    n = data.get("number")
    parts = [f"{source.upper()} #{n}: {data.get('title') or ''}".rstrip()]

    state = data.get("state")
    if state:
        who = _login(data.get("author"))
        line = f"[{state} by {who}]"
        labels = [l.get("name") for l in (data.get("labels") or []) if l.get("name")]
        if labels:
            line += " labels: " + ", ".join(labels)
        parts.append(line)

    body = (data.get("body") or "").strip()
    if body:
        parts.append(body)

    files = data.get("files") or []
    if files:
        shown = files[:_MAX_FILES_LISTED]
        listed = " · ".join(
            f"{f.get('path')} (+{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            for f in shown if f.get("path")
        )
        extra = len(files) - len(shown)
        if extra > 0:
            listed += f" · … and {extra} more file{'s' if extra != 1 else ''}"
        parts.append(f"Files changed ({len(files)}): {listed}")

    for c in data.get("comments") or []:
        text = (c.get("body") or "").strip()
        if text:
            parts.append(f"Comment by {_login(c.get('author'))}: {text}")

    for r in data.get("reviews") or []:
        text = (r.get("body") or "").strip()
        if not text:
            continue  # a bodyless APPROVED review is the commonest of all
        verdict = r.get("state") or ""
        head = f"Review by {_login(r.get('author'))}"
        parts.append(f"{head} ({verdict}): {text}" if verdict else f"{head}: {text}")

    out = "\n\n".join(parts).strip()
    if len(out) > _REF_DETAIL_MAX_CHARS:
        out = out[:_REF_DETAIL_MAX_CHARS] + "\n…[truncated]"
    return out


def fetch_prs(repo, token=None):
    """All PRs (open+closed+merged) up to PR_LIMIT, as chunks, plus the issue
    numbers they link.

    ONE `gh pr list --json ...` call, not a `gh pr view` per PR. The old per-PR
    loop made N+1 serial subprocess calls (verified live 2026-07-15:
    meta-llama/codellama's 47 PRs + 213 issues took ~2.5 min of serial `gh`
    calls); `list --json` returns every PR's title, body, closing refs, changed
    files, comments and reviews in a single request.

    The DISCUSSION is ingested, not just the description (2026-07-28). Storing
    title+body alone meant the reason a change was made -- which lives in the
    review thread far more often than in the description -- was absent from the
    index, producing an honest "no one wrote this down" about something the team
    HAD written down. The live path (`fetch_ref_detail`) had always fetched
    comments, so old unindexed PRs answered richly while recent ones did not."""
    prs = _gh_json(
        ["pr", "list", "-R", repo, "--state", "all", "--limit", str(PR_LIMIT),
         "--json", _PR_JSON_FIELDS],
        token=token,
    ) or []
    chunks, issue_ids = [], set()
    for pr in prs:
        n = pr["number"]
        chunks.append({"ref": f"pr:{n}", "source": "pr",
                       "text": _pr_or_issue_text(pr, "pr")})
        for ref in pr.get("closingIssuesReferences", []):
            issue_ids.add(ref["number"])
        for m in ISSUE_REF.findall(pr.get("body") or ""):
            issue_ids.add(int(m))
    return chunks, issue_ids


def fetch_all_issue_ids(repo, token=None):
    """All issue numbers (open AND closed) up to ISSUE_LIMIT, unfiltered by
    whether anything links to them -- closes the coverage gap where a
    standalone, never-linked issue (e.g. an open bug report) was invisible to
    fetch_issues because fetch_prs only ever surfaces issues mentioned by a
    merged PR.

    A repo with Issues disabled (a common, legitimate GitHub setting -- e.g.
    projects that track issues off-platform) makes `gh issue list` fail
    outright rather than return an empty list; treat that specific case as
    zero issues instead of failing the entire ingest, but let any OTHER
    failure (auth, network, rate limit) propagate -- this must not become a
    blanket swallow."""
    try:
        items = _gh_json(
            ["issue", "list", "-R", repo, "--state", "all", "--limit", str(ISSUE_LIMIT), "--json", "number"],
            token=token,
        )
    except subprocess.CalledProcessError as e:
        if "has disabled issues" in (e.stderr or ""):
            print(f"issues disabled for {repo!r}; treating as zero issues", file=sys.stderr)
            return set()
        raise
    return {it["number"] for it in items}


def fetch_issues(repo, issue_ids, token=None):
    """Chunks for the issues named in `issue_ids`, fetched in ONE
    `gh issue list --json ...,body` call rather than a `gh issue view` per
    issue (same N+1 -> 1 speedup as fetch_prs). Returns issues sorted by number
    for reproducible ingests regardless of `gh`'s return order.

    A number in `issue_ids` that is actually a PR (a `#N` body mention pointing
    at a PR) simply won't appear in the issue list and is dropped -- the same
    outcome the old per-item loop got by catching the failed `gh issue view`,
    now without the failing call. Issues-disabled is handled the same way
    fetch_all_issue_ids handles it (a `#N` PR mention could leave issue_ids
    non-empty even on a disabled-issues repo)."""
    if not issue_ids:
        return []
    try:
        items = _gh_json(
            ["issue", "list", "-R", repo, "--state", "all", "--limit", str(ISSUE_LIMIT),
             "--json", _ISSUE_JSON_FIELDS],
            token=token,
        ) or []
    except subprocess.CalledProcessError as e:
        if "has disabled issues" in (e.stderr or ""):
            return []  # no issues to fetch even if a PR body mentioned a #N
        raise
    wanted = set(issue_ids)
    chunks = []
    for it in sorted(items, key=lambda x: x["number"]):
        n = it["number"]
        if n not in wanted:
            continue
        chunks.append({"ref": f"issue:{n}", "source": "issue",
                       "text": _pr_or_issue_text(it, "issue")})
    return chunks


def fetch_ref_detail(repo, number, token=None) -> Optional[Chunk]:
    """Live-fetch ONE pull request or issue #number -- its title, body, AND its
    discussion COMMENTS -- as a single Chunk, for an explicit "#N" the pre-indexed
    slice (fetch_prs/fetch_issues cap at PR_LIMIT/ISSUE_LIMIT most-recent) doesn't
    cover. A number is either a PR or an issue on GitHub, so try `gh pr view`
    first, then `gh issue view`; whichever resolves wins. Returns None on any
    failure -- not found, network, auth, timeout, bad JSON -- so the caller
    abstains exactly as before (never a bluff). Leak-safe token via _gh_env; with
    token=None the caller's own gh identity is used, so a private repo the server
    can't read simply fails to None rather than exposing anything."""
    for source in ("pr", "issue"):
        fields = _PR_JSON_FIELDS if source == "pr" else _ISSUE_JSON_FIELDS
        try:
            data = _gh_json(
                [source, "view", str(number), "-R", repo, "--json", fields],
                token=token,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
            continue
        if not data:
            continue
        # Same builder as the indexed path, so a live-fetched ref and an indexed
        # one read identically -- the two diverging is what let the indexed path
        # silently stay shallower than the live one for weeks.
        return Chunk(ref=f"{source}:{data['number']}", source=source,
                     text=_pr_or_issue_text(data, source))
    return None


def fetch_commit_detail(repo, sha, token=None) -> Optional[Chunk]:
    """Live-fetch ONE commit -- its message, author, and per-file diff -- as a
    single Chunk, for an explicit SHA in the question.

    Commits are deliberately NOT indexed (a real repo has 10k-1M of them; they'd
    swamp the 50k chunk cap and BM25's IDF for zero benefit on ordinary
    questions). But "what did commit abc123 change?" names an exact identifier,
    so it's a lookup, not a search -- the same shape as fetch_ref_detail's #N.
    Fail-safe: None on not-found/network/auth/timeout/bad JSON, so the caller
    abstains exactly as before. Leak-safe token via _gh_env; token=None uses the
    server's own gh identity, so an unreadable private repo fails to None."""
    try:
        data = _gh_json(["api", f"repos/{repo}/commits/{sha}"], token=token)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None
    if not data or not data.get("sha"):
        return None
    full = data["sha"]
    commit = data.get("commit") or {}
    author = (commit.get("author") or {}).get("name") or "?"
    date = (commit.get("author") or {}).get("date") or "?"
    parts = [f"Commit {full[:12]}: {commit.get('message') or ''}".strip(),
             f"Author: {author} on {date}"]
    for f in data.get("files") or []:
        parts.append(
            f"{f.get('status', 'modified')} {f.get('filename')} "
            f"(+{f.get('additions', 0)}/-{f.get('deletions', 0)})\n{f.get('patch') or ''}".strip()
        )
    text = "\n\n".join(p for p in parts if p).strip()
    if len(text) > _REF_DETAIL_MAX_CHARS:
        text = text[:_REF_DETAIL_MAX_CHARS] + "\n…[truncated]"
    return Chunk(ref=f"commit:{full}", source="commit", text=text)


def fetch_code(repo, commit, code_dir, token=None, stats=None):
    # Fetch ONLY the pinned commit, never full history. This used to be a full
    # `git clone`, whose stated reason was keeping an ARBITRARY pinned commit
    # checkout-able (the eval board pins simonw/llm @ 94769b8) -- something
    # `clone --depth 1` genuinely cannot do, since it only fetches a branch tip.
    #
    # But a full clone made large real repos un-ingestable outright: measured
    # 2026-07-17, Expensify/App (2.7GB, the largest real public React Native
    # app) died with `fatal: early EOF` past the 120s _SUBPROCESS_TIMEOUT. Not
    # a truncated corpus -- a hard failure, at any cap.
    #
    # Fetching the SHA directly at depth 1 satisfies both constraints. GitHub
    # serves a reachable SHA to a depth-1 fetch, so the checkout stays exactly
    # as byte-reproducible as before while skipping all history. Verified live:
    # Expensify/App 27s (was >120s failure), the board's own pin 2s, each
    # landing that exact SHA. The token still rides in via _git_env's
    # http.extraHeader, which applies to fetch exactly as it did to clone --
    # never argv, never the URL.
    #
    # Timeouts still bound every call; size caps still bound memory.
    chunks, total = [], 0
    with tempfile.TemporaryDirectory() as d:
        env = _git_env(token)
        subprocess.run(["git", "init", "--quiet", d],
                       check=True, timeout=_SUBPROCESS_TIMEOUT, env=env)
        subprocess.run(["git", "-C", d, "remote", "add", "origin",
                        f"https://github.com/{repo}.git"],
                       check=True, timeout=_SUBPROCESS_TIMEOUT, env=env)
        subprocess.run(["git", "-C", d, "fetch", "--depth", "1", "--quiet", "origin", commit],
                       check=True, timeout=_SUBPROCESS_TIMEOUT, env=env)
        subprocess.run(["git", "-C", d, "checkout", "--quiet", "FETCH_HEAD"],
                       check=True, timeout=_SUBPROCESS_TIMEOUT, env=env)
        # Resolve once, consistently: _safe_code_dir already resolves its own
        # return value, and on macOS /var is a symlink to /private/var, so an
        # unresolved `d` used in relative_to() below would mismatch against
        # paths yielded by the resolved `base` -- resolving `d` too keeps refs
        # relative to the clone root (unchanged format) while fixing that.
        root = Path(d).resolve()
        base = _safe_code_dir(d, code_dir)
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            source = classify_file(path, root)
            if source is None:
                continue  # not ingestable (deny-listed, wrong extension, binary, oversized, ...)
            if total > _MAX_TOTAL_BYTES or len(chunks) >= _MAX_TOTAL_CHUNKS:
                # Stop once we've read enough across all sources, by bytes OR by
                # chunk count. Not silent: a truncated corpus must not read as
                # "covered everything" (esp. before sharing with testers) -- both
                # logged to stderr AND flagged in `stats` so it reaches /status.
                why = "byte" if total > _MAX_TOTAL_BYTES else "chunk"
                print(f"ingest: {why} cap reached; truncating code walk of {repo!r} "
                      f"at {len(chunks)} chunks / {total} bytes", file=sys.stderr)
                if stats is not None:
                    stats["truncated"] = True
                break
            rel = path.relative_to(root).as_posix()
            try:
                text = path.read_text(errors="replace")
            except OSError:
                continue  # e.g. vanished mid-walk, permission change, a dangling
                          # symlink/socket/fifo classify_file's is_file() let through
            total += len(text.encode("utf-8", "replace"))
            # AST-aware chunking (T4) only ever applies to CODE -- a doc/config
            # file has no function/class structure for a boundary-aware
            # chunker to make sense of.
            parts = (_chunk_code(text, f"{source}:{rel}", path.suffix.lower())
                     if source == "code" else chunk_text(text, f"{source}:{rel}"))
            for sub in parts:
                # HARD cap, enforced per-chunk (not just per-file): a single file
                # whose windows cross the cap must not overshoot silently. Log and
                # stop the instant we hit it, so a truncated corpus never reads as
                # "covered everything".
                if len(chunks) >= _MAX_TOTAL_CHUNKS:
                    print(f"ingest: chunk cap reached; truncating code walk of {repo!r} "
                          f"at {len(chunks)} chunks / {total} bytes", file=sys.stderr)
                    if stats is not None:
                        stats["truncated"] = True
                    return chunks
                chunks.append({"ref": sub["ref"], "source": source, "text": sub["text"]})
    return chunks


def ingest_repo(repo, out_dir, commit=None, code_dir="llm", token=None, refresh=False):
    """Fetch a repo and write chunks.jsonl + meta.json into out_dir.

    `refresh` is accepted and deliberately IGNORED here: this function always
    ingests, so "re-ingest rather than serve the cache" is meaningless to it.
    It exists so this and the registry's caching wrapper (`_ingest_once`, which
    genuinely needs to distinguish a refresh from a cache fill) share one
    signature, and a caller can pass it without knowing which one it holds.

    Returns counts keyed by every source tag actually ingested -- always "pr"
    and "issue" (0 if none), "code" (0 if none, kept present for backward
    compatibility), plus "doc"/"config" whenever fetch_code's whole-repo walk
    finds files of those kinds. Reusable by the CLI (default corpus) and the
    demo's per-repo cache. Network (gh + git); public repos by default. An
    optional caller token (never from the CLI -- programmatic callers only)
    authenticates git/gh as that caller for a private repo, via env only."""
    commit = resolve_commit(repo, commit, token=token)
    prs, issue_ids = fetch_prs(repo, token=token)
    # Union with ALL issue numbers (open+closed), not just ones a merged PR
    # happens to link -- closes the standalone-issue coverage gap (Brick B1)
    # without touching fetch_prs' own linked-issue detection.
    issue_ids = issue_ids | fetch_all_issue_ids(repo, token=token)
    issues = fetch_issues(repo, issue_ids, token=token)
    code_stats = {}
    code = fetch_code(repo, commit, code_dir, token=token, stats=code_stats)
    all_chunks = prs + issues + code
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "chunks.jsonl").open("w") as f:
        for c in all_chunks:
            f.write(json.dumps(c) + "\n")
    # code may now yield "code"/"doc"/"config" chunks (Task A3's whole-repo
    # walk), not just "code" -- bucket by whatever source tags actually
    # appeared, so every chunk's source is reflected in the counts.
    counts = {"pr": len(prs), "issue": len(issues)}
    for c in code:
        counts[c["source"]] = counts.get(c["source"], 0) + 1
    counts.setdefault("code", 0)
    chunking = CHUNKING_SCHEME_AST if ast_chunking_enabled() else CHUNKING_SCHEME_LINE_WINDOW
    write_meta(out_dir / "meta.json", repo=repo, commit=commit, code_dir=code_dir,
               counts=counts, chunking=chunking, truncated=code_stats.get("truncated", False))
    return counts


def main(argv=None):
    args = parse_args(argv)
    code_dir = resolve_code_dir(args.repo, args.code_dir)
    counts = ingest_repo(args.repo, OUT.parent, commit=args.commit, code_dir=code_dir)
    total = sum(counts.values())
    breakdown = ", ".join(f"{n} {k}" for k, n in counts.items())
    print(f"wrote {total} chunks ({breakdown}) from {args.repo} -> {OUT}")


if __name__ == "__main__":
    main()
