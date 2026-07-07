# demo/test_links.py
import unittest

from .links import ref_to_url

REPO = "simonw/llm"
COMMIT = "94769b8b076cde9392059d76bd766453cf900180"


class RefToUrlTests(unittest.TestCase):
    def test_pr(self):
        self.assertEqual(ref_to_url("pr:1435", REPO, COMMIT),
                         "https://github.com/simonw/llm/pull/1435")

    def test_issue(self):
        self.assertEqual(ref_to_url("issue:506", REPO, COMMIT),
                         "https://github.com/simonw/llm/issues/506")

    def test_code_path_splits_on_first_colon_only(self):
        self.assertEqual(ref_to_url("code:llm/models.py", REPO, COMMIT),
                         f"https://github.com/simonw/llm/blob/{COMMIT}/llm/models.py")

    def test_code_path_with_line_range_appends_fragment(self):
        self.assertEqual(
            ref_to_url("code:llm/models.py#L10-L40", REPO, COMMIT),
            f"https://github.com/simonw/llm/blob/{COMMIT}/llm/models.py#L10-L40")

    def test_doc_path_without_line_range(self):
        self.assertEqual(ref_to_url("doc:README.md", REPO, COMMIT),
                         f"https://github.com/simonw/llm/blob/{COMMIT}/README.md")

    def test_doc_path_with_line_range_appends_fragment(self):
        self.assertEqual(
            ref_to_url("doc:README.md#L1-L50", REPO, COMMIT),
            f"https://github.com/simonw/llm/blob/{COMMIT}/README.md#L1-L50")

    def test_config_path_without_line_range(self):
        self.assertEqual(
            ref_to_url("config:pyproject.toml", REPO, COMMIT),
            f"https://github.com/simonw/llm/blob/{COMMIT}/pyproject.toml")

    def test_config_path_with_line_range_appends_fragment(self):
        self.assertEqual(
            ref_to_url("config:pyproject.toml#L1-L300", REPO, COMMIT),
            f"https://github.com/simonw/llm/blob/{COMMIT}/pyproject.toml#L1-L300")

    def test_unknown_source_returns_none(self):
        self.assertIsNone(ref_to_url("slack:123", REPO, COMMIT))

    def test_malformed_ref_returns_none(self):
        self.assertIsNone(ref_to_url("nocolon", REPO, COMMIT))


if __name__ == "__main__":
    unittest.main()
