- Chat contract for verdicts, puntal corrections and open questions (#179, branch `fix/179-interpreter-contract`): the
  interpreter's item parser and the session reader accept the kinds `verdict`, `puntal_change` and `answer` and an optional
  `invocations` on any item; the request accepts `invocations`, `pending_question` and `ask` (a malformed one is `not_run`);
  new keys `interpreter.max_invocations` (5) and `sessions.mechanism_repository` (empty). No behaviour yet: #180 to #183 build
  on it. `docs/FEEDBACK_INTERPRETER.md` and `docs/AGENT_OS.md` §4.11 describe the shapes.
