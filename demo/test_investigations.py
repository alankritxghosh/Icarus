# demo/test_investigations.py
"""The conversation store's contract, weighted toward what must NOT persist and
what must NOT be inherited.

A wrongly inherited subject is the dangerous failure here: the answer that
follows is fully cited and completely confident, and about the wrong change.
Groundedness cannot catch it -- every citation is real (the 2026-08-06
selection-drift finding). So subject inheritance is deterministic, narrow, and
tested from the refusing side.
"""

import unittest

from evals.investigation import (
    Claim, Hypothesis, Investigation, Step, SUPPORT_EXPLICIT, SUPPORT_WEAK,
)
from .investigations import ConversationStore, refers_back


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def finished(subject=("pr:400",), objective="why was PR #400 introduced?"):
    inv = Investigation(objective=objective, question=objective,
                        subject=list(subject))
    inv.hypotheses = [Hypothesis("h1", "it fixed retrieval quality",
                                 status="supported")]
    inv.claims = [
        Claim(id="c1", text="It closes issue 372.", citations=["pr:400"],
              support=SUPPORT_EXPLICIT, verified=True),
        Claim(id="c2", text="A dropped candidate.", citations=["pr:400"],
              support=SUPPORT_WEAK, verified=False),
    ]
    inv.performed = [Step("inspect", {"ref": "pr:400"})]
    inv.unknowns = ["whether it was part of a migration"]
    return inv


class RememberResumeTests(unittest.TestCase):
    def test_a_finished_investigation_can_be_resumed_by_the_same_caller(self):
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        convo = store.resume("u1", "owner/repo")
        self.assertEqual(convo.subject, ["pr:400"])
        self.assertEqual(convo.objective, "why was PR #400 introduced?")

    def test_only_VERIFIED_findings_are_carried_forward(self):
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        self.assertEqual([c.text for c in store.resume("u1", "owner/repo").claims],
                         ["It closes issue 372."])

    def test_a_findings_support_class_is_carried_not_recomputed(self):
        # It was measured against the evidence THAT turn held. Re-deriving it
        # later against different evidence would restate an old finding at a
        # strength nothing ever measured.
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        self.assertEqual(store.resume("u1", "owner/repo").claims[0].support,
                         SUPPORT_EXPLICIT)

    def test_evidence_TEXT_is_never_stored(self):
        # The corpus can be refreshed under a live conversation. Holding text
        # would let a later turn quote something the repository no longer has.
        store = ConversationStore()
        inv = finished()
        inv.evidence = {"pr:400": object()}
        store.remember("u1", "owner/repo", inv)
        convo = store.resume("u1", "owner/repo")
        self.assertFalse(hasattr(convo, "evidence"))
        self.assertFalse(hasattr(convo.claims[0], "text_of_evidence"))
        self.assertEqual(convo.claims[0].citations, ["pr:400"])

    def test_turns_accumulate_across_a_conversation(self):
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        store.remember("u1", "owner/repo", finished())
        self.assertEqual(store.resume("u1", "owner/repo").turns, 2)

    def test_carried_claims_are_bounded(self):
        store = ConversationStore()
        inv = finished()
        inv.claims = [Claim(id=f"c{i}", text=f"finding {i}", citations=["pr:400"],
                            support=SUPPORT_WEAK, verified=True)
                      for i in range(100)]
        store.remember("u1", "owner/repo", inv)
        self.assertLessEqual(len(store.resume("u1", "owner/repo").claims), 40)


class IsolationTests(unittest.TestCase):
    def test_one_callers_conversation_is_invisible_to_another(self):
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        self.assertIsNone(store.resume("u2", "owner/repo"))

    def test_a_conversation_does_not_survive_a_repo_switch(self):
        # The repo is part of the KEY, not a field checked afterwards: a key
        # that cannot match is stronger than a comparison someone can forget.
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        self.assertIsNone(store.resume("u1", "other/repo"))

    def test_forget_drops_only_that_callers_conversation(self):
        store = ConversationStore()
        store.remember("u1", "owner/repo", finished())
        store.remember("u2", "owner/repo", finished())
        store.forget("u1", "owner/repo")
        self.assertIsNone(store.resume("u1", "owner/repo"))
        self.assertIsNotNone(store.resume("u2", "owner/repo"))

    def test_an_anonymous_caller_has_no_conversation_and_does_not_raise(self):
        store = ConversationStore()
        self.assertIsNone(store.remember("", "owner/repo", finished()))
        self.assertIsNone(store.resume("", "owner/repo"))
        self.assertIsNone(store.resume(None, None))


class ExpiryTests(unittest.TestCase):
    def test_a_quiet_conversation_expires(self):
        clock = Clock()
        store = ConversationStore(ttl=100.0, clock=clock)
        store.remember("u1", "owner/repo", finished())
        clock.t += 101
        self.assertIsNone(store.resume("u1", "owner/repo"))

    def test_following_up_keeps_a_conversation_alive(self):
        clock = Clock()
        store = ConversationStore(ttl=100.0, clock=clock)
        store.remember("u1", "owner/repo", finished())
        clock.t += 90
        self.assertIsNotNone(store.resume("u1", "owner/repo"))
        clock.t += 90                       # would have expired without the read
        self.assertIsNotNone(store.resume("u1", "owner/repo"))

    def test_the_store_is_bounded_and_evicts_the_oldest(self):
        clock = Clock()
        store = ConversationStore(ttl=10_000.0, clock=clock, max_conversations=2)
        for i in range(3):
            store.remember(f"u{i}", "owner/repo", finished())
            clock.t += 1
        self.assertIsNone(store.resume("u0", "owner/repo"))
        self.assertIsNotNone(store.resume("u2", "owner/repo"))

    def test_a_returning_caller_does_not_evict_themselves(self):
        store = ConversationStore(max_conversations=1)
        store.remember("u1", "owner/repo", finished())
        store.remember("u1", "owner/repo", finished())
        self.assertIsNotNone(store.resume("u1", "owner/repo"))

    def test_rejects_a_nonsensical_configuration(self):
        for kwargs in ({"ttl": 0}, {"ttl": -1}, {"max_conversations": 0}):
            with self.assertRaises(ValueError):
                ConversationStore(**kwargs)


class ReferringTests(unittest.TestCase):
    def test_the_follow_ups_this_feature_exists_for_all_refer_back(self):
        for question in ("why did it change?",
                         "what implications did it have?",
                         "why do you think they did it this way?",
                         "what did this affect?",
                         "what was the old implementation?",
                         "what came after that?",
                         "did they change it again later?"):
            self.assertTrue(refers_back(question), question)

    def test_a_question_that_names_its_own_subject_does_not_refer_back(self):
        for question in ("what does the chunker do?",
                         "who maintains authentication?",
                         "how does retrieval rank results?"):
            self.assertFalse(refers_back(question), question)

    def test_punctuation_and_case_do_not_hide_a_reference(self):
        self.assertTrue(refers_back("WHY DID IT CHANGE?!"))
        self.assertTrue(refers_back("...and why was that?"))

    def test_a_word_merely_CONTAINING_a_referring_word_is_not_one(self):
        # "commit" contains "it"; "database" contains "that"'s letters. Matching
        # on substrings would inherit a subject on almost any question.
        for question in ("what does the commit do?",
                         "how is the database initialised?",
                         "which items are indexed?"):
            self.assertFalse(refers_back(question), question)

    def test_empty_and_non_string_input_is_not_a_reference(self):
        for value in ("", "   ", None, 42, ["it"]):
            self.assertFalse(refers_back(value), repr(value))


if __name__ == "__main__":
    unittest.main()
