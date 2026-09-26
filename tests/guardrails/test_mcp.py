"""MCP server protocol tests (in-process handler + stdio smoke)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from neagent.mcp_server import handle  # noqa: E402
from neagent.tools import build_runtime  # noqa: E402


class McpHandlerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.rt = build_runtime(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_initialize(self):
        resp = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, self.rt)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "neagent")

    def test_tools_list_excludes_self_approval(self):
        resp = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, self.rt)
        names = {t["name"] for t in resp["result"]["tools"]}
        self.assertIn("bohr.submit", names)
        self.assertNotIn("gate.approve", names)
        self.assertNotIn("task.confirm", names)

    def test_tools_call_success(self):
        handle({"jsonrpc": "2.0", "id": 1, "method": "initialize"}, self.rt)
        resp = handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                       "params": {"name": "task.init",
                                  "arguments": {"task_id": "m1",
                                                "kwargs": {"title": "x"}}}}, self.rt)
        payload = json.loads(resp["result"]["content"][0]["text"])
        self.assertEqual(payload["state"], "draft")

    def test_tools_call_error_is_data_not_crash(self):
        resp = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                       "params": {"name": "task.status",
                                  "arguments": {"task_id": "nope", "kwargs": {}}}},
                      self.rt)
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("nope", resp["result"]["content"][0]["text"])

    def test_notification_returns_none(self):
        self.assertIsNone(handle({"jsonrpc": "2.0",
                                  "method": "notifications/initialized"}, self.rt))


if __name__ == "__main__":
    unittest.main()
