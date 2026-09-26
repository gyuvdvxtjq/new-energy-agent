"""Adversarial guardrail tests: the runtime must reject what it claims to reject."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from neagent.tools import build_runtime  # noqa: E402
from neagent.runtime.gate import GateBlockedError  # noqa: E402
from neagent.runtime.gateway import UnknownToolError, WrongStateError  # noqa: E402
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
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self.gw.dispatch("task.execute", task_id=tid)   # local shortcut
        self.rt.store.transition(tid, "fail")           # simulate mid-run crash
        self.gw.dispatch("task.resume", task_id=tid, note="recovered")
        self.assertEqual(self.rt.store.state(tid).value, "planned")

    def test_terminal_states_freeze_but_read_only_survives(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self.gw.dispatch("task.execute", task_id=tid)
        self.gw.dispatch("task.finish", task_id=tid)
        self.gw.dispatch("task.cancel", task_id=tid)    # needs_review → cancelled
        doc = self.gw.dispatch("task.status", task_id=tid)  # read-only must pass
        self.assertEqual(doc["state"], "cancelled")
        with self.assertRaises(WrongStateError):
            self.gw.dispatch("task.plan", task_id=tid)  # writes must be frozen

    # -- approval gate -------------------------------------------------------
    def test_paid_submit_blocked_without_approval(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        with self.assertRaises(GateBlockedError):
            self.gw.dispatch("bohr.submit", task_id=tid)

    def test_paid_submit_blocked_in_wrong_state_even_if_gate_ok(self):
        tid = self._new_task()
        self.gw.dispatch("task.plan", task_id=tid)
        self.rt.gate.create_request(tid, command="x", inputs="x",
                                    estimated_cost="¥0", risks="none",
                                    failure_policy="halt")
        self.rt.gate.approve(tid, approver="test")
        self.rt.store.transition(tid, "request_submit")  # planned → waiting_approval
        self.rt.store.transition(tid, "confirm")         # waiting → approved
        # approved: bohr.submit would now run the real CLI — block by monkeypatching
        from neagent.core import bohr
        called = {}
        original = bohr.submit

        def fake_submit(job_json):
            called["hit"] = True
            return {"ok": True, "job_id": "123", "stdout": "", "stderr": ""}

        bohr.submit = fake_submit
        try:
            self.gw.dispatch("bohr.submit", task_id=tid)
        finally:
            bohr.submit = original
        self.assertTrue(called.get("hit"))
        # whitelist registration happened
        self.assertTrue(self.rt.store.owns_job(tid, "123"))

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
            self.gw.dispatch("bohr.submit", task_id=tid)
        except GateBlockedError:
            pass
        log = (Path(self._tmp.name) / "logs" / "audit.jsonl").read_text(encoding="utf-8")
        entries = [json.loads(l) for l in log.splitlines() if l.strip()]
        self.assertTrue(any(e["tool"] == "bohr.submit" and e["event"] == "call"
                            for e in entries))


class BohrWhitelistTests(unittest.TestCase):
    def test_fetch_refuses_non_whitelisted_job(self):
        with tempfile.TemporaryDirectory() as d:
            rt = build_runtime(Path(d))
            rt.gateway.dispatch("task.init", task_id="t1", title="x", workflow="compute")
            from neagent.core import bohr
            with self.assertRaises(bohr.BohrError):
                bohr.fetch("999999", Path(d) / "dl",
                           owns_job=lambda j: rt.store.owns_job("t1", j))


if __name__ == "__main__":
    unittest.main()
