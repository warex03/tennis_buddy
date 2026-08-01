# Architecture

This repo is becoming a web app backed by microservice tools.

- Each top-level folder (e.g. `short-balls/`) is one service. Mirror that layout for new tools: own code, `Dockerfile`, `README`, and service-local I/O dirs.
- Root owns shared orchestration (`docker-compose.yml`, `Makefile`) — not per-service compose files.
- Keep services independent and runnable in isolation; the web app will call them as tools later.

# Workflow

- After finishing any task (big or small), use the **task-logging** skill to record it in `TASK_LOG/` — but confirm with the user first, and skip if they decline.
- Whenever a task log is written, use the **task-summary** skill to refresh `TASK_LOG/SUMMARY.md`.
- When the user asks about recent changes (or you need that context), read the top 10 entries in `TASK_LOG/` — start with `TASK_LOG/SUMMARY.md` (the rolling summary of those 10), then open individual logs if more detail is needed. Exclude `SUMMARY.md` itself when counting logs.

Both skills live in `.claude/skills/` and carry their own detailed instructions.
