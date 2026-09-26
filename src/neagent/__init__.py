"""neagent — a vertical-domain agent runtime with code-enforced guardrails.

Layering (see docs/ARCHITECTURE.md):
  runtime/  state machine + approval gate + tool gateway (the ONLY enforcement)
  core/     deterministic science/engineering capabilities (CLI-usable alone)
  tools.py  the single registry binding core into the gateway
  mcp_server.py / cli.py  two front doors into the same runtime
"""

__version__ = "2.0.0"
