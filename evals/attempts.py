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


# A MERGED pull request saying it replaces another one. Author-written BODY
# text, unlike `_REVIEW_IN_HEADER` above -- so it is honoured ONLY from a pull
# request whose own state header says MERGED. Writing this sentence into a body
# is free; getting that body merged needs write access, and anyone with write
# access has stronger ways to hide a refusal than editing prose. Disclosed
# rather than defended further.
#
# Direction is deliberate: the SUCCESSOR names the PR it replaces. The reverse
# ("superseded by #N" in the closed PR's own text) is not read, because the
# measured case cannot produce it -- pr:23 was auto-closed by GitHub AFTER it
# was written, so nothing was ever added to it.
_SUPERSEDES = re.compile(r"\b(?:replaces|supersedes)\s+#(\d+)\b", re.I)
_MERGED_STATE = "[MERGED "

# How many nearest successors to name. Three, because the point is to give a
# reader somewhere to look, not to enumerate the repository's history.
_LATER_MERGED_SHOWN = 3


def _superseded_numbers(evidence: Mapping[str, str]) -> set:
    """PR numbers that some MERGED pull request in `evidence` says it replaces.

    One pass over the evidence, so this stays linear in the number of chunks.
    """
    out = set()
    for ref, text in (evidence or {}).items():
        if not isinstance(ref, str) or not ref.startswith(_REJECTED_SOURCE):
            continue
        if not isinstance(text, str):
            continue
        lines = text.split("\n", _HEADER_SCAN_LINES)
        header = next((l for l in lines[:_HEADER_SCAN_LINES] if l.startswith("[")), None)
        if header is None or not header.startswith(_MERGED_STATE):
            continue
        out.update(_SUPERSEDES.findall(text))
    return out


def rejected_attempts(evidence: Mapping[str, str]) -> List[Dict[str, str]]:
    """Pull requests among `evidence` that were closed WITHOUT being merged.

    `evidence` maps ref -> the chunk text the writer was shown. Returns
    `[{"ref", "title"}]` in the order the refs were given, so the result is
    deterministic and mirrors retrieval rank rather than inventing a ranking.

    Conservative at every step: a chunk with no parseable header, or one whose
    state is anything other than CLOSED, is skipped. Nothing is inferred from
    the ref alone -- the indexed TEXT has to say it.

    **A closed pull request that a MERGED one says it REPLACES is not reported**
    (added 2026-08-24). Measured live on `SaravananJaichandar/world-model-mcp`:
    `pr:23` was auto-closed by GitHub when its base branch `#22` merged and was
    deleted, and the identical work landed as `pr:24`, whose body says "Replaces
    #23". The same payload therefore told a reader "replaced and shipped" in
    prose and "tried and refused" in this field, and a client renders the field.
    See docs/experiments/2026-08-24-agent-mode-matched-pair-results.md.

    This does NOT start judging why a pull request closed -- the line this module
    refuses to cross. It reads one sentence a DIFFERENT, merged pull request
    wrote about itself, which is still "the indexed TEXT has to say it". When no
    such successor is in evidence nothing is inferred and the attempt is reported
    exactly as before, because absence of a successor is not evidence of refusal.

    `unlanded_prs` below is deliberately UNCHANGED by this: `pr:23` genuinely
    never landed, so a claim resting on it still carries `rests_on_unlanded`.
    The two questions are different and only one of them was wrong.
    """
    superseded = _superseded_numbers(evidence)
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
        if ref.split(":", 1)[1] in superseded:
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


# Text that indexes a claim to the MOMENT IT WAS WRITTEN. Not "this is false"
# -- when written each of these was true. The defect is that a later reader,
# and a writer summarising for one, has no way to see that time has passed.
#
# Measured (docs/experiments/2026-08-25-agent-mode-three-trial-variance.md):
# instability in `get_task_context` tracks evidence recording SUCCESSIVE STATES
# of one feature. On `world-model-mcp`, `pr:22` carries a literal section
# "## Consumer wiring -- deferred" saying the work "land[s] in follow-up
# patches"; `pr:24` then merged it. Asked about that area, the writer produced
# "the retrieval consumers do NOT CURRENTLY have wiring" -- support `explicit`,
# citing `pr:22`, which resolves perfectly -- in 3 of 4 draws.
_DEFERRAL = re.compile(
    r"\b(deferred|defers|deferring|follow[- ]?up patch(?:es)?|"
    r"not yet implemented|not yet wired|in a future (?:patch|release|version)|"
    r"lands? in v?\d)\b", re.I)


def deferred_claims(evidence: Mapping[str, str]) -> Dict[str, Dict]:
    """Refs that DEFER something, where later merged work is also in evidence.

    Returns `{ref: {"phrase": <the literal matched text>, "later_merged":
    [refs]}}`.

    Conservative in the same way as everything else here, and the conservatism is
    the design: a deferral is reported ONLY when the evidence also holds a
    LATER-numbered MERGED pull request. Without one there is no reason to think
    time has moved, and flagging every "not yet" would bury the signal in a repo
    that says it constantly.

    **It reports that the claim is TIME-INDEXED and that later work exists. It
    never claims the deferral was resolved.** Deciding that `pr:24` delivered
    what `pr:22` deferred needs the semantic judgment this module refuses to
    make -- the same line `rejected_attempts` draws by reporting WHAT was closed
    and never WHY. A caller is told to go and look.

    `later_merged_count` is the honest strength indicator: 1-3 successors and the
    resolver is probably among them; hundreds and the deferral is ancient, the
    flag is near-meaningless, and the reader is told so rather than left to infer
    a link from a long list. Measured over the committed 526-PR corpus, exactly 3
    refs fire at all -- 0.6% -- so this is a narrow signal, not a klaxon.

    Pull request NUMBERS order this, not dates: ingest writes no date into a
    `pr:` header, and GitHub numbers are monotonic per repository, so "later" is
    decidable from the ref alone. Non-numeric refs are skipped rather than
    guessed at.
    """
    def _number(ref):
        tail = ref.split(":", 1)[1] if ":" in ref else ""
        return int(tail) if tail.isdigit() else None

    merged_later = []
    deferrals = {}
    for ref, text in (evidence or {}).items():
        if not isinstance(ref, str) or not ref.startswith(_REJECTED_SOURCE):
            continue
        if not isinstance(text, str):
            continue
        n = _number(ref)
        if n is None:
            continue
        lines = text.split("\n", _HEADER_SCAN_LINES)
        header = next((l for l in lines[:_HEADER_SCAN_LINES] if l.startswith("[")), None)
        if header is None:
            continue
        if header.startswith(_MERGED_STATE):
            merged_later.append((n, ref))
        found = _DEFERRAL.search(text)
        if found:
            deferrals[ref] = (n, found.group(0))

    out = {}
    for ref, (n, phrase) in deferrals.items():
        later = sorted(((m, r) for m, r in merged_later if m > n), key=lambda x: x[0])
        if later:
            # NEAREST first, and bounded. Found by running this over the whole
            # committed corpus: `pr:14`'s deferral listed essentially every
            # later merged pull request in the repository -- each one true, the
            # set worthless. The nearest successors are the plausible resolvers;
            # the COUNT is what tells a reader how much time passed, and it is
            # the honest measure of how weak the signal is. A deferral with 400
            # merged pull requests after it is ancient, and this says so instead
            # of implying a link.
            out[ref] = {"phrase": phrase,
                        "later_merged": [r for _, r in later[:_LATER_MERGED_SHOWN]],
                        "later_merged_count": len(later)}
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

_PAST_STATE_SOURCES = ("commit:",)


def past_state_only(evidence) -> set:
    """Refs among `evidence` that record a change AT A POINT IN TIME.

    A commit is evidence something happened once. It is never evidence that it
    is still true: the next commit may undo it, and the indexed message says
    nothing either way.

    Measured 2026-08-21 on firecrawl/firecrawl #4375, Agent Mode's first WRONG
    answer. Asked whether swallowing search failures was deliberate, the answer
    said it was not -- "developers have actively worked to surface these
    failures" -- citing commit 229141a (2026-06-18). Commit 2fc41237 removed
    that work the following day and HEAD holds none of it. The commit is real,
    the citation resolves, the honesty gate passed it correctly, and the answer
    was the opposite of what the repository had decided.

    Deliberately NOT a revert detector. Proving a commit was undone needs its
    diff matched against HEAD, and that misreads any line that was moved,
    renamed or reformatted -- a false "this was reverted" is worse than the
    weaker statement, which is never wrong: nothing cited establishes that this
    is still true today.

    Issues and pull requests are left alone. `unlanded_prs` above already
    covers them, and two overlapping warnings on one sentence make both easier
    to ignore.
    """
    return {
        ref for ref in (evidence or {})
        if isinstance(ref, str) and ref.startswith(_PAST_STATE_SOURCES)
    }


def _claim_rests_on_past_state(citations, past_state) -> bool:
    """Does this sentence rest ONLY on point-in-time records?

    One citation to code -- the repository as indexed, i.e. today -- anchors the
    sentence to the present and the flag stays off. An uncited sentence never
    fires: there is nothing to be wrong about.
    """
    cits = [c for c in (citations or []) if isinstance(c, str)]
    if not cits:
        return False
    return all(c in past_state for c in cits)

