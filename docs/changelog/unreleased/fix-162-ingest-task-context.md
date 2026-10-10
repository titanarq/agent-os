- Test-session issues keep the task apart from the context (#162, branch `fix/162-ingest-task-context`) -- found in use on
  2026-10-10: the issue `agent-os-sessions test-ingest` opened from a message with one change and four decisions quoted
  the whole message inside "Objective" and said the owner's messages beat the interpreter's reading, so a worker could
  build what the owner had not decided. Now `## Objective` is the "Task" (the item's summary and nothing else), `## Context`
  is "background, not part of the task" and carries the quoted messages, and `## Not included` lists every other item read
  from the same messages as "tracked separately, NOT part of this task". The validator's headings, the `budget`, `node` and
  `key` markers are unchanged; `prompts/worker.md` says what Task and Context mean in such an issue.
