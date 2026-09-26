"""Guardrail self-test — proves the enforcement layer holds, in seconds.

Run: PYTHONPATH=src python -m neagent.cli selfcheck  (or python src/.../selfcheck.py)
Asserts, against a throwaway workspace:
  1. illegal state transitions are rejected by the state machine
  2. a paid remote run without an approval record is blocked by the gate
  3. an APPROVED record for DIFFERENT content does not satisfy the gate
  4. a replan resets a stale APPROVED record back to PENDING
  5. a tool that reports failure (ok=False) does not advance the state
  6. compute workflows cannot use the planned→running local shortcut,
     and an approved compute task cannot flip into running without dft.run
  7. a predict task can run its full lifecycle to completed
  8. every attempt (blocked or not) lands in the audit log
  9. the agent tool surface contains no self-approval capability
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

if __package__ in (None, ""):  # direct-run compat: python src/neagent/runtime/selfcheck.py
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ..tools import build_runtime  # noqa: E402
from .gate import GateBlockedError  # noqa: E402
from .gateway import ToolFailedError, UnknownToolError, WrongStateError  # noqa: E402
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

        def unpaid_run_blocked():
            gw.dispatch("task.init", task_id="b", title="x", workflow="compute")
            gw.dispatch("task.plan", task_id="b")
            # forge minimal inputs so the gate check is what blocks, not files
            indir = Path(d) / "tasks" / "b" / "inputs"
            indir.mkdir(parents=True, exist_ok=True)
            (indir / "INPUT").write_text("INPUT_PARAMETERS\n", encoding="utf-8")
            try:
                gw.dispatch("dft.run", task_id="b")
            except GateBlockedError:
                return
            raise AssertionError("paid run WITHOUT approval was NOT blocked")

        def approval_bound_to_content():
            # write a fake approval file for a DIFFERENT content hash
            gate.create_request("b", command="test", inputs="test",
                                estimated_cost="n/a", risks="none",
                                failure_policy="halt",
                                content_paths=[Path(d) / "other.txt"])
            gate.approve("b", approver="selfcheck")
            try:
                gw.dispatch("dft.run", task_id="b")
            except GateBlockedError:
                return
            raise AssertionError(
                "approval for DIFFERENT content was NOT rejected")

        def replan_resets_stale_approval():
            # approve current content, then replan: the approval must reset
            gate.create_request("b", command="test", inputs="test",
                                estimated_cost="n/a", risks="none",
                                failure_policy="halt",
                                content_paths=[Path(d) / "tasks" / "b" / "inputs" / "INPUT"])
            gate.approve("b", approver="selfcheck")
            gate.create_request("b", command="test2", inputs="test2",
                                estimated_cost="n/a", risks="none",
                                failure_policy="halt",
                                content_paths=[Path(d) / "tasks" / "b" / "inputs" / "INPUT"])
            if gate.status("b") != "PENDING":
                raise AssertionError(
                    f"replan left stale decision (status: {gate.status('b')})")

        def failed_tool_does_not_advance_state():
            gw.dispatch("task.init", task_id="f", title="x", workflow="compute")
            gw.dispatch("task.plan", task_id="f")
            indir = Path(d) / "tasks" / "f" / "inputs"
            indir.mkdir(parents=True, exist_ok=True)
            (indir / "INPUT").write_text("INPUT_PARAMETERS\n", encoding="utf-8")
            gate.create_request("f", command="t", inputs="t", estimated_cost="n/a",
                                risks="none", failure_policy="halt",
                                content_paths=sorted(indir.glob("*")))
            gate.approve("f", approver="selfcheck")
            store.transition("f", "request_submit")
            store.transition("f", "confirm")
            with patch("neagent.core.abacus.ssh_execute",
                       return_value={"ok": False, "stage": "preflight",
                                     "stdout": "", "stderr": "no abacus"}):
                try:
                    gw.dispatch("dft.run", task_id="f")
                except ToolFailedError:
                    pass
            if store.state("f").value != "approved":
                raise AssertionError(
                    f"failed run advanced state to {store.state('f').value}")

        def compute_cannot_local_shortcut():
            gw.dispatch("task.init", task_id="s", title="x", workflow="compute")
            gw.dispatch("task.plan", task_id="s")
            try:
                gw.dispatch("task.execute", task_id="s")  # must NOT skip approval
            except IllegalTransitionError:
                return
            raise AssertionError(
                "compute workflow reached running without approval")

        def approved_compute_cannot_flip_execute():
            # task 'f' is still in approved (its failed run did not advance it);
            # a state-only flip must not be a path past the gated dft.run
            try:
                gw.dispatch("task.execute", task_id="f")
            except WrongStateError:
                return
            raise AssertionError(
                "approved compute task reached running via task.execute")

        def predict_chain_reaches_completed():
            gw.dispatch("task.init", task_id="p", title="x", workflow="predict")
            gw.dispatch("task.plan", task_id="p")
            gw.dispatch("task.execute", task_id="p")
            gw.dispatch("data.quality", task_id="p", profile_name="ncm")
            gw.dispatch("features.derive", task_id="p", profile_name="ncm")
            gw.dispatch("models.baseline", task_id="p", profile_name="ncm")
            gw.dispatch("evidence.report", task_id="p")
            if store.state("p").value != "completed":
                raise AssertionError(
                    f"predict chain stuck at {store.state('p').value}")

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
                gw.dispatch("dft.run", task_id="c")  # planned, gated, unapproved
            except (GateBlockedError, WrongStateError):
                return
            raise AssertionError("run in non-approved state was NOT rejected")

        def finish_requires_running():
            try:
                gw.dispatch("task.finish", task_id="c")  # planned → must fail
            except WrongStateError:
                return
            raise AssertionError("finish from planned was NOT rejected")

        check("illegal state transitions rejected", illegal_transition_rejected)
        check("paid run blocked without approval", unpaid_run_blocked)
        check("approval bound to content (stale hash rejected)", approval_bound_to_content)
        check("replan resets stale approval to PENDING", replan_resets_stale_approval)
        check("failed tool does not advance state", failed_tool_does_not_advance_state)
        check("compute workflow cannot use local shortcut", compute_cannot_local_shortcut)
        check("approved compute cannot flip execute", approved_compute_cannot_flip_execute)
        check("predict chain reaches completed", predict_chain_reaches_completed)
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
