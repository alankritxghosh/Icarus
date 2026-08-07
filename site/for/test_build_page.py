"""The prospect page's conscience.

Two things must never break silently, because the page is judged by a stranger:
a citation that links somewhere other than their own repository, and an
abstention rendered as if it were an answer. The second is the page's version
of a bluff -- the one thing the product refuses to do.

    python3 -m unittest site.for.test_build_page   (or run this file directly)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_page import build

META = {"repo": "acme/widget", "commit": "c6363f2f439f39ff86215bab3bf05e44fa93b8a6",
        "counts": {"pr": 3, "issue": 2, "commit": 9, "code": 4}}

ANSWERED = {"question": "Why is the poller debounced?", "verdict": "answer",
            "answer": "Because `SCShareableContent` leaked without a pool.",
            "citations": ["commit:dba287ece46d1ac9bb586f414c580f7171ba5190", "pr:2064",
                          "issue:1505", "code:apps/web/auth.ts#L1-L40"],
            "retrieved": ["pr:2064"]}
UNKNOWN = {"question": "Why Rust?", "verdict": "unknown", "answer": "",
           "citations": [], "retrieved": ["pr:1974", "doc:AGENTS.md#L1-L112"]}


class PageTests(unittest.TestCase):
    def test_every_citation_links_into_their_own_repo(self):
        html = build([ANSWERED], META)
        links = [s.split('"')[0] for s in html.split('class="chip ')[1:]
                 for s in [s.split('href="')[1]]]
        self.assertEqual(len(links), 4)
        for url in links:
            self.assertTrue(url.startswith("https://github.com/acme/widget/"), url)
        self.assertIn(f"/blob/{META['commit']}/apps/web/auth.ts#L1-L40", html)

    def test_an_abstention_is_never_rendered_as_an_answer(self):
        html = build([UNKNOWN], META)
        self.assertIn("No one wrote this down.", html)
        self.assertIn('<details data-verdict="unknown">', html)
        self.assertNotIn('<details data-verdict="answer">', html)
        self.assertIn("pr:1974", html)  # shows what it searched, per the product

    def test_a_verdict_of_answer_without_citations_is_treated_as_unknown(self):
        """The gate's own rule: prose with nothing grounding it is not an answer."""
        html = build([dict(ANSWERED, citations=[])], META)
        self.assertIn('<details data-verdict="unknown">', html)
        self.assertNotIn("leaked without a pool", html)

    def test_answer_text_is_escaped_before_code_spans_are_rendered(self):
        html = build([dict(ANSWERED, answer="drop `<script>alert(1)</script>`")], META)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_answer_naming_a_code_symbol_leads_over_a_longer_vague_one(self):
        vague = dict(ANSWERED, question="Vague one?", answer="Because " + "x" * 300)
        precise = dict(ANSWERED, question="Precise one?", answer="Because `retryPool` leaked.")
        html = build([vague, UNKNOWN, precise], META)
        self.assertLess(html.index("Precise one?"), html.index("Why Rust?"))
        self.assertLess(html.index("Why Rust?"), html.index("Vague one?"))

    def test_length_breaks_the_tie_when_no_answer_names_a_symbol(self):
        short = dict(ANSWERED, question="Short one?", answer="Because timing.")
        long_ = dict(ANSWERED, question="Long one?", answer="Because " + "x" * 200)
        html = build([short, long_], META)
        self.assertLess(html.index("Long one?"), html.index("Short one?"))

    def test_ordering_survives_a_page_with_no_unknowns(self):
        html = build([ANSWERED], META)          # must not IndexError
        self.assertIn("Why is the poller debounced?", html)


if __name__ == "__main__":
    unittest.main()
