#!/usr/bin/env python3
"""Small, explicit tabular baseline for numeric materials features.

This is a smoke-test baseline, not a claim of materials generalization.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split


def load_demo() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 80
    formation = rng.normal(-2.0, 0.4, n)
    band_gap = rng.uniform(0.1, 4.0, n)
    migration = rng.uniform(0.1, 1.2, n)
    retention = 78 + 5 * (-formation) + 2 * band_gap - 8 * migration + rng.normal(0, 2, n)
    return pd.DataFrame(
        {
            "dft_formation_energy_ev_atom": formation,
            "dft_band_gap_ev": band_gap,
            "dft_migration_barrier_ev": migration,
            "retention_pct": retention,
            "source_group": [f"paper-{i // 10}" for i in range(n)],
        }
    )


def run(df: pd.DataFrame, target: str, group: str | None, test_size: float) -> dict:
    if target not in df.columns:
        raise ValueError(f"target column not found: {target}")
    feature_columns = [
        column
        for column in df.select_dtypes(include=["number"]).columns
        if column != target and column != group
    ]
    if not feature_columns:
        raise ValueError("no numeric feature columns found")
    usable = df[feature_columns + [target] + ([group] if group else [])].dropna()
    if len(usable) < 10:
        raise ValueError("fewer than 10 complete rows after dropping missing values")

    if group:
        if group not in usable.columns:
            raise ValueError(f"group column not found: {group}")
        splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=42)
        train_idx, test_idx = next(splitter.split(usable, groups=usable[group]))
        split_rule = f"GroupShuffleSplit by {group}"
    else:
        train_idx, test_idx = train_test_split(
            np.arange(len(usable)), test_size=test_size, random_state=42
        )
        split_rule = "random train_test_split; material/source leakage must be reviewed"

    model = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
    model.fit(usable.iloc[train_idx][feature_columns], usable.iloc[train_idx][target])
    prediction = model.predict(usable.iloc[test_idx][feature_columns])
    actual = usable.iloc[test_idx][target]
    return {
        "task_type": "regression",
        "target": target,
        "features": feature_columns,
        "rows_total": int(len(df)),
        "rows_used": int(len(usable)),
        "rows_train": int(len(train_idx)),
        "rows_test": int(len(test_idx)),
        "split_rule": split_rule,
        "metrics": {
            "mae": float(mean_absolute_error(actual, prediction)),
            "rmse": float(mean_squared_error(actual, prediction) ** 0.5),
            "r2": float(r2_score(actual, prediction)),
        },
        "feature_importance": {
            feature: float(value) for feature, value in zip(feature_columns, model.feature_importances_)
        },
        "limitations": [
            "Numeric features only; categorical formula and structure features are not encoded.",
            "A random split is not evidence of chemical or structural extrapolation.",
            "Check source, material, batch, protocol, and structure-family leakage before interpretation.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--target", default="retention_pct")
    parser.add_argument("--group")
    parser.add_argument("--out", type=Path, default=Path("reports/baseline_metrics.json"))
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if not args.demo and not args.csv:
        parser.error("provide --csv or --demo")
    df = load_demo() if args.demo else pd.read_csv(args.csv)
    result = run(df, args.target, args.group, 0.2)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
