"""The Swift MCP contract must not drift from the Python one.

Two servers now answer the same three tools: `demo/mcp_server.py` (Python,
stdio, used from a checkout) and the Mac app's `Icarus --mcp` (Swift, what a
user who installed the DMG actually runs). They must describe the tools
IDENTICALLY.

This is not tidiness. The descriptions are measured: rewriting them to trigger
on observable events took unprompted calls from 0/11 to 4/4, and the caveats
inside them are honesty disclosures with numbers behind them (a closed pull
request usually means "already done", relevance noise up to one in three).
A drifted Swift copy would keep working while quietly serving a worse or less
honest contract than the one that was measured -- a silent failure, which is
the kind this repo is built to refuse.

Stdlib only, always runs.
"""
import pathlib
import subprocess
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
GENERATOR = REPO / "scripts" / "gen_mcp_tools.py"
GENERATED = REPO / "mac" / "Icarus" / "Sources" / "IcarusKit" / "McpContract.swift"

sys.path.insert(0, str(REPO))


class GeneratedContractTests(unittest.TestCase):

    def test_committed_swift_matches_python(self):
        """Regenerate in memory and compare; fails when either side moved."""
        sys.path.insert(0, str(REPO / "scripts"))
        import gen_mcp_tools

        self.assertTrue(GENERATED.exists(),
                        f"{GENERATED} is missing -- run scripts/gen_mcp_tools.py")
        self.assertEqual(
            GENERATED.read_text(), gen_mcp_tools.render(),
            "McpContract.swift is stale. Run: python3 scripts/gen_mcp_tools.py")

    def test_generator_is_deterministic(self):
        """Same input, same bytes -- otherwise the drift check is noise."""
        sys.path.insert(0, str(REPO / "scripts"))
        import gen_mcp_tools
        self.assertEqual(gen_mcp_tools.render(), gen_mcp_tools.render())

    def test_swift_carries_the_measured_wording(self):
        """Spot-check the phrases the experiments actually bought.

        Guards against a generator that "succeeds" while emitting something
        empty or truncated -- the equality test above would still pass if BOTH
        sides became empty.
        """
        text = GENERATED.read_text()
        self.assertIn("you are about to", text)
        self.assertNotIn("meaningful code change", text)
        self.assertIn("not evidence that the approach was rejected", text)
        self.assertIn("get_change_context", text)
        self.assertIn("explain_code_context", text)
        self.assertIn("get_task_context", text)

    def test_generator_runs_clean_as_a_script(self):
        """It is a command a human runs; it must not be import-only."""
        result = subprocess.run(
            [sys.executable, str(GENERATOR)],
            capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("current", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
