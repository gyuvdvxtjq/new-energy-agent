#!/usr/bin/env python3
"""Derive transparent composition features without requiring pymatgen.

This parser intentionally supports simple chemical formulae and records its limits.
Use pymatgen for disordered/parenthesized/charged formulas.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


TOKEN = re.compile(r"([A-Z][a-z]?)([0-9]*(?:\.[0-9]+)?)")


def parse_formula(value: str) -> dict[str, float]:
    result: dict[str, float] = {}
    position = 0
    for match in TOKEN.finditer(value or ""):
        if match.start() != position:
            raise ValueError(f"unsupported formula syntax near {value[position:]!r}")
        element, amount = match.groups()
        result[element] = result.get(element, 0.0) + (float(amount) if amount else 1.0)
        position = match.end()
    if position != len(value or "") or not result:
        raise ValueError(f"cannot parse formula: {value!r}")
    return result


def parse_elements(value: str) -> dict[str, float]:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, dict):
            return {str(key): float(amount) for key, amount in parsed.items()}
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return parse_formula(value)


def derive(composition: dict[str, float]) -> dict[str, float]:
    total = sum(composition.values())
    features = {
        "composition_total_atoms": total,
        "composition_element_count": float(len(composition)),
    }
    if total <= 0:
        return features
    for element, amount in composition.items():
        features[f"element_fraction_{element}"] = amount / total
    for element in ("Li", "Na", "K", "Ni", "Co", "Mn", "Fe", "P", "S", "O", "F"):
        features.setdefault(f"element_fraction_{element}", 0.0)
    return features


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--formula-column", default="Name")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    frame = pd.read_csv(args.csv_path)
    if args.formula_column not in frame.columns:
        raise SystemExit(f"formula column not found: {args.formula_column}")
    rows = []
    failures = []
    for index, value in frame[args.formula_column].items():
        try:
            rows.append(derive(parse_elements(str(value))))
        except ValueError as error:
            rows.append({})
            failures.append({"row": int(index), "value": str(value), "error": str(error)})
    features = pd.DataFrame(rows, index=frame.index)
    result = pd.concat([frame, features], axis=1)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    report = {
        "input": str(args.csv_path),
        "output": str(args.out),
        "rows": len(result),
        "parse_failures": failures[:20],
        "parse_failure_count": len(failures),
        "limitations": [
            "Simple formula parser only; parenthesized, disordered, charged, and site-occupancy formulas require pymatgen.",
            "Derived fractions are descriptors, not evidence of a causal composition effect.",
        ],
    }
    report_path = args.out.with_suffix(args.out.suffix + ".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
