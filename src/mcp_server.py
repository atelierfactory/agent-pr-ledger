#!/usr/bin/env python3
"""agent-pr-ledger as an MCP server (stdio, JSON-RPC 2.0, standard library only).

Exposes two tools to any MCP client (Claude, Cursor, Copilot, Codex, ...):

  agent_pr_ledger  - the ledger for one repository (definition v1.0)
  agent_pr_watch   - one pull request at the moment it closes

Same code paths as the GitHub Action. Read-only. Contacts nothing but api.github.com.
Set GITHUB_TOKEN for 5,000 requests/hour (60 without).

  python3 src/mcp_server.py            # speaks MCP on stdin/stdout
"""
from __future__ import annotations
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from ledger import build, render, DEFINITION_VERSION, TOOL_VERSION  # noqa: E402
import watch as watchmod  # noqa: E402

PROTOCOL = "2025-06-18"
TOOLS = [
    {
        "name": "agent_pr_ledger",
        "title": "Agent PR ledger",
        "description": ("Count, for one GitHub repository, how many pull requests opened by coding agents "
                        "(Copilot, Devin, OpenAI Codex, Cursor, Claude Code, Jules) were merged with a human "
                        "review record and how many without (definition v1.0). It counts; it does not score. "
                        "Read-only; nothing is sent anywhere."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "OWNER/REPO, e.g. microsoft/vscode"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 1000, "default": 100,
                          "description": "How many of the most recent pull requests to scan"},
                "lang": {"type": "string", "enum": ["en", "ja"], "default": "en"},
                "month": {"type": "string", "pattern": "^[0-9]{4}-(0[1-9]|1[0-2])$",
                          "description": "Restrict counts to one month, YYYY-MM"},
                "format": {"type": "string", "enum": ["text", "json"], "default": "text"},
            },
            "required": ["repo"],
        },
    },
    {
        "name": "agent_pr_watch",
        "title": "Agent PR watch",
        "description": ("Apply definition v1.0 to a single pull request: was it agent-authored, and if merged, "
                        "does a review record from someone other than the author exist before the merge? "
                        "Read-only."),
        "inputSchema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "OWNER/REPO"},
                "pr": {"type": "integer", "minimum": 1, "description": "Pull request number"},
                "lang": {"type": "string", "enum": ["en", "ja"], "default": "en"},
            },
            "required": ["repo", "pr"],
        },
    },
]


def _text(s: str, is_error: bool = False) -> dict:
    return {"content": [{"type": "text", "text": s}], "isError": is_error}


def call_tool(name: str, args: dict) -> dict:
    if name == "agent_pr_ledger":
        repo = str(args["repo"])
        led = build(repo, int(args.get("limit", 100)))
        month = args.get("month")
        if args.get("format") == "json":
            rows = [r for r in led["rows"] if not month or r["created_at"][:7] == month]
            out = {**led, "rows": rows, "month": month}
            return _text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
        return _text(render(led, month, args.get("lang", "en")))
    if name == "agent_pr_watch":
        w = watchmod.watch(str(args["repo"]), int(args["pr"]))
        return _text(watchmod.render(w, args.get("lang", "en")) + "\n\n" + json.dumps(w, ensure_ascii=False))
    return _text(f"unknown tool: {name}", True)


def handle(msg: dict):
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", PROTOCOL),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "agent-pr-ledger", "title": "agent-pr-ledger", "version": TOOL_VERSION},
            "instructions": ("agent-pr-ledger counts agent-authored pull requests merged with and without a human "
                             f"review record (definition v{DEFINITION_VERSION}). It counts; it does not score. "
                             "Do not present its output as a judgement of a repository or a comparison between agents.")}}
    if method is None or method.startswith("notifications/"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}}
    if method == "tools/call":
        p = msg.get("params", {})
        try:
            return {"jsonrpc": "2.0", "id": mid, "result": call_tool(p.get("name", ""), p.get("arguments") or {})}
        except Exception as e:  # noqa: BLE001
            return {"jsonrpc": "2.0", "id": mid, "result": _text(f"{type(e).__name__}: {e}", True)}
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}


def serve(inp=sys.stdin, out=sys.stdout):
    for line in inp:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out.write(json.dumps({"jsonrpc": "2.0", "id": None,
                                  "error": {"code": -32700, "message": "parse error"}}) + "\n")
            out.flush()
            continue
        resp = handle(msg)
        if resp is not None:
            out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            out.flush()


def cli():
    serve()


if __name__ == "__main__":
    serve()
