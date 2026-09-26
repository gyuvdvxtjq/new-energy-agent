"""Task lifecycle state machine — the single source of truth for legal transitions.

This module is the ONLY code allowed to change task state. The MCP server and
CLI must go through TaskStore.transition(); the host LLM has no other channel.
"""

from __future__ import annotations

import re
import time
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

_TASK_ID_RE = re.compile(r"[A-Za-z0-9._-]+")


def validate_task_id(task_id: str) -> str:
    """task_id becomes a path segment (workspace dirs, the remote ~/neagent/<id>
    namespace), so it is restricted to a shell- and path-safe alphabet. Pure-dot
    ids ('.', '..') pass the regex but are traversal, so they are rejected too."""
    if (not task_id or not _TASK_ID_RE.fullmatch(task_id)
            or set(task_id) <= {"."}):
        raise ValueError(
            f"illegal task_id {task_id!r}: must match [A-Za-z0-9._-]+ and not "
            "be all dots — it is used as a path segment locally and remotely")
    return task_id


class TaskState(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    RUNNING = "running"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATES = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}

# (current_state, trigger) -> next_state
TRANSITIONS: dict[tuple[str, str], str] = {
    ("draft", "plan"): "planned",
    ("draft", "cancel"): "cancelled",
    ("planned", "request_submit"): "waiting_approval",
    ("planned", "cancel"): "cancelled",
    ("waiting_approval", "confirm"): "approved",
    ("waiting_approval", "reject"): "planned",
    ("waiting_approval", "cancel"): "cancelled",
    ("approved", "execute"): "running",
    ("approved", "cancel"): "cancelled",
    ("running", "finish"): "needs_review",
    ("running", "fail"): "failed",
    ("needs_review", "accept"): "completed",
    ("needs_review", "revise"): "planned",
    ("needs_review", "cancel"): "cancelled",
    ("failed", "resume"): "planned",
    ("failed", "cancel"): "cancelled",
}

# Simplified local path: light-weight local workflows (quality/predict) never
# touch the approval states; they run draft -> planned -> running -> ... directly.
LOCAL_SHORTCUTS: dict[tuple[str, str], str] = {
    ("planned", "execute"): "running",  # allowed only for tools NOT marked `paid`
}


class IllegalTransitionError(Exception):
    """Raised when a trigger is not legal in the current state."""

    def __init__(self, current: str, trigger: str):
        self.current = current
        self.trigger = trigger
        legal = sorted(t for (s, t) in TRANSITIONS if s == current)
        super().__init__(
            f"illegal transition: state '{current}' does not accept trigger "
            f"'{trigger}'. legal triggers here: {legal or '(none — terminal state)'}"
        )


class TaskStore:
    """YAML-backed task store. One file per task under workspace/tasks/<id>/task.yaml."""

    def __init__(self, workspace_root: Path):
        self.root = Path(workspace_root)
        self.tasks_dir = self.root / "tasks"

    def path(self, task_id: str) -> Path:
        return self.tasks_dir / task_id / "task.yaml"

    def create(self, task_id: str, title: str, workflow: str) -> dict[str, Any]:
        validate_task_id(task_id)
        p = self.path(task_id)
        if p.exists():
            raise FileExistsError(f"task '{task_id}' already exists: {p}")
        doc = {
            "task_id": task_id,
            "title": title,
            "workflow": workflow,  # predict | compute | compare
            "state": TaskState.DRAFT.value,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "steps": [],
            "history": [
                {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "from": None,
                 "to": TaskState.DRAFT.value, "trigger": "create"}
            ],
        }
        p.parent.mkdir(parents=True, exist_ok=True)
        self._write(p, doc)
        return doc

    def load(self, task_id: str) -> dict[str, Any]:
        validate_task_id(task_id)
        p = self.path(task_id)
        if not p.exists():
            raise FileNotFoundError(f"unknown task '{task_id}': {p} not found")
        return yaml.safe_load(p.read_text(encoding="utf-8"))

    def state(self, task_id: str) -> TaskState:
        return TaskState(self.load(task_id)["state"])

    def transition(self, task_id: str, trigger: str, *, allow_local_shortcut: bool = False) -> TaskState:
        """Apply a trigger. Raises IllegalTransitionError if not legal.

        allow_local_shortcut is set by the gateway for non-paid tools; it never
        applies to paid triggers (request_submit/confirm/execute on paid tools).
        The gateway additionally passes allow_local_shortcut=False for paid
        workflows (compute) so the paid path is the only path.
        """
        doc = self.load(task_id)
        current = doc["state"]
        if allow_local_shortcut:
            # the shortcut exists for lightweight LOCAL workflows (predict);
            # a compute workflow must go through the approval states
            if doc.get("workflow") == "compute":
                raise IllegalTransitionError(current, trigger)
        key = (current, trigger)
        next_state = TRANSITIONS.get(key)
        if next_state is None and allow_local_shortcut:
            next_state = LOCAL_SHORTCUTS.get(key)
        if next_state is None:
            raise IllegalTransitionError(current, trigger)
        # terminal-state safety: completed/cancelled have no outgoing triggers
        # in TRANSITIONS, so they are frozen by lookup; 'failed' intentionally
        # keeps resume/cancel as recovery paths.
        if current in {s.value for s in TERMINAL_STATES} and current not in {"failed"}:
            raise IllegalTransitionError(current, trigger)
        doc["state"] = next_state
        doc["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        doc["history"].append(
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "from": current,
             "to": next_state, "trigger": trigger}
        )
        self._write(self.path(task_id), doc)
        return TaskState(next_state)

    def record_step(self, task_id: str, step: dict[str, Any]) -> None:
        doc = self.load(task_id)
        doc["steps"].append(step)
        doc["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._write(self.path(task_id), doc)

    @staticmethod
    def _write(p: Path, doc: dict[str, Any]) -> None:
        tmp = p.with_suffix(".tmp")
        tmp.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
        tmp.replace(p)
