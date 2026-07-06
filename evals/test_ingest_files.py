"""Tests for classify_file, the pure per-file ingest classifier (Task A1).

Offline/pure: builds a fixture tree in a TemporaryDirectory and asserts each
file gets exactly the right source tag (or None if it should be skipped).
Does not touch _collect_files/fetch_code/ingest_repo -- that wiring is A3.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from .ingest import _MAX_FILE_BYTES, classify_file


class ClassifyFileTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel_path, content, binary=False):
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if binary:
            path.write_bytes(content)
        else:
            path.write_text(content)
        return path

    def test_python_file_is_code(self):
        path = self._write("pkg/models.py", "def load():\n    return 1\n")
        self.assertEqual(classify_file(path, self.root), "code")

    def test_go_file_is_code(self):
        path = self._write("cmd/main.go", "package main\n\nfunc main() {}\n")
        self.assertEqual(classify_file(path, self.root), "code")

    def test_yaml_file_is_config(self):
        path = self._write("config/app.yaml", "name: icarus\nversion: 1\n")
        self.assertEqual(classify_file(path, self.root), "config")

    def test_markdown_file_is_doc(self):
        path = self._write("README.md", "# Title\n\nSome docs.\n")
        self.assertEqual(classify_file(path, self.root), "doc")

    def test_binary_content_rejected_despite_allowed_extension(self):
        # Misnamed binary: .py extension, but null byte in the content.
        path = self._write("pkg/blob.py", b"\x00\x01\x02binary junk", binary=True)
        self.assertIsNone(classify_file(path, self.root))

    def test_file_in_node_modules_is_rejected(self):
        path = self._write("node_modules/left-pad/index.js", "module.exports = 1;\n")
        self.assertIsNone(classify_file(path, self.root))

    def test_file_in_git_dir_is_rejected(self):
        path = self._write(".git/HEAD", "ref: refs/heads/main\n")
        self.assertIsNone(classify_file(path, self.root))

    def test_file_in_vendor_dir_is_rejected(self):
        path = self._write("vendor/some_pkg/lib.go", "package pkg\n")
        self.assertIsNone(classify_file(path, self.root))

    def test_oversized_file_is_rejected(self):
        path = self._write("pkg/huge.py", "x = 1\n" * (_MAX_FILE_BYTES // 6 + 1000))
        self.assertGreater(path.stat().st_size, _MAX_FILE_BYTES)
        self.assertIsNone(classify_file(path, self.root))

    def test_unallowed_extension_is_rejected(self):
        path = self._write("assets/logo.png", b"\x89PNG\r\n\x1a\nfakepngbytes", binary=True)
        self.assertIsNone(classify_file(path, self.root))

    def test_lockfile_is_rejected(self):
        path = self._write("package-lock.json", '{"name": "x"}\n')
        self.assertIsNone(classify_file(path, self.root))

    def test_minified_asset_is_rejected(self):
        path = self._write("static/app.min.js", "!function(){}();\n")
        self.assertIsNone(classify_file(path, self.root))


if __name__ == "__main__":
    unittest.main()
