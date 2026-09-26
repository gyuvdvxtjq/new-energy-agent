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


def load_dotenv(path: Path | None = None) -> None:
    """Minimal .env loader (KEY=VALUE lines, # comments, optional quotes).

    Docs tell users to keep credentials in .env — so the runtime must actually
    read it. Real environment variables always win (setdefault). Called once
    by each entry point (CLI / MCP server), not at import time.
    """
    import os
    p = Path(path) if path else repo_root() / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
