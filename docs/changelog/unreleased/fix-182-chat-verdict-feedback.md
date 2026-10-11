- `test-ingest` records an approved, not withdrawn `verdict` item of a chat session in the puntal's `feedback.jsonl` against its
  invocation (same record as `puntal_task.sh feedback`, plus the key `chat-verdict.<session>.<item>`, so a second run adds
  nothing); a proposed one waits and is listed in `understood.json`, an unknown invocation is a `problem:` line, and the
  per-window summary of verdicts counts a chat verdict once, in its own session. The plan now words `puntal_change` and `answer`
  items by what they are instead of as open questions of what (#182).
