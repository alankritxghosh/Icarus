"""What was tried and REFUSED — the one thing `git log` cannot record.

Measured across six Agent Mode tasks (docs/experiments/2026-08-10-*): in 6 of 6
an unaided code-only reading produced the wrong action, and twice the decisive
fact was a pull request that ATTEMPTED the very change the agent was about to
write and was closed without merging:

- #20744: PR #20787 proposed verbatim the fix a control agent had just written,
  closed by a maintainer with "we need to understand the actual supported
  behavior of pip before we can make any changes here" -- and #20751 had tried
  it before that. The agent's patch would have been the third rejection.
- #20675: a control agent declared a live bug already fixed, because the merged
  fix is in the commit graph. The follow-up attempt (#20754) was closed
  unmerged, the issue stayed open, and only that fact reveals the bug survived.

**A merged PR leaves a commit; a rejected one leaves nothing.** `git log`,
`git blame` and the working tree are all downstream of merges, so an agent with
a full clone still cannot see a refusal. That asymmetry is why this exists.

Deliberately DETERMINISTIC and derived from evidence already retrieved: no
model, no extra fetch, no ingest change. GitHub's own `state` already
distinguishes MERGED from CLOSED and `evals/ingest._pr_or_issue_text` already
writes it into every chunk's header line -- it was sitting there as prose that
nothing read. Because it is computed rather than written, it cannot be bluffed:
there is no path by which this reports an attempt that the indexed text does
not state.

Scope, kept narrow on purpose: this reports that a pull request touching the
retrieved evidence was closed unmerged. It does NOT claim the PR attempted the
caller's specific change, and it cannot say WHY it was closed -- the reason
lives in review comments, and asserting one would be exactly the composed
rationale these experiments caught Icarus inventing twice. Callers are told to
go read it, not told what it says.

**"Closed unmerged" is a much weaker signal than "refused", and the gap was
measured** (docs/experiments/2026-08-11-agent-mode-exp-c2-results.md). Across
the nine pull requests this surfaced over four real tasks on `simonw/llm`,
EIGHT were closed because the same change arrived another way -- four swept in
29 seconds when the maintainer wrote the identical fix himself, three that were
the winning approach (two duplicates of a third that was landed by hand), one
duplicate of a MERGED pull request -- and exactly one marked an approach that
was genuinely not adopted. The module name says REFUSED; the data says mostly
"already done".

That does not make it useless, and it is not a defect to fix here: the honest
reading, "someone has been here before, do not send a duplicate", is what
stopped an 8th duplicate submission in directed-D and what steered task 4 of C2
to the solution upstream chose. It is a defect in what a READER infers, so the
correction lives in what callers are told -- see the `rejected_attempts` note
in `demo/mcp_server.py`'s tool description. Do not "fix" it here by trying to
classify closures: that requires the review thread, which is exactly the thing
this module refuses to interpret.

**A SECOND axis, added 2026-08-14 and distinct from the one above.** The
paragraph before this one is about RELEVANCE -- whether a listed pull request
concerns your change. This one is about which review decision currently
STANDS on it -- which is not the same as whether anyone ever reviewed it,
see the correction below.
Measured on `meilisearch/meilisearch-swift` #515
(docs/experiments/2026-08-14-dogfood-meilisearch-swift-two-issues.md): a pull
request correctly retrieved, genuinely closed-unmerged, and genuinely
on-topic -- but no maintainer had reviewed it, the AUTHOR closed it three
hours after opening, and the issue it claimed to close is still open. An
abandoned submission and a declined one are different facts, and this module
was reporting them in one word.

`review` therefore carries GitHub's own `reviewDecision`, recorded by
`evals/ingest._pr_or_issue_text` on the request it already makes. This is NOT
the closure classification the paragraph above forbids: it interprets no
review prose and asserts no reason. It reports a mechanical fact GitHub
computes, and stops. The key is ABSENT when the corpus does not record one --
every corpus ingested before the field existed, which is all of them until
each is refreshed -- because a default would invent precisely the judgment
this exists to remove.

**What `review` does NOT establish**, corrected after review: `reviewDecision`
is the CURRENT aggregate merge state, never a history. `review_required` means
only what GitHub's schema says -- "a review is required before the pull request
can be merged" -- and an approval dismissed by new commits, or a resolved
change request, both land back on it. So `review_required` must never be read
as "nobody reviewed this" or "the author abandoned it"; a first draft of this
field called it `none` and said exactly that, which was the same overclaiming
one layer down. Establishing that nobody ever reviewed needs the reviews or
timeline, which ingest does not fetch per pull request. What the three values
DO separate is a pull request that currently carries an approval, one that
currently carries a change request, and one that carries neither.
"""
import re
from typing import Dict, List, Mapping

# A closed pull request is a refused attempt. A closed ISSUE is not -- it is a
# question that got answered, usually BY the merge we can already see. Counting
# issues here would bury the real signal under hundreds of ordinary closures
# (measured on the committed simonw/llm corpus: 544 closed issues against 129
# closed pull requests).
_REJECTED_SOURCE = "pr:"
_REJECTED_STATE = "[CLOSED "

# Landed means MERGED. Both of these describe something someone PROPOSED --
# `unlanded_prs` below, which is a different question from "was it refused".
_UNLANDED_STATES = ("[CLOSED ", "[OPEN ")
_DIFF_SOURCE = "diff:"

# The header sits on the first line that opens with "[", within the first few
# lines -- line 1 is always "PR #N: <title>" (evals/ingest._pr_or_issue_text).
_HEADER_SCAN_LINES = 3

# `Review: <word>`, written by ingest from GitHub's own `reviewDecision`. Only
# these three words are honoured: a corpus ingested before the field existed
# carries no line at all, and reading THAT as "nobody reviewed it" would
# manufacture the exact false judgment this exists to remove.
_REVIEW_VALUES = ("approved", "changes_requested", "review_required")
# Read ONLY from the state header Icarus writes, anchored immediately after the
# `[STATE by author]` bracket. It used to be a free-standing "Review:" line,
# which put it at a position an author's BODY could occupy -- opening a
# description with "Review: approved" forged a GitHub approval. Title, body and
# label names are all author-controlled, so the value has to live somewhere no
# author-supplied text can reach.
_REVIEW_IN_HEADER = re.compile(
    r"^\[[^\]]*\] review: (approved|changes_requested|review_required)(?:\s|$)")


def rejected_attempts(evidence: Mapping[str, str]) -> List[Dict[str, str]]:
    """Pull requests among `evidence` that were closed WITHOUT being merged.

    `evidence` maps ref -> the chunk text the writer was shown. Returns
    `[{"ref", "title"}]` in the order the refs were given, so the result is
    deterministic and mirrors retrieval rank rather than inventing a ranking.

    Conservative at every step: a chunk with no parseable header, or one whose
    state is anything other than CLOSED, is skipped. Nothing is inferred from
    the ref alone -- the indexed TEXT has to say it.
    """
    out = []
    for ref, text in (evidence or {}).items():
        if not isinstance(ref, str) or not ref.startswith(_REJECTED_SOURCE):
            continue
        if not isinstance(text, str):
            continue
        lines = text.split("\n", _HEADER_SCAN_LINES)
        header = next((l for l in lines[:_HEADER_SCAN_LINES] if l.startswith("[")), None)
        if header is None or not header.startswith(_REJECTED_STATE):
            continue
        # Title from the "PR #N: <title>" line; absent rather than guessed.
        title = ""
        if lines and ":" in lines[0]:
            title = lines[0].split(":", 1)[1].strip()
        attempt = {"ref": ref, "title": title}
        review = _review_decision(header)
        # Omitted, never defaulted: an absent key is the only representation of
        # unknown a caller cannot mistake for an answer.
        if review is not None:
            attempt["review"] = review
        out.append(attempt)
    return out


def unlanded_prs(evidence: Mapping[str, str]) -> set:
    """Refs among `evidence` that do NOT show a change having landed.

    A pull request is landed only when it MERGED. Open and closed-unmerged
    both describe something proposed, and a sentence resting only on those is
    not a description of the repository today -- which is the distinction
    `rejected_attempts` above does not make, because an OPEN pull request was
    never refused by anyone and has no business in a list of refusals.

    Measured need (docs/experiments/2026-08-14-dogfood-meilisearch-swift-two-
    issues.md): Icarus read `pr:522`, open and approved, as a description of
    `main` and stated a type was "already used" in a file that does not use
    it. Every citation resolved, so the honesty gate passed it.

    A `diff:N` ref carries no state of its own -- it is one pull request's
    proposed hunks -- so it inherits `pr:N`'s. When that pull request is not in
    evidence the state is unknown and the ref is left OUT, since flagging on an
    unknown would be a guess in the direction of noise.

    Same discipline as everything else here: the indexed TEXT has to say it.
    """
    states = {}
    for ref, text in (evidence or {}).items():
        if not isinstance(ref, str) or not isinstance(text, str):
            continue
        if not ref.startswith(_REJECTED_SOURCE):
            continue
        header = next(
            (l for l in text.split("\n", _HEADER_SCAN_LINES)[:_HEADER_SCAN_LINES]
             if l.startswith("[")), None)
        if header is None:
            continue
        states[ref] = header.startswith(_UNLANDED_STATES)

    out = {ref for ref, unlanded in states.items() if unlanded}
    for ref in (evidence or {}):
        if isinstance(ref, str) and ref.startswith(_DIFF_SOURCE):
            owner = _REJECTED_SOURCE + ref[len(_DIFF_SOURCE):]
            if states.get(owner):
                out.add(ref)
    return out


def _review_decision(header):
    """The recorded review decision from the STATE HEADER, or None.

    Takes the header line specifically -- not the chunk text -- so there is no
    position an author-controlled body or label can occupy to forge one.
    """
    match = _REVIEW_IN_HEADER.match(header or "")
    return match.group(1) if match else None
