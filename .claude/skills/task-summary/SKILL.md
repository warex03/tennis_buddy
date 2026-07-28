---
name: task-summary
description: Refresh TASK_LOG/SUMMARY.md from the 10 most recent task logs, ending with a next-steps prompt for another agent. Use right after a task log is written.
---

# Task summary

Refresh `TASK_LOG/SUMMARY.md` after a task log is written (only if one was written).

1. Read the 10 most recent log files (by date/filename, newest first). `SUMMARY.md` is not a log — exclude it from the count.
2. Summarize the changes across those logs.
3. End with a `## Next steps` section: recommended follow-up work, written as a ready-to-use prompt that can be handed directly to another agent.

Structure:

```
# Task summary
Updated: YYYY-MM-DD

<bulleted summary of changes from the last 10 logs>

## Next steps
<prompt an agent could act on directly>
```