# Architecture

This repo is becoming a web app backed by microservice tools.

- Each top-level folder (e.g. `short-balls/`) is one service. Mirror that layout for new tools: own code, `Dockerfile`, `README`, and service-local I/O dirs.
- Root owns shared orchestration (`docker-compose.yml`, `Makefile`) — not per-service compose files.
- Keep services independent and runnable in isolation; the web app will call them as tools later.

# Workflow

- After finishing any task (big or small), use the **task-logging** skill to record it in `TASK_LOG/` — but confirm with the user first, and skip if they decline.
- Whenever a task log is written, use the **task-summary** skill to refresh `TASK_LOG/SUMMARY.md`.

Both skills live in `.claude/skills/` and carry their own detailed instructions.
