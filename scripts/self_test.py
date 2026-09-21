#!/usr/bin/env python3
"""Run local, no-network acceptance checks."""
from pathlib import Path
import json, subprocess, sys, tempfile
ROOT = Path(__file__).resolve().parents[1]
def run(*args): return subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True, check=False)
def main() -> int:
    checks = [("doctor", run("scripts/doctor.py").returncode == 0)]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d); (p / "outcar").write_text("free  energy   TOTEN  =      -123.456 eV\nE-fermi : 5.12\nvolume of cell : 100.2\nreached required accuracy\n")
        ok = run("scripts/parse_dft_output.py", str(p / "outcar"), "--out", str(p / "parsed.json")).returncode == 0 and json.loads((p / "parsed.json").read_text())["values"]["energy_eV"] == -123.456
        checks.append(("dft_parser", ok))
    for name, ok in checks: print(f"{name}: {'ok' if ok else 'FAIL'}")
    return 0 if all(ok for _, ok in checks) else 1
if __name__ == "__main__": raise SystemExit(main())
