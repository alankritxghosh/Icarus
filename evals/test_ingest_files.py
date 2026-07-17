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

    # --- React Native coverage (2026-07-17, tester-reported) -----------------
    # Measured against two real RN repos rather than guessed: wix/
    # react-native-navigation drops 298 .mm files (its ENTIRE ios/ tree) while
    # indexing 280 .h headers, so Icarus read every Objective-C declaration and
    # none of the implementations -- it could see a method exist and never see
    # what it did. Same silent-invisibility class as the wolf3d uppercase bug
    # documented in classify_file.

    def test_objective_c_implementation_is_code(self):
        # AppDelegate.m is the canonical entry point of every RN iOS app.
        path = self._write("ios/AppDelegate.m", "@implementation AppDelegate\n@end\n")
        self.assertEqual(classify_file(path, self.root), "code")

    def test_objective_cpp_implementation_is_code(self):
        # The 298-file case: RN's iOS native bridge is overwhelmingly .mm.
        path = self._write("ios/TopBarTitlePresenter.mm",
                           "@implementation TopBarTitlePresenter\n@end\n")
        self.assertEqual(classify_file(path, self.root), "code")

    def test_objective_c_header_and_implementation_classify_together(self):
        # The asymmetry itself is the bug: a header indexed while its
        # implementation is dropped is worse than dropping both, because the
        # corpus then *looks* like it covers the module.
        header = self._write("ios/RNNBridge.h", "@interface RNNBridge\n@end\n")
        impl = self._write("ios/RNNBridge.mm", "@implementation RNNBridge\n@end\n")
        self.assertEqual(classify_file(header, self.root), "code")
        self.assertEqual(classify_file(impl, self.root), "code")

    def test_jsx_file_is_code(self):
        path = self._write("src/App.jsx", "export default () => <View />;\n")
        self.assertEqual(classify_file(path, self.root), "code")

    def test_esm_and_cjs_modules_are_code(self):
        # metro.config.cjs / eslint.config.mjs are real, hand-written config.
        mjs = self._write("eslint.config.mjs", "export default [];\n")
        cjs = self._write("metro.config.cjs", "module.exports = {};\n")
        self.assertEqual(classify_file(mjs, self.root), "code")
        self.assertEqual(classify_file(cjs, self.root), "code")

    def test_gradle_file_is_config(self):
        path = self._write("android/app/build.gradle", "android {\n  minSdkVersion 21\n}\n")
        self.assertEqual(classify_file(path, self.root), "config")

    def test_podspec_file_is_config(self):
        path = self._write("RNNavigation.podspec", "Pod::Spec.new do |s|\nend\n")
        self.assertEqual(classify_file(path, self.root), "config")

    def test_json_is_rejected_despite_being_the_biggest_rn_drop(self):
        # DELIBERATE exclusion, not an oversight -- locks the decision in.
        # .json was the single largest dropped extension on a real RN app
        # (mattermost-mobile: 123 files, 5.9MB), but the volume is Xcode asset
        # catalogs (30x Contents.json) and i18n locale bundles, against ~8 real
        # package.json. Indexing it would skew BM25/IDF corpus-wide with
        # translation strings. If package.json specifically ever needs to be
        # evidence, allowlist that FILENAME -- do not open the extension.
        locale = self._write("assets/i18n/zh-TW.json", '{"login": "登入"}\n')
        self.assertIsNone(classify_file(locale, self.root))

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

    def test_path_not_under_root_raises(self):
        # Contract: path must be under root (a tree walk always satisfies
        # this). A path outside root is a caller misuse -- must raise loudly
        # rather than silently scan the absolute path's own segments, which
        # could spuriously match a deny-listed name in an unrelated prefix.
        with TemporaryDirectory() as other_dir:
            other_root = Path(other_dir)
            outside_path = self._write("pkg/models.py", "x = 1\n")
            with self.assertRaises(ValueError):
                classify_file(outside_path, other_root)


if __name__ == "__main__":
    unittest.main()
