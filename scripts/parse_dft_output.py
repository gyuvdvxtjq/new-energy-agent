#!/usr/bin/env python3
"""Parse common scalar signals from VASP OUTCAR-like text."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

PATTERNS = {"energy_eV": r"free\s+energy\s+TOTEN\s*=\s*([+-]?[0-9.]+)", "fermi_energy_eV": r"E-fermi\s*:\s*([+-]?[0-9.]+)", "volume_A3": r"volume of cell\s*:\s*([+-]?[0-9.]+)"}
def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("path", type=Path); p.add_argument("--out", type=Path, required=True); a = p.parse_args(); text = a.path.read_text(errors="replace")
    result = {"input": str(a.path), "parser": "parse_dft_output.py", "values": {}, "matches": {}, "warnings": []}
    for key, pattern in PATTERNS.items():
        values = [float(x) for x in re.findall(pattern, text, re.I)]; result["matches"][key] = len(values)
        if values: result["values"][key] = values[-1]
        else: result["warnings"].append(f"not found: {key}")
    result["convergence"] = {"electronic": bool(re.search(r"EDIFF is reached|reached required accuracy", text, re.I)), "ionic": bool(re.search(r"reached required accuracy", text, re.I))}
    result["limitations"] = ["Scalar parser only; inspect full OUTCAR/vasprun.xml and settings before interpretation."]
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
if __name__ == "__main__": raise SystemExit(main())
