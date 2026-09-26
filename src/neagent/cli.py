"""neagent CLI — the human/CI channel into the same runtime the MCP server uses.

Subcommands:
  selfcheck                     run guardrail self-test (state/gate/gateway)
  task new|status|list|plan|execute|finish|resume|cancel
  gate approve|status           HUMAN approval channel (not exposed to agents)
  dispatch <tool> [--kw v ...]  call any gateway tool directly
  demo predict                  run the demo prediction chain end-to-end
  mcp                           start the MCP stdio server
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _runtime(workspace: str | None):
    from .tools import build_runtime
    return build_runtime(Path(workspace) if workspace else None)


def cmd_selfcheck(_a) -> int:
    from .runtime import selfcheck
    return selfcheck.main()


def _print(doc) -> None:
    print(json.dumps(doc, ensure_ascii=False, indent=2, default=str))


def cmd_task(a) -> int:
    rt = _runtime(a.workspace)
    if a.op == "new":
        _print(rt.gateway.dispatch("task.init", task_id=a.task_id,
                                   title=a.title or a.task_id or "untitled",
                                   workflow=a.workflow))
    elif a.op == "status":
        _print(rt.gateway.dispatch("task.status", task_id=a.task_id))
    elif a.op == "list":
        _print(rt.gateway.dispatch("task.list"))
    elif a.op in ("plan", "execute", "cancel", "finish"):
        _print(rt.gateway.dispatch(f"task.{a.op}", task_id=a.task_id))
    elif a.op == "resume":
        _print(rt.gateway.dispatch("task.resume", task_id=a.task_id, note=a.note or ""))
    else:
        print(f"unknown op {a.op}", file=sys.stderr)
        return 2
    return 0


def cmd_gate(a) -> int:
    """Human-only approval channel. Deliberately NOT a gateway/MCP tool."""
    rt = _runtime(a.workspace)
    if a.op == "approve":
        rt.gate.approve(a.task_id, approver=a.approver)
        rt.store.transition(a.task_id, "confirm")
        _print({"task_id": a.task_id, "approval": "APPROVED",
                "state": rt.store.state(a.task_id).value})
    else:
        _print({"task_id": a.task_id, "approval": rt.gate.status(a.task_id),
                "state": rt.store.state(a.task_id).value})
    return 0


def cmd_dispatch(a) -> int:
    rt = _runtime(a.workspace)
    kwargs = {}
    for kv in a.kwarg or []:
        k, _, v = kv.partition("=")
        kwargs[k] = v
    task_id = kwargs.pop("task_id", None)
    _print(rt.gateway.dispatch(a.tool, task_id=task_id, **kwargs))
    return 0


def cmd_demo(a) -> int:
    rt = _runtime(a.workspace)
    doc = rt.gateway.dispatch("task.init", task_id=a.task_id or "demo-predict",
                              title="demo: NCM retention smoke test", workflow="predict")
    tid = doc["task_id"]
    rt.gateway.dispatch("task.plan", task_id=tid)
    rt.gateway.dispatch("task.execute", task_id=tid)
    rt.gateway.dispatch("data.quality", task_id=tid, profile_name="ncm")
    rt.gateway.dispatch("features.derive", task_id=tid, profile_name="ncm")
    result = rt.gateway.dispatch("models.baseline", task_id=tid, profile_name="ncm")
    rt.gateway.dispatch("evidence.report", task_id=tid)  # needs_review → completed
    _print({"task": tid, "state": rt.store.state(tid).value, "result": result})
    return 0


def cmd_mcp(_a) -> int:
    from .mcp_server import main as mcp_main
    return mcp_main()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="neagent", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--workspace", help="workspace root (default <repo>/workspace)")
    p.add_argument("--workspace", help=argparse.SUPPRESS)  # accepted before subcommand too
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("selfcheck", parents=[common],
                   help="guardrail self-test").set_defaults(fn=cmd_selfcheck)

    t = sub.add_parser("task", parents=[common])
    t.add_argument("op", choices=["new", "status", "list", "plan", "execute",
                                  "finish", "resume", "cancel"])
    t.add_argument("task_id", nargs="?")
    t.add_argument("--title")
    t.add_argument("--workflow", default="predict",
                   choices=["predict", "compute", "compare"])
    t.add_argument("--note")
    t.set_defaults(fn=cmd_task)

    g = sub.add_parser("gate", parents=[common], help="human approval channel")
    g.add_argument("op", choices=["approve", "status"])
    g.add_argument("task_id")
    g.add_argument("--approver", default="user")
    g.set_defaults(fn=cmd_gate)

    d = sub.add_parser("dispatch", parents=[common], help="call a gateway tool directly")
    d.add_argument("tool")
    d.add_argument("kwarg", nargs="*", help="key=value pairs; task_id=<id> required")
    d.set_defaults(fn=cmd_dispatch)

    m = sub.add_parser("demo", parents=[common])
    m.add_argument("what", choices=["predict"])
    m.add_argument("--task-id")
    m.set_defaults(fn=cmd_demo)

    sub.add_parser("mcp", parents=[common], help="start MCP stdio server").set_defaults(fn=cmd_mcp)
    return p


def main(argv: list[str] | None = None) -> int:
    from .paths import load_dotenv
    load_dotenv()  # credentials live in .env; real env vars win
    a = build_parser().parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
