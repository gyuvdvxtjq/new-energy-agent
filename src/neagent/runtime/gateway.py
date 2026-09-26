"""Tool gateway — the ONLY execution path for every agent-invocable tool.

Every dispatch:
  1. is audited BEFORE any check (blocked/illegal attempts are exactly what
     the security log is for)
  2. hits the approval gate first for `paid` tools (the clearest failure mode
     for a paid op is "you have no approval", not a state error)
  3. enforces the state contract: tools declare `allowed_states`; terminal
     states reject everything except read-only inspection
  4. applies the declared `success_trigger` through the state machine

There is no other channel: the MCP server and the CLI both end here.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .gate import ApprovalGate
from .state import TERMINAL_STATES, TaskState, TaskStore


class UnknownToolError(RuntimeError):
    pass


class WrongStateError(RuntimeError):
    def __init__(self, tool: str, current: str, allowed: list[str]):
        self.tool, self.current, self.allowed = tool, current, allowed
        super().__init__(
            f"tool '{tool}' cannot run in state '{current}' "
            f"(allowed: {allowed or ['any-non-terminal']}). "
            "Use task.status / task.resume first."
        )


class ToolFailedError(RuntimeError):
    """Raised when a tool ran but reported failure (ok_key falsy) — the
    state machine intentionally does not advance on failure."""

    def __init__(self, tool: str, task_id: str | None, ok_key: str,
                 detail: Any = None):
        self.tool, self.task_id, self.ok_key, self.detail = tool, task_id, ok_key, detail
        msg = (f"tool '{tool}' reported {ok_key}=false for task '{task_id}' — "
               f"state NOT advanced. Inspect the result, fix the cause, retry.")
        if detail:
            msg += f"\nlast output: {str(detail)[-500:]}"
        super().__init__(msg)


@dataclass
class ToolSpec:
    name: str
    fn: Callable[..., Any]
    desc: str
    read: bool = False
    write: bool = False
    network: bool = False
    paid: bool = False
    gated: bool = False
    requires_task: bool = True
    allowed_states: list[str] = field(default_factory=list)
    success_trigger: str | None = None
    ok_key: str | None = None
    content_paths_resolver: Callable[[str], list[Path]] | None = None
    """ok_key: result field that gates success_trigger. If set (e.g. dft
    tools return {"ok": bool}), the state advances ONLY when result[ok_key]
    is truthy — a failed submit/fetch must not move the task forward.
    content_paths_resolver: for gated tools, returns the file set the
    approval must be bound to (checked by the gate at dispatch time)."""


def _short(result: Any, limit: int = 300) -> Any:
    try:
        s = json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        s = str(result)
    return s[:limit] if len(s) > limit else result


class ToolGateway:
    def __init__(self, root: Path, store: TaskStore, gate: ApprovalGate):
        self.root = Path(root)
        self.store = store
        self.gate = gate
        self.tools: dict[str, ToolSpec] = {}
        self.log_dir = self.root / "logs"

    # -- registration --------------------------------------------------------
    def register(self, spec: ToolSpec) -> None:
        if spec.name in self.tools:
            raise ValueError(f"tool '{spec.name}' registered twice")
        self.tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        """Tool manifest for MCP tools/list — note what is ABSENT: gate.approve
        and task.confirm exist nowhere on this surface."""
        return [
            {
                "name": s.name,
                "description": s.desc,
                "permissions": {"read": s.read, "write": s.write,
                                "network": s.network, "paid": s.paid},
                "allowed_states": s.allowed_states or ["any-non-terminal"],
                "gated": s.gated,
            }
            for s in self.tools.values()
        ]

    # -- audit ---------------------------------------------------------------
    def _audit(self, event: str, tool_name: str, task_id: str | None,
               payload: Any) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event": event, "tool": tool_name, "task_id": task_id,
            "payload": payload,
        }
        with open(self.log_dir / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    # -- dispatch ------------------------------------------------------------
    def dispatch(self, tool_name: str, task_id: str | None = None,
                 **kwargs: Any) -> Any:
        spec = self.tools.get(tool_name)
        if spec is None:
            raise UnknownToolError(f"unknown tool '{tool_name}'")

        # audit BEFORE any check: blocked/illegal attempts are exactly what
        # the security log is for
        self._audit("call", tool_name, task_id, kwargs)

        if spec.requires_task:
            if not task_id:
                raise ValueError(f"tool '{tool_name}' requires a task_id")
            # gated tools hit the approval gate FIRST: the clearest failure
            # mode for a paid op is "you have no approval", not a state error.
            # content_paths_resolver (set by the tool registration) binds the
            # approval to the exact input content at dispatch time — BEFORE
            # the state check, so a stale approval is caught even if the
            # task state alone would have allowed it.
            if spec.gated:
                assert task_id
                content = (spec.content_paths_resolver(task_id)
                           if spec.content_paths_resolver else None)
                self.gate.require(task_id, content_paths=content)
            current = self.store.state(task_id)
            # terminal states reject everything except read-only inspection
            # (task.status/task.list on a completed task) and tools that
            # explicitly operate on them (task.resume on 'failed', task.cancel)
            readonly = spec.read and not spec.write
            if current in TERMINAL_STATES:
                if not readonly and current.value not in spec.allowed_states:
                    raise WrongStateError(tool_name, current.value, spec.allowed_states)
            elif spec.allowed_states and current.value not in spec.allowed_states:
                raise WrongStateError(tool_name, current.value, spec.allowed_states)

        result = spec.fn(task_id=task_id, **kwargs)

        if spec.requires_task and task_id and spec.success_trigger:
            # result gating: a tool that reports failure (ok=False) must NOT
            # advance the state machine — "the call returned" is not success
            if spec.ok_key is None or (isinstance(result, dict)
                                       and result.get(spec.ok_key)):
                # the planned→running shortcut is for LOCAL workflows only;
                # a compute workflow's only path to running is the paid,
                # gated dft.run (approved→running)
                task_doc = self.store.load(task_id)
                shortcut_ok = (not spec.paid
                               and task_doc.get("workflow") != "compute")
                self.store.transition(
                    task_id, spec.success_trigger,
                    allow_local_shortcut=shortcut_ok,
                )
            else:
                detail = result.get("stderr") or result.get("stdout") \
                    if isinstance(result, dict) else None
                raise ToolFailedError(tool_name, task_id, spec.ok_key, detail)
        self._audit("ok", tool_name, task_id, {"result": _short(result)})

        if spec.requires_task and task_id:
            self.store.record_step(task_id, {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "tool": tool_name,
            })
        return result
