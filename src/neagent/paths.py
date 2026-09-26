"""Workspace paths — one place that knows where runtime artifacts live."""

from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def workspace_root() -> Path:
    """Default workspace: <repo>/workspace (override via NEAGENT_WORKSPACE)."""
    import os
    env = os.environ.get("NEAGENT_WORKSPACE")
    return Path(env) if env else repo_root() / "workspace"
