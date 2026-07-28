# Workflow

- After finishing any task (big or small), use the **task-logging** skill to record it in `TASK_LOG/` — but confirm with the user first, and skip if they decline.
- Whenever a task log is written, use the **task-summary** skill to refresh `TASK_LOG/SUMMARY.md`.

Both skills live in `.claude/skills/` and carry their own detailed instructions.