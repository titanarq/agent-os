"""Schema 2 of the test session file: the chat of the owner with the feedback interpreter.

`docs/adr/2026-10-09-a-chat-test-session-is-ingested-directly-except-decisions.md` amends the ADR of
the command that plans first; the file is the contract of `docs/AGENT_OS.md` §4.11.

- `model` -- the closed session as the chat writes it: comments, cases, interpreted items.
- `reader` -- the schema 2 reader `session_file` registers.
- `plan` -- what a session would do: launch, keep for the next session, record, quote.
- `ticket` -- the dispatchable issue a launched change returns as.
- `understood` -- the file the app reads when the owner opens the next session.
- `apply` and `render` -- carry a plan out, and print it.
"""
