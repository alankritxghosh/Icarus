# evals/investigation.py
"""The state an investigation carries, and the deterministic rules over it.

An investigation is a bounded, evidence-first walk through a repository: form
hypotheses, gather evidence with the primitives, decide what each piece supports,
stop when more looking would not change the conclusion. This module holds the
STATE and every rule that must not be delegated to a model -- how strongly a
claim is supported, whether a step is worth running, when to stop. The loop
itself and the probes live beside it (see
docs/plans/2026-08-08-investigation-engine.md).

Three properties are deliberate:

**Confidence is computed, never generated.** `classify_support` reads the
evidence's own source kind and rationale markers straight out of `evals/gate.py`
-- the same `_states_reason` and `_source` the honesty gate uses for its (b)
guard. Asking a model how confident it is would produce a number that no longer
means what the gate means, and the whole product rests on those meaning the same
thing.

**State holds refs, never text.** A ref is stable and citable; chunk text is
large and belongs to the corpus, which can be refreshed underneath a
conversation. Every claim can be re-verified later by looking its refs up again.

**Budget is a hard ceiling, not advice.** `Budget.allows` is checked by the loop
before every round, and `should_stop` ends a run that has stopped learning --
measured on whether new REFS appeared, never on a model saying it is satisfied.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .gate import _source, _states_reason

# What KIND OF EVIDENCE a claim rests on. Read the boundary carefully, because
# it is the one AGENTS.md draws and the one this vocabulary must not cross.
#
# What is proven deterministically: the citations resolve to evidence that was
# actually retrieved, and (for `explicit`) at least one cited chunk is a
# rationale-bearing source whose text records SOME reason.
#
# What is NOT proven, and cannot be without a second model: that the recorded
# reason is the reason for THIS finding. Evidence reading "changed because
# logging was noisy" and a finding reading "changed to improve database
# scalability" are indistinguishable to marker matching. That linkage is the
# WRITER's reading, exactly as arbitrary semantic entailment is writer-reliant
# everywhere else in Icarus.
#
# So these classify the EVIDENCE, never the entailment, and `SUPPORT_HEADLINES`
# is the wording every surface must use so no UI upgrades a class into a claim
# that the repository asserts the finding.
SUPPORT_EXPLICIT = "explicit"        # cites evidence that records a reason
SUPPORT_STRONG = "strong"            # several independent kinds of evidence
SUPPORT_WEAK = "weak"                # one piece of evidence, or code alone
SUPPORT_UNSUPPORTED = "unsupported"  # nothing retrieved backs it

SUPPORT_ORDER = (SUPPORT_UNSUPPORTED, SUPPORT_WEAK, SUPPORT_STRONG, SUPPORT_EXPLICIT)

# The canonical wording for each class. Deliberately describes what was CITED,
# never what the repository asserts: "The repository states this" over a finding
# the repository does not state is a bluff groundedness cannot catch, because
# the citation underneath it is genuinely real. The Mac UI mirrors these strings
# and pins the same no-entailment property in its own tests.
SUPPORT_HEADLINES = {
    SUPPORT_EXPLICIT: "Cites evidence that records a reason",
    SUPPORT_STRONG: "Cites several independent kinds of evidence",
    SUPPORT_WEAK: "Cites one piece of evidence, or code alone",
    SUPPORT_UNSUPPORTED: "Not backed by evidence Icarus retrieved",
}

# Sources that can carry a WRITTEN reason: someone explaining a change in prose.
# Identical to gate._records_reason's list, and pinned to it by test.
_RATIONALE_SOURCES = ("pr", "issue", "doc", "commit")

HYPOTHESIS_OPEN = "open"
HYPOTHESIS_SUPPORTED = "supported"
HYPOTHESIS_PARTIAL = "partial"
HYPOTHESIS_REFUTED = "refuted"
HYPOTHESIS_UNSUPPORTED = "unsupported"

STOP_DECIDED = "every hypothesis decided, no contradiction left open"
STOP_EXHAUSTED = "nothing left to investigate"
STOP_BUDGET = "investigation budget spent"
STOP_DIMINISHING = "two rounds found no new evidence"


@dataclass(frozen=True)
class EvidenceRef:
    """One piece of evidence, reduced to what the state needs to reason about it.

    `states_reason` is computed ONCE, when the evidence is first read, from the
    gate's own marker list -- so a claim's support class never depends on when it
    happened to be evaluated.
    """

    ref: str
    source: str
    via: str                    # id of the step that surfaced it: the audit trail
    states_reason: bool = False

    @classmethod
    def of(cls, ref: str, text: str, via: str) -> "EvidenceRef":
        return cls(ref=ref, source=_source(ref) or "unknown", via=via,
                   states_reason=_states_reason(text))


@dataclass
class Claim:
    """One assertion an investigation is prepared to make, and its receipts."""

    id: str
    text: str
    citations: List[str] = field(default_factory=list)
    support: str = SUPPORT_UNSUPPORTED
    hypothesis_id: Optional[str] = None
    polarity: bool = True       # False = this claim tells AGAINST its hypothesis
    verified: bool = False      # the gate re-checked this claim on its own


@dataclass
class Hypothesis:
    id: str
    statement: str
    supporting: List[str] = field(default_factory=list)     # claim ids
    contradicting: List[str] = field(default_factory=list)
    status: str = HYPOTHESIS_OPEN


@dataclass(frozen=True)
class Step:
    """One planned use of a primitive. `id` is derived from the call itself, so
    the same investigation can never pay for the same lookup twice -- duplicate
    detection is identity, not a similarity judgement."""

    primitive: str
    args: Dict
    reason: str = ""

    @property
    def id(self) -> str:
        payload = json.dumps([self.primitive, self.args], sort_keys=True,
                             separators=(",", ":"))
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


@dataclass
class Budget:
    """Hard ceilings. Every one of these bounds something that costs real money
    or real seconds: a step is a subprocess or a search, a writer call is billed,
    evidence chars land in a prompt."""

    max_steps: int = 12
    max_writer_calls: int = 10
    max_rounds: int = 4
    max_evidence_chars: int = 120_000
    max_parallel: int = 4
    # Writer calls held back for the final synthesis. Without it, `conclude()`
    # spent an eleventh call on a ten-call budget -- the ceiling covered the
    # gathering half of a request and not the half a user always pays for.
    # Reserving beats refusing at the end: an investigation that gathered
    # evidence and then had no budget left to say anything would be a worse
    # product than one that gathered slightly less.
    synthesis_reserve: int = 1

    steps_spent: int = 0
    writer_calls_spent: int = 0
    rounds_spent: int = 0
    evidence_chars_spent: int = 0

    def allows_step(self) -> bool:
        return self.steps_spent < self.max_steps

    def allows_writer(self) -> bool:
        """Any writer call at all -- what `conclude()` asks before synthesising."""
        return self.writer_calls_spent < self.max_writer_calls

    def allows_gathering_writer(self) -> bool:
        """A planning or reading call, which must leave the synthesis slot free."""
        return self.writer_calls_spent < self.max_writer_calls - self.synthesis_reserve

    def allows_round(self) -> bool:
        return (self.rounds_spent < self.max_rounds
                and self.allows_step()
                and self.allows_gathering_writer()
                and self.evidence_chars_spent < self.max_evidence_chars)

    def remaining_evidence_chars(self) -> int:
        """How much evidence may still be RETAINED. Asked before a step's
        evidence enters the state or a prompt, never after: charging afterwards
        made this a counter rather than a bound, and one parallel round retained
        2,000 characters against a 1-character allowance."""
        return max(0, self.max_evidence_chars - self.evidence_chars_spent)

    def spend_step(self, chars: int = 0) -> None:
        self.steps_spent += 1
        self.evidence_chars_spent += max(0, chars)

    def spend_writer(self) -> None:
        self.writer_calls_spent += 1

    def spend_round(self) -> None:
        self.rounds_spent += 1

    def exhausted_reason(self) -> Optional[str]:
        """Which ceiling stopped this run, for disclosure in the answer. A
        budget-truncated investigation must never read as a complete one."""
        if self.rounds_spent >= self.max_rounds:
            return "reached the maximum number of investigation rounds"
        if not self.allows_step():
            return "reached the maximum number of investigation steps"
        if not self.allows_gathering_writer():
            return "reached the maximum number of reasoning calls"
        if self.evidence_chars_spent >= self.max_evidence_chars:
            return "reached the maximum amount of evidence it can hold"
        return None


def classify_support(citations, evidence: Dict[str, EvidenceRef]) -> str:
    """What KIND of evidence a claim rests on. NOT a claim about entailment.

    Deterministic and deliberately conservative:

    - EXPLICIT needs prose written to explain -- a pr/issue/doc/commit chunk
      whose text trips the gate's own rationale markers. It proves the cited
      evidence records A reason; it cannot prove that reason is the reason for
      this finding, which stays writer-reliant (see SUPPORT_HEADLINES).
    - STRONG needs at least two pieces of evidence of at least two different
      kinds. One PR quoted twice is one source's account of itself; a PR plus the
      code it changed is two independent things agreeing.
    - WEAK is everything else that has any evidence at all, including code alone
      -- code proves what happens, never why it was chosen.
    - UNSUPPORTED means the citations resolve to no evidence held. A claim in
      this class must never reach a reader as a claim.

    Unknown citations are ignored rather than counted, so a model naming a ref
    that was never retrieved can only ever LOWER the support class.
    """
    refs = [evidence[c] for c in dict.fromkeys(citations or ()) if c in evidence]
    if not refs:
        return SUPPORT_UNSUPPORTED
    if any(e.states_reason and e.source in _RATIONALE_SOURCES for e in refs):
        return SUPPORT_EXPLICIT
    if len(refs) >= 2 and len({e.source for e in refs}) >= 2:
        return SUPPORT_STRONG
    return SUPPORT_WEAK


def score_hypothesis(hypothesis: Hypothesis, claims: Dict[str, Claim]) -> str:
    """A hypothesis's status, from the claims attached to it. Never a model's
    verdict: a model that may declare its own hypothesis true will.

    A claim only counts once it is VERIFIED -- the gate re-checked it standing
    alone. Unverified claims are noise from a reading pass, not findings.
    """
    supporting = [claims[c] for c in hypothesis.supporting if c in claims]
    against = [claims[c] for c in hypothesis.contradicting if c in claims]
    supporting = [c for c in supporting if c.verified and c.support != SUPPORT_UNSUPPORTED]
    against = [c for c in against if c.verified and c.support != SUPPORT_UNSUPPORTED]

    if against and not supporting:
        return HYPOTHESIS_REFUTED
    if not supporting:
        return HYPOTHESIS_UNSUPPORTED
    best = max(SUPPORT_ORDER.index(c.support) for c in supporting)
    if against:
        # Evidence pulls both ways. That is a finding to REPORT, not a tie to
        # break -- resolving it silently is exactly how a contradiction becomes
        # a confident wrong answer.
        return HYPOTHESIS_PARTIAL
    if best >= SUPPORT_ORDER.index(SUPPORT_STRONG):
        return HYPOTHESIS_SUPPORTED
    return HYPOTHESIS_PARTIAL


@dataclass
class Investigation:
    """Everything one investigation knows. Answers, in order: what am I trying to
    determine, what do I know, where did it come from, what am I hypothesising,
    what is unresolved, what should I do next, and may I stop."""

    objective: str
    subject: List[str] = field(default_factory=list)        # refs "it" refers to
    question: str = ""
    hypotheses: List[Hypothesis] = field(default_factory=list)
    claims: List[Claim] = field(default_factory=list)
    evidence: Dict[str, EvidenceRef] = field(default_factory=dict)
    performed: List[Step] = field(default_factory=list)
    pending: List[Step] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    contradictions: List[Tuple[str, str, str]] = field(default_factory=list)
    budget: Budget = field(default_factory=Budget)
    stopped_because: Optional[str] = None
    _barren_rounds: int = 0

    # -- state updates (all deterministic) ---------------------------------
    def queue(self, step: Step) -> bool:
        """Queue a step unless this investigation already ran or queued it.
        Returns whether it was actually added, so a caller can report how much of
        a model's plan was redundant rather than silently discarding it."""
        known = {s.id for s in self.performed} | {s.id for s in self.pending}
        if step.id in known:
            return False
        self.pending.append(step)
        return True

    def take_round(self) -> List[Step]:
        """The next batch of steps to run concurrently, bounded by the budget."""
        room = min(self.budget.max_parallel,
                   self.budget.max_steps - self.budget.steps_spent)
        batch, self.pending = self.pending[:max(0, room)], self.pending[max(0, room):]
        return batch

    def absorb(self, evidence: Dict[str, EvidenceRef]) -> int:
        """Fold a step's evidence in. Returns how many refs were NEW -- the
        number the diminishing-returns stop is measured on."""
        new = 0
        for ref, item in evidence.items():
            if ref not in self.evidence:
                self.evidence[ref] = item
                new += 1
        return new

    def add_claim(self, claim: Claim) -> Claim:
        claim.support = classify_support(claim.citations, self.evidence)
        self.claims.append(claim)
        target = self.hypothesis(claim.hypothesis_id)
        if target is not None:
            (target.supporting if claim.polarity else target.contradicting).append(claim.id)
        return claim

    def hypothesis(self, hid) -> Optional[Hypothesis]:
        return next((h for h in self.hypotheses if h.id == hid), None)

    def rescore(self) -> None:
        by_id = {c.id: c for c in self.claims}
        for h in self.hypotheses:
            h.status = score_hypothesis(h, by_id)

    def note_round(self, new_refs: int) -> None:
        """Record a completed round. Two consecutive rounds that surfaced no new
        evidence mean the investigation has stopped learning, whatever the model
        thinks it might still try."""
        self.budget.spend_round()
        self._barren_rounds = 0 if new_refs else self._barren_rounds + 1

    def detect_contradictions(self) -> List[Tuple[str, str, str]]:
        """Pairs of verified claims that pull opposite ways on one hypothesis.

        Deliberately shallow: it detects that the REPOSITORY disagrees with
        itself about a hypothesis, which is a fact about the evidence. It does
        not attempt semantic contradiction between two arbitrary sentences --
        that is a model's judgement wearing a deterministic disguise.
        """
        by_id = {c.id: c for c in self.claims}
        found = []
        for h in self.hypotheses:
            fors = [c for c in (by_id.get(i) for i in h.supporting) if c and c.verified]
            againsts = [c for c in (by_id.get(i) for i in h.contradicting) if c and c.verified]
            for a in fors:
                for b in againsts:
                    found.append((a.id, b.id, h.statement))
        self.contradictions = found
        return found

    # -- stopping ----------------------------------------------------------
    def should_stop(self) -> Optional[str]:
        """Why this investigation should end, or None to keep going.

        Order matters: a hard ceiling is reported as a ceiling even if the run
        also happens to look finished, because a truncated investigation must
        never be presented as a complete one.
        """
        if not self.budget.allows_round():
            return STOP_BUDGET
        if self._barren_rounds >= 2:
            return STOP_DIMINISHING
        if not self.pending:
            # Nothing left to try. Report WHY it ended: if every hypothesis was
            # settled it is a finished investigation, otherwise it merely ran
            # out of moves, and those are different things to tell a reader.
            undecided = [h for h in self.hypotheses
                         if h.status in (HYPOTHESIS_OPEN, HYPOTHESIS_UNSUPPORTED)]
            if self.hypotheses and not undecided and not self.contradictions:
                return STOP_DECIDED
            return STOP_EXHAUSTED
        # With work still queued, "every hypothesis is decided" is NOT a reason
        # to stop. Measured live on the committed corpus: an investigation of
        # PR #1525 read the pull request, traced its linked issue, changed file
        # and follow-up pull requests -- and stopped before READING any of them,
        # because the PR body alone had already made its hypothesis look
        # supported. It scored 25% hop recall while reporting itself finished.
        #
        # A hypothesis supported by one source that has not yet met the evidence
        # which could refute it is a hypothesis nobody has tested. Only an empty
        # queue, a spent budget, or two rounds that found nothing new end a run;
        # each is a fact about the investigation rather than a belief formed
        # inside it.
        return None

    def summary(self) -> Dict:
        """What a caller renders: claims with their support class, what is still
        unknown, and the full step trail in the order it happened."""
        return {
            "objective": self.objective,
            "subject": list(self.subject),
            "hypotheses": [{"statement": h.statement, "status": h.status}
                           for h in self.hypotheses],
            "claims": [{"id": c.id, "text": c.text, "support": c.support,
                        "citations": list(c.citations), "verified": c.verified}
                       for c in self.claims if c.verified],
            "unknowns": list(self.unknowns),
            "contradictions": [{"claims": [a, b], "about": about}
                               for a, b, about in self.contradictions],
            "trail": [{"step": s.id, "primitive": s.primitive, "args": s.args,
                       "reason": s.reason} for s in self.performed],
            "stopped_because": self.stopped_because,
            "budget_note": self.budget.exhausted_reason(),
        }
