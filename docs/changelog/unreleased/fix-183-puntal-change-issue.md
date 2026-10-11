- `test-ingest` opens one issue on `sessions.mechanism_repository` for each approved, not withdrawn `puntal_change` item of a
  chat session (key `puntal-change.<session>.<item>`, so a second run opens nothing): the Task is to assess `prompts/puntal.md`,
  reproduce the behaviour as a replay-battery case and change the prompt only if the battery says so; the Context carries the
  owner's words, the invocation's action, node, outcome and `versions` and the case's description. A `puntal_change` is always
  proposed first, whatever `sessions.confirm_before_dispatch` says; with the key empty it is held and listed in `understood.json`
  and nothing is opened (#183).
