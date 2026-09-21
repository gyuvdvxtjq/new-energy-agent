---
description: Plan or execute a confirmed remote materials computation.
argument-hint: [calculation goal and structure path]
---

Read the project rules and current task state. Inspect structure, target property, method, parameters, and available local tools. Generate a calculation plan and resource estimate. For GPU, remote, long-running, paid, batch, or destructive operations, write `approvals/<task-id>.md` and stop for user confirmation. After confirmation, use the user's SSH configuration and never read or write private keys. Record commands, host alias, scheduler job ID, logs, outputs, failures, and parsing status.

If the user has not confirmed a remote operation, do not submit it.

User request: $ARGUMENTS
