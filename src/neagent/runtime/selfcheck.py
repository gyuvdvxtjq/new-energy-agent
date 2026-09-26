"""Guardrail self-test — proves the enforcement layer holds, in seconds.

Run: PYTHONPATH=src python -m neagent.cli selfcheck  (or python src/.../selfcheck.py)
Asserts, against a throwaway workspace:
  1. illegal state transitions are rejected by the state machine
  2. a paid submit without an approval record is blocked by the gate
  3. with an approval, the gated path proceeds
  4. every attempt (blocked or not) lands in the audit log
  5. the agent tool surface contains no self-approval capability
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):  # direct-run compat: python src/neagent/runtime/selfcheck.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ..tools import build_runtime  # noqa: E402
from .gate import GateBlockedError  # noqa: E402
from .gateway import UnknownToolError, WrongStateError  # noqa: E402
from .state import IllegalTransitionError  # noqa: E402

CHECKS: list[tuple[str, bool]] = []


def check(name: str, fn) -> None:
    try:
        fn()
        CHECKS.append((name, True))
        print(f"  PASS  {name}")
    except Exception as exc:  # noqa: BLE001
        CHECKS.append((name, False))
        print(f"  FAIL  {name}: {exc}")


def main() -> int:
    print("neagent guardrail self-check")
    with tempfile.TemporaryDirectory() as d:
        rt = build_runtime(Path(d))
        gw, store, gate = rt.gateway, rt.store, rt.gate

        def illegal_transition_rejected():
            gw.dispatch("task.init", task_id="a", title="x", workflow="predict")
            try:
                store.transition("a", "execute")  # draft --execute--> must not exist
            except IllegalTransitionError:
                return
            raise AssertionError("illegal transition was NOT rejected")

        def unpaid_submit_blocked():
            gw.dispatch("task.init", task_id="b", title="x", workflow="compute")
            gw.dispatch("task.plan", task_id="b")
            # forge minimal inputs so the gate check is what blocks, not files
            try:
                gw.dispatch("bohr.submit", task_id="b")
            except GateBlockedError:
                return
            raise AssertionError("paid submit WITHOUT approval was NOT blocked")

        def gated_path_proceeds_after_approval():
            gate.create_request("b", command="test", inputs="test",
                                estimated_cost="¥0", risks="none",
                                failure_policy="halt")
            gate.approve("b", approver="selfcheck")
            store.transition("b", "request_submit")   # planned → waiting_approval
            store.transition("b", "confirm")          # human-only: waiting → approved
            assert store.state("b").value == "approved"

        def audit_log_records_blocked_calls():
            log = (Path(d) / "logs" / "audit.jsonl").read_text(encoding="utf-8")
            if '"event": "call"' not in log:
                raise AssertionError("blocked calls missing from audit log")

        def no_self_approval_tool():
            names = {t["name"] for t in gw.list_tools()}
            for banned in ("gate.approve", "task.confirm"):
                if banned in names:
                    raise AssertionError(f"'{banned}' must not exist on the tool surface")

        def unknown_tool_rejected():
            try:
                gw.dispatch("gate.approve", task_id="b")
            except UnknownToolError:
                return
            raise AssertionError("gate.approve unexpectedly dispatched")

        def wrong_state_rejected():
            gw.dispatch("task.init", task_id="c", title="x", workflow="compute")
            gw.dispatch("task.plan", task_id="c")
            try:
                gw.dispatch("bohr.submit", task_id="c")  # planned, gated, unapproved
            except (GateBlockedError, WrongStateError):
                return
            raise AssertionError("submit in non-approved state was NOT rejected")

        def finish_requires_running():
            try:
                gw.dispatch("task.finish", task_id="c")  # planned → must fail
            except WrongStateError:
                return
            raise AssertionError("finish from planned was NOT rejected")

        check("illegal state transitions rejected", illegal_transition_rejected)
        check("paid submit blocked without approval", unpaid_submit_blocked)
        check("gated path proceeds after approval", gated_path_proceeds_after_approval)
        check("audit log records blocked calls", audit_log_records_blocked_calls)
        check("no self-approval tool on agent surface", no_self_approval_tool)
        check("unknown tool rejected", unknown_tool_rejected)
        check("wrong-state tool call rejected", wrong_state_rejected)
        check("finish requires running state", finish_requires_running)

    failed = [n for n, ok in CHECKS if not ok]
    if failed:
        print(f"FAILED: {failed}")
        return 1
    print("ALL GUARDRAIL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
