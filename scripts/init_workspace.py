#!/usr/bin/env python3
"""Create a reproducible project workspace for one research task."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\-\u4e00-\u9fff]+", "-", value, flags=re.UNICODE)
    return value.strip("-")[:80] or "research-task"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("title")
    parser.add_argument("--task-id", default=None)
    args = parser.parse_args()

    task_id = args.task_id or f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{slugify(args.title)}"
    for directory in (
        "workspace/handoffs",
        "papers",
        "extracted",
        "datasets/raw",
        "datasets/processed",
        "structures",
        "calculations",
        "reports",
        "logs",
        "approvals",
    ):
        (ROOT / directory).mkdir(parents=True, exist_ok=True)

    (ROOT / "workspace/current_task.yaml").write_text(
        "\n".join(
            [
                f"task_id: {task_id}",
                f"title: {args.title}",
                "status: draft",
                "mode: needs_clarification",
                "evidence_status: unverified",
                "requires_approval: false",
                "completed_steps: []",
                "next_actions: []",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (ROOT / "workspace/task_log.md").write_text(
        f"# {args.title}\n\n- task_id: `{task_id}`\n- created_at: `{datetime.now(timezone.utc).isoformat()}`\n- status: `draft`\n\n",
        encoding="utf-8",
    )
    print(f"created task: {task_id}")
    print(f"workspace: {ROOT / 'workspace'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
