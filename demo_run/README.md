# End-to-end battery workflow run

This run uses the locally downloaded public Zenodo record `4032561`, file `LGM50_cell03.csv`.

Pipeline:

```text
raw cycler CSV
→ prepare_cycle_ml.py
→ data_quality.py (group: cycle)
→ baseline_predict.py (target: capacity_ah)
→ evaluate_run.py
```

The result is a cell-level cycling smoke test, not a material-generalization claim and not a DFT-feature result. The source manifest is stored under `datasets/raw/` and records the SHA256 of the downloaded file.
