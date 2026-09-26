"""Human approval gate — file-based, human-channel-only approval records.

Design invariants:
  * an approval is a FILE under workspace/approvals/<task_id>.md that records
    what will run, the estimated cost, the risks and the failure policy
  * `require()` is what paid tools hit before executing; PENDING/MISSING
    approvals raise GateBlockedError
  * approving is a HUMAN act (edit the file or `neagent gate approve`) — it is
    deliberately NOT exposed as a gateway/MCP tool, so an agent can never
    approve itself
"""

from __future__ import annotations

import re
import time
from pathlib import Path


class GateBlockedError(RuntimeError):
    """Raised when a gated operation has no APPROVED record."""


class ApprovalGate:
    def __init__(self, workspace_root: Path):
        self.root = Path(workspace_root)
        self.dir = self.root / "approvals"

    def path(self, task_id: str) -> Path:
        return self.dir / f"{task_id}.md"

    def create_request(self, task_id: str, *, command: str, inputs: str,
                       estimated_cost: str, risks: str,
                       failure_policy: str) -> Path:
        """Write a PENDING approval request (idempotent for the same task)."""
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.path(task_id)
        if p.exists():
            return p
        doc = f"""# Approval request — {task_id}

status: PENDING
created: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Command

```
{command}
```

## Inputs

{inputs}

## Estimated cost

{estimated_cost}

## Risks

{risks}

## Failure policy

{failure_policy}

---

To approve: set `status: PENDING` above to `APPROVED` and add your
name/date on the line below (or run `neagent gate approve {task_id}`).
"""
        p.write_text(doc, encoding="utf-8")
        return p

    def status(self, task_id: str) -> str:
        p = self.path(task_id)
        if not p.exists():
            return "MISSING"
        m = re.search(r"^status:\s*(\S+)", p.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else "MALFORMED"

    def approve(self, task_id: str, *, approver: str = "user") -> None:
        p = self.path(task_id)
        if not p.exists():
            raise FileNotFoundError(f"no approval request for '{task_id}': {p}")
        text = p.read_text(encoding="utf-8")
        text = re.sub(r"^status:\s*PENDING\s*$",
                      f"status: APPROVED\napproved_by: {approver}"
                      f"\napproved_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                      text, count=1, flags=re.M)
        p.write_text(text, encoding="utf-8")

    def require(self, task_id: str) -> None:
        s = self.status(task_id)
        if s != "APPROVED":
            raise GateBlockedError(
                f"approval gate blocked: task '{task_id}' approval status is "
                f"'{s}' (need APPROVED). Paid operations require a human "
                "confirmation recorded in workspace/approvals/ — there is no "
                "agent-side way to self-approve."
            )
