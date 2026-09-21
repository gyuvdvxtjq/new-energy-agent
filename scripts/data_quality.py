#!/usr/bin/env python3
"""Quality and leakage preflight for tabular scientific data."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path); p.add_argument("--target"); p.add_argument("--group", action="append", default=[]); p.add_argument("--out", type=Path, required=True)
    a = p.parse_args(); df = pd.read_csv(a.csv)
    report = {"input": str(a.csv), "rows": len(df), "columns": list(df.columns), "target": a.target, "groups": a.group, "missing": {c: int(df[c].isna().sum()) for c in df.columns}, "duplicate_rows": int(df.duplicated().sum()), "warnings": []}
    if a.target and a.target not in df: report["warnings"].append(f"target missing: {a.target}")
    for g in a.group:
        if g not in df: report["warnings"].append(f"group missing: {g}")
        else: report.setdefault("group_cardinality", {})[g] = int(df[g].nunique(dropna=True))
    id_like = [c for c in df.columns if c.lower() in {"id", "record_id", "material_id", "sample_id", "filename", "source_id"} or c.lower().endswith("_id")]
    report["identifier_like_columns"] = id_like
    if id_like: report["warnings"].append("identifier-like columns must not be used as features without scientific justification")
    if not a.group: report["warnings"].append("no grouping rule supplied; random splitting may leak material, source, batch, or protocol information")
    if a.target and a.target in df: report["target_summary"] = {"non_null": int(df[a.target].notna().sum()), "unique": int(df[a.target].nunique(dropna=True))}
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not any(w.startswith("target missing") for w in report["warnings"]) else 2
if __name__ == "__main__": raise SystemExit(main())
