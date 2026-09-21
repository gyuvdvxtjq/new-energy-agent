---
description: Run a materials data quality and property prediction workflow.
argument-hint: [target and optional data path]
---

Read the project rules. Locate the user's dataset or ask for its path and target column. Before modeling, report sample unit, field meanings, units, missingness, duplicates, material/source/batch grouping, leakage risks, and the split rule. Run the lightest credible baseline first. Separate experimental labels, database-native DFT values, computed values, and model predictions. Write metrics, logs, and a report under `reports/` and `logs/`.

Do not claim generalization beyond the observed chemical or structural domain.

User request: $ARGUMENTS
