---
name: task-logging
description: Record a completed task as a dated entry in TASK_LOG/. Use after finishing any task (big or small) in this repo, once the user confirms they want it logged.
---

# Task logging

Record each task as one file in `TASK_LOG/`.

1. Confirm with the user before writing a log. Skip it if they decline.
2. Create one file per task: `TASK_LOG/YYYY-MM-DD-short-slug.md`
   - date = today, slug = kebab-case summary.
   - Multiple tasks the same day = separate files (slug keeps them distinct).
3. Keep it concise — only necessary information. Use this structure:

   ```
   # <task title>
   Date: YYYY-MM-DD
   Status: done | in-progress | abandoned
   What: <one or two lines on what changed and why>
   Files: <paths touched>
   ```

4. Write the entry as part of the task, not as a separate follow-up.

After writing a log, refresh the summary via the `task-summary` skill.