# demo/investigations.py
"""What one caller's investigation remembers between turns.

A conversation about a change is a sequence of questions about the SAME thing:

    "talk to me about PR #400"   -> the subject is bound
    "why did it change?"         -> "it" is that subject
    "what did it affect?"        -> still that subject
    "why do you think they did it this way?"

Nothing in Icarus could carry that. `/ask` is stateless by design, `demo/ledger.py`
records questions against the repo with NO identity, and `demo/visits.py` records
identity with NO questions -- and those two must never be joined, which is why
this is a third store rather than a column on either.

## What is kept, and what is deliberately recomputed

Kept: the subject refs, the objective, the verified claims with their citations
and support class, the hypotheses, and the steps already performed.

NOT kept: evidence TEXT. A ref is stable and citable; the text behind it belongs
to the corpus, which can be refreshed under a live conversation (a `/connect
refresh` republishes it). Holding text would let turn three quote something turn
one read and the repository no longer contains. Every turn re-reads what it
cites from the corpus that exists NOW.

## Why memory, not disk

The whole point is continuity within one sitting. An in-memory, TTL-bounded,
LRU-capped store loses a conversation on restart, which is the correct failure:
a stale investigation resumed days later against a moved index would answer
about a repository that has since changed. `demo/visits.py` persists the four
facts that genuinely survive a restart; this holds the working state that
should not.

## Isolation and provenance

Keyed on (identity, repo, INDEXED COMMIT) and never enumerable across
identities, the same boundary `LibraryRegistry` draws. A follow-up can only ever
continue an investigation the SAME GitHub identity started about the repo they
are currently connected to -- so a subject cannot leak between users, and cannot
survive a repo switch.

The commit is in the key because `/connect refresh` republishes the corpus under
a live conversation. Carried findings were marked verified against evidence that
may no longer exist, and would still publish their previous strength label; a
key that cannot match is a stronger guarantee than a comparison someone can
forget to write. The cost is that a refresh ends the conversation, which is the
honest outcome: those findings were about a different index.

## Ordering

Every write carries the GENERATION it started under. "Start over" bumps it, so
an investigation the user abandoned cannot finish later and overwrite the fresh
conversation that replaced it -- resurrecting a subject they explicitly
discarded. Compare-and-set under the existing lock; no lock is ever held across
a model or network call.
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# A conversation that has gone quiet is over. Twenty minutes is long enough to
# read an answer, think, and follow up; short enough that a subject bound before
# lunch is not silently reused after it.
_DEFAULT_TTL = 1200.0
_MAX_CONVERSATIONS = 2048
# How many turns of claims one conversation carries forward. A follow-up needs
# what was established, not a transcript -- and an unbounded list would grow
# until it no longer fits a prompt.
_MAX_CARRIED_CLAIMS = 40


@dataclass
class CarriedClaim:
    """A finding from an earlier turn: the sentence, its refs, and how strongly
    the repository backed it. The support class is carried rather than
    recomputed because it was computed against the evidence THAT turn actually
    held, and re-deriving it later against different evidence would silently
    restate an old finding at a strength nothing ever measured."""

    text: str
    citations: List[str]
    support: str


@dataclass
class Conversation:
    repo: str
    subject: List[str] = field(default_factory=list)
    objective: str = ""
    claims: List[CarriedClaim] = field(default_factory=list)
    hypotheses: List[dict] = field(default_factory=list)
    performed: List[dict] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    turns: int = 0


class ConversationStore:
    """Per-(identity, repo) investigation state. Thread-safe, TTL'd, LRU-capped."""

    def __init__(self, ttl: float = _DEFAULT_TTL, clock=time.time,
                 max_conversations: int = _MAX_CONVERSATIONS):
        if ttl <= 0 or max_conversations < 1:
            raise ValueError("ttl and max_conversations must be positive")
        self._ttl = float(ttl)
        self._clock = clock
        self._max = int(max_conversations)
        self._live: Dict[tuple, tuple] = {}
        # (identity, repo) -> generation. Deliberately NOT keyed by commit: a
        # "start over" must invalidate in-flight writes for that repo whatever
        # index they were reading.
        self._generations: Dict[tuple, int] = {}
        self._lock = threading.Lock()

    def _purge(self, now):
        for key in [k for k, (_c, expiry) in self._live.items() if expiry <= now]:
            self._live.pop(key, None)

    def begin(self, identity: str, repo: str, fresh: bool = False) -> int:
        """The generation this request is running under.

        `fresh` (the user pressing Start over) bumps it, which is what makes an
        abandoned in-flight investigation unable to overwrite its replacement.
        """
        if not identity or not repo:
            return 0
        with self._lock:
            key = (identity, repo)
            if fresh:
                self._generations[key] = self._generations.get(key, 0) + 1
            return self._generations.get(key, 0)

    def resume(self, identity: str, repo: str, commit: str = None) -> Optional[Conversation]:
        """The live conversation for this identity, repo AND indexed commit.

        All three are part of the key, not fields to check afterwards: a caller
        who switches repos -- or whose index was refreshed underneath them --
        must not inherit a subject built from evidence that is no longer there.
        """
        if not identity or not repo:
            return None
        now = self._clock()
        with self._lock:
            self._purge(now)
            key = (identity, repo, commit)
            entry = self._live.get(key)
            if entry is None:
                return None
            # Reading is activity: a conversation being followed up stays alive.
            self._live[key] = (entry[0], now + self._ttl)
            return entry[0]

    def remember(self, identity: str, repo: str, investigation, commit: str = None,
                 generation: int = None) -> Optional[Conversation]:
        """Fold a finished investigation into this caller's conversation.

        `generation` is what this request began under (see `begin`). A write
        carrying a stale one is DISCARDED: it belongs to an investigation the
        user abandoned, and letting it land would resurrect the subject they
        explicitly started over from.

        Never raises into a request: continuity is an improvement on a stateless
        answer, never a precondition for one. A caller with no identity (the
        unauthenticated local demo) simply has no conversation, and every turn
        stands alone exactly as `/ask` does today.
        """
        if not identity or not repo or investigation is None:
            return None
        now = self._clock()
        convo = Conversation(
            repo=repo,
            subject=list(investigation.subject),
            objective=investigation.objective,
            claims=[CarriedClaim(text=c.text, citations=list(c.citations),
                                 support=c.support)
                    for c in investigation.claims if c.verified][-_MAX_CARRIED_CLAIMS:],
            hypotheses=[{"statement": h.statement, "status": h.status}
                        for h in investigation.hypotheses],
            performed=[{"primitive": s.primitive, "args": dict(s.args)}
                       for s in investigation.performed],
            unknowns=list(investigation.unknowns),
        )
        key = (identity, repo, commit)
        with self._lock:
            if generation is not None \
                    and generation != self._generations.get((identity, repo), 0):
                return None          # a superseded investigation finishing late
            self._purge(now)
            existing = self._live.get(key)
            convo.turns = (existing[0].turns + 1) if existing else 1
            while len(self._live) >= self._max and key not in self._live:
                oldest = min(self._live, key=lambda k: self._live[k][1])
                self._live.pop(oldest, None)
            self._live[key] = (convo, now + self._ttl)
        return convo

    def forget(self, identity: str, repo: str) -> None:
        """Drop this caller's conversation about a repo, at EVERY indexed commit
        -- a disconnect must not leave a subject behind for an earlier index.
        Their subject must not outlive their access to the thing it names."""
        with self._lock:
            for key in [k for k in self._live if k[0] == identity and k[1] == repo]:
                self._live.pop(key, None)
            # The generation counter survives on purpose: it is monotonic, and
            # resetting it would let a request that began before the disconnect
            # write back into a reconnected conversation.


# Words that refer back to something already under discussion rather than naming
# it. Deliberately a small, closed list of DEICTIC forms -- "it", "that change",
# "the old implementation" -- and nothing that merely sounds conversational. A
# question that names its own subject ("what did PR 412 do?") must rebind, so
# this is only consulted when the question resolves to no refs of its own.
_REFERRING = (
    "it", "its", "it's", "this", "that", "these", "those", "them", "they",
    "the change", "that change", "this change", "the pr", "that pr",
    "the old implementation", "the new implementation", "the previous",
    "afterwards", "after that", "later", "the same",
)


def refers_back(question: str) -> bool:
    """Does this question lean on something already established?

    Deterministic and deliberately narrow. Resolving a reference is not a job
    for a model here: a model asked "does 'it' mean PR #400?" will say yes to
    almost anything, and a wrongly-inherited subject produces a confident,
    fully-cited answer about the wrong change -- the exact failure the selection
    marker was built to fix in `.explain()` (2026-08-06). A subject is inherited
    only when the question names none of its own AND uses a referring word.
    """
    if not isinstance(question, str):
        return False
    words = "".join(ch.lower() if ch.isalnum() or ch in "' " else " "
                    for ch in question).split()
    if not words:
        return False
    if any(w in _REFERRING for w in words):
        return True
    # Multi-word entries match a complete TOKEN SEQUENCE, never a substring.
    # "the pr" is a prefix of "the project", "the protocol" and "the primary",
    # so substring matching made every one of those inherit the previous
    # investigation's subject -- producing a fully cited answer about the wrong
    # change, which groundedness cannot detect.
    for phrase in _REFERRING:
        parts = phrase.split()
        if len(parts) < 2:
            continue
        if any(words[i:i + len(parts)] == parts
               for i in range(len(words) - len(parts) + 1)):
            return True
    return False
