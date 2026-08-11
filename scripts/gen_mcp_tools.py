#!/usr/bin/env python3
"""Generate the Swift copy of the MCP tool contract from the Python one.

`demo/mcp_server.py` is the SINGLE SOURCE OF TRUTH for what the tools are
called, what they do, and -- the part that matters -- exactly how they are
described. That wording is not decoration: rewriting it from "before planning a
meaningful code change" to a list of observable triggers took unprompted Icarus
calls from 0/11 to 4/4 in a controlled run (docs/experiments/2026-08-11-agent-
mode-exp-c2-results.md), and the caveats in it are honesty disclosures backed by
measurements.

The Mac app serves the same tools over stdio so a user who installed the DMG
needs no Python. Hand-copying that text into Swift would let the two drift, and
the failure would be silent: the app would keep answering, just with a worse or
less honest description than the one that was measured.

So the Swift side is GENERATED here and committed, and
`demo/test_mcp_tools_generated.py` fails if the committed file no longer matches
what `demo/mcp_server.py` would produce. Regenerate with:

    python3 scripts/gen_mcp_tools.py

Deliberately a committed generated file rather than a build-time step or a
bundled resource: no SwiftPM resource plumbing, no codegen in the build, and the
diff is reviewable in the pull request that changes the wording.
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from demo import mcp_server  # noqa: E402

TARGET = (pathlib.Path(__file__).resolve().parents[1]
          / "mac" / "Icarus" / "Sources" / "IcarusKit" / "McpContract.swift")

_HEADER = '''// GENERATED FILE -- DO NOT EDIT BY HAND.
//
// Written by scripts/gen_mcp_tools.py from demo/mcp_server.py, which is the
// single source of truth for the MCP tool contract. The wording of these
// descriptions is measured, not decorative (see docs/experiments/
// 2026-08-11-agent-mode-exp-c2-results.md), so the Python and Swift servers
// must never describe the same tool differently.
//
// To change a description: edit demo/mcp_server.py, run
// `python3 scripts/gen_mcp_tools.py`, and commit both.
// demo/test_mcp_tools_generated.py fails if this file is stale.

import Foundation

public enum McpContract {
    public static let serverName = %s
    public static let serverVersion = %s
    public static let defaultProtocolVersion = %s

    /// The `instructions` field returned by `initialize`.
    public static let instructions = %s

    /// The `tools` array returned by `tools/list`, verbatim as JSON.
    public static let toolsJSON = %s
}
'''


def _swift_string(value: str) -> str:
    """A Swift raw string literal, so nothing in the text is interpreted.

    Raw strings (`#"..."#`) disable both escapes and interpolation, which is
    what we want: the descriptions contain backslashes, quotes and parentheses
    that Swift would otherwise try to read. The delimiter grows if the text
    itself contains the closing sequence, so this cannot silently truncate.
    """
    pounds = "#"
    while pounds + '"' in value or '"' + pounds in value:
        pounds += "#"
    if "\n" in value:
        return f'{pounds}"""\n{value}\n"""{pounds}'
    return f'{pounds}"{value}"{pounds}'


def render() -> str:
    tools = json.dumps(mcp_server._TOOLS, ensure_ascii=False,
                       separators=(",", ":"), sort_keys=True)
    return _HEADER % (
        _swift_string(mcp_server._SERVER_NAME),
        _swift_string(mcp_server._SERVER_VERSION),
        _swift_string(mcp_server._DEFAULT_PROTOCOL_VERSION),
        _swift_string(mcp_server._INSTRUCTIONS),
        _swift_string(tools),
    )


def main() -> int:
    text = render()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    current = TARGET.read_text() if TARGET.exists() else None
    if current == text:
        print(f"{TARGET.name} already current")
        return 0
    TARGET.write_text(text)
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
