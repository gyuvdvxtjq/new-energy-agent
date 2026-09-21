#!/usr/bin/env python3
"""Validate a sub-agent handoff using only the Python standard library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "task_id": str,
    "role": str,
    "status": str,
    "completed_steps": list,
    "findings": list,
    "uncertainties": list,
    "next_actions": list,
}
ALLOWED_STATUS = {"draft", "running", "completed", "blocked", "needs_review"}


def validate(payload: dict) -> list[str]:
    errors = []
    for key, expected in REQUIRED.items():
        if key not in payload:
            errors.append(f"missing: {key}")
        elif not isinstance(payload[key], expected):
            errors.append(f"wrong type: {key} (expected {expected.__name__})")
    if payload.get("status") not in ALLOWED_STATUS:
        errors.append(f"invalid status: {payload.get('status')!r}")
    if payload.get("requires_approval") is not None and not isinstance(payload["requires_approval"], bool):
        errors.append("wrong type: requires_approval")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"invalid JSON: {error}")
        return 2
    errors = validate(payload)
    if errors:
        print("handoff invalid:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"handoff valid: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
