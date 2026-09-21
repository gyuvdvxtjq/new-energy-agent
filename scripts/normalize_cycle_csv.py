#!/usr/bin/env python3
"""Normalize a cycle-test CSV into one row per cycle without inventing labels."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--header-line", type=int, default=14)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    frame = pd.read_csv(args.csv_path, skiprows=args.header_line - 1)
    required = {"Cycle C", "Capacity [Ah]", "Temperature Cell [degC]", "Current [A]", "Voltage [V]"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise SystemExit(f"missing required columns: {', '.join(missing)}")

    numeric = ["Cycle C", "Capacity [Ah]", "Temperature Cell [degC]", "Current [A]", "Voltage [V]"]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["Cycle C"])
    result = (
        frame.groupby("Cycle C", as_index=False)
        .agg(
            capacity_ah_max=("Capacity [Ah]", "max"),
            capacity_ah_min=("Capacity [Ah]", "min"),
            temperature_cell_c_mean=("Temperature Cell [degC]", "mean"),
            current_a_abs_max=("Current [A]", lambda values: values.abs().max()),
            voltage_v_min=("Voltage [V]", "min"),
            voltage_v_max=("Voltage [V]", "max"),
            points=("Cycle C", "size"),
        )
        .rename(columns={"Cycle C": "cycle"})
        .sort_values("cycle")
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(args.out, index=False)
    print(f"wrote {len(result)} cycle rows to {args.out}")
    print("This is a derived table; raw data and provenance manifest remain unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
