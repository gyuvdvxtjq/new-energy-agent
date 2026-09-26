"""Evidence chain: manifest hashing + honest comparison."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from neagent.core import evidence  # noqa: E402


class ManifestTests(unittest.TestCase):
    def test_sha256_and_missing_files_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            f = d / "a.txt"
            f.write_text("hello", encoding="utf-8")
            doc = evidence.manifest("t", [f, d / "missing.txt"], [], {})
            self.assertEqual(len(doc["inputs"]), 1)
            self.assertEqual(doc["inputs"][0]["sha256"],
                             "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824")

    def test_write_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p = evidence.write_manifest("t9", Path(d) / "evidence", [], [],
                                        {"stage": "test"})
            doc = json.loads(Path(p).read_text(encoding="utf-8"))
            self.assertEqual(doc["task_id"], "t9")
            self.assertEqual(doc["meta"]["stage"], "test")


class CompareReportTests(unittest.TestCase):
    def test_records_nested_and_honest(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "mp.json"
            db.write_text(json.dumps({
                "records": [{"material_id": "mp-149", "band_gap": 0.61,
                             "formula_pretty": "Si"}]}), encoding="utf-8")
            rep = evidence.compare_report(
                {"converged": True, "evidence_level": "computed",
                 "final_etot_ev": -213.66}, db)
            self.assertEqual(rep["computed"]["evidence_level"], "computed")
            self.assertEqual(rep["database_native"]["source_id"], "mp-149")
            self.assertAlmostEqual(rep["database_native"]["band_gap_ev"], 0.61)
            self.assertFalse(rep["comparable"])       # honest: not comparable
            self.assertIn("NOT expected", rep["why"])

    def test_flat_record_also_works(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "mp.json"
            db.write_text(json.dumps({"material_id": "mp-1", "band_gap": 1.0}),
                          encoding="utf-8")
            rep = evidence.compare_report({"converged": False}, db)
            self.assertEqual(rep["database_native"]["source_id"], "mp-1")


if __name__ == "__main__":
    unittest.main()
