import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ToolkitTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT / "new_energy_agent.py"), *args], cwd=ROOT, text=True, capture_output=True)

    def test_doctor(self):
        self.assertEqual(self.run_cli("doctor").returncode, 0)

    def test_demo_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            result = self.run_cli("predict", "--demo", "--group", "source_group", "--out", str(Path(d) / "metrics.json"))
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads((Path(d) / "metrics.json").read_text())
            self.assertIn("metrics", payload)
            self.assertEqual(payload["split_rule"], "GroupShuffleSplit by source_group")

    def test_dft_parse(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d); raw = d / "OUTCAR"; out = d / "parsed.json"
            raw.write_text("free energy TOTEN = -1.25 eV\nE-fermi : 4.2\nvolume of cell : 88.0\n")
            result = self.run_cli("parse-dft", str(raw), "--out", str(out))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(out.read_text())["values"]["energy_eV"], -1.25)

if __name__ == "__main__": unittest.main()
