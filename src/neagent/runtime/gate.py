"""Human approval gate — file-based, human-channel-only approval records.

Design invariants:
  * an approval is a FILE under workspace/approvals/<task_id>.md that records
    what will run, the estimated cost, the risks and the failure policy
  * an approval is BOUND to the content it was issued for: dft.plan records
    a SHA256 fingerprint of the planned inputs, `require()` re-checks it at
    submit time, and every replan rewrites the request (resetting it to
    PENDING) — a decision can never be reused for different content
  * `require()` is what paid tools hit before executing; PENDING/MISSING
    approvals raise GateBlockedError
  * approving is a HUMAN act (edit the file or `neagent gate approve`) — it is
    deliberately NOT exposed as a gateway/MCP tool, so an agent can never
    approve itself
"""

from __future__ import annotations

import hashlib
import re
import time
from pathlib import Path


class GateBlockedError(RuntimeError):
    """Raised when a gated operation has no APPROVED record."""


def fingerprint(paths: list[Path]) -> str:
    """Content hash over files/directories. Directories are walked
    recursively with stable relative-path labels, so the hash is bound to
    content, not to where the content lives."""
    h = hashlib.sha256()

    def feed(label: str, p: Path) -> None:
        h.update(label.encode("utf-8"))
        try:
            h.update(p.read_bytes())
        except OSError:
            h.update(b"<missing>")

    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    feed(f.relative_to(p).as_posix(), f)
        else:
            feed(p.name, p)
    return h.hexdigest()


class ApprovalGate:
    def __init__(self, workspace_root: Path):
        self.root = Path(workspace_root)
        self.dir = self.root / "approvals"

    def path(self, task_id: str) -> Path:
        return self.dir / f"{task_id}.md"

    def create_request(self, task_id: str, *, command: str, inputs: str,
                       estimated_cost: str, risks: str,
                       failure_policy: str,
                       content_paths: list[Path] | None = None) -> Path:
        """Write a PENDING approval request. NOT idempotent: a replan always
        rewrites the file, which RESETS any previous decision — a stale
        APPROVED record must never survive a new plan. `content_paths`
        (used by dft.plan) binds the approval to the exact content hash;
        a hand-written request without it leaves content binding to the
        human who wrote it."""
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.path(task_id)
        fp_line = (f"content_sha256: {fingerprint(content_paths)}\n"
                   if content_paths else "")
        doc = f"""# Approval request — {task_id}

status: PENDING
created: {time.strftime('%Y-%m-%d %H:%M:%S')}
{fp_line}
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

    def content_fingerprint(self, task_id: str) -> str | None:
        """The content hash recorded at request time, if the request was
        content-bound (dft.plan always binds; hand-written requests may not)."""
        p = self.path(task_id)
        if not p.exists():
            return None
        m = re.search(r"^content_sha256:\s*([0-9a-f]{64})",
                      p.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None

    def approve(self, task_id: str, *, approver: str = "user") -> None:
        p = self.path(task_id)
        if not p.exists():
            raise FileNotFoundError(f"no approval request for '{task_id}': {p}")
        text = p.read_text(encoding="utf-8")
        if not re.search(r"^status:\s*PENDING\s*$", text, re.M):
            raise ValueError(
                f"approval request for '{task_id}' is not PENDING "
                f"(status: {self.status(task_id)}). Only a pending request "
                "can be approved; if a replan reset it, review the new "
                "content before approving."
            )
        text = re.sub(r"^status:\s*PENDING\s*$",
                      f"status: APPROVED\napproved_by: {approver}"
                      f"\napproved_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                      text, count=1, flags=re.M)
        p.write_text(text, encoding="utf-8")

    def require(self, task_id: str, *,
                content_paths: list[Path] | None = None) -> None:
        s = self.status(task_id)
        if s != "APPROVED":
            raise GateBlockedError(
                f"approval gate blocked: task '{task_id}' approval status is "
                f"'{s}' (need APPROVED). Paid operations require a human "
                "confirmation recorded in workspace/approvals/ — there is no "
                "agent-side way to self-approve."
            )
        if content_paths:
            recorded = self.content_fingerprint(task_id)
            current = fingerprint(content_paths)
            if recorded != current:
                raise GateBlockedError(
                    f"approval gate blocked: task '{task_id}' was approved for "
                    f"different content (recorded sha256 {recorded or 'none'} != "
                    f"current {current}). The approval request must be regenerated "
                    "by dft.plan and re-approved — a human decision cannot be "
                    "reused for different inputs."
                )
