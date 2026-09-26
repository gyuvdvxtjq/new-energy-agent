"""End-to-end predict chain against the real NCM dataset (no network)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from neagent.tools import build_runtime  # noqa: E402


class PredictChainTests(unittest.TestCase):
    def test_full_chain_reaches_completed(self):
        with tempfile.TemporaryDirectory() as d:
            rt = build_runtime(Path(d))
            gw = rt.gateway
            gw.dispatch("task.init", task_id="p1", title="x", workflow="predict")
            gw.dispatch("task.plan", task_id="p1")
            gw.dispatch("task.execute", task_id="p1")
            q = gw.dispatch("data.quality", task_id="p1", profile_name="ncm")
            self.assertGreater(q["rows"], 0)
            f = gw.dispatch("features.derive", task_id="p1", profile_name="ncm")
            self.assertIn("elemental amounts", f["note"] or "")
            m = gw.dispatch("models.baseline", task_id="p1", profile_name="ncm")
            self.assertIn("random train_test_split", m["split_rule"])  # honest rule
            self.assertEqual(rt.store.state("p1").value, "needs_review")

    def test_crash_recovery(self):
        with tempfile.TemporaryDirectory() as d:
            rt = build_runtime(Path(d))
            gw = rt.gateway
            gw.dispatch("task.init", task_id="p3", title="x", workflow="predict")
            gw.dispatch("task.plan", task_id="p3")
            gw.dispatch("task.execute", task_id="p3")
            rt.store.transition("p3", "fail")            # simulate mid-run crash
            gw.dispatch("task.resume", task_id="p3", note="after crash")
            # back to planned → rerun the local shortcut
            gw.dispatch("task.execute", task_id="p3")
            self.assertEqual(rt.store.state("p3").value, "running")


if __name__ == "__main__":
    unittest.main()
