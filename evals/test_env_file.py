# evals/test_env_file.py
"""The .env loader: parses KEY=VALUE into os.environ without overriding real env,
tolerates comments/blanks/quotes/export, and no-ops on a missing file."""

import os
import tempfile
import unittest
from pathlib import Path

from .env_file import load_env_file


class LoadEnvFileTests(unittest.TestCase):
    def setUp(self):
        self._added = []

    def tearDown(self):
        for k in self._added:
            os.environ.pop(k, None)

    def _write(self, text):
        d = tempfile.mkdtemp()
        p = Path(d) / ".env"
        p.write_text(text)
        return p

    def test_loads_key_value_into_environ(self):
        self._added += ["ICARUS_T_A", "ICARUS_T_B"]
        p = self._write("ICARUS_T_A=alpha\nICARUS_T_B = beta\n")
        load_env_file(p)
        self.assertEqual(os.environ["ICARUS_T_A"], "alpha")
        self.assertEqual(os.environ["ICARUS_T_B"], "beta")

    def test_does_not_override_existing_env(self):
        self._added.append("ICARUS_T_C")
        os.environ["ICARUS_T_C"] = "real"
        load_env_file(self._write("ICARUS_T_C=fromfile"))
        self.assertEqual(os.environ["ICARUS_T_C"], "real")  # real env wins

    def test_ignores_comments_and_blanks(self):
        self._added.append("ICARUS_T_D")
        load_env_file(self._write("# a comment\n\n   \nICARUS_T_D=d\n"))
        self.assertEqual(os.environ["ICARUS_T_D"], "d")

    def test_strips_quotes_and_export(self):
        self._added += ["ICARUS_T_E", "ICARUS_T_F"]
        load_env_file(self._write('ICARUS_T_E="quoted"\nexport ICARUS_T_F=\'q2\'\n'))
        self.assertEqual(os.environ["ICARUS_T_E"], "quoted")
        self.assertEqual(os.environ["ICARUS_T_F"], "q2")

    def test_missing_file_is_noop(self):
        self.assertEqual(load_env_file(Path(tempfile.mkdtemp()) / "nope.env"), {})

    def test_value_with_equals_sign_is_preserved(self):
        self._added.append("ICARUS_T_G")
        load_env_file(self._write("ICARUS_T_G=a=b=c\n"))
        self.assertEqual(os.environ["ICARUS_T_G"], "a=b=c")


if __name__ == "__main__":
    unittest.main()
