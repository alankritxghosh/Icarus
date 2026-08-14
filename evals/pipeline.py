"""The pipeline interface the harness calls, plus the Phase-1 stub baseline.

A "pipeline" takes a question and returns a Result: a verdict (answer or
abstain), the prose answer, the citations it actually used, and the candidate
evidence it retrieved. The harness in run.py grades that Result against the
labelled set; it never looks inside the pipeline.

The real brain (ingest -> chunk -> embed -> retrieve -> honesty gate ->
synthesize) is the *next* brick. This file only defines the contract and a
do-nothing stub, so we can stand up an honest red baseline first.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List

from .corpus import chunk_covers_lines

# Words that sit between the kind and its number in ordinary speech: "the PR OF
# 400", "the PR FOR 400", "PR NUMBER 400", "pr NO 400". Bounded to this closed
# list and to ONE of them, so the kind word stays adjacent to the number: a
# sentence mentioning a PR at one end and an unrelated number at the other
# ("the PR reworked retries ... we saw 400 errors") must not read as a
# reference to "PR 400". Found live 2026-08-09 on Tracer-Cloud/opensre, where
# "Why was the PR of 400 introduced" anchored NOTHING, fell through to ordinary
# search, and produced a confident, fully cited answer about an unrelated pull
# request -- groundedness cannot catch that, because the citation was real.
_REF_CONNECTOR = r"(?:\s+(?:of|for|number|no|num|#)\b)?"

# An explicit "issue #N" / "PR #N" / bare "#N" mention names a specific ref by
# identifier, not a concept -- BM25/semantic search treats the number as one
# ordinary keyword with no exact-match guarantee, and a chunk whose own text
# never happens to repeat that number can score 0 and never be retrieved at
# all, even though the exact ref exists in the corpus (a live-found bug).
_ISSUE_OR_PR_REF = re.compile(
    r"(?:\b(?:issue|pr|pull\s*request)s?" + _REF_CONNECTOR + r"\s*#?|#)\s*(\d+)\b",
    re.IGNORECASE,
)

# The KIND the question named, when it named one. GitHub shares a single number
# sequence between issues and pull requests, so issue:N and pr:N can both exist
# for the same N -- and the anchor used to resolve them with a fixed
# ("issue", "pr") order, so the issue silently won every tie no matter what was
# asked. "What did PR 1481 change?" anchored the ISSUE (found 2026-07-28 while
# root-causing a live report). Capturing the word lets the named kind win, and a
# bare "#N" that names no kind keeps the previous precedence unchanged.
_NAMED_REF_KIND = re.compile(
    r"\b(issues?|prs?|pull\s*requests?)" + _REF_CONNECTOR + r"\s*#?\s*(\d+)\b",
    re.IGNORECASE,
)


_KIND_WORD = {"issue": "an issue", "pr": "a pull request"}


def _premise_notes(question: str, anchor_refs):
    """Facts derived from which ref ACTUALLY resolved, when the question named a
    different kind for the same number.

    GitHub shares one number sequence between issues and pull requests, so a
    question can be wrong about its own subject: "What did PR 6952 change?" when
    #6952 is an issue. Before this, that produced an honest-but-misleading "no
    one wrote this down" -- the evidence was right there and simply disagreed
    with the question (found live 2026-07-28). Stating the mismatch as a fact
    lets the writer correct it and still cite, which is a GROUNDED answer, not a
    guess: the kind comes from the ref that resolved, never from the model.

    Returns [] when nothing was misnamed, so questions with no mismatch get a
    byte-identical prompt and no behaviour changes anywhere else.
    """
    notes = []
    for word, n in _NAMED_REF_KIND.findall(question or ""):
        asked = "issue" if word.lower().startswith("issue") else "pr"
        for ref in anchor_refs:
            src, _, num = ref.partition(":")
            if num == n and src in _KIND_WORD and src != asked:
                notes.append(f"#{n} is {_KIND_WORD[src]} ({ref}), not "
                             f"{_KIND_WORD[asked]}.")
    return notes


def _preferred_sources(question: str, number: str):
    """Source order to try for `number`, honouring the kind the question named."""
    for word, n in _NAMED_REF_KIND.findall(question or ""):
        if n != number:
            continue
        return ("issue", "pr") if word.lower().startswith("issue") else ("pr", "issue")
    return ("issue", "pr")  # no kind named -- unchanged precedence

# Same exact-identifier problem for a commit SHA, which is never indexed at all
# (see ingest.fetch_commit_detail). Hex-only English words are real ("defaced",
# "decade"), so a bare SHA must contain a digit; an explicit "commit " prefix
# lifts that requirement.
_COMMIT_SHA = re.compile(r"\b(commits?\s+)?([0-9a-fA-F]{7,40})\b")


@dataclass
class Result:
    """What every pipeline returns for one question.

    verdict:   "answer" or "unknown" (the honesty-gate decision).
    answer:    prose answer; empty when the verdict is "unknown".
    citations: refs the answer actually rests on, normalized as "source:ref"
               (e.g. "pr:1435"). Must be a subset of `retrieved`.
    retrieved: candidate evidence refs the retriever surfaced, same "source:ref"
               form, best-first. Used for retrieval recall@k.
    anchored:  the subset of `retrieved` resolved by EXACT LOOKUP rather than by
               search -- because the question named it ("PR 6952") or, in
               .explain(), because the user selected those lines. Always a
               prefix of `retrieved`, and usually empty.
    """

    verdict: str
    answer: str = ""
    citations: List[str] = field(default_factory=list)
    retrieved: List[str] = field(default_factory=list)
    # evidence: {cited ref -> the chunk text the writer actually saw}, for CITED
    # refs only. Lets a caller show the proof itself rather than a pointer to it.
    # Never an input to the honesty gate -- purely what was already used.
    evidence: Dict[str, str] = field(default_factory=dict)
    # anchored: which refs were looked up because the caller NAMED them, split
    # out from the ones search merely suggested. Both already sat in `retrieved`
    # (anchor-first), but a flat list makes a correctly-anchored abstention look
    # identical to one that ignored the question and searched blindly -- reported
    # live 2026-07-28. Display only: nothing here feeds the writer or the gate.
    anchored: List[str] = field(default_factory=list)
    # WHY the gate abstained, when it did (evals/gate.py's ABSTAIN_* constants);
    # None on an answer. "Unknown" alone collapses several very different
    # situations -- nobody recorded it, versus the thing asked about not
    # existing here -- and the unknowns map cannot tell a team's real
    # documentation debt from a typo without this.
    abstention_reason: str = None
    # claims: the writer's per-sentence self-report of which refs each sentence
    # restates, validated against `retrieved` (evals/gate.attribute_claims).
    # Empty unless the caller asked for it with `per_claim=True`. ADVISORY: it
    # says whether a sentence quotes one chunk or merges several, which is the
    # one distinction that separated the accurate answers from the fabricated
    # one across four measured tasks -- and which provably cannot be recovered
    # after the fact (docs/experiments/2026-08-10-quotation-vs-composition-
    # negative-result.md). Never feeds the gate; a verdict is identical with it
    # on or off.
    claims: List[Dict] = field(default_factory=list)
    # rejected_attempts: pull requests among the evidence the writer saw that
    # were CLOSED WITHOUT MERGING (evals/attempts.py). A merged PR leaves a
    # commit; a refused one leaves nothing, so `git log`, `git blame` and the
    # working tree cannot show it -- measured twice as the decisive fact an
    # agent could not otherwise reach (docs/experiments/2026-08-10-agent-mode-
    # exp-d*.md). Deterministic, derived from indexed text, so it cannot be
    # bluffed; never feeds the gate.
    rejected_attempts: List[Dict] = field(default_factory=list)


class Pipeline:
    """Interface: implementations answer one question at a time."""

    def answer(self, question: str, token: str = None) -> Result:  # pragma: no cover - interface
        raise NotImplementedError

    def indexed_chunks(self) -> List:
        """The loaded corpus, for a caller that wants to DESCRIBE what was
        indexed (demo/repo_map.py) rather than query it.

        Read-only and outside the honesty path entirely -- it hands back what
        is already in memory and can never widen what an answer may cite. The
        base returns nothing, so a pipeline holding no corpus says so honestly
        instead of raising."""
        return []


class StubPipeline(Pipeline):
    """The honest red baseline: a brain that knows nothing.

    It always abstains and retrieves nothing. This deliberately PASSES the two
    non-negotiable honesty gates (it never bluffs, so groundedness and
    abstention-recall are trivially 100%) while FAILING every quality metric
    (it retrieves and cites nothing). That failing-on-quality, holding-on-honesty
    board is exactly the baseline the real pipeline must turn green -- without
    ever letting a gate drop. See docs/EVALUATION.md.
    """

    def answer(self, question: str, token: str = None) -> Result:
        return Result(verdict="unknown")


class RetrievalPipeline(Pipeline):
    """Retrieves candidate evidence but does not yet answer.

    Populates `retrieved` so retrieval recall@k can rise, while still abstaining
    (verdict 'unknown', no citations) so groundedness and abstention recall stay
    trivially at 100%. The honesty gate and the writer are the next brick.
    """

    def __init__(self, retriever, top_n: int = 20):
        self._retriever = retriever
        self._top_n = top_n

    def answer(self, question: str, token: str = None) -> Result:
        return Result(verdict="unknown", retrieved=self._retriever.search(question, self._top_n))


class GatedPipeline(Pipeline):
    """Retrieve -> writer (provider) -> deterministic honesty gate -> Result.

    The writer is constrained to answer only from retrieved evidence or abstain;
    the gate (evals/gate.py) enforces that deterministically, failing safe to
    'unknown'. `retrieved` is always the full top-recall_n list so retrieval
    recall@k stays measurable regardless of the verdict.
    """

    # Brick D's default writer prompt when a GitHub selection carries no typed
    # question (the common case: select a line, click "Ask Icarus").
    # NOT compound. "What does this code do, and why is it here?" shipped until
    # 2026-08-06 and measurably abstained on plain utility code that the SAME
    # pipeline explained correctly when asked only the first half: the writer's
    # contract is answer-everything-or-unknown, with no partial path, so an
    # unrecorded "why" dragged an answerable "what" down with it. The "why" is
    # not lost -- a user who wants it types it, and then an honest unknown is
    # the correct answer rather than a side effect.
    _DEFAULT_EXPLAIN_QUESTION = ("What does this code do, and how is it used in "
                                 "this codebase?")

    def __init__(self, retriever, chunks, provider, recall_n: int = 20, writer_k: int = 10,
                 live_fetch=None, live_commit_fetch=None):
        self._retriever = retriever
        self._by_ref = {c.ref: c for c in chunks}
        self._provider = provider
        self._recall_n = recall_n
        self._writer_k = writer_k
        # Built once per pipeline, not per ask: it is derived purely from the
        # corpus, which cannot change under a live pipeline (a refresh builds a
        # new one). None for an empty corpus -- see index_facts.build_index_chunk.
        self._index = None
        self._index_built = False
        # Optional `live_fetch(number:int, token:str|None) -> Optional[Chunk]`:
        # resolves an explicit "PR/issue #N" the corpus never indexed (it caps at
        # the most-recent PR_LIMIT/ISSUE_LIMIT) by fetching that one ref + its
        # discussion on demand. `token` is the CALLER's, per call -- without it a
        # private repo's fetch fails safe to None, which is why the Company Brain
        # saw none of this until the token was threaded through (2026-07-28).
        # None (the eval board / tests) keeps the pipeline fully offline and
        # reproducible; serving binds the real gh-backed fetch (demo/library.py).
        self._live_fetch = live_fetch
        # Optional `live_commit_fetch(sha:str, token:str|None) -> Optional[Chunk]`:
        # resolves an explicit commit SHA, which is NEVER indexed (commits are
        # excluded from ingest by design). Same fail-safe contract as live_fetch.
        self._live_commit_fetch = live_commit_fetch

    def indexed_chunks(self) -> List:
        return list(self._by_ref.values())

    # --- read-only accessors for the investigation layer -------------------
    # evals/probes.py needs the same retrieval and the same chunk store .answer()
    # uses, and reaching into privates from another module would make every
    # future change to this class a guess about who else is holding it. These
    # three add no logic and no honesty surface: they hand back what is already
    # in memory, exactly as indexed_chunks() does.
    def chunk_for(self, ref: str):
        """The indexed chunk with this ref, or None. Never fetches."""
        return self._by_ref.get(ref)

    def search_refs(self, query: str, k: int) -> List[str]:
        """The retriever's own ranking -- the identical hybrid + normalized path
        /ask uses, so an investigation can never retrieve differently from it."""
        return self._retriever.search(query, k)

    def fetchers(self):
        """(live_fetch, live_commit_fetch) -- both may be None offline."""
        return self._live_fetch, self._live_commit_fetch

    def provider(self):
        """The writer this pipeline was built with.

        An investigation must use the SAME provider, because that provider went
        through the trust interlock (evals/trust.py) when the pipeline was built.
        Constructing a second one for the investigation path would be a second
        place the interlock has to be remembered -- and the one that gets
        forgotten is always the one that touches private code."""
        return self._provider

    def answer(self, question: str, token: str = None, audience: str = None,
               per_claim: bool = False) -> Result:
        # `per_claim` (2026-08-10) asks the writer to also report which refs each
        # sentence restates (evals/synth._PER_CLAIM_RULE). Default False keeps the
        # prompt byte-identical, so /ask and the eval board are untouched.
        #
        # `audience` (2026-08-06): None/"developer" is byte-identical to before
        # this parameter existed (see synth.build_prompt). "plain" asks the
        # writer for prose a non-technical reader can follow -- same evidence,
        # same honesty gate, same JSON contract, only the sentence changes.
        #
        # `token`, when given, is the CALLER's own GitHub token, used only to
        # live-fetch an exact ref they named. It is passed straight through to
        # the fetcher for the duration of this call and never stored on the
        # pipeline -- a private repo's live fetch is impossible without it (the
        # server's own gh identity cannot read private code), and holding it
        # would widen the credential surface for every later request.
        # An explicit "issue/PR #N" mention gets a guaranteed anchor lookup
        # against self._by_ref (bypassing .search()/query normalization
        # entirely, same as .explain()'s anchor resolution already does) --
        # a numeric identifier is an exact-match problem, not a similarity
        # one. Anchor first, then ordinary search results, de-duplicated;
        # mirrors .explain()'s own anchor-then-neighbors merge exactly.
        anchor_refs = []
        fetched = {}
        for n in _ISSUE_OR_PR_REF.findall(question):
            sources = _preferred_sources(question, n)
            hit = next((f"{s}:{n}" for s in sources if f"{s}:{n}" in self._by_ref), None)
            if hit is not None:
                anchor_refs.append(hit)                 # indexed -> use the cached chunk
            elif self._live_fetch is not None:
                # Not in the indexed slice: fetch that exact PR/issue live. Fail-safe
                # -- a None result just leaves it unanchored, as if unmentioned.
                ch = self._live_fetch(int(n), token)
                if ch is not None and ch.ref not in fetched:
                    fetched[ch.ref] = ch
                    anchor_refs.append(ch.ref)
        if self._live_commit_fetch is not None:
            for prefix, sha in _COMMIT_SHA.findall(question):
                if not prefix and not any(c.isdigit() for c in sha):
                    continue  # hex-shaped English word, not a SHA
                ch = self._live_commit_fetch(sha, token)
                if ch is not None and ch.ref not in fetched:
                    fetched[ch.ref] = ch
                    anchor_refs.append(ch.ref)
        searched = self._retriever.search(question, self._recall_n)
        retrieved = list(dict.fromkeys(anchor_refs + searched))
        lookup = {**self._by_ref, **fetched} if fetched else self._by_ref
        top = [lookup[r] for r in retrieved[: self._writer_k] if r in lookup]
        return self._answer_from(question, top, retrieved, audience=audience,
                                 notes=_premise_notes(question, anchor_refs),
                                 anchored=anchor_refs, per_claim=per_claim)

    def explain(self, path: str, start: int, end: int, question: str = None,
                neighbors: bool = True, per_claim: bool = False) -> Result:
        """Brick D: explain a GitHub line selection, not a free-text question.

        Resolves evidence by LOCATION -- the chunk(s) covering [start, end] in
        `path` (evals/corpus.chunk_covers_lines) -- rather than by `.search()`,
        since a line selection isn't a query. Adds semantic neighbors for
        surrounding context, same as a real /ask: when the caller supplied a
        `question`, neighbors are searched using THAT question -- proven live
        against the real corpus to reproduce .answer()'s exact top-k for the
        identical question (an earlier version always searched on the anchor's
        own code text, which measurably found WORSE neighbors than searching
        the actual question and caused real, reproducible under-answering: the
        writer honestly abstained on a question /ask answers confidently, not
        because evidence didn't exist, but because explain() fed it worse
        evidence). With no question (the common "just click Explain" case),
        there is no natural-language query to search with, so the anchor's own
        text is the best available signal. Then goes through the IDENTICAL
        writer -> gate() path as .answer() via `_answer_from` -- no new
        honesty logic, no special-cased error path. No coverage at all for
        this location -> the gate's ordinary "no top chunks" abstention (an
        honest unknown), exactly like an unanswerable question today.

        `neighbors=False` answers from the addressed location ALONE, skipping
        the neighbour search entirely. Found live 2026-07-30: the onboarding
        tour addressed a repo's own CONTRIBUTING.md, the anchor resolved and
        ranked FIRST, and the writer cited a neighbouring commit message
        instead -- reporting another project's conventions, quoted inside our
        own commit, as this repository's. Addressing a document guarantees it
        is PRESENT, not that it is USED, and neighbours that merely discuss the
        topic can outrank the document that answers it.

        Narrowing evidence is fail-safe: fewer chunks can only produce MORE
        abstention, never more fabrication, so this cannot weaken the gate.
        Neighbours stay ON by default -- a code selection genuinely wants its
        surrounding context, which is what `.explain()` was built for.
        """
        anchor = [c for c in self._by_ref.values() if chunk_covers_lines(c, path, start, end)]
        if neighbors:
            neighbor_query = question or (anchor[0].text if anchor else path)
            neighbor_refs = self._retriever.search(neighbor_query, self._recall_n)
        else:
            neighbor_refs = []

        anchor_refs = [c.ref for c in anchor]
        # Anchor first (most relevant), then neighbors, de-duplicated (the
        # anchor's own text search can find itself) -- one ordered de-dup
        # drives both `top` (Chunk objects, capped at writer_k by the caller)
        # and `retrieved` (refs, for recall@k), so they can never disagree.
        ordered_refs = list(dict.fromkeys(anchor_refs + neighbor_refs))
        top = [self._by_ref[r] for r in ordered_refs if r in self._by_ref]
        retrieved = ordered_refs

        return self._answer_from(
            question or self._DEFAULT_EXPLAIN_QUESTION, top[: self._writer_k], retrieved,
            guard_rationale=False,   # explain delivers the selected code's "what"
            anchored=anchor_refs,    # the chunks covering the user's own selection
            selection=anchor_refs,   # ...and the writer is TOLD which those are
            # `neighbors=False` means "answer from the addressed location ALONE"
            # -- the guarantee the onboarding tour's README step rests on, after
            # a live bug where a neighbouring commit was cited instead. The index
            # is context like any other, so it is withheld there too.
            index_evidence=neighbors,
            index_standalone=False,  # a location that resolved to nothing stays unknown
            per_claim=per_claim,
        )

    def _index_chunk(self):
        """Icarus's own index as one evidence chunk, memoised. Lazy so a
        pipeline that is built but never asked pays nothing."""
        if not self._index_built:
            from .index_facts import build_index_chunk
            self._index = build_index_chunk(list(self._by_ref.values()))
            self._index_built = True
        return self._index

    def _answer_from(self, question: str, top: List, retrieved: List[str],
                     guard_rationale: bool = True, notes=None, anchored=None,
                     selection=None, index_evidence: bool = True,
                     index_standalone: bool = True, audience: str = None,
                     per_claim: bool = False) -> Result:
        """The shared writer -> gate() core both .answer() and .explain() go
        through -- one honesty path, two ways of assembling the evidence
        (search vs. location resolution) that feed it.

        `guard_rationale` toggles the gate's (b) why->what check. It is ON for
        .answer() (a user asking a pointed "why?" deserves an honest abstain when
        the reason isn't recorded) and OFF for .explain(): there the user has
        SELECTED specific code and a "what does this do" answer is the intended
        deliverable, not a dodged why -- so requiring rationale prose would wrongly
        abstain on plain code. Groundedness (the hard invariant) is enforced
        identically either way; only the soft rationale heuristic is scoped.

        `anchored` is carried through untouched for display (see Result). It is
        set on BOTH exits -- an abstention is exactly the case where a reader
        needs to see that the thing they named was in fact looked up.

        `selection` is DIFFERENT from `anchored` and deliberately not merged with
        it. Both are exact-lookup refs, but only `selection` is shown to the
        writer as "this is the subject". .answer() sets `anchored` whenever a
        question names a PR/commit, so merging them would change every /ask
        prompt the eval board was measured on -- a silent re-baselining of every
        number in the repo. Only .explain() passes `selection`, because only
        there did the USER point at specific lines."""
        from .synth import build_prompt   # local imports avoid a circular import
        from .gate import gate, attribute_claims, extract_json
        from .attempts import rejected_attempts, unlanded_prs
        anchored = list(dict.fromkeys(anchored or ()))
        # Icarus's own index, offered as ordinary evidence (evals/index_facts).
        #
        # APPENDED, never prepended: retrieved[:k] drives recall@k on every eval
        # number in this repo, so putting it first would push a real ref out of
        # the top-k window and silently re-baseline the board while looking like
        # an improvement. Appending leaves the first k refs exactly as the
        # retriever ranked them.
        #
        # `index_standalone` decides whether it may be the ONLY evidence:
        #   .answer()  -- yes. "what languages is this in?" matches no chunk
        #                 lexically, so retrieval legitimately returns nothing
        #                 and the index IS the answer. Withholding it here was
        #                 the whole bug (found live on muxinc/media-chrome).
        #   .explain() -- no. A line selection that resolves to no chunk means
        #                 "that location isn't in the index"; answering it with
        #                 a repo-wide file listing would be a non sequitur
        #                 dressed as an answer. It stays an honest unknown.
        index_chunk = self._index_chunk() if index_evidence else None
        if index_chunk is not None and index_chunk.ref not in retrieved \
                and (top or index_standalone):
            top = list(top) + [index_chunk]
            retrieved = list(retrieved) + [index_chunk.ref]
        if not top:
            from .gate import ABSTAIN_NO_EVIDENCE
            return Result(verdict="unknown", retrieved=retrieved, anchored=anchored,
                          abstention_reason=ABSTAIN_NO_EVIDENCE)
        # Pass the question + the evidence text the writer actually saw so the
        # gate can enforce the (b) rationale-support guard, not just groundedness.
        evidence = {c.ref: c.text for c in top}
        raw = self._provider.complete(
            build_prompt(question, top, notes=notes, selection=selection,
                         audience=audience, per_claim=per_claim))
        result = gate(raw, retrieved,
                      question=question if guard_rationale else None, evidence=evidence)
        result.retrieved = retrieved
        result.anchored = anchored
        # Carry the text of the CITED evidence back out, so a caller can show the
        # proof instead of a pointer to it. Cited-only, and read from the same map
        # the writer and gate saw -- it cannot surface anything that wasn't already
        # grounded, so this adds no new honesty surface.
        result.evidence = {ref: evidence[ref] for ref in result.citations if ref in evidence}
        # Parsed a second time rather than threading the decode out of gate():
        # keeping gate()'s signature and return untouched is worth one cheap
        # re-parse, since every honesty number in the repo is measured through it.
        if per_claim:
            result.claims = attribute_claims(extract_json(raw), retrieved)
        # Computed from the FULL set of chunks the writer saw, not just the
        # cited ones: a refused attempt is worth surfacing even when the answer
        # did not rest on it -- that is precisely the case where an agent is
        # about to redo it. Set on the abstention path too, for the same reason.
        result.rejected_attempts = rejected_attempts(evidence)
        # A claim whose every citation is a REFUSED pull request is not a
        # statement of how the system behaves -- it restates something somebody
        # proposed and had rejected. Found 2026-08-11 re-running Experiment A's
        # fabrication (docs/experiments/2026-08-11-fabrication-recheck-per-claim.md):
        # the fabricated sentence cited `pr:17122` ALONE, so it was labelled
        # `quoted` -- the label the agent is told to trust -- while that PR sits
        # in this same result's `rejected_attempts`.
        #
        # A separate field, not a fourth label: `label` is about HOW MANY chunks
        # a sentence rests on, this is about WHAT KIND they are, and collapsing
        # two axes into one enum would make `quoted` mean two different things.
        # Set only when true, so every existing payload is byte-identical.
        #
        # The test is "nothing cited shows the change ever LANDED", not the
        # original "every citation is a refused PR". Both real cases from
        # Experiment C2 decided this (docs/experiments/2026-08-11-agent-mode-
        # exp-c2-results.md):
        #   - MISSED by the old rule: "the accepted fix is..." citing a refused
        #     PR plus the ISSUE that reported the bug. An issue reports a
        #     problem; it never records an adoption, so it cannot rescue the
        #     claim -- yet its presence alone switched the flag off.
        #   - Must STAY silent: a claim citing a refused PR alongside a MERGED
        #     one. The merged PR is proof the approach landed, so flagging it
        #     would be noise. This is what rules out the obvious alternative
        #     fix of marking whenever ANY citation is refused.
        # Anything that is not a refused PR or an issue -- a merged PR, a
        # commit, code, a doc -- is evidence of something that exists, and is
        # deliberately treated as solid ground.
        #
        # Widened 2026-08-14 from closed-unmerged to UNLANDED, and renamed with
        # it. The rule the comment above always described -- "nothing cited
        # shows the change ever LANDED" -- was implemented against
        # `rejected_attempts`, which is closed-only, so an OPEN pull request
        # slipped through the exact same hole: Icarus read `pr:522`, open and
        # approved, as a description of `main` and said a type was "already
        # used" in a file that does not use it (docs/experiments/
        # 2026-08-14-dogfood-meilisearch-swift-two-issues.md). An open PR is
        # not a refusal, so it must NOT join `rejected_attempts` -- hence a
        # separate predicate rather than a wider list. The name moved from
        # `rests_on_rejected` because calling an approved open pull request
        # "rejected" is the same overclaiming this whole flag exists to catch.
        #
        # Widened again 2026-08-14: the "at least one unlanded pull request"
        # anchor is gone, so a claim resting ONLY on issues is marked too. The
        # principle was already written above -- an issue reports a problem, it
        # never records an adoption -- but it was applied only when a pull
        # request happened to be cited alongside, leaving issues-alone as the
        # one arrangement nothing checked. That is the arrangement the measured
        # case used: "adding indexSize/usedIndexSize has been attempted before"
        # citing `issue:531`, the issue REQUESTING those fields, i.e. the issue
        # restating its own existence read as evidence of a prior attempt. The
        # live re-measurement is in the same experiment record.
        #
        # Measured before widening rather than argued: over 10 real questions
        # on meilisearch-swift, 3 of 8 claims were issue-only, and all three
        # were true positives (two describing a Core module that is proposed
        # and not built, one answering "has this been added" with the issue
        # asking for it). A claim citing code or a MERGED pull request
        # alongside an issue still does not fire, which is what keeps this from
        # marking ordinary grounded answers.
        unlanded = unlanded_prs(evidence)
        for claim in result.claims:
            cits = claim.get("citations") or []
            if not cits:
                continue
            if all(ref in unlanded or ref.startswith("issue:") for ref in cits):
                claim["rests_on_unlanded"] = True
        return result
