"""MCP server (zero-dependency stdio JSON-RPC) exposing the gateway tool surface.

Protocol surface: initialize / tools/list / tools/call (+ notifications).
Every tools/call goes through ToolGateway.dispatch — the same enforcement the
CLI uses. What is NOT on this surface: gate.approve / task.confirm. An agent
connected through MCP physically cannot approve a paid operation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .paths import workspace_root
from .tools import build_runtime

JSONRPC = "2.0"
SERVER_INFO = {"name": "neagent", "version": "2.0.0"}


def _result(req_id, payload) -> dict:
    return {"jsonrpc": JSONRPC, "id": req_id, "result": payload}


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": JSONRPC, "id": req_id, "error": {"code": code, "message": message}}


def _tool_error_message(exc: Exception) -> str:
    """Human-readable, agent-actionable error lines (what the LLM will read)."""
    return str(exc)


def handle(req: dict, rt) -> dict | None:
    method = req.get("method", "")
    req_id = req.get("id")
    if method == "initialize":
        return _result(req_id, {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": {"tools": {}},
        })
    if method == "notifications/initialized":
        return None  # notification: no response
    if method == "tools/list":
        return _result(req_id, {"tools": [
            {
                "name": t["name"],
                "description": f"{t['description']} "
                               f"[perms:{','.join(k for k, v in t['permissions'].items() if v) or 'none'}"
                               f" states:{'+'.join(t['allowed_states']) or 'any-non-terminal'}]",
                "inputSchema": {"type": "object", "properties": {
                    "task_id": {"type": "string"},
                    "kwargs": {"type": "object",
                               "description": "tool-specific keyword arguments"},
                }, "required": []},
            } for t in rt.gateway.list_tools()
        ]})
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        task_id = args.get("task_id")
        kwargs = args.get("kwargs") or {}
        try:
            data = rt.gateway.dispatch(name, task_id=task_id, **kwargs)
            return _result(req_id, {
                "content": [{"type": "text",
                             "text": json.dumps(data, ensure_ascii=False, indent=2,
                                                default=str)}],
                "isError": False,
            })
        except Exception as exc:
            return _result(req_id, {
                "content": [{"type": "text", "text": _tool_error_message(exc)}],
                "isError": True,
            })
    if req_id is not None:
        return _error(req_id, -32601, f"method not found: {method}")
    return None


def main(workspace: Path | None = None) -> int:
    from .paths import load_dotenv
    load_dotenv()  # credentials live in .env; real env vars win
    rt = build_runtime(workspace or workspace_root())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(req, rt)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
