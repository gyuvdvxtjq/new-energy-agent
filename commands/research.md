---
description: Run an evidence-tracked research workflow for a materials question.
argument-hint: [research question]
---

Read `AGENTS.md`, `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `DECISIONS.md`, and `TASKS.md`.

Treat the user's text as a research question. First identify the material system, scientific goal, inputs, outputs, sample unit, success criterion, and missing information. Ask only questions that change the workflow. Then create or update `workspace/current_task.yaml`, plan the search, record sources in `papers/`, and produce a report in `reports/` with evidence status and unresolved verification items.

Do not invent papers, properties, DFT results, or conclusions. Keep research facts, hypotheses, and model predictions separate.

User request: $ARGUMENTS
