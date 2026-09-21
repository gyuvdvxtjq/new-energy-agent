#!/usr/bin/env python3
"""Generate a reviewable remote-computation plan; never submits a job."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("goal")
    parser.add_argument("--structure", type=Path, required=True)
    parser.add_argument("--method", default="未指定")
    parser.add_argument("--host", default="未指定")
    parser.add_argument("--scheduler", default="slurm")
    parser.add_argument("--out", type=Path, default=Path("approvals/computation-plan.json"))
    args = parser.parse_args()

    plan = {
        "status": "waiting_user_approval",
        "submitted": False,
        "goal": args.goal,
        "structure": str(args.structure),
        "method": args.method,
        "host_alias": args.host,
        "scheduler": args.scheduler,
        "resource_estimate": "待用户/Agent 根据实际结构、方法和队列确认",
        "inputs": [str(args.structure)],
        "outputs": ["raw_output/", "parsed_result.json", "run.log"],
        "commands": [
            "ssh <host_alias>",
            "mkdir -p <remote_project_dir>",
            "# upload inputs and inspect before submission",
            f"{args.scheduler} submit submit.sh",
        ],
        "approval_required_because": [
            "remote execution",
            "potentially long-running or resource-consuming task",
        ],
        "failure_policy": "pause and report; no unlimited automatic retries",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote reviewable plan: {args.out}")
    print("No remote command was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
