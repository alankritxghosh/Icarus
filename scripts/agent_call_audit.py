#!/usr/bin/env python3
"""Count real Icarus MCP calls in Claude Code session transcripts.

Exists because a coding agent's SELF-REPORT of its own tool use is unreliable:
twice in one session (2026-08-10) a self-reported count disagreed with the
harness metadata for the same run -- once 6 reported against 14 actual. The
trustworthy record is the transcript Claude Code persists as JSONL under
`~/.claude/projects/<project-slug>/*.jsonl`, which contains the real
`tool_use` blocks.

This is the measurement half of "make the MCP tool irresistible": the tool
descriptions were rewritten to trigger on observable events rather than on the
agent's own judgement of importance (demo/mcp_server.py `_INSTRUCTIONS`), and
that is a behavioural claim, so it needs a number rather than an impression.

Usage:
    python3 scripts/agent_call_audit.py                 # all projects
    python3 scripts/agent_call_audit.py --project uv    # slug substring
    python3 scripts/agent_call_audit.py --selftest      # no transcripts needed
"""
import argparse
import json
import sys
from pathlib import Path

TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"
ICARUS_PREFIX = "mcp__icarus__"

# A session where the USER said "icarus" (or named a tool) was DIRECTED, so its
# calls say nothing about whether the tool gets reached for on its own. Coarse
# on purpose: it can only ever move a session out of the "unprompted" column,
# so it under-claims rather than over-claims, which is the safe direction for a
# number being used to argue the change worked.
_DIRECTION_MARKERS = ("icarus", "get_change_context", "get_task_context",
                      "explain_code_context")


def _text_of(content) -> str:
    """Flatten a message's content to searchable text; shapes vary by version."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return ""


def audit_session(path: Path) -> dict:
    """One transcript -> {calls, tools, directed}. Never raises on a bad line."""
    calls, tools, directed = 0, [], False
    with path.open(errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue  # a partially-flushed final line is normal
            message = row.get("message")
            if not isinstance(message, dict):
                continue
            if message.get("role") == "user":
                if any(m in _text_of(message.get("content")).lower()
                       for m in _DIRECTION_MARKERS):
                    directed = True
                continue
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                if name.startswith(ICARUS_PREFIX):
                    calls += 1
                    tools.append(name[len(ICARUS_PREFIX):])
    return {"session": path.stem, "calls": calls, "tools": tools,
            "directed": directed}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", default="",
                    help="only projects whose directory name contains this")
    ap.add_argument("--root", type=Path, default=TRANSCRIPT_ROOT)
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    if not args.root.is_dir():
        print(f"no transcripts at {args.root}", file=sys.stderr)
        return 1

    rows = [
        audit_session(f)
        for project in sorted(args.root.iterdir()) if project.is_dir()
        if args.project in project.name
        for f in sorted(project.glob("*.jsonl"))
    ]
    if not rows:
        print("no sessions matched", file=sys.stderr)
        return 1

    spontaneous = [r for r in rows if not r["directed"]]
    used = [r for r in spontaneous if r["calls"]]
    for r in rows:
        if r["calls"] or not r["directed"]:
            flag = "directed" if r["directed"] else "unprompted"
            print(f"{r['session'][:8]}  {r['calls']:>3} calls  {flag:<10} "
                  f"{','.join(sorted(set(r['tools']))) or '-'}")
    print(f"\n{len(rows)} sessions, {len(spontaneous)} undirected; "
          f"{len(used)} of those called Icarus "
          f"({sum(r['calls'] for r in used)} calls total)")
    return 0


def _selftest() -> int:
    """One runnable check: the parser counts what it should and skips the rest."""
    import tempfile

    lines = [
        {"message": {"role": "user", "content": "fix the dedup bug"}},
        {"message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {}},
            {"type": "tool_use", "name": "mcp__icarus__get_change_context",
             "input": {}}]}},
        "{ not json",                       # tolerated, not fatal
        {"summary": "no message key"},      # tolerated
    ]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "abc.jsonl"
        p.write_text("\n".join(
            l if isinstance(l, str) else json.dumps(l) for l in lines))
        got = audit_session(p)
    assert got["calls"] == 1, got            # Bash must not be counted
    assert got["tools"] == ["get_change_context"], got
    assert got["directed"] is False, got     # user never said "icarus"

    directed = [{"message": {"role": "user", "content": [
        {"type": "text", "text": "ask Icarus about this first"}]}}]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "def.jsonl"
        p.write_text("\n".join(json.dumps(l) for l in directed))
        assert audit_session(p)["directed"] is True

    print("selftest ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
