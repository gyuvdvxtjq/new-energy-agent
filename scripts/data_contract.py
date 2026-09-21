#!/usr/bin/env python3
"""Dependency-free CSV inspection for an initial materials data contract."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


def inspect_csv(path: Path, target: str | None) -> dict:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)

    missing = {field: sum(1 for row in rows if not (row.get(field) or "").strip()) for field in fields}
    duplicates = Counter(tuple((row.get(field) or "").strip() for field in fields) for row in rows)
    duplicate_rows = sum(count - 1 for count in duplicates.values() if count > 1)
    return {
        "path": str(path),
        "rows": len(rows),
        "columns": fields,
        "target": target,
        "target_present": target in fields if target else None,
        "missing_by_column": missing,
        "duplicate_rows_exact": duplicate_rows,
        "notes": [
            "This is a schema and quality preflight, not a model result.",
            "Confirm material, batch, source, structure-family, and time grouping before splitting.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--target")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = inspect_csv(args.csv_path, args.target)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if result["target_present"] is not False else 2


if __name__ == "__main__":
    raise SystemExit(main())
