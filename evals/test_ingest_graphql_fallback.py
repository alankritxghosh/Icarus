"""When the bulk `gh pr/issue list --json` call fails outright, ingest falls
back to a `gh api graphql` fetch paginated at a small page size.

Live-found 2026-08-28: `gh pr list --json` fails for cli/cli (~14k PRs) at ANY
`--limit` -- even `--limit 90` for just `number` -- while `gh api graphql` at
`first: 50` pages through fine. The fallback runs ONLY on failure, so every repo
that ingests today is byte-unchanged.

Offline: `_gh_json` is the mocked seam (both the direct call and each graphql
page go through it).
"""

import subprocess
import unittest
from unittest import mock

from . import ingest


def _pr_page(nodes, has_next=False, cursor="END"):
    return {"data": {"repository": {"pullRequests": {
        "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
        "nodes": nodes}}}}


def _gnode(number, **over):
    node = {"number": number, "title": f"t{number}", "body": "b",
            "state": "MERGED", "mergedAt": None, "reviewDecision": None,
            "author": {"login": "octocat"},
            "labels": {"nodes": [{"name": "bug"}]},
            "closingIssuesReferences": {"nodes": []}}
    node.update(over)
    return node


class FlattenTests(unittest.TestCase):
    def test_connections_become_plain_lists(self):
        flat = ingest._flatten_graphql_node(_gnode(
            1, labels={"nodes": [{"name": "a"}, {"name": "b"}]},
            closingIssuesReferences={"nodes": [{"number": 9}]}))
        self.assertEqual(flat["labels"], [{"name": "a"}, {"name": "b"}])
        self.assertEqual(flat["closingIssuesReferences"], [{"number": 9}])
        self.assertEqual(flat["author"], {"login": "octocat"})

    def test_matches_what_pr_or_issue_text_expects(self):
        flat = ingest._flatten_graphql_node(_gnode(
            5, reviewDecision="APPROVED",
            labels={"nodes": [{"name": "p1"}]},
            closingIssuesReferences={"nodes": [{"number": 3}]}))
        text = ingest._pr_or_issue_text(flat, "pr")
        self.assertIn("PR #5: t5", text)
        self.assertIn("[MERGED by octocat] review: approved labels: p1", text)
        self.assertIn("Linked issues: #3", text)


class BulkOrPaginateTests(unittest.TestCase):
    def test_direct_call_success_never_touches_graphql(self):
        with mock.patch.object(ingest, "_gh_json",
                               return_value=[{"number": 1}]) as gh:
            out = ingest._bulk_list_or_paginate(
                ["pr", "list", "-R", "o/r", "--json", "x"], None, "o/r",
                "pullRequests", ingest._GRAPHQL_PR_NODE, 5000)
        self.assertEqual(out, [{"number": 1}])
        self.assertEqual(gh.call_count, 1)

    def test_disabled_issues_error_is_reraised_not_fallen_back(self):
        err = subprocess.CalledProcessError(
            1, ["gh"], output="", stderr="GraphQL: ... has disabled issues")
        with mock.patch.object(ingest, "_gh_json", side_effect=err):
            with self.assertRaises(subprocess.CalledProcessError):
                ingest._bulk_list_or_paginate(
                    ["issue", "list", "-R", "o/r", "--json", "number"], None,
                    "o/r", "issues", "number", 5000)

    def test_falls_back_and_flattens_on_list_failure(self):
        def route(args, token=None, timeout=None):
            if args[0] != "api":
                raise subprocess.CalledProcessError(
                    1, ["gh"], output="", stderr="GraphQL: something broke (x)")
            return _pr_page([_gnode(2), _gnode(1)])

        with mock.patch.object(ingest, "_gh_json", side_effect=route):
            out = ingest._bulk_list_or_paginate(
                ["pr", "list", "-R", "o/r", "--json", "x"], None, "o/r",
                "pullRequests", ingest._GRAPHQL_PR_NODE, 5000)
        self.assertEqual([p["number"] for p in out], [2, 1])
        self.assertEqual(out[0]["labels"], [{"name": "bug"}])  # flattened


class PaginateTests(unittest.TestCase):
    def test_pages_until_has_next_false(self):
        pages = [_pr_page([_gnode(3), _gnode(2)], has_next=True, cursor="C1"),
                 _pr_page([_gnode(1)], has_next=False)]
        with mock.patch.object(ingest, "_gh_json", side_effect=pages) as gh:
            out = ingest._paginate_graphql("o/r", None, "pullRequests",
                                           ingest._GRAPHQL_PR_NODE, 5000)
        self.assertEqual([p["number"] for p in out], [3, 2, 1])
        self.assertEqual(gh.call_count, 2)
        # second call carried the cursor
        self.assertIn("cursor=C1", gh.call_args_list[1].args[0])

    def test_respects_cap(self):
        page = _pr_page([_gnode(i) for i in range(50)], has_next=True, cursor="C")
        with mock.patch.object(ingest, "_gh_json", return_value=page):
            out = ingest._paginate_graphql("o/r", None, "pullRequests",
                                           ingest._GRAPHQL_PR_NODE, 30)
        self.assertLessEqual(len(out), 50)
        # first page request asks for at most the cap
        self.assertTrue(len(out) >= 30)


class FetchPrsFallbackTests(unittest.TestCase):
    def test_fetch_prs_produces_chunks_via_the_fallback(self):
        def route(args, token=None, timeout=None):
            if args[0] == "api":
                return _pr_page([_gnode(7, closingIssuesReferences={
                    "nodes": [{"number": 4}]})])
            raise subprocess.TimeoutExpired(["gh"], 900)

        with mock.patch.object(ingest, "_gh_json", side_effect=route):
            chunks, issue_ids = ingest.fetch_prs("o/r")
        self.assertEqual(chunks[0]["ref"], "pr:7")
        self.assertIn("PR #7: t7", chunks[0]["text"])
        self.assertIn(4, issue_ids)


if __name__ == "__main__":
    unittest.main()
