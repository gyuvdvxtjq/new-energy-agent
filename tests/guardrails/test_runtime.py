"""Adversarial guardrail tests: the runtime must reject what it claims to reject."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from neagent.tools import build_runtime  # noqa: E402
from neagent.runtime.gate import GateBlockedError  # noqa: E402
from neagent.runtime.gateway import (ToolFailedError, UnknownToolError,  # noqa: E402
                                     WrongStateError)
from neagent.runtime.state import IllegalTransitionError  # noqa: E402


class RuntimeGuardrailTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rt = build_runtime(Path(self._tmp.name))
        self.gw = self.rt.gateway

    def tearDown(self):
        self._tmp.cleanup()

    def _new_task(self, task_id="t1", workflow="compute"):
        self.gw.dispatch("task.init", task_id=task_id, title="x", workflow=workflow)
        return task_id

    def _inputs_dir(self, task_id: str) -> Path:
        d = Path(self._tmp.name) / "tasks" / task_id / "inputs"
        d.mkdir(parents=True, exist_ok=True)
        (d / "INPUT").write_text("INPUT_PARAMETERS\n", encoding="utf-8")
        (d / "STRU").write_text("ATOMIC_POSITIONS\n", encoding="utf-8")
        return d

    # -- state machine -------------------------------------------------------
    def test_illegal_transition_rejected(self):
        tid = self._new_task()
        with self.assertRaises(IllegalTransitionError):
            self.rt.store.transition(tid, "execute")  # draft → running: no such edge

    def test_finish_requires_running(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        with self.assertRaises(WrongStateError):
            self.gw.dispatch("task.finish", task_id=tid)

    def test_failed_task_resumes_to_planned(self):
        tid = self._new_task(workflow="predict")
        self.gw.dispatch("task.plan", task_id=tid)
        self.gw.dispatch("task.execute", task_id=tid)   # local shortcut
        self.rt.store.transition(tid, "fail")           # simulate mid-run crash
        self.gw.dispatch("task.resume", task_id=tid, note="recovered")
        self.assertEqual(self.rt.store.state(tid).value, "planned")

    def test_terminal_states_freeze_but_read_only_survives(self):
        tid = self._new_task(workflow="predict")
        self.gw.dispatch("task.plan", task_id=tid)
        self.gw.dispatch("task.execute", task_id=tid)
        self.gw.dispatch("task.finish", task_id=tid)
        self.gw.dispatch("task.cancel", task_id=tid)    # needs_review → cancelled
        doc = self.gw.dispatch("task.status", task_id=tid)  # read-only must pass
        self.assertEqual(doc["state"], "cancelled")
        with self.assertRaises(WrongStateError):
            self.gw.dispatch("task.plan", task_id=tid)  # writes must be frozen

    # -- high-risk fix #4: compute workflow cannot use the local shortcut ----
    def test_compute_workflow_cannot_local_shortcut_to_running(self):
        tid = self._new_task(workflow="compute")
        self.gw.dispatch("task.plan", task_id=tid)
        with self.assertRaises(IllegalTransitionError):
            self.gw.dispatch("task.execute", task_id=tid)  # must NOT skip approval
        self.assertEqual(self.rt.store.state(tid).value, "planned")

    # -- approval gate -------------------------------------------------------
    def test_paid_run_blocked_without_approval(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self._inputs_dir(tid)
        with self.assertRaises(GateBlockedError):
            self.gw.dispatch("dft.run", task_id=tid)

    # -- high-risk fix #1: approval is bound to content ----------------------
    def test_approval_for_different_content_rejected(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        indir = self._inputs_dir(tid)
        # approve a request bound to DIFFERENT files than what will run
        other = Path(self._tmp.name) / "other_inputs"
        other.mkdir()
        (other / "INPUT").write_text("INPUT_PARAMETERS\necutwfc 999\n",
                                     encoding="utf-8")
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt",
                                    content_paths=[other / "INPUT"])
        self.rt.gate.approve(tid, approver="test")
        self.rt.store.transition(tid, "request_submit")
        self.rt.store.transition(tid, "confirm")
        with patch("neagent.core.abacus.ssh_execute") as fake:
            with self.assertRaises(GateBlockedError):
                self.gw.dispatch("dft.run", task_id=tid)
            fake.assert_not_called()  # the blocked path never reached SSH

    def test_approved_matching_content_proceeds(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self._inputs_dir(tid)
        indir = Path(self._tmp.name) / "tasks" / tid / "inputs"
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt",
                                    content_paths=sorted(indir.glob("*")))
        self.rt.gate.approve(tid, approver="test")
        self.rt.store.transition(tid, "request_submit")
        self.rt.store.transition(tid, "confirm")
        with patch("neagent.core.abacus.ssh_execute",
                   return_value={"ok": True, "stage": "run", "log": "x",
                                 "stdout": "", "stderr": ""}) as fake:
            self.gw.dispatch("dft.run", task_id=tid)
        fake.assert_called_once()
        self.assertEqual(self.rt.store.state(tid).value, "running")

    # -- high-risk fix #2: replan resets a stale approval --------------------
    def test_replan_resets_stale_approval_to_pending(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self._inputs_dir(tid)
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt",
                                    content_paths=[])
        self.rt.gate.approve(tid, approver="test")
        # fail → resume → replan: the OLD approval must not survive
        self.rt.store.transition(tid, "request_submit")
        self.rt.store.transition(tid, "confirm")
        self.rt.store.transition(tid, "execute")
        self.rt.store.transition(tid, "fail")
        self.rt.store.transition(tid, "resume")
        self.rt.gate.create_request(tid, command="x2", inputs="x2",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt",
                                    content_paths=[])
        self.assertEqual(self.rt.gate.status(tid), "PENDING")
        with self.assertRaises(GateBlockedError):
            self.rt.gate.require(tid)
        # approve() must also refuse to re-approve a non-PENDING record
        self.rt.gate.approve(tid, approver="again")  # back to PENDING, ok now
        with self.assertRaises(ValueError):
            self.rt.gate.approve(tid, approver="twice")  # already APPROVED

    def test_approve_rejects_non_pending(self):
        tid = self._new_task()
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt")
        self.rt.gate.approve(tid, approver="test")
        with self.assertRaises(ValueError):
            self.rt.gate.approve(tid, approver="again")  # already APPROVED

    # -- high-risk fix #3: failure does not advance state --------------------
    def test_failed_run_does_not_advance_state(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self._inputs_dir(tid)
        # bind the approval to the SAME file set the dft.run resolver uses
        # (every file under inputs/)
        indir = Path(self._tmp.name) / "tasks" / tid / "inputs"
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt",
                                    content_paths=sorted(indir.glob("*")))
        self.rt.gate.approve(tid, approver="test")
        self.rt.store.transition(tid, "request_submit")
        self.rt.store.transition(tid, "confirm")
        with patch("neagent.core.abacus.ssh_execute",
                   return_value={"ok": False, "stage": "preflight",
                                 "stdout": "", "stderr": "no abacus on PATH"}):
            with self.assertRaises(ToolFailedError):
                self.gw.dispatch("dft.run", task_id=tid)
        # state must still be approved, not running
        self.assertEqual(self.rt.store.state(tid).value, "approved")

    def test_no_self_approval_tool_on_surface(self):
        names = {t["name"] for t in self.gw.list_tools()}
        for banned in ("gate.approve", "task.confirm"):
            self.assertNotIn(banned, names)

    def test_unknown_tool_rejected(self):
        with self.assertRaises(UnknownToolError):
            self.gw.dispatch("gate.approve", task_id="whatever")

    # -- audit ---------------------------------------------------------------
    def test_blocked_calls_are_audited(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        try:
            self.gw.dispatch("dft.run", task_id=tid)
        except GateBlockedError:
            pass
        log = (Path(self._tmp.name) / "logs" / "audit.jsonl").read_text(encoding="utf-8")
        entries = [json.loads(l) for l in log.splitlines() if l.strip()]
        self.assertTrue(any(e["tool"] == "dft.run" and e["event"] == "call"
                            for e in entries))


class TaskIdValidationTests(unittest.TestCase):
    """task_id is a path segment locally AND remotely — it must be a safe token."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rt = build_runtime(Path(self._tmp.name))
        self.gw = self.rt.gateway

    def tearDown(self):
        self._tmp.cleanup()

    def test_traversal_and_shell_ids_rejected(self):
        for bad in ("../evil", "..", ".", "a/b", "x;rm -rf ~", "a b", "a\\b"):
            with self.assertRaises(ValueError, msg=f"task_id {bad!r} accepted"):
                self.gw.dispatch("task.init", task_id=bad, title="x")

    def test_legit_ids_accepted(self):
        for good in ("t1", "demo-predict", "si-scf-2", "run_2026.09.26"):
            self.gw.dispatch("task.init", task_id=good, title="x")
            self.assertEqual(self.rt.store.state(good).value, "draft")


class ComputeCompletionPathTests(unittest.TestCase):
    """The only way a compute task enters running is the gated dft.run."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rt = build_runtime(Path(self._tmp.name))
        self.gw = self.rt.gateway

    def tearDown(self):
        self._tmp.cleanup()

    def _approved_compute_task(self, tid="c1") -> str:
        self.gw.dispatch("task.init", task_id=tid, title="x", workflow="compute")
        self.gw.dispatch("task.plan", task_id=tid)
        indir = Path(self._tmp.name) / "tasks" / tid / "inputs"
        indir.mkdir(parents=True, exist_ok=True)
        (indir / "INPUT").write_text("INPUT_PARAMETERS\n", encoding="utf-8")
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="n/a", risks="none",
                                    failure_policy="halt",
                                    content_paths=sorted(indir.rglob("*")))
        self.rt.gate.approve(tid, approver="test")
        self.rt.store.transition(tid, "request_submit")
        self.rt.store.transition(tid, "confirm")
        return tid

    def test_approved_compute_cannot_execute_flip(self):
        tid = self._approved_compute_task()
        with self.assertRaises(WrongStateError):
            self.gw.dispatch("task.execute", task_id=tid)  # state-only bypass
        self.assertEqual(self.rt.store.state(tid).value, "approved")

    def test_np_mpi_string_rejected_before_any_ssh(self):
        tid = self._approved_compute_task()
        from neagent.core import abacus
        with patch("neagent.core.sshrun.run") as ssh_run:
            with self.assertRaises(abacus.AbacusError):
                # CLI dispatch passes every kwarg as a string — this must be
                # caught as an int-coercion error, not interpolated remotely
                self.gw.dispatch("dft.run", task_id=tid, np_mpi="2;echo pwned")
            ssh_run.assert_not_called()
        self.assertEqual(self.rt.store.state(tid).value, "approved")

    def test_plan_content_files_cover_nested_orbital_dirs(self):
        tid = self._approved_compute_task()
        indir = Path(self._tmp.name) / "tasks" / tid / "inputs"
        orb = indir / "orbital_dir"
        orb.mkdir()
        (orb / "Si.orb").write_text("orb", encoding="utf-8")
        from neagent.tools import _plan_content_files
        names = [f.name for f in _plan_content_files(indir)]
        self.assertIn("Si.orb", names)  # nested files are part of the approval


if __name__ == "__main__":
    unittest.main()
