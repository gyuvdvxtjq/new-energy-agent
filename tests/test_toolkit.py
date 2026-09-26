"""CLI smoke tests through subprocess (the human/CI channel)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ToolkitTests(unittest.TestCase):
    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "neagent.cli", *args],
            cwd=ROOT, text=True, capture_output=True, env=env,
            encoding="utf-8", errors="replace")  # Windows GBK console must not crash us

    def test_selfcheck(self):
        r = self.run_cli("selfcheck")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ALL GUARDRAIL CHECKS PASSED", r.stdout)

    def test_demo_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_cli("demo", "predict", "--workspace", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            payload = json.loads(r.stdout[r.stdout.index("{"):])
            self.assertEqual(payload["state"], "completed")  # demo runs to done
            self.assertIn("mae", payload["result"])

    def test_paid_run_blocked_via_cli(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_cli("task", "new", "smoke1", "--workflow", "compute",
                         "--title", "smoke", "--workspace", d)
            self.run_cli("task", "plan", "smoke1", "--workspace", d)
            r = self.run_cli("dispatch", "dft.run", "task_id=smoke1",
                             "--workspace", d)
            self.assertNotEqual(r.returncode, 0)
            combined = (r.stdout + r.stderr).lower()
            self.assertIn("gate", combined)   # blocked by the approval gate
            # state unchanged by the blocked attempt
            r = self.run_cli("task", "status", "smoke1", "--workspace", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("planned", r.stdout)

    def test_status_readable_after_terminal(self):
        with tempfile.TemporaryDirectory() as d:
            self.run_cli("task", "new", "smoke2", "--workspace", d)
            self.run_cli("task", "plan", "smoke2", "--workspace", d)
            self.run_cli("task", "execute", "smoke2", "--workspace", d)
            self.run_cli("task", "finish", "smoke2", "--workspace", d)
            self.run_cli("task", "cancel", "smoke2", "--workspace", d)
            r = self.run_cli("task", "status", "smoke2", "--workspace", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("cancelled", r.stdout)


if __name__ == "__main__":
    unittest.main()
