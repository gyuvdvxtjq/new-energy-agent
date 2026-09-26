"""Quality/leakage preflight for tabular scientific data (ported from v1)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def quality_report(csv_path: Path, target: str | None = None,
                   group: list[str] | None = None) -> dict:
    group = group or []
    df = pd.read_csv(csv_path)
    report = {
        "input": str(csv_path), "rows": len(df), "columns": list(df.columns),
        "target": target, "groups": group,
        "missing": {c: int(df[c].isna().sum()) for c in df.columns},
        "duplicate_rows": int(df.duplicated().sum()), "warnings": [],
    }
    if target and target not in df:
        report["warnings"].append(f"target missing: {target}")
    for g in group:
        if g not in df:
            report["warnings"].append(f"group missing: {g}")
        else:
            report.setdefault("group_cardinality", {})[g] = int(df[g].nunique(dropna=True))
    id_like = [c for c in df.columns
               if c.lower() in {"id", "record_id", "material_id", "sample_id",
                                "filename", "source_id"}
               or c.lower().endswith("_id")]
    report["identifier_like_columns"] = id_like
    if id_like:
        report["warnings"].append(
            "identifier-like columns must not be used as features without "
            "scientific justification")
    if not group:
        report["warnings"].append(
            "no grouping rule supplied; random splitting may leak material, "
            "source, batch, or protocol information")
    if target and target in df:
        report["target_summary"] = {
            "non_null": int(df[target].notna().sum()),
            "unique": int(df[target].nunique(dropna=True)),
        }
    return report


def write_report(report: dict, out_path: Path) -> None:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("csv", type=Path)
    p.add_argument("--target")
    p.add_argument("--group", action="append", default=[])
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    report = quality_report(a.csv, a.target, a.group)
    write_report(report, a.out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not any(w.startswith("target missing") for w in report["warnings"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
